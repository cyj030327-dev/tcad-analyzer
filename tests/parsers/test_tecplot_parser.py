import pytest

from tcad_analyzer.parsers.errors import TecplotParseError
from tcad_analyzer.parsers.tecplot_parser import parse_tecplot_file


def test_parse_basic_single_zone(tmp_path):
    content = (
        'TITLE = "basic"\n'
        'VARIABLES = "Gate Voltage (V)" "Drain Current (A)" "Drain Voltage (V)"\n'
        'ZONE T="split1" I=3 F=POINT\n'
        "0.0 1.0e-12 0.05\n"
        "0.1 2.0e-12 0.05\n"
        "0.2 3.0e-12 0.05\n"
    )
    path = tmp_path / "basic.plt"
    path.write_text(content, encoding="utf-8")

    tf = parse_tecplot_file(path)

    assert tf.title == "basic"
    assert tf.variables == ["Gate Voltage (V)", "Drain Current (A)", "Drain Voltage (V)"]
    assert len(tf.zones) == 1
    zone = tf.zones[0]
    assert zone.title == "split1"
    assert zone.data.shape == (3, 3)
    assert zone.column("Gate Voltage (V)").tolist() == [0.0, 0.1, 0.2]


def test_parse_multiple_zones(tmp_path):
    content = (
        'TITLE = "multi"\n'
        'VARIABLES = "Vg" "Id" "Vd"\n'
        'ZONE T="zoneA" I=2 F=POINT\n'
        "0.0 1.0e-12 0.05\n"
        "0.1 2.0e-12 0.05\n"
        'ZONE T="zoneB" I=2 F=POINT\n'
        "0.0 3.0e-12 0.05\n"
        "0.1 4.0e-12 0.05\n"
    )
    path = tmp_path / "multi.plt"
    path.write_text(content, encoding="utf-8")

    tf = parse_tecplot_file(path)

    assert len(tf.zones) == 2
    assert tf.zones[0].title == "zoneA"
    assert tf.zones[1].title == "zoneB"
    assert tf.zones[1].column("Id").tolist() == [3.0e-12, 4.0e-12]


def test_variables_spanning_multiple_lines(tmp_path):
    content = (
        'TITLE = "ml"\n'
        "VARIABLES = \n"
        '"Gate Voltage (V)"\n'
        '"Drain Current (A)"\n'
        '"Drain Voltage (V)"\n'
        'ZONE T="ml" I=2 F=POINT\n'
        "0.0 1.0e-12 0.05\n"
        "0.1 2.0e-12 0.05\n"
    )
    path = tmp_path / "ml.plt"
    path.write_text(content, encoding="utf-8")

    tf = parse_tecplot_file(path)

    assert tf.variables == ["Gate Voltage (V)", "Drain Current (A)", "Drain Voltage (V)"]
    assert len(tf.zones) == 1


def test_fortran_exponent_and_crlf(tmp_path):
    content = (
        'TITLE = "fortran"\r\n'
        'VARIABLES = "Vg" "Id" "Vd"\r\n'
        'ZONE T="z" I=2 F=POINT\r\n'
        "0.0 1.0D-12 0.05\r\n"
        "0.1 2.0D-12 0.05\r\n"
    )
    path = tmp_path / "fortran.plt"
    path.write_bytes(content.encode("utf-8"))

    tf = parse_tecplot_file(path)

    assert tf.zones[0].column("Id").tolist() == [1.0e-12, 2.0e-12]


def test_column_count_mismatch_raises_with_line_number(tmp_path):
    content = (
        'TITLE = "bad"\n'
        'VARIABLES = "Vg" "Id" "Vd"\n'
        'ZONE T="bad" I=3 F=POINT\n'
        "0.0 1.0e-12 0.05\n"
        "0.1 2.0e-12\n"  # 컬럼 누락 -> 4번째 줄(1-indexed)
        "0.2 3.0e-12 0.05\n"
    )
    path = tmp_path / "bad.plt"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(TecplotParseError) as exc_info:
        parse_tecplot_file(path)

    assert exc_info.value.line_no == 5
    assert "0.1 2.0e-12" in exc_info.value.raw_line


def test_declared_i_mismatch_uses_actual_row_count(tmp_path):
    content = (
        'TITLE = "mismatch"\n'
        'VARIABLES = "Vg" "Id" "Vd"\n'
        'ZONE T="mismatch" I=10 F=POINT\n'
        "0.0 1.0e-12 0.05\n"
        "0.1 2.0e-12 0.05\n"
        "0.2 3.0e-12 0.05\n"
    )
    path = tmp_path / "mismatch.plt"
    path.write_text(content, encoding="utf-8")

    tf = parse_tecplot_file(path)

    assert tf.zones[0].data.shape == (3, 3)


def test_missing_variables_header_raises(tmp_path):
    path = tmp_path / "no_vars.plt"
    path.write_text('TITLE = "x"\nZONE T="z" I=1 F=POINT\n0.0 1.0e-12 0.05\n', encoding="utf-8")

    with pytest.raises(TecplotParseError):
        parse_tecplot_file(path)


def test_no_zone_raises(tmp_path):
    path = tmp_path / "no_zone.plt"
    path.write_text('TITLE = "x"\nVARIABLES = "Vg" "Id" "Vd"\n', encoding="utf-8")

    with pytest.raises(TecplotParseError):
        parse_tecplot_file(path)


def test_missing_file_raises():
    with pytest.raises(TecplotParseError):
        parse_tecplot_file("does_not_exist.plt")
