import pytest

from tcad_analyzer.analysis.regression import (
    build_regression_summary,
    describe_regression_effect,
    fit_multivariate_model,
)
from tcad_analyzer.models import DeviceMeta, ExtractedParameter, Polarity, SplitCondition

DEVICE = DeviceMeta(device_id="N", polarity=Polarity.NMOS)

# x1, x2가 서로 얽혀서(상관돼서) 같이 움직이지만, y = 2*x1 - 3*x2를 노이즈 없이 정확히
# 만족하도록 설계 — 단순 상관(피어슨 r)으로는 두 변수의 "순수한" 기여를 분리하지 못하지만,
# 다중회귀는 정확한 계수(2, -3)를 그대로 복원해야 한다.
_X1 = [1, 2, 3, 4, 5, 6, 7, 8]
_X2 = [1, 3, 2, 5, 4, 7, 6, 9]
_Y = [2 * a - 3 * b for a, b in zip(_X1, _X2)]


def _build_params():
    params = []
    for i, (x1, x2, y) in enumerate(zip(_X1, _X2, _Y)):
        split = SplitCondition(split_name=f"n{i}", attributes={"x1": str(x1), "x2": str(x2)})
        params.append(ExtractedParameter(None, DEVICE, split, "y", float(y), unit="", method="test"))
    return params


def test_fit_multivariate_model_recovers_exact_coefficients_on_noiseless_data():
    params = _build_params()
    result = fit_multivariate_model(params, "y")

    assert result is not None
    assert set(result.attribute_names) == {"x1", "x2"}
    assert result.coefficients["x1"] == pytest.approx(2.0, abs=1e-6)
    assert result.coefficients["x2"] == pytest.approx(-3.0, abs=1e-6)
    assert result.intercept == pytest.approx(0.0, abs=1e-6)
    assert result.r_squared == pytest.approx(1.0, abs=1e-6)
    assert result.n == 8


def test_fit_multivariate_model_predicts_new_combination():
    params = _build_params()
    result = fit_multivariate_model(params, "y")

    predicted = result.predict({"x1": 10.0, "x2": 5.0})

    assert predicted == pytest.approx(2 * 10.0 - 3 * 5.0, abs=1e-6)


def test_predict_raises_when_missing_attribute_value():
    params = _build_params()
    result = fit_multivariate_model(params, "y")

    with pytest.raises(ValueError):
        result.predict({"x1": 10.0})  # x2 값 누락


def test_standardized_coefficients_match_sign_of_raw_coefficients():
    params = _build_params()
    result = fit_multivariate_model(params, "y")

    assert result.standardized_coefficients["x1"] > 0  # 원래 계수 +2와 같은 부호
    assert result.standardized_coefficients["x2"] < 0  # 원래 계수 -3과 같은 부호


def test_ranked_attributes_orders_by_absolute_standardized_coefficient():
    params = _build_params()
    result = fit_multivariate_model(params, "y")

    ranked = result.ranked_attributes()
    assert abs(result.standardized_coefficients[ranked[0]]) >= abs(result.standardized_coefficients[ranked[1]])


def test_fit_multivariate_model_returns_none_when_not_enough_data():
    # split 2개(자유도 부족: 변수 2개 + 절편이면 최소 4개는 있어야 함)
    params = _build_params()[:2]
    result = fit_multivariate_model(params, "y")

    assert result is None


def test_fit_multivariate_model_returns_none_when_metric_missing():
    params = _build_params()
    result = fit_multivariate_model(params, "does_not_exist")

    assert result is None


def test_fit_multivariate_model_excludes_constant_attribute():
    params = _build_params()
    for p in params:
        p.split.attributes["const"] = "5"  # 항상 같은 값 -> 회귀에서 제외돼야 함

    result = fit_multivariate_model(params, "y")

    assert "const" not in result.attribute_names


def test_describe_regression_effect_mentions_holding_other_variables_fixed():
    text = describe_regression_effect("Nd", "Vth_CC", 0.8)
    assert "다른 변수를 고정" in text
    assert "Nd" in text and "Vth_CC" in text
    assert "같이 커지는" in text


def test_describe_regression_effect_negative_coefficient():
    text = describe_regression_effect("Nd", "Vth_CC", -0.6)
    assert "반대로 작아지는" in text


def test_describe_regression_effect_near_zero_says_little_effect():
    text = describe_regression_effect("Nd", "Vth_CC", 0.05)
    assert "거의 영향이 없어" in text


def test_fit_multivariate_model_stable_when_attribute_scales_differ_wildly():
    # 실제 데이터에서 발견된 버그의 재현: 변수끼리 스케일이 극단적으로 다르면(예: Nd는
    # 1e13~1e17, Tigzo는 0.01~0.05) raw 스케일로 바로 최소자승을 풀 때 수치가 불안정해져
    # 훈련 데이터에서조차 R^2가 음수로 나오는 문제가 있었다 — 절편 포함 OLS의 훈련 R^2는
    # 수학적으로 항상 0 이상이어야 하므로, 음수가 나오면 버그다.
    big = [1e13, 1e14, 1e15, 1e16, 1e17, 5e16, 2e13, 7e15]
    small = [0.01, 0.05, 0.02, 0.04, 0.03, 0.015, 0.045, 0.025]
    y = [2e-16 * b + 100.0 * s for b, s in zip(big, small)]  # 노이즈 없는 정확한 선형결합

    params = []
    for i, (b, s, val) in enumerate(zip(big, small, y)):
        split = SplitCondition(split_name=f"n{i}", attributes={"big": str(b), "small": str(s)})
        params.append(ExtractedParameter(None, DEVICE, split, "y", float(val), unit="", method="test"))

    result = fit_multivariate_model(params, "y")

    assert result is not None
    assert result.r_squared >= 0.0
    assert result.r_squared == pytest.approx(1.0, abs=1e-3)
    assert result.coefficients["big"] == pytest.approx(2e-16, rel=1e-2)
    assert result.coefficients["small"] == pytest.approx(100.0, rel=1e-2)


def test_build_regression_summary_groups_by_metric():
    params = _build_params()
    summary = build_regression_summary(params, ["y"])

    assert list(summary["metric"]) == ["y", "y"]
    assert set(summary["attribute"]) == {"x1", "x2"}
