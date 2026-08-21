import pytest

from tcad_analyzer.parsers.dfise_parser import looks_like_dfise, parse_dfise_file
from tcad_analyzer.parsers.errors import TecplotParseError
from tcad_analyzer.parsers.plt_loader import load_plt_file, sniff_plt_format

DFISE_SAMPLE = """Info {
  version = 300
  type = xy
  datasets = [
    "gate OuterVoltage"
    "drain TotalCurrent"
  ]
}
Data {
  0.0 1.0e-12
  0.1 2.0e-12
  0.2 3.0e-12
}
"""


def test_parse_dfise_basic(tmp_path):
    path = tmp_path / "IdVg_n1_des.plt"
    path.write_text(DFISE_SAMPLE, encoding="utf-8")

    tf = parse_dfise_file(path)

    assert tf.variables == ["gate OuterVoltage", "drain TotalCurrent"]
    assert len(tf.zones) == 1
    zone = tf.zones[0]
    assert zone.data.shape == (3, 2)
    assert zone.column("gate OuterVoltage").tolist() == [0.0, 0.1, 0.2]
    assert zone.column("drain TotalCurrent").tolist() == [1.0e-12, 2.0e-12, 3.0e-12]


def test_looks_like_dfise_detects_format():
    assert looks_like_dfise(DFISE_SAMPLE) is True
    assert looks_like_dfise('TITLE = "x"\nVARIABLES = "a" "b"\nZONE T="z" I=1\n0 0\n') is False


def test_dfise_missing_datasets_raises(tmp_path):
    path = tmp_path / "bad.plt"
    path.write_text("Data {\n0.0 1.0\n}\n", encoding="utf-8")
    with pytest.raises(TecplotParseError):
        parse_dfise_file(path)


def test_dfise_column_count_mismatch_raises(tmp_path):
    path = tmp_path / "bad.plt"
    path.write_text(
        'Info { datasets = [ "a" "b" ] }\nData {\n0.0 1.0 2.0\n}\n',  # 3개는 2로 안 나눠떨어짐
        encoding="utf-8",
    )
    with pytest.raises(TecplotParseError):
        parse_dfise_file(path)


def test_dfise_incomplete_data_raises(tmp_path):
    # 시뮬레이션이 덜 끝나 파일이 중간에 잘린 상황 흉내
    path = tmp_path / "incomplete.plt"
    path.write_text('Info { datasets = [ "a" "b" "c" ] }\nData {\n0.0 1.0\n}\n', encoding="utf-8")
    with pytest.raises(TecplotParseError):
        parse_dfise_file(path)


def test_plt_loader_dispatches_dfise(tmp_path):
    path = tmp_path / "IdVg_n1_des.plt"
    path.write_text(DFISE_SAMPLE, encoding="utf-8")
    assert sniff_plt_format(path) == "dfise"
    tf = load_plt_file(path)
    assert tf.variables == ["gate OuterVoltage", "drain TotalCurrent"]


def test_plt_loader_dispatches_tecplot(tmp_path):
    path = tmp_path / "n1_des.plt"
    path.write_text(
        'TITLE = "x"\nVARIABLES = "Vg" "Id"\nZONE T="z" I=2 F=POINT\n0.0 1.0e-12\n0.1 2.0e-12\n',
        encoding="utf-8",
    )
    assert sniff_plt_format(path) == "tecplot"
    tf = load_plt_file(path)
    assert tf.variables == ["Vg", "Id"]


def test_plt_loader_unknown_format_raises(tmp_path):
    path = tmp_path / "n1_des.plt"
    path.write_text("this is neither format\n", encoding="utf-8")
    with pytest.raises(TecplotParseError):
        load_plt_file(path)
