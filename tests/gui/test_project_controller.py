import pytest
from PySide6.QtWidgets import QApplication

from tcad_analyzer.gui.controllers import project_controller as pc_module
from tcad_analyzer.gui.controllers.project_controller import ProjectController
from tcad_analyzer.models import CurveType


@pytest.fixture(autouse=True)
def _isolate_real_user_config(monkeypatch):
    """import_folder()는 항상 save_last_import_dir()를 부르므로, 이 값을 막아두지 않으면
    테스트를 돌릴 때마다 실제 사용자의 ~/.tcad_analyzer/config.json이 pytest의 임시 경로로
    덮어써진다. 모든 테스트에 기본적으로 안전한 no-op을 적용하고, 필요한 테스트만 개별적으로
    load_last_import_dir을 오버라이드한다.
    """
    monkeypatch.setattr(pc_module, "save_last_import_dir", lambda path: None)
    monkeypatch.setattr(pc_module, "load_last_import_dir", lambda: None)

DFISE_SAMPLE = """Info {
  datasets = [
    "gate OuterVoltage"
    "drain TotalCurrent"
  ]
}
Data {
  0.0 1.0e-12
  0.1 2.0e-12
}
"""


def _ensure_qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_import_folder_recurses_into_subfolders(tmp_path):
    _ensure_qapp()
    sub1 = tmp_path / "n668"
    sub2 = tmp_path / "n673"
    sub1.mkdir()
    sub2.mkdir()
    (sub1 / "IdVg_n668_des.plt").write_text(DFISE_SAMPLE, encoding="utf-8")
    (sub2 / "IdVg_n673_des.plt").write_text(DFISE_SAMPLE, encoding="utf-8")

    controller = ProjectController()
    controller.import_folder(tmp_path)

    assert len(controller.imported_plt) == 2
    assert all(status.ok for status in controller.import_status)


def test_import_folder_saves_as_last_dir(tmp_path, monkeypatch):
    _ensure_qapp()
    saved = {}
    monkeypatch.setattr(pc_module, "save_last_import_dir", lambda p: saved.setdefault("path", p))

    controller = ProjectController()
    controller.import_folder(tmp_path)

    assert saved["path"] == tmp_path
    assert controller.last_import_dir == tmp_path


def test_restore_last_session_folder_reimports_when_remembered(tmp_path, monkeypatch):
    _ensure_qapp()
    (tmp_path / "IdVg_n1_des.plt").write_text(DFISE_SAMPLE, encoding="utf-8")
    monkeypatch.setattr(pc_module, "load_last_import_dir", lambda: tmp_path)

    controller = ProjectController()
    controller.restore_last_session_folder()

    assert len(controller.imported_plt) == 1


def test_restore_last_session_folder_noop_when_nothing_remembered(monkeypatch):
    _ensure_qapp()
    monkeypatch.setattr(pc_module, "load_last_import_dir", lambda: None)

    controller = ProjectController()
    controller.restore_last_session_folder()

    assert controller.imported_plt == {}


def test_remove_paths_drops_plt_and_its_mapping(tmp_path):
    _ensure_qapp()
    p1 = tmp_path / "IdVg_n668_des.plt"
    p2 = tmp_path / "IdVg_n673_des.plt"
    p1.write_text(DFISE_SAMPLE, encoding="utf-8")
    p2.write_text(DFISE_SAMPLE, encoding="utf-8")

    controller = ProjectController()
    controller.import_paths([p1, p2])
    assert len(controller.imported_plt) == 2

    controller.remove_paths([p1])

    assert len(controller.imported_plt) == 1
    assert str(p1) not in controller.imported_plt
    assert str(p1) not in controller.plt_mappings
    assert all(status.path != p1 for status in controller.import_status)
    # 남은 파일은 그대로 유지
    assert str(p2) in controller.imported_plt


