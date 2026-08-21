import pandas as pd
import pytest

from tcad_analyzer.parsers.errors import TableLoadError
from tcad_analyzer.parsers.table_loader import load_parameter_table


def test_load_csv_basic(tmp_path):
    path = tmp_path / "params.csv"
    path.write_text("Lot,Split,Device,Vth,SS\nLOT1,A,NMOS,0.40,80\nLOT1,B,NMOS,0.38,82\n", encoding="utf-8")

    df = load_parameter_table(path)

    assert list(df.columns) == ["Lot", "Split", "Device", "Vth", "SS"]
    assert len(df) == 2
    assert df.loc[0, "Vth"] == 0.40


def test_load_csv_semicolon_delimiter(tmp_path):
    path = tmp_path / "params.csv"
    path.write_text("Lot;Split;Vth\nLOT1;A;0.40\nLOT1;B;0.38\n", encoding="utf-8")

    df = load_parameter_table(path)

    assert list(df.columns) == ["Lot", "Split", "Vth"]
    assert len(df) == 2


def test_load_csv_strips_column_whitespace_and_drops_empty_rows(tmp_path):
    path = tmp_path / "params.csv"
    path.write_text("Lot , Vth \nLOT1,0.40\n,\nLOT1,0.38\n", encoding="utf-8")

    df = load_parameter_table(path)

    assert list(df.columns) == ["Lot", "Vth"]
    assert len(df) == 2  # 완전 빈 행 제거


def test_load_excel_roundtrip(tmp_path):
    path = tmp_path / "params.xlsx"
    pd.DataFrame({"Lot": ["LOT1", "LOT1"], "Vth": [0.40, 0.38]}).to_excel(path, index=False)

    df = load_parameter_table(path)

    assert list(df.columns) == ["Lot", "Vth"]
    assert len(df) == 2


def test_missing_file_raises(tmp_path):
    with pytest.raises(TableLoadError):
        load_parameter_table(tmp_path / "missing.csv")


def test_unsupported_extension_raises(tmp_path):
    path = tmp_path / "params.txt"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(TableLoadError):
        load_parameter_table(path)


def test_empty_file_raises(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")
    with pytest.raises(TableLoadError):
        load_parameter_table(path)
