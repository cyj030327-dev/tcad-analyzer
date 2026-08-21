"""Subthreshold Swing(SS) 추출."""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np

from .config import ExtractionConfig
from .errors import ExtractionError


def _r_squared(x: np.ndarray, y: np.ndarray, slope: float, intercept: float) -> float:
    pred = slope * x + intercept
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0


def _auto_detect_subthreshold_region(
    vg_s: np.ndarray,
    log_id: np.ndarray,
    window_frac: float = 0.3,
    min_window: int = 5,
    r2_gate: float = 0.95,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """subthreshold 영역을 sliding window로 탐색.

    단순히 R^2가 가장 높은 구간을 고르면, 전류가 noise floor 근처까지 떨어져 사실상
    평평한(기울기≈0) 구간이 우연히 그럴듯한 R^2를 보이는 함정에 빠지기 쉽다(짧은 구간을
    수십 개 비교하는 다중비교 상황이라 더 그렇다). 그래서 R^2가 기준(r2_gate) 이상인
    구간들 중에서 |기울기|(=log(Id) 변화가 가장 가파른, 즉 진짜 subthreshold다운) 구간을
    우선 선택하고, 기준을 넘는 구간이 하나도 없으면 R^2가 가장 높은 구간으로 폴백한다.
    """
    n = len(vg_s)
    window = max(min_window, int(n * window_frac))
    window = min(window, n)

    candidates = []  # (abs_slope, r2, start, end)
    for start in range(0, n - window + 1):
        end = start + window
        vg_w = vg_s[start:end]
        log_w = log_id[start:end]
        if vg_w.max() == vg_w.min():
            continue
        slope, intercept = np.polyfit(vg_w, log_w, 1)
        r2 = _r_squared(vg_w, log_w, slope, intercept)
        candidates.append((abs(slope), r2, start, end))

    if not candidates:
        return vg_s[0:window], log_id[0:window], 0.0

    well_fit = [c for c in candidates if c[1] >= r2_gate]
    pool = well_fit if well_fit else candidates
    best_slope, best_r2, start, end = max(pool, key=lambda c: c[0])
    return vg_s[start:end], log_id[start:end], best_r2


def extract_ss(vg: np.ndarray, id_: np.ndarray, config: ExtractionConfig) -> Tuple[float, Dict]:
    """subthreshold 영역에서 log10(|Id|) vs Vg 선형회귀 기울기로부터 SS[mV/decade] 계산.

    반환: (ss_mV_per_dec, diagnostics) — diagnostics에는 r2, 사용된 vg 범위, 포인트 수,
    신뢰도 낮음(low_confidence) 플래그가 담긴다.
    """
    vg = np.asarray(vg, dtype=float)
    abs_id = np.abs(np.asarray(id_, dtype=float))

    valid = abs_id > 0
    vg_valid = vg[valid]
    abs_id_valid = abs_id[valid]
    if len(vg_valid) < 3:
        raise ExtractionError("SS 계산을 위한 유효한(0이 아닌 전류) 데이터 포인트가 부족합니다")

    order = np.argsort(vg_valid)
    vg_s = vg_valid[order]
    log_id = np.log10(abs_id_valid[order])

    if config.ss_vg_range is not None:
        lo, hi = sorted(config.ss_vg_range)
        mask = (vg_s >= lo) & (vg_s <= hi)
        vg_fit = vg_s[mask]
        log_id_fit = log_id[mask]
        if len(vg_fit) < 3:
            raise ExtractionError("지정한 SS 구간에 데이터 포인트가 부족합니다")
        r2_hint = None
    else:
        vg_fit, log_id_fit, r2_hint = _auto_detect_subthreshold_region(vg_s, log_id)

    slope, intercept = np.polyfit(vg_fit, log_id_fit, 1)
    if slope == 0:
        raise ExtractionError("subthreshold 기울기가 0이라 SS를 계산할 수 없습니다")

    r2 = r2_hint if r2_hint is not None else _r_squared(vg_fit, log_id_fit, slope, intercept)
    ss_value = abs(1.0 / slope) * 1000.0  # V/decade -> mV/decade

    diagnostics = {
        "r2": float(r2),
        "vg_range": (float(vg_fit.min()), float(vg_fit.max())),
        "n_points": int(len(vg_fit)),
        "low_confidence": bool(r2 < config.ss_min_r2),
    }
    return float(ss_value), diagnostics
