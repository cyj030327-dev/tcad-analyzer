"""필드효과 이동도(μFE) 추출: 포화영역, sqrt(|Id|)-Vg 기울기 방식.

포화영역에서 Id_sat = (W·Cox·μsat)/(2L) · (Vgs-Vth)^2 이므로 sqrt(Id_sat)는 Vgs에 대해
선형이고, 그 기울기 m으로부터 μsat = 2·L·m^2 / (W·Cox)를 얻는다 — Vth를 몰라도(절편 계산이
필요 없어) 기울기만 있으면 계산되는 게 이 방식의 장점이다.

Cox(산화막 커패시턴스, F/cm^2)는 원본 데이터(.plt/gtree.dat)에 없는 값이라 사용자가 직접
입력하거나(가장 정확), 산화막 두께+비유전율로 계산해야 한다.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from ..models import DeviceMeta
from .config import ExtractionConfig
from .errors import ExtractionError

_EPS0_F_PER_CM = 8.854e-14  # 진공 유전율 [F/cm]


def resolve_cox_f_cm2(config: ExtractionConfig) -> Optional[float]:
    """설정에서 Cox[F/cm^2]를 계산한다. 직접 입력한 값이 있으면 그걸 우선 쓰고,
    없으면 산화막 두께+비유전율로 계산한다. 둘 다 없으면 None(이동도 계산 스킵 신호)."""
    if config.mobility_cox_F_cm2 is not None:
        return config.mobility_cox_F_cm2
    if config.mobility_oxide_thickness_nm and config.mobility_oxide_rel_permittivity:
        thickness_cm = config.mobility_oxide_thickness_nm * 1e-7  # nm -> cm
        return _EPS0_F_PER_CM * config.mobility_oxide_rel_permittivity / thickness_cm
    return None


def extract_mobility_saturation(
    vg: np.ndarray, id_: np.ndarray, config: ExtractionConfig, device: DeviceMeta
) -> float:
    """포화영역 field-effect mobility μsat [cm^2/V·s]를 계산."""
    cox = resolve_cox_f_cm2(config)
    if cox is None:
        raise ExtractionError(
            "이동도 계산에 필요한 Cox(산화막 커패시턴스)가 설정되지 않았습니다. "
            "Extraction Config에서 Cox를 직접 입력하거나 산화막 두께+비유전율을 입력하세요"
        )
    if cox <= 0:
        raise ExtractionError(f"Cox 값이 올바르지 않습니다({cox:.3e} F/cm^2)")
    if not device.width_um or not device.length_um:
        raise ExtractionError("이동도 계산에는 W/L(폭/길이) 정보가 필요합니다 (Column Mapping에서 입력)")

    vg = np.asarray(vg, dtype=float)
    id_ = np.asarray(id_, dtype=float)
    order = np.argsort(vg)
    vg_s = vg[order]
    sqrt_id_s = np.sqrt(np.abs(id_[order]))

    if config.mobility_fit_vg_range is not None:
        lo, hi = sorted(config.mobility_fit_vg_range)
        mask = (vg_s >= lo) & (vg_s <= hi)
        vg_fit, sqrt_id_fit = vg_s[mask], sqrt_id_s[mask]
    else:
        vg_fit, sqrt_id_fit = vg_s, sqrt_id_s

    if len(vg_fit) < 3:
        raise ExtractionError("이동도 계산을 위한 데이터 포인트가 부족합니다")

    slope_arr = np.gradient(sqrt_id_fit, vg_fit)
    # gm_max 탐색과 동일한 이유로, 배열 경계는 가능하면 제외하고 최대 기울기 지점을 찾는다
    if len(slope_arr) > 2:
        interior = slope_arr[1:-1]
        peak_idx = int(np.argmax(interior)) + 1
    else:
        peak_idx = int(np.argmax(slope_arr))
    slope = float(slope_arr[peak_idx])  # sqrt(A)/V

    if slope <= 0:
        raise ExtractionError("sqrt(Id)-Vg 기울기가 0 이하라 이동도를 계산할 수 없습니다")

    w_cm = device.width_um * 1e-4  # um -> cm
    l_cm = device.length_um * 1e-4

    mu_sat_cm2_v_s = 2.0 * l_cm * (slope ** 2) / (w_cm * cox)
    return float(mu_sat_cm2_v_s)
