"""Id-Vd 곡선 기반 지표: Ron(온저항), gds(출력 컨덕턴스)."""

from __future__ import annotations

import numpy as np

from .config import ExtractionConfig
from .errors import ExtractionError


def extract_ron(vd_array: np.ndarray, id_: np.ndarray, config: ExtractionConfig) -> float:
    """선형영역(작은 Vd) 구간에서 dVd/dId — 온저항[ohm]."""
    vd = np.asarray(vd_array, dtype=float)
    id_ = np.asarray(id_, dtype=float)
    order = np.argsort(vd)
    vd_s = vd[order]
    id_s = id_[order]

    if config.ron_vd_range is not None:
        lo, hi = sorted(config.ron_vd_range)
        mask = (vd_s >= lo) & (vd_s <= hi)
    else:
        span = vd_s.max() - vd_s.min()
        threshold = vd_s.min() + 0.2 * span
        mask = vd_s <= threshold

    vd_fit, id_fit = vd_s[mask], id_s[mask]
    if len(vd_fit) < 2:
        raise ExtractionError("Ron 계산을 위한 선형영역 데이터 포인트가 부족합니다")

    slope, _ = np.polyfit(vd_fit, id_fit, 1)  # slope = dId/dVd
    if slope == 0:
        raise ExtractionError("선형영역 기울기가 0이라 Ron을 계산할 수 없습니다")
    return float(abs(1.0 / slope))


def extract_gds(vd_array: np.ndarray, id_: np.ndarray, config: ExtractionConfig) -> float:
    """포화영역(큰 Vd) 구간에서 dId/dVd — 출력 컨덕턴스[S]."""
    vd = np.asarray(vd_array, dtype=float)
    id_ = np.asarray(id_, dtype=float)
    order = np.argsort(vd)
    vd_s = vd[order]
    id_s = id_[order]

    if config.gds_vd_range is not None:
        lo, hi = sorted(config.gds_vd_range)
        mask = (vd_s >= lo) & (vd_s <= hi)
    else:
        span = vd_s.max() - vd_s.min()
        threshold = vd_s.max() - 0.2 * span
        mask = vd_s >= threshold

    vd_fit, id_fit = vd_s[mask], id_s[mask]
    if len(vd_fit) < 2:
        raise ExtractionError("gds 계산을 위한 포화영역 데이터 포인트가 부족합니다")

    slope, _ = np.polyfit(vd_fit, id_fit, 1)
    return float(abs(slope))