def test_remove_paths_drops_gtree_and_cmd_summary(tmp_path):
    _ensure_qapp()
    gtree = tmp_path / "gtree.dat"
    gtree.write_text(
        'sdevice sdevice "" {}\n'
        'sdevice Nta "1e16" {1e16 1e18}\n'
        "0 3 0 {} {default} 0\n"
        "1 668 3 {1e18} {default} 0\n",
        encoding="utf-8",
    )
    cmd = tmp_path / "n668_des.cmd"
    cmd.write_text(
        'Electrode { { Name="gate" } }\nSolve { Quasistationary ( Goal { Name="gate" Voltage=1.0 } ) {} }\n',
        encoding="utf-8",
    )

    controller = ProjectController()
    controller.import_paths([gtree, cmd])
    assert controller.gtree_project is not None
    assert "668" in controller.cmd_summaries

    controller.remove_paths([gtree, cmd])

    assert controller.gtree_project is None
    assert "668" not in controller.cmd_summaries
    assert controller.import_status == []


def _make_dfise_text(gate_values, drain_values, current_values) -> str:
    rows = zip(gate_values, drain_values, current_values)
    data = "\n".join(f"{g} {d} {i}" for g, d, i in rows)
    return (
        'Info {\n'
        '  datasets = [\n'
        '    "gate OuterVoltage"\n'
        '    "drain OuterVoltage"\n'
        '    "drain TotalCurrent"\n'
        '  ]\n'
        '}\n'
        f'Data {{\n{data}\n}}\n'
    )


def test_import_detects_id_vd_curve_from_single_zone_sweep(tmp_path):
    """Vg는 고정, Vd만 스윕되는(zone 1개짜리) 실제 Id-Vd 파일이 Id-Vg로 잘못 분류되지
    않는지 확인 — 예전에는 zone 개수만 보고 판단해 이런 파일을 놓쳤다."""
    _ensure_qapp()
    path = tmp_path / "IdVd_n1_des.plt"
    gate = [1.0] * 12
    drain = [round(0.15 * i, 2) for i in range(12)]  # 0.0 ~ 1.65V로 스윕
    current = [1e-6 * (i + 1) for i in range(12)]
    path.write_text(_make_dfise_text(gate, drain, current), encoding="utf-8")

    controller = ProjectController()
    controller.import_paths([path])

    mapping = controller.plt_mappings[str(path)]
    assert mapping.curve_type == CurveType.ID_VD
    status = controller.import_status[0]
    assert "Id-Vd로 인식" in status.message
    assert "스윕 아닌 것 같음" not in status.message  # Vg가 고정인 건 정상이므로 경고 없어야 함


def test_import_detects_id_vg_curve_when_vg_is_swept(tmp_path):
    _ensure_qapp()
    path = tmp_path / "IdVg_n1_des.plt"
    gate = [round(0.15 * i, 2) for i in range(12)]  # 0.0 ~ 1.65V로 스윕
    drain = [1.0] * 12
    current = [1e-9 * (i + 1) for i in range(12)]
    path.write_text(_make_dfise_text(gate, drain, current), encoding="utf-8")

    controller = ProjectController()
    controller.import_paths([path])

    mapping = controller.plt_mappings[str(path)]
    assert mapping.curve_type == CurveType.ID_VG
    status = controller.import_status[0]
    assert "Id-Vg로 인식" in status.message
    assert "스윕 아닌 것 같음" not in status.message


SPROCESS_SAMPLE = """
set Tox    0.100
set Lch    10.0

line x location=0.0   spacing=0.02

contact name=gate bottom

deposit material=Oxide type=anisotropic thickness=$Tox

init field=Phosphorus concentration=1e20

struct tdr=n55_fps
"""

PMOS_LIKE_DFISE_SAMPLE = """Info {
  datasets = [
    "gate OuterVoltage"
    "drain TotalCurrent"
  ]
}
Data {
  0.0 -1.0e-12
  0.1 -2.0e-12
}
"""


