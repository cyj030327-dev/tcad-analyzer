from tcad_analyzer.analysis.sensitivity import (
    build_sensitivity_table,
    compute_sensitivity_summary,
    describe_relationship,
    numeric_attribute_names,
    relationship_strength,
)
from tcad_analyzer.models import DeviceMeta, ExtractedParameter, Polarity, SplitCondition

DEVICE = DeviceMeta(device_id="N", polarity=Polarity.NMOS)

# Nd가 커질수록 Vth도 커지도록(양의 상관), SS는 Nd와 무관하게 거의 일정하도록 설계
SPLITS = [
    ("n1", {"Nd": "1e15", "Tigzo": "0.030"}, {"Vth_CC": 0.30, "SS": 100.0}),
    ("n2", {"Nd": "1e16", "Tigzo": "0.030"}, {"Vth_CC": 0.40, "SS": 101.0}),
    ("n3", {"Nd": "1e17", "Tigzo": "0.030"}, {"Vth_CC": 0.55, "SS": 99.0}),
    ("n4", {"Nd": "5e17", "Tigzo": "0.030"}, {"Vth_CC": 0.70, "SS": 100.0}),
]


def _build_params():
    params = []
    for split_name, attrs, values in SPLITS:
        split = SplitCondition(split_name=split_name, attributes=attrs)
        for name, value in values.items():
            params.append(ExtractedParameter(None, DEVICE, split, name, value, unit="", method="test"))
    return params


def test_numeric_attribute_names_only_includes_numeric_looking_values():
    params = _build_params()
    # split_name(n1, n2, ...)은 attribute가 아니라 SplitCondition.split_name이라 여기 안 섞임
    assert numeric_attribute_names(params) == ["Nd", "Tigzo"]


def test_numeric_attribute_names_excludes_non_numeric_attribute():
    params = _build_params()
    params.append(
        ExtractedParameter(
            None,
            DEVICE,
            SplitCondition(split_name="n5", attributes={"Nd": "1e18", "Note": "재시뮬레이션"}),
            "Vth_CC",
            0.8,
            "",
            "test",
        )
    )
    names = numeric_attribute_names(params)
    assert "Nd" in names
    assert "Note" not in names


def test_build_sensitivity_table_has_attribute_and_metric_columns():
    params = _build_params()
    table = build_sensitivity_table(params, ["Vth_CC", "SS"])
    assert set(table.columns) == {"split_label", "Nd", "Tigzo", "Vth_CC", "SS"}
    assert len(table) == 4
    # Nd가 문자열("1e17")이 아니라 숫자로 변환됐는지
    row = table[table["split_label"].str.contains("n3")].iloc[0]
    assert row["Nd"] == 1e17


def test_compute_sensitivity_summary_ranks_strong_correlation_first():
    params = _build_params()
    summary = compute_sensitivity_summary(params, ["Vth_CC", "SS"])
    assert not summary.empty
    top = summary.iloc[0]
    assert top["attribute"] == "Nd"
    assert top["metric"] == "Vth_CC"
    assert top["pearson_r"] > 0.9  # Nd가 커질수록 Vth도 커지도록 설계했으므로 강한 양의 상관

    # Tigzo는 모든 split에서 값이 똑같아(변화 없음) 상관계수가 정의되지 않으므로 요약에서 빠져야 함
    assert not ((summary["attribute"] == "Tigzo")).any()


def test_compute_sensitivity_summary_empty_when_not_enough_data():
    params = _build_params()[:2]  # 2개 split만 남기면(최소 3개 미만) 상관계수 계산 안 함
    summary = compute_sensitivity_summary(params, ["Vth_CC"])
    assert summary.empty


def test_build_sensitivity_table_empty_when_no_params():
    assert build_sensitivity_table([], ["Vth_CC"]).empty


def test_relationship_strength_thresholds():
    assert relationship_strength(0.85) == "강한"
    assert relationship_strength(-0.85) == "강한"  # 방향과 무관하게 크기만 봄
    assert relationship_strength(0.5) == "중간 정도의"
    assert relationship_strength(0.3) == "약한"
    assert relationship_strength(0.05) == "거의 없는"


def test_describe_relationship_positive_correlation_mentions_same_direction():
    text = describe_relationship("Nd", "Vth_CC", 0.8)
    assert "Nd" in text and "Vth_CC" in text
    assert "같이 커지는" in text
    assert "강한" in text


def test_describe_relationship_negative_correlation_mentions_opposite_direction():
    text = describe_relationship("Nd", "Ion_Ioff_ratio", -0.6)
    assert "반대로 작아지는" in text


def test_describe_relationship_weak_correlation_says_no_clear_relationship():
    text = describe_relationship("Tigzo", "SS", 0.05)
    assert "뚜렷하게 바뀌지 않는" in text


def test_describe_relationship_handles_missing_r():
    text = describe_relationship("Tigzo", "SS", None)
    assert "데이터가 부족" in text


def test_compute_sensitivity_summary_groups_by_metric_instead_of_global_r_sort():
    # Nd-SS(|r|~0.32), Nta-Vth(|r|~0.33)처럼 서로 다른 지표의 상관계수가 비슷하게 섞여
    # 있어도, |r| 하나로만 전체 정렬하면 같은 지표의 행이 표 여기저기로 흩어진다(뒤죽박죽).
    # 지표별로 먼저 묶이는지 확인한다("이 지표는 뭐에 영향받는지"를 한눈에 보기 위함).
    splits = [
        ("n1", {"Nd": "1", "Nta": "1"}, {"Vth_CC": 0.30, "SS": 100.0}),
        ("n2", {"Nd": "2", "Nta": "4"}, {"Vth_CC": 0.40, "SS": 101.0}),
        ("n3", {"Nd": "3", "Nta": "2"}, {"Vth_CC": 0.55, "SS": 99.0}),
        ("n4", {"Nd": "4", "Nta": "3"}, {"Vth_CC": 0.70, "SS": 100.0}),
    ]
    params = []
    for split_name, attrs, values in splits:
        split = SplitCondition(split_name=split_name, attributes=attrs)
        for name, value in values.items():
            params.append(ExtractedParameter(None, DEVICE, split, name, value, unit="", method="test"))

    summary = compute_sensitivity_summary(params, ["Vth_CC", "SS"])

    # 같은 지표의 행끼리 붙어 있어야 한다(Vth_CC 두 줄이 먼저, 그다음 SS 두 줄 — metric_names 순서)
    assert list(summary["metric"]) == ["Vth_CC", "Vth_CC", "SS", "SS"]
    # 각 지표 그룹 안에서는 |r|이 큰 변수가 먼저 와야 한다
    vth_rows = summary[summary["metric"] == "Vth_CC"]
    assert vth_rows.iloc[0]["attribute"] == "Nd"  # Nd-Vth_CC(r~0.99) > Nta-Vth_CC(r~0.33)
    ss_rows = summary[summary["metric"] == "SS"]
    assert ss_rows.iloc[0]["attribute"] == "Nta"  # Nta-SS(r~0.63) > Nd-SS(r~0.32)
