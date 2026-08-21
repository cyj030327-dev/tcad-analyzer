from tcad_analyzer.analysis.ranking import (
    MetricDirection,
    OptimizationProfile,
    pareto_front,
    recommend_optimal,
)
from tcad_analyzer.models import DeviceMeta, ExtractedParameter, Polarity, SplitCondition

DEVICE = DeviceMeta(device_id="N", polarity=Polarity.NMOS)

# A: Ion 최고, Ioff 최악 / B: 중간(밸런스) / C: Ion 최악, Ioff 최고 / D: B에게 완전히 지배됨
SPLIT_VALUES = {
    "A": {"Ion": 10.0, "Ioff": 2.0},
    "B": {"Ion": 5.0, "Ioff": 0.5},
    "C": {"Ion": 1.0, "Ioff": 0.05},
    "D": {"Ion": 3.0, "Ioff": 1.5},
}
DIRECTIONS = {"Ion": MetricDirection.HIGHER_BETTER, "Ioff": MetricDirection.LOWER_BETTER}


def _build_params():
    params = []
    for split_name, values in SPLIT_VALUES.items():
        split = SplitCondition(split_name=split_name)
        for param_name, value in values.items():
            params.append(
                ExtractedParameter(None, DEVICE, split, param_name, value, unit="", method="test")
            )
    return params


def test_pareto_front_excludes_dominated_split():
    params = _build_params()
    result = recommend_optimal(params, ["Ion", "Ioff"], directions=DIRECTIONS, profile=OptimizationProfile.BALANCED)

    candidate_names = {label.split(": ")[-1] for label in result.pareto_candidates}
    assert candidate_names == {"A", "B", "C"}  # D는 B에게 지배됨


def test_low_power_profile_prefers_lowest_ioff():
    params = _build_params()
    result = recommend_optimal(params, ["Ion", "Ioff"], directions=DIRECTIONS, profile=OptimizationProfile.LOW_POWER)

    assert result.top_recommendation.endswith("C")


def test_high_performance_profile_prefers_highest_ion():
    params = _build_params()
    result = recommend_optimal(
        params, ["Ion", "Ioff"], directions=DIRECTIONS, profile=OptimizationProfile.HIGH_PERFORMANCE
    )

    assert result.top_recommendation.endswith("A")


def test_balanced_profile_prefers_middle_split():
    params = _build_params()
    result = recommend_optimal(params, ["Ion", "Ioff"], directions=DIRECTIONS, profile=OptimizationProfile.BALANCED)

    assert result.top_recommendation.endswith("B")


def test_custom_weights_are_normalized():
    params = _build_params()
    result = recommend_optimal(
        params,
        ["Ion", "Ioff"],
        directions=DIRECTIONS,
        profile=OptimizationProfile.CUSTOM,
        custom_weights={"Ion": 3.0, "Ioff": 1.0},
    )

    assert result.weights_used["Ion"] == 0.75
    assert result.weights_used["Ioff"] == 0.25


def test_pareto_front_directly():
    import pandas as pd

    table = pd.DataFrame(
        {"Ion": [10.0, 5.0, 1.0, 3.0], "Ioff": [2.0, 0.5, 0.05, 1.5]},
        index=["A", "B", "C", "D"],
    )
    front = pareto_front(table, DIRECTIONS)
    assert set(front) == {"A", "B", "C"}
