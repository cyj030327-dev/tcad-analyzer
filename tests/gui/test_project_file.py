import pytest
from PySide6.QtWidgets import QApplication

from tcad_analyzer.extraction import ExtractionConfig
from tcad_analyzer.gui.controllers import project_controller as pc_module
from tcad_analyzer.gui.controllers.project_controller import ProjectController
from tcad_analyzer.gui.project_file import load_project, save_project
from tcad_analyzer.models import CurveType, Polarity

DFISE_SAMPLE = """Info {
  datasets = [
    "gate OuterVoltage"
    "drain TotalCurrent"
  ]
}
Data {
  0.0 1.0e-12
  0.1 2.0e-12
  0.2 4.0e-12
  0.3 8.0e-12
}
"""


@pytest.fixture(autouse=True)
def _isolate_real_user_config(monkeypatch):
    """다른 controller 테스트들과 같은 이유로, 실제 사용자의 ~/.tcad_analyzer/config.json을
    건드리지 않도록 기본적으로 막아둔다."""
    monkeypatch.setattr(pc_module, "save_last_import_dir", lambda path: None)
    monkeypatch.setattr(pc_module, "load_last_import_dir", lambda: None)


def _ensure_qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_save_and_load_roundtrip_restores_manual_mapping_overrides(tmp_path):
    _ensure_qapp()
    plt_path = tmp_path / "IdVg_n668_des.plt"
    plt_path.write_text(DFISE_SAMPLE, encoding="utf-8")

    controller = ProjectController()
    controller.import_paths([plt_path])

    mapping = controller.plt_mappings[str(plt_path)]
    # 사용자가 Column Mapping에서 직접 고쳤다고 가정
    mapping.polarity = Polarity.PMOS
    mapping.device_id = "PMOS_custom"
    mapping.width_um = 12.0
    mapping.length_um = 3.0
    mapping.length_um_source = "user"
    mapping.split_attributes = {"Temperature": "950"}

    project_path = tmp_path / "myproject.tcadproj"
    save_project(controller, project_path)

    fresh = ProjectController()
    result = load_project(fresh, project_path)

    assert result.missing_files == []
    restored = fresh.plt_mappings[str(plt_path)]
    assert restored.polarity == Polarity.PMOS
    assert restored.device_id == "PMOS_custom"
    assert restored.width_um == 12.0
    assert restored.length_um == 3.0
    assert restored.length_um_source == "user"
    assert restored.split_attributes == {"Temperature": "950"}


def test_load_project_rebuilds_curves_and_extraction(tmp_path):
    _ensure_qapp()
    plt_path = tmp_path / "IdVg_n668_des.plt"
    plt_path.write_text(DFISE_SAMPLE, encoding="utf-8")

    controller = ProjectController()
    controller.import_paths([plt_path])
    project_path = tmp_path / "myproject.tcadproj"
    save_project(controller, project_path)

    fresh = ProjectController()
    load_project(fresh, project_path)

    assert len(fresh.curves) > 0
    assert len(fresh.extracted_params) > 0


def test_load_project_reports_missing_files_without_crashing(tmp_path):
    _ensure_qapp()
    plt_path = tmp_path / "IdVg_n668_des.plt"
    plt_path.write_text(DFISE_SAMPLE, encoding="utf-8")

    controller = ProjectController()
    controller.import_paths([plt_path])
    project_path = tmp_path / "myproject.tcadproj"
    save_project(controller, project_path)

    plt_path.unlink()  # 원본 파일이 없어진 상황을 흉내

    fresh = ProjectController()
    result = load_project(fresh, project_path)

    assert str(plt_path) in result.missing_files
    assert fresh.plt_mappings == {}


def test_load_project_clears_previous_state_first(tmp_path):
    _ensure_qapp()
    old_plt = tmp_path / "IdVg_n1_des.plt"
    old_plt.write_text(DFISE_SAMPLE, encoding="utf-8")
    new_plt = tmp_path / "IdVg_n2_des.plt"
    new_plt.write_text(DFISE_SAMPLE, encoding="utf-8")

    project_controller = ProjectController()
    project_controller.import_paths([new_plt])
    project_path = tmp_path / "myproject.tcadproj"
    save_project(project_controller, project_path)

    controller = ProjectController()
    controller.import_paths([old_plt])  # 프로젝트 파일과 무관한 기존 상태
    load_project(controller, project_path)

    assert str(old_plt) not in controller.plt_mappings
    assert str(new_plt) in controller.plt_mappings


def test_save_and_load_roundtrip_restores_extraction_config_tuple_fields(tmp_path):
    _ensure_qapp()
    plt_path = tmp_path / "IdVg_n668_des.plt"
    plt_path.write_text(DFISE_SAMPLE, encoding="utf-8")

    controller = ProjectController()
    controller.import_paths([plt_path])
    controller.extraction_config = ExtractionConfig(
        cc_current_ref=5e-8,
        ss_vg_range=(0.1, 0.25),
        mobility_cox_F_cm2=3.45e-8,
    )
    project_path = tmp_path / "myproject.tcadproj"
    save_project(controller, project_path)

    fresh = ProjectController()
    load_project(fresh, project_path)

    assert fresh.extraction_config.cc_current_ref == 5e-8
    assert fresh.extraction_config.ss_vg_range == (0.1, 0.25)  # 리스트가 아니라 튜플이어야 함
    assert isinstance(fresh.extraction_config.ss_vg_range, tuple)
    assert fresh.extraction_config.mobility_cox_F_cm2 == 3.45e-8


def test_save_project_preserves_curve_type(tmp_path):
    _ensure_qapp()
    plt_path = tmp_path / "IdVg_n668_des.plt"
    plt_path.write_text(DFISE_SAMPLE, encoding="utf-8")

    controller = ProjectController()
    controller.import_paths([plt_path])
    controller.plt_mappings[str(plt_path)].curve_type = CurveType.ID_VD

    project_path = tmp_path / "myproject.tcadproj"
    save_project(controller, project_path)

    fresh = ProjectController()
    load_project(fresh, project_path)

    assert fresh.plt_mappings[str(plt_path)].curve_type == CurveType.ID_VD
