"""Curve -> ExtractedParameter[] 오케스트레이션.

curve 하나 안에서 개별 파라미터 계산이 실패해도 나머지는 계속 진행하고(부분 성공),
컬렉션 단위로는 curve 하나가 완전히 실패해도 나머지 curve 처리를 막지 않는다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple

from ..models import Curve, CurveCollection, CurveType, ExtractedParameter
from .config import ExtractionConfig
from .dibl import extract_dibl, find_dibl_pair
from .errors import ExtractionError
from .id_vd_metrics import extract_gds, extract_ron
from .ion_ioff import extract_ion_ioff
from .mobility import extract_mobility_saturation, resolve_cox_f_cm2
from .ss import extract_ss
from .vth import extract_gm_max, extract_vth_constant_current, extract_vth_linear_extrapolation

# Ion/Ioff 비율이 이보다 작으면(= decade 차이가 얼마 안 나면), 스윕이 진짜 off 영역까지
# 못 내려가서 "Ioff"가 사실상 off 전류가 아닐 가능성이 크다고 보고 경고를 낸다.
# 정상적인 MOSFET은 보통 수백~수백만 배(수 decade) 차이가 나므로, 1000배(3 decade) 미만이면
# 의심해볼 만하다는 경험적 기준.
MIN_ON_OFF_RATIO_FOR_TRUE_OFF = 1e3


@dataclass
class ExtractionOutcome:
    curve_id: str
    parameters: List[ExtractedParameter] = field(default_factory=list)
    failures: List[Tuple[str, str]] = field(default_factory=list)  # (param_name, message) — 계산 자체가 실패
    warnings: List[Tuple[str, str]] = field(default_factory=list)  # (param_name, message) — 계산은 됐지만 신뢰도 주의


def extract_parameters(curve: Curve, config: ExtractionConfig) -> ExtractionOutcome:
    device = curve.device
    split = curve.split
    outcome = ExtractionOutcome(curve_id=curve.curve_id)

    def _add(param_name: str, value: float, unit: str, method: str, method_params: dict | None = None) -> None:
        outcome.parameters.append(
            ExtractedParameter(
                curve_id=curve.curve_id,
                device=device,
                split=split,
                param_name=param_name,
                value=value,
                unit=unit,
                method=method,
                method_params=method_params or {},
            )
        )

    if curve.curve_type == CurveType.ID_VG:
        try:
            if config.vth_method == "constant_current":
                vth = extract_vth_constant_current(curve.vg, curve.id_, config, device)
                _add("Vth_CC", vth, "V", "constant_current")
            else:
                vth = extract_vth_linear_extrapolation(curve.vg, curve.id_, curve.vd, config)
                _add("Vth_SD", vth, "V", "linear_extrapolation")
        except ExtractionError as exc:
            outcome.failures.append(("Vth", str(exc)))

        try:
            ss_value, diagnostics = extract_ss(curve.vg, curve.id_, config)
            _add("SS", ss_value, "mV/dec", "regression", diagnostics)
            if diagnostics.get("low_confidence"):
                lo, hi = diagnostics["vg_range"]
                outcome.warnings.append(
                    (
                        "SS",
                        f"subthreshold 구간 피팅의 R²={diagnostics['r2']:.3f}로 낮습니다 "
                        f"(사용 구간 {lo:.2f}~{hi:.2f}V). 진짜 log-linear한 subthreshold 구간을 "
                        "못 찾았을 수 있어 SS 값의 신뢰도가 낮습니다.",
                    )
                )
        except ExtractionError as exc:
            outcome.failures.append(("SS", str(exc)))

        try:
            ion, ioff, ratio = extract_ion_ioff(curve.vg, curve.id_, config, device)
            _add("Ion", ion, "A", "point_read")
            _add("Ioff", ioff, "A", "point_read")
            _add("Ion_Ioff_ratio", ratio, "", "derived")
            if ratio < MIN_ON_OFF_RATIO_FOR_TRUE_OFF:
                # Ion/Ioff가 몇 decade 안 되면, 스윕이 진짜 off(subthreshold) 영역까지
                # 못 내려가서 "Ioff"가 사실 off 전류가 아니라 스윕 시작점의 전류일 가능성이
                # 크다. 이 경우 SS도 실제보다 나쁘게(크게) 계산된다.
                outcome.warnings.append(
                    (
                        "SS/Ioff",
                        f"Ion/Ioff 비율이 {ratio:.1f}로 작습니다(decade 환산 {math.log10(max(ratio, 1e-300)):.1f} 자리). "
                        "게이트 스윕이 진짜 off(subthreshold) 영역까지 내려가지 않았을 수 있어 "
                        "SS/Ioff 값을 그대로 신뢰하기 어렵습니다.",
                    )
                )
        except ExtractionError as exc:
            outcome.failures.append(("Ion/Ioff", str(exc)))

        try:
            gm = extract_gm_max(curve.vg, curve.id_)
            _add("gm", gm, "S", "max_gradient")
        except ExtractionError as exc:
            outcome.failures.append(("gm", str(exc)))

        # 이동도는 Cox(산화막 커패시턴스)를 사용자가 따로 입력해야 계산되는 선택적
        # 지표다. 설정 안 됐으면(대부분의 기본 상태) 매 curve마다 "실패" 메시지를 쌓지
        # 않고 조용히 건너뛴다 — 안 쓰는 사람에게는 노이즈일 뿐이므로.
        if resolve_cox_f_cm2(config) is not None:
            try:
                mobility = extract_mobility_saturation(curve.vg, curve.id_, config, device)
                _add("Mobility_sat", mobility, "cm2/Vs", "sqrt_id_slope")
            except ExtractionError as exc:
                outcome.failures.append(("Mobility_sat", str(exc)))

    elif curve.curve_type == CurveType.ID_VD:
        if curve.vd_array is None:
            outcome.failures.append(("Ron/gds", "Id-Vd curve에 vd_array가 없습니다"))
        else:
            try:
                ron = extract_ron(curve.vd_array, curve.id_, config)
                _add("Ron", ron, "ohm", "linear_fit")
            except ExtractionError as exc:
                outcome.failures.append(("Ron", str(exc)))
            try:
                gds = extract_gds(curve.vd_array, curve.id_, config)
                _add("gds", gds, "S", "linear_fit")
            except ExtractionError as exc:
                outcome.failures.append(("gds", str(exc)))

    return outcome


def extract_for_collection(
    curves: CurveCollection, config: ExtractionConfig
) -> Tuple[List[ExtractedParameter], List[Tuple[str, str]]]:
    """컬렉션 전체에 대해 추출 + split별 DIBL까지 함께 계산.

    반환: (모든 ExtractedParameter 리스트, (curve_id 또는 split 라벨, 실패 사유) 리스트)
    """
    all_params: List[ExtractedParameter] = []
    all_failures: List[Tuple[str, str]] = []

    for curve in curves:
        try:
            outcome = extract_parameters(curve, config)
            all_params.extend(outcome.parameters)
            all_failures.extend((curve.curve_id, f"{name}: {msg}") for name, msg in outcome.failures)
            all_failures.extend((curve.curve_id, f"[경고] {name}: {msg}") for name, msg in outcome.warnings)
        except Exception as exc:  # curve 하나의 예기치 못한 실패가 전체를 막지 않도록 격리
            all_failures.append((curve.curve_id, str(exc)))

    # split별로 Id-Vg curve를 모아 DIBL 계산 시도
    id_vg_curves = curves.filter(curve_type=CurveType.ID_VG)
    for split_key, split_curves in id_vg_curves.group_by_split().items():
        device_id = split_curves[0].device.device_id
        split_label = f"{device_id}: {split_curves[0].split.label()}"
        pair = find_dibl_pair(split_curves, config)
        if pair is None:
            all_failures.append((split_label, "DIBL: 서로 다른 Vd 조건의 curve가 2개 이상 필요합니다"))
            continue
        curve_lin, curve_sat = pair
        try:
            dibl_value = extract_dibl(curve_lin, curve_sat, config, curve_lin.device)
            all_params.append(
                ExtractedParameter(
                    curve_id=None,
                    device=curve_lin.device,
                    split=curve_lin.split,
                    param_name="DIBL",
                    value=dibl_value,
                    unit="mV/V",
                    method="constant_current_pair",
                    method_params={"vd_lin": curve_lin.vd, "vd_sat": curve_sat.vd},
                )
            )
        except ExtractionError as exc:
            all_failures.append((split_label, f"DIBL: {exc}"))

    return all_params, all_failures