def test_import_recognizes_sprocess_cmd_and_fills_config_hint(tmp_path):
    _ensure_qapp()
    path = tmp_path / "pp55_fps.cmd"
    path.write_text(SPROCESS_SAMPLE, encoding="utf-8")

    controller = ProjectController()
    controller.import_paths([path])

    assert controller.sprocess_summary is not None
    assert controller.sprocess_summary.channel_length_um == 10.0
    assert controller.sprocess_summary.gate_oxide_thickness_um == 0.100
    status = controller.import_status[0]
    assert status.kind == "sprocess"
    assert "L=10.0um" in status.message


def test_import_sprocess_retroactively_fills_length_for_existing_plt_mapping(tmp_path):
    _ensure_qapp()
    plt_path = tmp_path / "IdVg_n668_des.plt"
    plt_path.write_text(DFISE_SAMPLE, encoding="utf-8")
    sprocess_path = tmp_path / "pp55_fps.cmd"
    sprocess_path.write_text(SPROCESS_SAMPLE, encoding="utf-8")

    controller = ProjectController()
    controller.import_paths([plt_path])  # sprocess보다 먼저 임포트
    assert controller.plt_mappings[str(plt_path)].length_um is None

    controller.import_paths([sprocess_path])  # 나중에 sprocess 임포트 -> 소급 적용돼야 함

    assert controller.plt_mappings[str(plt_path)].length_um == 10.0


def test_gtree_length_variable_wins_over_sprocess_global_length(tmp_path):
    # 채널 길이(Lg) 자체가 split마다 다르게 스윕되는 프로젝트를 흉내낸다. sprocess 파일 하나로
    # 읽은 "프로젝트 전체 고정 L"(여기선 10.0)을 모든 split에 그대로 적용하면, 실제로는
    # split마다 다른 L(여기선 노드 668의 0.2)을 무시하게 돼 틀린다 — gtree의 split별 값이
    # 항상 우선해야 한다.
    _ensure_qapp()
    gtree = tmp_path / "gtree.dat"
    gtree.write_text(
        'sdevice sdevice "" {}\n'
        'sdevice Lg "0.2" {0.2 0.3}\n'
        "0 3 0 {} {default} 0\n"
        "1 668 3 {0.2} {default} 0\n",
        encoding="utf-8",
    )
    plt_path = tmp_path / "IdVg_n668_des.plt"
    plt_path.write_text(DFISE_SAMPLE, encoding="utf-8")
    sprocess_path = tmp_path / "pp55_fps.cmd"
    sprocess_path.write_text(SPROCESS_SAMPLE, encoding="utf-8")  # Lch=10.0(전체 고정값 흉내)

    controller = ProjectController()
    controller.import_paths([gtree, plt_path, sprocess_path])

    mapping = controller.plt_mappings[str(plt_path)]
    assert mapping.split_attributes.get("Lg") == "0.2"
    assert mapping.length_um == 0.2  # sprocess의 10.0이 아니라 gtree의 split별 값을 써야 함


def test_gtree_length_variable_applies_retroactively_when_gtree_loads_last(tmp_path):
    _ensure_qapp()
    plt_path = tmp_path / "IdVg_n668_des.plt"
    plt_path.write_text(DFISE_SAMPLE, encoding="utf-8")
    sprocess_path = tmp_path / "pp55_fps.cmd"
    sprocess_path.write_text(SPROCESS_SAMPLE, encoding="utf-8")
    gtree = tmp_path / "gtree.dat"
    gtree.write_text(
        'sdevice sdevice "" {}\n'
        'sdevice Lg "0.2" {0.2 0.3}\n'
        "0 3 0 {} {default} 0\n"
        "1 668 3 {0.2} {default} 0\n",
        encoding="utf-8",
    )

    controller = ProjectController()
    controller.import_paths([plt_path, sprocess_path])  # sprocess가 먼저 -> 10.0으로 채워짐
    assert controller.plt_mappings[str(plt_path)].length_um == 10.0

    controller.import_paths([gtree])  # gtree가 나중에 -> split별 값(0.2)으로 덮어써야 함

    assert controller.plt_mappings[str(plt_path)].length_um == 0.2


