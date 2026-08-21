"""'최적 소자 추천' 분석.

3단계로 동작한다:
  1) Pareto 후보군 탐색: 목표값 없이도 여러 지표를 동시에 고려해 다른 어떤 split보다도
     열등하지 않은 split 집합(비지배 집합)을 계산.
  2) 최적화 프로파일(저전력/고성능/밸런스/사용자 지정)로 지표별 가중치를 결정.
  3) Pareto 후보군 내에서 가중합 점수를 매겨 1위를 "추천 최적 split"으로 제시.

다목적 최적화 알고리즘(NSGA-II 등)까지는 가지 않고 dominance 비교 + 정규화 가중합 정도로
단순하게 구현한다(학부생 프로젝트 범위에 적합).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

import pandas as pd

from ..models import ExtractedParameter
from .stats import to_dataframe


class MetricDirection(str, Enum):
    LOWER_BETTER = "lower_better"
    HIGHER_BETTER = "higher_better"
    CLOSER_TO_TARGET = "closer_to_target"


class OptimizationProfile(str, Enum):
    LOW_POWER = "low_power"
    HIGH_PERFORMANCE = "high_performance"
    BALANCED = "balanced"
    CUSTOM = "custom"


# 프로파일별 기본 가중치(선택된 지표 중 여기 있는 것만 반영, 없는 지표는 0).
PROFILE_DEFAULT_WEIGHTS: Dict[OptimizationProfile, Dict[str, float]] = {
    OptimizationProfile.LOW_POWER: {"Ioff": 0.4, "SS": 0.3, "DIBL": 0.2, "Ion": 0.1},
    OptimizationProfile.HIGH_PERFORMANCE: {"Ion": 0.4, "gm": 0.3, "Ron": 0.2, "Ioff": 0.1},
    OptimizationProfile.BALANCED: {},  # 런타임에 선택된 지표 전부 동일 가중치로 계산
}

# 지표별 기본 방향성. 여기 없는 지표(예: 사용자 정의 파라미터)는 호출부에서 지정해야 한다.
DEFAULT_METRIC_DIRECTIONS: Dict[str, MetricDirection] = {
    "Vth_CC": MetricDirection.CLOSER_TO_TARGET,
    "Vth_SD": MetricDirection.CLOSER_TO_TARGET,
    "SS": MetricDirection.LOWER_BETTER,
    "Ion": MetricDirection.HIGHER_BETTER,
    "Ioff": MetricDirection.LOWER_BETTER,
    "Ion_Ioff_ratio": MetricDirection.HIGHER_BETTER,
    "Ron": MetricDirection.LOWER_BETTER,
    "gm": MetricDirection.HIGHER_BETTER,
    "gds": MetricDirection.LOWER_BETTER,
    "DIBL": MetricDirection.LOWER_BETTER,
}


def build_split_metric_table(params: List[ExtractedParameter], metric_names: List[str]) -> pd.DataFrame:
    """split_label을 행으로, 지표를 열로 하는 표. 같은 split에 curve가 여럿이면 평균."""
    df = to_dataframe(params)
    df = df[df["param_name"].isin(metric_names)]
    if df.empty:
        return pd.DataFrame(columns=metric_names)
    pivot = df.pivot_table(index="split_label", columns="param_name", values="value", aggfunc="mean")
    return pivot.reindex(columns=metric_names)


def _better_worse(a: float, b: float, direction: MetricDirection, target: Optional[float]) -> tuple[bool, bool]:
    """(a가 b보다 나은가, a가 b보다 못한가)."""
    if direction == MetricDirection.LOWER_BETTER:
        return a < b, a > b
    if direction == MetricDirection.HIGHER_BETTER:
        return a > b, a < b
    # CLOSER_TO_TARGET
    if target is None:
        return False, False
    da, db = abs(a - target), abs(b - target)
    return da < db, da > db


def _dominates(
    row_a: pd.Series,
    row_b: pd.Series,
    directions: Dict[str, MetricDirection],
    targets: Optional[Dict[str, float]],
) -> bool:
    """row_a가 row_b를 지배하는가: 모든 지표에서 같거나 낫고, 하나 이상에서 진짜로 낫다."""
    at_least_as_good = True
    strictly_better = False
    for metric, direction in directions.items():
        if metric not in row_a.index or pd.isna(row_a[metric]) or pd.isna(row_b[metric]):
            continue
        target = (targets or {}).get(metric)
        better, worse = _better_worse(row_a[metric], row_b[metric], direction, target)
        if worse:
            at_least_as_good = False
            break
        if better:
            strictly_better = True
    return at_least_as_good and strictly_better


def pareto_front(
    table: pd.DataFrame,
    directions: Dict[str, MetricDirection],
    targets: Optional[Dict[str, float]] = None,
) -> List[str]:
    """table(행=split_label)에서 비지배(non-dominated) split_label 목록을 O(n^2)로 계산."""
    labels = list(table.index)
    non_dominated: List[str] = []
    for label in labels:
        row = table.loc[label]
        dominated = any(
            other != label and _dominates(table.loc[other], row, directions, targets) for other in labels
        )
        if not dominated:
            non_dominated.append(label)
    return non_dominated


def _normalize_column(series: pd.Series, direction: MetricDirection, target: Optional[float]) -> pd.Series:
    """0(나쁨)~1(좋음)로 정규화. 값이 모두 같으면 구분 불가로 보고 1(동점)로 처리."""
    if direction == MetricDirection.CLOSER_TO_TARGET and target is not None:
        distance = (series - target).abs()
        span = distance.max() - distance.min()
        if span == 0:
            return pd.Series(1.0, index=series.index)
        return 1.0 - (distance - distance.min()) / span

    span = series.max() - series.min()
    if span == 0:
        return pd.Series(1.0, index=series.index)
    normalized = (series - series.min()) / span
    return normalized if direction == MetricDirection.HIGHER_BETTER else (1.0 - normalized)


def resolve_weights(
    profile: OptimizationProfile,
    metric_names: List[str],
    custom_weights: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """프로파일 + 선택된 지표로부터 실제 가중치를 만든다(합이 1이 되도록 정규화)."""
    if profile == OptimizationProfile.CUSTOM:
        raw = {m: (custom_weights or {}).get(m, 0.0) for m in metric_names}
    elif profile == OptimizationProfile.BALANCED:
        raw = {m: 1.0 for m in metric_names}
    else:
        preset = PROFILE_DEFAULT_WEIGHTS.get(profile, {})
        raw = {m: preset.get(m, 0.0) for m in metric_names}
        if not any(raw.values()):
            # 선택된 지표가 프리셋에 하나도 없으면 균등 가중치로 폴백
            raw = {m: 1.0 for m in metric_names}

    total = sum(raw.values())
    if total <= 0:
        n = len(metric_names) or 1
        return {m: 1.0 / n for m in metric_names}
    return {m: v / total for m, v in raw.items()}


@dataclass
class RankingResult:
    metric_table: pd.DataFrame
    pareto_candidates: List[str]
    scored_table: pd.DataFrame  # Pareto 후보군 + score 컬럼, score 내림차순 정렬
    top_recommendation: Optional[str]
    weights_used: Dict[str, float]


def recommend_optimal(
    params: List[ExtractedParameter],
    metric_names: List[str],
    directions: Optional[Dict[str, MetricDirection]] = None,
    profile: OptimizationProfile = OptimizationProfile.BALANCED,
    custom_weights: Optional[Dict[str, float]] = None,
    targets: Optional[Dict[str, float]] = None,
) -> RankingResult:
    """Pareto 후보군 + 프로파일 가중치 + (선택적) 목표값을 결합해 최적 split을 추천."""
    resolved_directions = directions or {
        m: DEFAULT_METRIC_DIRECTIONS.get(m, MetricDirection.HIGHER_BETTER) for m in metric_names
    }

    table = build_split_metric_table(params, metric_names)
    if table.empty:
        return RankingResult(table, [], table, None, {})

    candidates = pareto_front(table, resolved_directions, targets)
    weights = resolve_weights(profile, metric_names, custom_weights)

    candidate_table = table.loc[candidates].copy()
    score = pd.Series(0.0, index=candidate_table.index)
    for metric in metric_names:
        if metric not in candidate_table.columns:
            continue
        direction = resolved_directions.get(metric, MetricDirection.HIGHER_BETTER)
        target = (targets or {}).get(metric)
        normalized = _normalize_column(candidate_table[metric], direction, target)
        score = score + normalized.fillna(0.0) * weights.get(metric, 0.0)

    candidate_table["score"] = score
    scored_table = candidate_table.sort_values("score", ascending=False)
    top = scored_table.index[0] if not scored_table.empty else None

    return RankingResult(
        metric_table=table,
        pareto_candidates=candidates,
        scored_table=scored_table,
        top_recommendation=top,
        weights_used=weights,
    )
