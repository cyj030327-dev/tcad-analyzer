from tcad_analyzer.parsers.sdevice_cmd_parser import parse_sdevice_cmd

REAL_STYLE_CMD = """File {
   Grid = "n1_fps.tdr"
   Plot = "n668_des.tdr"
   Current = "n668_des.plt"
   Output = "n668_des.log"
}

Electrode {
   { Name="gate"   Voltage=0.0 }
   { Name="drain"  Voltage=0.0 }
}

Physics {
   Temperature = 300
   Mobility ( ConstantMobility )
}

Solve {
   Quasistationary (
      Goal { name="drain" Voltage=5.0 }
   ) { Coupled { Poisson Electron Hole } }

   NewCurrentPrefix="IdVg_"

   Quasistationary (
      Goal { name="gate" Voltage=20.0 }
   ) { Coupled { Poisson Electron Hole } }
}
"""


def test_extracts_electrodes_and_voltage_sweeps(tmp_path):
    path = tmp_path / "pp668_des.cmd"
    path.write_text(REAL_STYLE_CMD, encoding="utf-8")

    summary = parse_sdevice_cmd(path)

    assert "gate" in summary.electrodes
    assert "drain" in summary.electrodes
    assert any("5.0" in s for s in summary.voltage_sweeps)
    assert any("20.0" in s for s in summary.voltage_sweeps)


def test_node_id_hint_from_content_when_filename_does_not_match():
    # 파일명이 "pp668_des.cmd"라 n<N>_ 관례를 안 따르지만, 내용의 Current="n668_des.plt"에서
    # 노드 번호를 찾아낼 수 있어야 한다.
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "pp668_des.cmd"
        path.write_text(REAL_STYLE_CMD, encoding="utf-8")
        summary = parse_sdevice_cmd(path)

    assert summary.node_id_hint == "668"


def test_physics_models_extracted():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "n1_des.cmd"
        path.write_text(REAL_STYLE_CMD, encoding="utf-8")
        summary = parse_sdevice_cmd(path)

    assert "Mobility" in summary.physics_models
    assert "ConstantMobility" in summary.physics_models