def test_import_plt_after_sprocess_auto_fills_unit_width_for_2d_structure(tmp_path):
    _ensure_qapp()
    sprocess_path = tmp_path / "pp55_fps.cmd"
    sprocess_path.write_text(SPROCESS_SAMPLE, encoding="utf-8")
    plt_path = tmp_path / "IdVg_n668_des.plt"
    plt_path.write_text(DFISE_SAMPLE, encoding="utf-8")

    controller = ProjectController()
    controller.import_paths([sprocess_path, plt_path])  # sprocess를 먼저 임포트

    assert controller.sprocess_summary.is_2d_structure is True
    assert controller.plt_mappings[str(plt_path)].width_um == 1.0


def test_import_sprocess_retroactively_fills_unit_width_for_existing_plt_mapping(tmp_path):
    _ensure_qapp()
    plt_path = tmp_path / "IdVg_n668_des.plt"
    plt_path.write_text(DFISE_SAMPLE, encoding="utf-8")
    sprocess_path = tmp_path / "pp55_fps.cmd"
    sprocess_path.write_text(SPROCESS_SAMPLE, encoding="utf-8")

    controller = ProjectController()
    controller.import_paths([plt_path])  # sprocess보다 먼저 임포트
    assert controller.plt_mappings[str(plt_path)].width_um is None

    controller.import_paths([sprocess_path])  # 나중에 sprocess 임포트 -> 소급 적용돼야 함

    assert controller.plt_mappings[str(plt_path)].width_um == 1.0


def test_import_sprocess_does_not_override_user_set_width(tmp_path):
    _ensure_qapp()
    plt_path = tmp_path / "IdVg_n668_des.plt"
    plt_path.write_text(DFISE_SAMPLE, encoding="utf-8")
    sprocess_path = tmp_path / "pp55_fps.cmd"
    sprocess_path.write_text(SPROCESS_SAMPLE, encoding="utf-8")

    controller = ProjectController()
    controller.import_paths([plt_path])
    controller.plt_mappings[str(plt_path)].width_um = 5.0  # 사용자가 직접 값을 입력했다고 가정

    controller.import_paths([sprocess_path])

    assert controller.plt_mappings[str(plt_path)].width_um == 5.0  # 덮어쓰지 않아야 함


def test_import_sprocess_does_not_override_user_set_length(tmp_path):
    _ensure_qapp()
    plt_path = tmp_path / "IdVg_n668_des.plt"
    plt_path.write_text(DFISE_SAMPLE, encoding="utf-8")
    sprocess_path = tmp_path / "pp55_fps.cmd"
    sprocess_path.write_text(SPROCESS_SAMPLE, encoding="utf-8")

    controller = ProjectController()
    controller.import_paths([plt_path])
    # Column Mapping에서 사용자가 직접 입력한 상황을 흉내낸다(실제로는
    # ColumnMappingPage._save_current_plt_mapping()이 이 두 필드를 같이 설정함)
    controller.plt_mappings[str(plt_path)].length_um = 5.0
    controller.plt_mappings[str(plt_path)].length_um_source = "user"

    controller.import_paths([sprocess_path])

    assert controller.plt_mappings[str(plt_path)].length_um == 5.0  # 덮어쓰지 않아야 함


def test_import_does_not_misclassify_sdevice_cmd_as_sprocess(tmp_path):
    _ensure_qapp()
    path = tmp_path / "pp799_des.cmd"
    path.write_text(
        'File {\n   Current = "n799_des.plt"\n}\nElectrode {\n   { Name="gate" Voltage=0.0 }\n}\n'
        'Solve {\n   Coupled { Poisson Electron Hole }\n}\n',
        encoding="utf-8",
    )

    controller = ProjectController()
    controller.import_paths([path])

    assert controller.sprocess_summary is None
    assert controller.import_status[0].kind == "cmd"


