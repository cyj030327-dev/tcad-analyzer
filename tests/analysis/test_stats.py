import pytest

from tcad_analyzer.analysis.stats import summarize_by_split, to_dataframe
from tcad_analyzer.models import DeviceMeta, ExtractedParameter, Polarity, SplitCondition


def _param(device_id, polarity, split_attrs, name, value):
    device = DeviceMeta(device_id=device_id, polarity=polarity)
    split = SplitCondition(attributes=split_attrs)
    return ExtractedParameter(
        curve_id=f"{device_id}-{split_attrs}",
        device=device,
        split=split,
        param_name=name,
        value=value,
        unit="V",
        method="test",
    )


def test_summarize_by_split_computes_expected_stats():
    params = [
        _param("N", Polarity.NMOS, {"T": "900"}, "Vth_CC", 0.40),
        _param("N", Polarity.NMOS, {"T": "900"}, "Vth_CC", 0.42),
        _param("N", Polarity.NMOS, {"T": "950"}, "Vth_CC", 0.38),
    ]

    summary = summarize_by_split(params, "Vth_CC")

    row_900 = summary[summary["split_label"] == "N: T=900"].iloc[0]
    assert row_900["mean"] == pytest.approx(0.41)
    assert row_900["count"] == 2

    row_950 = summary[summary["split_label"] == "N: T=950"].iloc[0]
    assert row_950["mean"] == pytest.approx(0.38)
    assert row_950["count"] == 1


def test_split_label_disambiguates_different_devices_with_same_condition():
    # NMOS와 PMOS가 우연히 같은 split(예: 같은 온도) 라벨을 가져도 섞이면 안 된다
    params = [
        _param("NMOS", Polarity.NMOS, {"T": "950"}, "Vth_CC", 0.40),
        _param("PMOS", Polarity.PMOS, {"T": "950"}, "Vth_CC", -0.40),
    ]

    df = to_dataframe(params)

    assert df["split_label"].nunique() == 2
    assert set(df["split_label"]) == {"NMOS: T=950", "PMOS: T=950"}


def test_summarize_missing_param_returns_empty():
    params = [_param("N", Polarity.NMOS, {"T": "900"}, "Vth_CC", 0.4)]
    summary = summarize_by_split(params, "SS")
    assert summary.empty
