import pytest

from tcad_analyzer.parsers.errors import GtreeParseError
from tcad_analyzer.parsers.gtree_parser import extract_node_id_from_filename, parse_gtree


def test_parse_tcl_style(tmp_path):
    path = tmp_path / "gtree.dat"
    path.write_text(
        "set gtree(1,Temperature) 900\n"
        "set gtree(1,Dose) 1e13\n"
        "set gtree(2,Temperature) 950\n"
        "set gtree(2,Dose) 1e13\n",
        encoding="utf-8",
    )

    project = parse_gtree(path)

    assert sorted(project.variable_names) == ["Dose", "Temperature"]
    assert project.nodes["1"] == {"Temperature": "900", "Dose": "1e13"}
    assert project.nodes["2"]["Temperature"] == "950"
    assert project.split_attributes_for_node("1")["Temperature"] == "900"
    assert project.split_attributes_for_node("99") is None


def test_parse_swb_tree_style(tmp_path):
    # 실제 Sentaurus Workbench gtree.dat을 축약한 형태: sprocess(Tigzo) -> sdevice(Nta) 2단 트리
    path = tmp_path / "gtree.dat"
    path.write_text(
        "# --- simulation flow\n"
        'sprocess sprocess "" {}\n'
        'sprocess Tigzo "0.030" {0.030 0.010}\n'
        'sdevice sdevice "" {}\n'
        'sdevice Nta "1e16" {1e16 1e18}\n'
        "# --- simulation tree\n"
        "0 3 0 {} {default} 0\n"
        "1 4 3 {0.030} {default} 0\n"
        "2 67 4 {} {default} 0\n"
        "3 668 67 {1e18} {default} 0\n"
        "3 669 67 {1e16} {default} 0\n",
        encoding="utf-8",
    )

    project = parse_gtree(path)

    assert sorted(project.variable_names) == ["Nta", "Tigzo"]
    assert project.split_attributes_for_node("668") == {"Tigzo": "0.030", "Nta": "1e18"}
    assert project.split_attributes_for_node("669") == {"Tigzo": "0.030", "Nta": "1e16"}


def test_parse_table_style(tmp_path):
    path = tmp_path / "gtree.dat"
    path.write_text("node Temperature Dose\n1 900 1e13\n2 950 1e13\n", encoding="utf-8")

    project = parse_gtree(path)

    assert project.nodes["1"] == {"Temperature": "900", "Dose": "1e13"}
    assert project.nodes["2"] == {"Temperature": "950", "Dose": "1e13"}


def test_unrecognized_format_raises(tmp_path):
    path = tmp_path / "gtree.dat"
    path.write_text("this is not a recognized gtree format at all\n", encoding="utf-8")

    with pytest.raises(GtreeParseError):
        parse_gtree(path)


def test_missing_file_raises(tmp_path):
    with pytest.raises(GtreeParseError):
        parse_gtree(tmp_path / "missing.dat")


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("n1_des.plt", "1"),
        ("n12_des.plt", "12"),
        ("n7_des.cmd", "7"),
        ("no_node_number.plt", None),
    ],
)
def test_extract_node_id_from_filename(filename, expected):
    assert extract_node_id_from_filename(filename) == expected
