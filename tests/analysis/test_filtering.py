from tcad_analyzer.analysis.filtering import filter_by_ranges
from tcad_analyzer.models import DeviceMeta, ExtractedParameter, Polarity, SplitCondition

DEVICE = DeviceMeta(device_id="N", polarity=Polarity.NMOS)

SPLIT_VALUES = {
    "A": {"Vth_CC": 0.40, "SS": 80.0},
    "B": {"Vth_CC": 0.44, "SS": 120.0},
    "C": {"Vth_CC": 0.55, "SS": 90.0},
}


def _build_params():
    params = []
    for split_name, values in SPLIT_VALUES.items():
        split = SplitCondition(split_name=split_name)
        for name, value in values.items():
            params.append(ExtractedParameter(None, DEVICE, split, name, value, unit="", method="test"))
    return params


def test_filter_single_criterion():
    params = _build_params()
    result = filter_by_ranges(params, {"Vth_CC": (0.38, 0.45)})
    labels = {label.split(": ")[-1] for label in result.index}
    assert labels == {"A", "B"}


def test_filter_multiple_criteria_requires_all():
    params = _build_params()
    result = filter_by_ranges(params, {"Vth_CC": (0.38, 0.45), "SS": (0.0, 100.0)})
    labels = {label.split(": ")[-1] for label in result.index}
    assert labels == {"A"}  # B는 Vth는 맞지만 SS가 범위 밖


def test_filter_no_match_returns_empty():
    params = _build_params()
    result = filter_by_ranges(params, {"Vth_CC": (10.0, 20.0)})
    assert result.empty


def test_filter_unknown_parameter_yields_no_results():
    params = _build_params()
    result = filter_by_ranges(params, {"DoesNotExist": (0.0, 1.0)})
    assert result.empty


def test_filter_empty_criteria_returns_empty():
    assert filter_by_ranges(_build_params(), {}).empty
