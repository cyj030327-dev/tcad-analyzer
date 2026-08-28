"""Id-Vd 곡선 기반 지표: Ron(온저항), gds(출력 컨덕턴스)."""

from __future__ import annotations

import numpy as np

from .config import ExtractionConfig
from .errors import ExtractionError


def extract_ron(vd_array: np.ndarray, id_: np.ndarray, config: ExtractionConfig) -> float:
    """선형영역(작은 Vd) 구간에서 dVd/dId — 온저항[ohm].

    지정한(또는 자동 20%) 구간에 점이 2개 미만이면, 그 구간만 고집하지 않고 전체
    데이터로 대체해서라도 값을 낸다 — 전체 데이터마저 2개 미만일 때만 진짜로 실패한다.
    """
    vd = np.asarray(vd_array, dtype=float)
    id_ = np.asarray(id_, dtype=float)
    order = np.argsort(vd)
    vd_s = vd[order]
    id_s = id_[order]
    if len(vd_s) < 2:
        raise ExtractionError("Ron 계산을 위한 데이터 포인트가 부족합니다(최소 2개 필요)")

    if config.ron_vd_range is not None:
        lo, hi = sorted(config.ron_vd_range)
        mask = (vd_s >= lo) & (vd_s <= hi)
    else:
        span = vd_s.max() - vd_s.min()
        threshold = vd_s.min() + 0.2 * span
        mask = vd_s <= threshold

    vd_fit, id_fit = vd_s[mask], id_s[mask]
    if len(vd_fit) < 2:
        # 구간 안에 점이 부족하면 전체 데이터로 폴백(이미 위에서 전체가 2개 이상임을 확인함)
        vd_fit, id_fit = vd_s, id_s

    # Id 값이 전부 완전히 똑같으면 polyfit의 부동소수점 잡음으로 정확히 0이 아닌 극도로
    # 작은 기울기가 나올 수 있어(ss.py와 같은 이유), 먼저 직접 확인한다.
    if id_fit.max() == id_fit.min():
        slope = 0.0
    else:
        slope, _ = np.polyfit(vd_fit, id_fit, 1)  # slope = dId/dVd
    # 기울기가 정확히 0이면 온저항은 수학적으로 무한대다 — 실패 대신 그 값 자체를 낸다.
    return float("inf") if slope == 0 else float(abs(1.0 / slope))


def extract_gds(vd_array: np.ndarray, id_: np.ndarray, config: ExtractionConfig) -> float:
    """포화영역(큰 Vd) 구간에서 dId/dVd — 출력 컨덕턴스[S].

    지정한(또는 자동 20%) 구간에 점이 2개 미만이면, 그 구간만 고집하지 않고 전체
    데이터로 대체해서라도 값을 낸다 — 전체 데이터마저 2개 미만일 때만 진짜로 실패한다.
    """
    vd = np.asarray(vd_array, dtype=float)
    id_ = np.asarray(id_, dtype=float)
    order = np.argsort(vd)
    vd_s = vd[order]
    id_s = id_[order]
    if len(vd_s) < 2:
        raise ExtractionError("gds 계산을 위한 데이터 포인트가 부족합니다(최소 2개 필요)")

    if config.gds_vd_range is not None:
        lo, hi = sorted(config.gds_vd_range)
        mask = (vd_s >= lo) & (vd_s <= hi)
    else:
        span = vd_s.max() - vd_s.min()
        threshold = vd_s.max() - 0.2 * span
        mask = vd_s >= threshold

    vd_fit, id_fit = vd_s[mask], id_s[mask]
    if len(vd_fit) < 2:
        vd_fit, id_fit = vd_s, id_s

    slope, _ = np.polyfit(vd_fit, id_fit, 1)
    return float(abs(slope))
