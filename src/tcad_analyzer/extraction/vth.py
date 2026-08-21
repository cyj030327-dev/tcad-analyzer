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
    """|Id(Vg)| = I_ref가 되는 Vg를 보간으로 계산.

    I_ref = cc_current_ref * (W/L) (W/L 정보 있고 정규화 옵션 켜져 있을 때), 아니면
    cc_current_ref를 절대 전류값으로 그대로 사용.
    """
    abs_id = np.abs(np.asarray(id_, dtype=float))
    vg = np.asarray(vg, dtype=float)
    if len(abs_id) < 2:
        raise ExtractionError("CC 방식 Vth 계산을 위한 데이터 포인트가 부족합니다")

    i_ref = _cc_reference_current(config, device)
    if i_ref < abs_id.min() or i_ref > abs_id.max():
        raise ExtractionError(
            f"기준 전류({i_ref:.3e} A)가 데이터의 전류 범위"
            f"[{abs_id.min():.3e}, {abs_id.max():.3e}] A를 벗어납니다"
        )

    # |Id|를 기준으로 정렬해 np.interp(단조증가 x축 요구)에 맞춘다. 곡선이 완벽히
    # 단조가 아니어도(약간의 noise) 합리적인 근사값을 준다.
    order = np.argsort(abs_id)
    abs_id_sorted = abs_id[order]
    vg_sorted = vg[order]
    vth = float(np.interp(i_ref, abs_id_sorted, vg_sorted))
    return vth


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

    if len(vg_fit) < 3:
        raise ExtractionError("Linear Extrapolation 방식을 위한 데이터 포인트가 부족합니다")

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
    if len(vg_s) < 3:
        raise ExtractionError("gm 계산을 위한 데이터 포인트가 부족합니다")
    gm = np.gradient(id_s, vg_s)
    return float(np.max(np.abs(gm)))
