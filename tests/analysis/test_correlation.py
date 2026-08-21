import pytest

from tcad_analyzer.analysis.correlation import compute_correlation
from tcad_analyzer.models import DeviceMeta, ExtractedParameter, Polarity, SplitCondition

DEVICE = DeviceMeta(device_id="N", polarity=Polarity.NMOS)


def _param(curve_id, split_label, name, value):
    split = SplitCondition(split_name=split_label)
    return ExtractedParameter(
        curve_id=curve_id, device=DEVICE, split=split, param_name=name, value=value, unit="", method="test"
    )


def test_correlation_joins_by_curve_id_and_computes_pearson_r():
    params = []
    for i in range(5):
        params.append(_param(f"c{i}", f"s{i}", "Vth_CC", 0.4 + 0.01 * i))
        params.append(_param(f"c{i}", f"s{i}", "SS", 80 + 2 * i))  # 완전한 선형관계

    merged = compute_correlation(params, "Vth_CC", "SS")

    assert len(merged) == 5
    assert merged.attrs["pearson_r"] == pytest.approx(1.0)


def test_correlation_handles_same_parameter_for_x_and_y():
    # GUI에서 X/Y 드롭다운이 우연히 같은 파라미터를 가리킬 때 pandas의 자동 _x/_y 접미사에
    # 걸려 KeyError가 나던 회귀 버그에 대한 테스트.
    params = [_param("c0", "s0", "DIBL", 40.0), _param("c1", "s1", "DIBL", 42.0)]

    merged = compute_correlation(params, "DIBL", "DIBL")

    assert len(merged) == 2
    assert merged.attrs["pearson_r"] == pytest.approx(1.0)
    assert list(merged.columns).count("DIBL") == 1


def test_correlation_falls_back_to_split_label_when_curve_id_missing():
    params = [
        ExtractedParameter(None, DEVICE, SplitCondition(split_name="s1"), "Vth_CC", 0.40, "V", "imported"),
        ExtractedParameter(None, DEVICE, SplitCondition(split_name="s1"), "SS", 80.0, "mV/dec", "imported"),
        ExtractedParameter(None, DEVICE, SplitCondition(split_name="s2"), "Vth_CC", 0.38, "V", "imported"),
        ExtractedParameter(None, DEVICE, SplitCondition(split_name="s2"), "SS", 84.0, "mV/dec", "imported"),
    ]

    merged = compute_correlation(params, "Vth_CC", "SS")

    assert len(merged) == 2