def test_import_plt_after_sprocess_shows_polarity_match_note(tmp_path):
    _ensure_qapp()
    sprocess_path = tmp_path / "pp55_fps.cmd"
    sprocess_path.write_text(SPROCESS_SAMPLE, encoding="utf-8")
    plt_path = tmp_path / "IdVg_n668_des.plt"
    plt_path.write_text(DFISE_SAMPLE, encoding="utf-8")  # 전류가 양수 -> NMOS로 추정됨

    controller = ProjectController()
    controller.import_paths([sprocess_path, plt_path])  # sprocess를 먼저 임포트

    plt_status = next(s for s in controller.import_status if s.kind == "plt")
    assert "✓ sprocess 도핑" in plt_status.message
    assert "극성 일치" in plt_status.message


def test_import_plt_after_sprocess_shows_polarity_mismatch_warning(tmp_path):
    _ensure_qapp()
    sprocess_path = tmp_path / "pp55_fps.cmd"
    sprocess_path.write_text(SPROCESS_SAMPLE, encoding="utf-8")  # Phosphorus -> n형
    plt_path = tmp_path / "IdVg_n668_des.plt"
    plt_path.write_text(PMOS_LIKE_DFISE_SAMPLE, encoding="utf-8")  # 전류가 음수 -> PMOS로 추정됨

    controller = ProjectController()
    controller.import_paths([sprocess_path, plt_path])

    plt_status = next(s for s in controller.import_status if s.kind == "plt")
    assert "⚠ 극성 불일치 가능성" in plt_status.message


def test_import_plt_before_sprocess_retroactively_gets_polarity_note(tmp_path):
    _ensure_qapp()
    plt_path = tmp_path / "IdVg_n668_des.plt"
    plt_path.write_text(DFISE_SAMPLE, encoding="utf-8")
    sprocess_path = tmp_path / "pp55_fps.cmd"
    sprocess_path.write_text(SPROCESS_SAMPLE, encoding="utf-8")

    controller = ProjectController()
    controller.import_paths([plt_path])  # sprocess 없이 먼저 임포트
    plt_status = next(s for s in controller.import_status if s.kind == "plt")
    assert "극성" not in plt_status.message

    controller.import_paths([sprocess_path])  # 나중에 sprocess 임포트 -> 소급 적용

    plt_status = next(s for s in controller.import_status if s.kind == "plt")
    assert "✓ sprocess 도핑" in plt_status.message


def test_import_plt_no_polarity_note_when_sprocess_has_no_dopant_info(tmp_path):
    _ensure_qapp()
    sprocess_path = tmp_path / "pp55_fps.cmd"
    # Phosphorus 줄을 뺀 버전 -> 도펀트 정보 없음
    no_dopant_sprocess = SPROCESS_SAMPLE.replace("init field=Phosphorus concentration=1e20\n\n", "")
    sprocess_path.write_text(no_dopant_sprocess, encoding="utf-8")
    plt_path = tmp_path / "IdVg_n668_des.plt"
    plt_path.write_text(DFISE_SAMPLE, encoding="utf-8")

    controller = ProjectController()
    controller.import_paths([sprocess_path, plt_path])

    plt_status = next(s for s in controller.import_status if s.kind == "plt")
    assert "극성" not in plt_status.message


def test_clear_all_imports_resets_everything(tmp_path):
    _ensure_qapp()
    p1 = tmp_path / "IdVg_n668_des.plt"
    p1.write_text(DFISE_SAMPLE, encoding="utf-8")

    controller = ProjectController()
    controller.import_paths([p1])
    assert controller.imported_plt

    controller.clear_all_imports()

    assert controller.imported_plt == {}
    assert controller.imported_tables == {}
    assert controller.plt_mappings == {}
    assert controller.table_mappings == {}
    assert controller.gtree_project is None
    assert controller.cmd_summaries == {}
    assert controller.import_status == []
