"""프로젝트 저장/불러오기.

지금까지 임포트한 파일 구성 + Column Mapping에서 손으로 고친 값들(Vg/Id/Vd 컬럼, 극성,
W/L, split 조건) + Extraction Config 설정을 파일 하나(JSON)에 저장해뒀다가, 나중에 다시
열어서 곧바로 이어서 작업할 수 있게 한다.

curve의 원본 숫자 배열(Vg/Id 등)은 저장하지 않는다 — 대신 원본 파일 "경로"만 저장해두고,
불러올 때 그 경로에서 다시 파싱한다:
  - 프로젝트 파일 용량이 작다(수백 KB짜리 .plt 수십 개를 통째로 복사해 넣는 게 아니라
    경로 문자열 몇 개만 저장하므로).
  - 파서가 나중에 개선되더라도 불러올 때 항상 최신 파싱 로직을 다시 타므로, 저장 당시의
    (버그가 있었을 수도 있는) 파싱 결과가 그대로 굳어 남는 일이 없다.
  - 단점은 원본 파일들이 저장 당시와 "같은 경로"에 그대로 있어야 완전하게 복원된다는
    것 — 파일이 없어졌거나 옮겨졌으면 그 파일만 건너뛰고(참고 메시지로 알려줌) 나머지는
    정상적으로 복원한다.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from ..extraction import ExtractionConfig
from ..models import CurveType, Polarity

if TYPE_CHECKING:
    from .controllers.project_controller import PltFileMapping, ProjectController, TableMapping

PROJECT_FILE_VERSION = 1

# ExtractionConfig의 필드 중 (Optional[Tuple[float, float]]) 타입이라, JSON에 저장하면
# 배열([lo, hi])이 되고 불러올 때 다시 튜플로 되돌려야 하는 것들.
_EXTRACTION_CONFIG_TUPLE_FIELDS = (
    "le_fit_vg_range",
    "ss_vg_range",
    "ron_vd_range",
    "gds_vd_range",
    "dibl_vd_pair",
    "curve_vg_analysis_range",
    "mobility_fit_vg_range",
)


def _plt_mapping_to_dict(m: "PltFileMapping") -> Dict[str, Any]:
    return {
        "path": str(m.path),
        "curve_type": m.curve_type.value,
        "vg_col": m.vg_col,
        "id_col": m.id_col,
        "vd_col": m.vd_col,
        "polarity": m.polarity.value,
        "device_id": m.device_id,
        "width_um": m.width_um,
        "length_um": m.length_um,
        "length_um_source": m.length_um_source,
        "split_attributes": dict(m.split_attributes),
        "node_id": m.node_id,
    }


def _table_mapping_to_dict(m: "TableMapping") -> Dict[str, Any]:
    return {
        "path": str(m.path),
        "split_col": m.split_col,
        "device_col": m.device_col,
        "default_device_id": m.default_device_id,
        "polarity": m.polarity.value,
        "param_cols": list(m.param_cols),
    }


def _extraction_config_to_dict(config: ExtractionConfig) -> Dict[str, Any]:
    return asdict(config)


def _extraction_config_from_dict(data: Dict[str, Any]) -> ExtractionConfig:
    kwargs = dict(data)
    for name in _EXTRACTION_CONFIG_TUPLE_FIELDS:
        value = kwargs.get(name)
        if value is not None:
            kwargs[name] = tuple(value)
    return ExtractionConfig(**kwargs)


def save_project(controller: "ProjectController", path: Path) -> None:
    """현재 상태(임포트 구성 + 매핑 + 추출 설정)를 JSON 파일로 저장."""
    data = {
        "version": PROJECT_FILE_VERSION,
        "last_import_dir": str(controller.last_import_dir) if controller.last_import_dir else None,
        "plt_mappings": [_plt_mapping_to_dict(m) for m in controller.plt_mappings.values()],
        "table_mappings": [_table_mapping_to_dict(m) for m in controller.table_mappings.values()],
        "extraction_config": _extraction_config_to_dict(controller.extraction_config),
    }
    path = Path(path)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class ProjectLoadResult:
    def __init__(self) -> None:
        self.missing_files: List[str] = []
        self.restored_plt_count: int = 0
        self.restored_table_count: int = 0

    @property
    def ok(self) -> bool:
        return not self.missing_files


def load_project(controller: "ProjectController", path: Path) -> ProjectLoadResult:
    """저장된 프로젝트 파일을 읽어 controller 상태를 복원한다.

    기존에 임포트돼 있던 것들은 먼저 전부 지우고(clear_all_imports) 새로 시작한다 — "이어서
    작업"이 아니라 "이 프로젝트를 연다"는 의미이므로, 현재 상태와 뒤섞이지 않게 한다.
    """
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    result = ProjectLoadResult()

    controller.clear_all_imports()

    plt_entries = data.get("plt_mappings", [])
    table_entries = data.get("table_mappings", [])
    all_paths = [Path(e["path"]) for e in plt_entries] + [Path(e["path"]) for e in table_entries]

    existing_paths = [p for p in all_paths if p.exists()]
    result.missing_files = [str(p) for p in all_paths if not p.exists()]
    if existing_paths:
        controller.import_paths(existing_paths)

    # 자동 매핑/인식 결과 위에, 저장해뒀던(사용자가 손으로 고쳤을 수 있는) 값을 덮어써서
    # 저장 당시의 최종 상태를 그대로 복원한다.
    for entry in plt_entries:
        key = entry["path"]
        mapping = controller.plt_mappings.get(key)
        if mapping is None:
            continue  # 파일이 없어져서 애초에 임포트가 안 된 경우
        mapping.curve_type = CurveType(entry["curve_type"])
        mapping.vg_col = entry["vg_col"]
        mapping.id_col = entry["id_col"]
        mapping.vd_col = entry["vd_col"]
        mapping.polarity = Polarity(entry["polarity"])
        mapping.device_id = entry["device_id"]
        mapping.width_um = entry["width_um"]
        mapping.length_um = entry["length_um"]
        mapping.length_um_source = entry.get("length_um_source", "user")
        mapping.split_attributes = dict(entry["split_attributes"])
        mapping.node_id = entry["node_id"]
        result.restored_plt_count += 1

    for entry in table_entries:
        key = entry["path"]
        mapping = controller.table_mappings.get(key)
        if mapping is None:
            continue
        mapping.split_col = entry["split_col"]
        mapping.device_col = entry["device_col"]
        mapping.default_device_id = entry["default_device_id"]
        mapping.polarity = Polarity(entry["polarity"])
        mapping.param_cols = list(entry["param_cols"])
        result.restored_table_count += 1

    if "extraction_config" in data:
        controller.extraction_config = _extraction_config_from_dict(data["extraction_config"])

    controller.importChanged.emit()

    # 매핑이 다 복원됐으니 곧바로 curve/추출 결과까지 재현해서, 정말로 "이어서 작업"할 수
    # 있는 상태로 만든다.
    controller.build_curves()
    controller.run_extraction()

    return result
