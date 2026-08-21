from tcad_analyzer.parsers.column_matcher import suggest_column_roles


def test_suggests_simple_tecplot_style_names():
    variables = ["Gate Voltage (V)", "Drain Current (A)", "Drain Voltage (V)"]
    roles = suggest_column_roles(variables)
    assert roles["Vg"] == "Gate Voltage (V)"
    assert roles["Id"] == "Drain Current (A)"
    assert roles["Vd"] == "Drain Voltage (V)"


def test_prefers_total_current_over_component_currents():
    # 실제 DF-ISE 데이터는 eCurrent/hCurrent가 TotalCurrent보다 먼저 나열되는 경우가 있다.
    # eCurrent(전자 전류 성분)를 잘못 고르면 안 되고 TotalCurrent를 골라야 한다.
    variables = [
        "gate OuterVoltage",
        "gate InnerVoltage",
        "drain OuterVoltage",
        "drain InnerVoltage",
        "drain eCurrent",
        "drain hCurrent",
        "drain TotalCurrent",
    ]
    roles = suggest_column_roles(variables)
    assert roles["Id"] == "drain TotalCurrent"
    assert roles["Vg"] == "gate OuterVoltage"
    assert roles["Vd"] == "drain OuterVoltage"


def test_falls_back_to_generic_current_when_no_total_column():
    variables = ["gate OuterVoltage", "drain eCurrent"]
    roles = suggest_column_roles(variables)
    assert roles["Id"] == "drain eCurrent"


def test_no_match_returns_none():
    roles = suggest_column_roles(["foo", "bar"])
    assert roles["Vg"] is None
    assert roles["Id"] is None
