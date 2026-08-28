"""Vth(문턱전압) 추출: Constant Current(CC) 방식 / Linear Extrapolation(SD) 방식."""

from __future__ import annotations

from typing import Optional

import numpy as np

from ..models import DeviceMeta
from .config import ExtractionConfig
from .errors import ExtractionError


def _cc_reference_current(config: ExtractionConfig, device: DeviceMeta) -> float:
    if config.cc_normalize_by_wl and device.wl_ratio is not None:
        return config.cc_current_ref * device.wl_ratio
    return config.cc_current_ref


def extract_vth_constant_current(
    vg: np.ndarray, id_: np.ndarray, config: ExtractionConfig, device: DeviceMeta
) -> float:
    """|Id(Vg)| = I_ref가 되는 Vg를 보간(또는 범위 밖이면 외삽)으로 계산.

    I_ref = cc_current_ref * (W/L) (W/L 정보 있고 정규화 옵션 켜져 있을 때), 아니면
    cc_current_ref를 절대 전류값으로 그대로 사용.

    기준전류가 측정된 |Id| 범위를 벗어나도 실패시키지 않고, 가장 가까운 두 점으로 직선을
    연장해 값을 낸다 — "값이 아예 안 나온다"보다는 "이 값은 외삽된 것"이라고 경고로
    알려주는 편이 낫다는 판단(경고는 pipeline.py에서 같은 범위 검사를 다시 해서 붙인다).
    데이터가 2개 미만이면(직선조차 못 그음) 그때만 진짜로 실패한다.
    """
    abs_id = np.abs(np.asarray(id_, dtype=float))
    vg = np.asarray(vg, dtype=float)
    if len(abs_id) < 2:
        raise ExtractionError("CC 방식 Vth 계산을 위한 데이터 포인트가 부족합니다(최소 2개 필요)")

    i_ref = _cc_reference_current(config, device)

    # |Id|를 기준으로 정렬해 단조증가 x축을 만든다. 곡선이 완벽히 단조가 아니어도(약간의
    # noise) 합리적인 근사값을 준다.
    order = np.argsort(abs_id)
    abs_id_sorted = abs_id[order]
    vg_sorted = vg[order]

    if i_ref < abs_id_sorted[0] or i_ref > abs_id_sorted[-1]:
        # np.interp는 범위 밖이면 그냥 끝점 값으로 clamp해버려서(=은근슬쩍 틀린 값을
        # 맞는 값처럼 보이게 함) 대신 두 끝점으로 직선을 그어 명시적으로 외삽한다.
        if i_ref < abs_id_sorted[0]:
            x0, x1, y0, y1 = abs_id_sorted[0], abs_id_sorted[1], vg_sorted[0], vg_sorted[1]
        else:
            x0, x1, y0, y1 = abs_id_sorted[-2], abs_id_sorted[-1], vg_sorted[-2], vg_sorted[-1]
        if x1 == x0:
            return float(y1)
        slope = (y1 - y0) / (x1 - x0)
        return float(y0 + slope * (i_ref - x0))

    return float(np.interp(i_ref, abs_id_sorted, vg_sorted))


def extract_vth_linear_extrapolation(
    vg: np.ndarray,
    id_: np.ndarray,
    vd: Optional[float],
    config: ExtractionConfig,
) -> float:
    """gm=dId/dVg 최대점에서 접선을 그어 Id=0과 만나는 절편으로 Vth를 계산.

    선형영역(작은 Vd)에서 추출한 경우 관례적으로 Vd/2 보정을 뺀다(옵션).
    """
    vg = np.asarray(vg, dtype=float)
    id_ = np.asarray(id_, dtype=float)

    order = np.argsort(vg)
    vg_s = vg[order]
    id_s = id_[order]

    if config.le_fit_vg_range is not None:
        lo, hi = sorted(config.le_fit_vg_range)
        mask = (vg_s >= lo) & (vg_s <= hi)
        vg_fit = vg_s[mask]
        id_fit = id_s[mask]
    else:
        vg_fit, id_fit = vg_s, id_s

    if len(vg_fit) < 2:
        raise ExtractionError("Linear Extrapolation 방식을 위한 데이터 포인트가 부족합니다(최소 2개 필요)")

    gm = np.gradient(id_fit, vg_fit)
    # 배열 경계에서는 gradient가 부정확할 수 있어 가능하면 양 끝을 제외하고 탐색
    if len(gm) > 2:
        interior = gm[1:-1]
        peak_idx = int(np.argmax(np.abs(interior))) + 1
    else:
        peak_idx = int(np.argmax(np.abs(gm)))

    gm_max = gm[peak_idx]
    if gm_max == 0:
        raise ExtractionError("gm 최댓값이 0이라 접선을 구할 수 없습니다")

    vg_intercept = vg_fit[peak_idx] - id_fit[peak_idx] / gm_max
    vth = vg_intercept
    if config.le_apply_vd_half_correction and vd is not None:
        vth -= vd / 2
    return float(vth)


def extract_gm_max(vg: np.ndarray, id_: np.ndarray) -> float:
    """Id-Vg 곡선의 최대 transconductance(|dId/dVg|)."""
    vg = np.asarray(vg, dtype=float)
    id_ = np.asarray(id_, dtype=float)
    order = np.argsort(vg)
    vg_s = vg[order]
    id_s = id_[order]
    if len(vg_s) < 2:
        raise ExtractionError("gm 계산을 위한 데이터 포인트가 부족합니다(최소 2개 필요)")
    gm = np.gradient(id_s, vg_s)
    return float(np.max(np.abs(gm)))
