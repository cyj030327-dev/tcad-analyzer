"""애플리케이션 상태(임포트된 파일, 매핑, curve, 추출 결과)를 보관하고
각 페이지 위젯에 시그널로 변경을 알리는 중앙 컨트롤러.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PySide6.QtCore import QObject, Signal

from ..app_config import load_last_import_dir, save_last_import_dir
from ...analysis import to_dataframe
from ...extraction import ExtractionConfig, extract_for_collection
from ...models import Curve, CurveCollection, CurveType, DeviceMeta, ExtractedParameter, Polarity, SplitCondition
from ...parsers import (
    GtreeProject,
    SimulationSummary,
    SprocessSummary,
    TecplotFile,
    check_sweep,
    extract_node_id_from_filename,
    load_parameter_table,
    load_plt_file,
    looks_like_sprocess,
    parse_gtree,
    parse_sdevice_cmd,
    parse_sprocess_cmd,
    suggest_column_roles,
)

PLT_SUFFIXES = {".plt"}
TABLE_SUFFIXES = {".csv", ".xlsx", ".xls"}
CMD_SUFFIXES = {".cmd"}


@dataclass
class ImportStatus:
    path: Path
    kind: str  # "plt" | "table" | "gtree" | "cmd"
    ok: bool
    message: str = ""


@dataclass
class PltFileMapping:
    path: Path
    curve_type: CurveType = CurveType.ID_VG
    vg_col: Optional[str] = None
    id_col: Optional[str] = None
    vd_col: Optional[str] = None
    polarity: Polarity = Polarity.NMOS
    device_id: str = "device"
    width_um: Optional[float] = None
    length_um: Optional[float] = None
    # length_um을 채운 출처. 자동 채움 소스끼리는 우선순위가 있다(gtree의 split별 값이
    # sprocess의 "프로젝트 전체 고정값"보다 항상 더 정확함) — 그래서 나중에 더 우선순위 높은
    # 소스가 나타나면 자동으로 갱신할 수 있어야 하지만, 사용자가 Column Mapping에서 직접
    # 입력한 값("user")은 무엇이 나중에 오든 절대 덮어쓰지 않는다.
    length_um_source: str = "none"  # "none" | "sprocess" | "gtree" | "user"
    split_attributes: Dict[str, str] = field(default_factory=dict)
    node_id: Optional[str] = None


@dataclass
class TableMapping:
    path: Path
    split_col: Optional[str] = None
    device_col: Optional[str] = None
    default_device_id: str = "imported"
    polarity: Polarity = Polarity.NMOS
    param_cols: List[str] = field(default_factory=list)


def _guess_curve_type(tf: TecplotFile, vg_col: Optional[str], vd_col: Optional[str]) -> CurveType:
    """Vg/Vd 중 실제로 값이 넓게 변하는(=스윕된) 쪽을 보고 Id-Vg/Id-Vd를 추정한다.

    모든 TCAD 시뮬레이션이 Id-Vg 스윕만 내놓는 건 아니다 — 순수 Id-Vd 특성만 뽑는 실행도
    있고, 그런 파일은 zone이 1개뿐인 경우가 많다. "zone이 여러 개면 Id-Vd"라는 예전 방식은
    이런 단일 zone Id-Vd 파일을 Id-Vg로 잘못 분류해, Vth/SS 추출은 실패하고 정작 계산 가능한
    Ron/gds는 시도조차 안 되는 문제가 있었다. 대신 실제 데이터에서 어느 축의 값이 더 넓게
    퍼져 있는지(스윕된 축일수록 값이 넓게 변함)를 직접 비교한다 — Vg family curve(zone
    여러 개, zone마다 Vd가 스윕)여도 zone 하나의 Vd 변화폭이 여전히 Vg보다 크므로 그대로
    맞게 판별된다.
    """

    def _span(col: Optional[str]) -> float:
        if col is None or not tf.zones:
            return 0.0
        try:
            values = tf.zones[0].column(col)
        except (KeyError, ValueError):
            return 0.0
        if values.size == 0:
            return 0.0
        return float(np.max(values) - np.min(values))

    vg_span = _span(vg_col)
    vd_span = _span(vd_col)
    if vd_span > vg_span and vd_span > 0:
        return CurveType.ID_VD
    return CurveType.ID_VG


# gtree.dat에서 채널 길이 자체가 split마다 다르게 스윕되는 경우(예: 위 프로젝트의 "Lg"처럼)에
# 대비한 이름 목록. 이런 프로젝트는 sprocess 파일 하나에서 읽은 "프로젝트 전체 고정 L"을 모든
# split에 똑같이 적용하면 틀린다 — split 자신의 gtree 값을 최우선으로 써야 한다.
_LENGTH_ATTR_NAMES = {"lg", "lch", "l", "length", "channellength", "gatelength"}


def _length_from_split_attributes(attrs: Dict[str, str]) -> Optional[float]:
    """gtree.dat의 split attribute 중 채널 길이로 보이는 게 있으면 그 값을 그대로 쓴다.
    노드별 실제 값이라 sprocess에서 읽은 프로젝트 전체 고정값보다 항상 우선한다."""
    for name, raw in attrs.items():
        if name.lower() in _LENGTH_ATTR_NAMES:
            try:
                return float(raw)
            except (TypeError, ValueError):
                continue
    return None


def _guess_polarity(tf: TecplotFile, id_col: Optional[str]) -> Optional[Polarity]:
    """전류 컬럼 값의 부호로 극성을 추정하는 가벼운 휴리스틱(확정 아님, 사용자가 확인/수정 가능).

    Sentaurus 출력 관례상 NMOS의 드레인 전류는 대체로 양수, PMOS는 대체로 음수로 기록되므로
    첫 ZONE의 중앙값 부호를 본다. 컬럼을 못 찾거나 데이터가 없으면 None(추정 불가)을 반환하고,
    이 경우 호출부는 기존 기본값(NMOS)을 그대로 둔다.
    """
    if id_col is None or not tf.zones:
        return None
    try:
        values = tf.zones[0].column(id_col)
    except (KeyError, ValueError):
        return None
    if values.size == 0:
        return None
    return Polarity.PMOS if float(np.median(values)) < 0 else Polarity.NMOS


def _polarity_cross_check_note(
    guessed_polarity: Optional[Polarity], sprocess: Optional[SprocessSummary]
) -> Optional[str]:
    """데이터(전류 부호) 기반 극성 추정과, sprocess에서 감지한 도펀트 종류를 교차 확인한다.

    둘 중 하나가 항상 정답이라고 볼 수 없어(전류 부호 추정도 휴리스틱, sprocess 도펀트 감지도
    정규식 기반 참고용) "참고 문구"로만 취급한다. sprocess가 없거나, 도펀트를 하나도 못
    찾았거나, n형/p형이 섞여 나오면(예: 같은 스크립트에 CMOS처럼 양쪽 다 있는 경우) 판단을
    보류하고 None을 반환한다.
    """
    if sprocess is None or not sprocess.dopant_species or guessed_polarity is None:
        return None
    hint = sprocess.dopant_polarity_hint
    if hint not in ("n", "p"):
        return None
    expected = Polarity.NMOS if hint == "n" else Polarity.PMOS
    species_txt = ", ".join(sprocess.dopant_species)
    if expected == guessed_polarity:
        return f"✓ sprocess 도핑({species_txt})과 극성 일치"
    return (
        f"⚠ 극성 불일치 가능성: 전류 부호로는 {guessed_polarity.value.upper()}인데 "
        f"sprocess 도핑({species_txt})은 {expected.value.upper()}로 보입니다 — 확인해보세요"
    )


class ProjectController(QObject):
    importChanged = Signal()
    curvesBuilt = Signal()
    extractionCompleted = Signal()

    def __init__(self):
        super().__init__()
        self.imported_plt: Dict[str, TecplotFile] = {}
        self.imported_tables: Dict[str, "object"] = {}  # path -> DataFrame
        self.gtree_project: Optional[GtreeProject] = None
        self.cmd_summaries: Dict[str, SimulationSummary] = {}
        # sprocess는 gtree처럼 노드별로 갈리지 않는 경우가 많다(Tox/L 등은 보통 스윕 대상이
        # 아니라 프로젝트 전체에 고정된 값) — 그래서 여러 개를 노드별로 관리하지 않고,
        # 가장 최근에 읽은 sprocess 요약 하나를 "이 프로젝트의 지오메트리 기본값"으로 써서
        # 모든 split에 공통 적용한다. 노드별로 지오메트리가 다른 프로젝트라면 이 단순화가
        # 안 맞을 수 있다.
        self.sprocess_summary: Optional[SprocessSummary] = None
        self.import_status: List[ImportStatus] = []
        self.last_import_dir: Optional[Path] = None

        self.plt_mappings: Dict[str, PltFileMapping] = {}
        self.table_mappings: Dict[str, TableMapping] = {}

        self.curves = CurveCollection()
        self.imported_table_params: List[ExtractedParameter] = []

        self.extraction_config = ExtractionConfig()
        self.extracted_params: List[ExtractedParameter] = []
        self.extraction_failures: List[Tuple[str, str]] = []

    # ---------------------------------------------------------------- import
    def import_paths(self, paths: List[Path]) -> None:
        for path in paths:
            path = Path(path)
            suffix = path.suffix.lower()
            key = str(path)
            try:
                if path.name.lower() == "gtree.dat":
                    self.gtree_project = parse_gtree(path)
                    self.import_status.append(ImportStatus(path, "gtree", True, f"{len(self.gtree_project.nodes)}개 노드"))
                elif suffix in PLT_SUFFIXES:
                    tf = load_plt_file(path)  # Tecplot / DF-ISE 포맷 자동 감지
                    self.imported_plt[key] = tf
                    node_id = extract_node_id_from_filename(path.name)
                    mapping = PltFileMapping(path=path, node_id=node_id)
                    if node_id and self.gtree_project:
                        attrs = self.gtree_project.split_attributes_for_node(node_id)
                        if attrs:
                            mapping.split_attributes = dict(attrs)
                            length_from_gtree = _length_from_split_attributes(attrs)
                            if length_from_gtree is not None:
                                mapping.length_um = length_from_gtree
                                mapping.length_um_source = "gtree"
                    roles = suggest_column_roles(tf.variables)
                    mapping.vg_col = roles.get("Vg")
                    mapping.id_col = roles.get("Id")
                    mapping.vd_col = roles.get("Vd")
                    mapping.curve_type = _guess_curve_type(tf, mapping.vg_col, mapping.vd_col)
                    guessed_polarity = _guess_polarity(tf, mapping.id_col)
                    if guessed_polarity is not None:
                        mapping.polarity = guessed_polarity
                        # 사용자가 Column Mapping에서 고치지 않아도 NMOS/PMOS가 같은
                        # device_id("device")로 뭉쳐 비교/랭킹 단계에서 섞이는 것을 방지
                        mapping.device_id = guessed_polarity.value.upper()
                    # 2D 구조는 지오메트리에 폭(W)이 아예 없어, Sentaurus 2D 시뮬레이션 관례상
                    # 단위폭(1um)으로 취급한다 — 이걸 자동으로 채워주지 않으면 이동도(μFE)
                    # 계산에 필요한 W가 계속 비어 있어 Mobility_sat이 지표 목록에 아예 안
                    # 나타나는 문제가 있었다.
                    if self.sprocess_summary and self.sprocess_summary.is_2d_structure and mapping.width_um is None:
                        mapping.width_um = 1.0
                    self.plt_mappings[key] = mapping

                    status_msg = f"{len(tf.zones)}개 ZONE"
                    status_msg += " | Id-Vd로 인식" if mapping.curve_type == CurveType.ID_VD else " | Id-Vg로 인식"
                    # 실제로 스윕되는 축(Id-Vg면 Vg, Id-Vd면 Vd)이 스윕처럼 안 보이면 경고.
                    # curve_type과 무관하게 항상 Vg만 검사하면, 정상적인 Id-Vd 파일(Vg는
                    # 고정, Vd가 스윕)에서 "Vg가 안 변한다"는 게 당연한데도 매번 잘못된
                    # 경고가 뜨는 문제가 있었다.
                    swept_col = mapping.vd_col if mapping.curve_type == CurveType.ID_VD else mapping.vg_col
                    if swept_col is None:
                        status_msg += " | ⚠ Vg/Vd 컬럼을 자동으로 찾지 못했습니다 — Column Mapping에서 직접 지정하세요"
                    else:
                        sweep_ok, sweep_reason = check_sweep(tf.zones[0].column(swept_col))
                        if not sweep_ok:
                            status_msg += f" | ⚠ 스윕 아닌 것 같음 ({sweep_reason}) — transient 결과일 수 있으니 확인하세요"
                    polarity_note = _polarity_cross_check_note(guessed_polarity, self.sprocess_summary)
                    if polarity_note:
                        status_msg += f" | {polarity_note}"
                    self.import_status.append(ImportStatus(path, "plt", True, status_msg))
                elif suffix in TABLE_SUFFIXES:
                    df = load_parameter_table(path)
                    self.imported_tables[key] = df
                    self.table_mappings[key] = TableMapping(path=path)
                    self.import_status.append(ImportStatus(path, "table", True, f"{len(df)}행"))
                elif suffix in CMD_SUFFIXES:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                    if looks_like_sprocess(text):
                        # sprocess(지오메트리/공정) 스크립트 — sdevice .cmd(전극/전압스윕)와
                        # 같은 확장자를 쓰지만 문법이 달라 내용으로 구분한다
                        sp_summary = parse_sprocess_cmd(path)
                        self.sprocess_summary = sp_summary
                        parts = []
                        if sp_summary.gate_oxide_thickness_um is not None:
                            eps_txt = (
                                f", εr≈{sp_summary.gate_oxide_rel_permittivity}"
                                if sp_summary.gate_oxide_rel_permittivity is not None
                                else " (εr 모름 — 이동도 설정에서 직접 입력하세요)"
                            )
                            parts.append(
                                f"산화막 {sp_summary.gate_dielectric_material} "
                                f"{sp_summary.gate_oxide_thickness_um * 1000:.0f}nm{eps_txt}"
                            )
                        elif sp_summary.oxide_grown_thermally:
                            tag_txt = f"'{', '.join(sp_summary.doe_log_tags)}' 로 " if sp_summary.doe_log_tags else ""
                            parts.append(
                                "⚠ 게이트 산화막이 열산화(diffuse ... O2)로 자란 것 같아 두께를 스크립트에서 "
                                f"못 찾았습니다 — 로그 파일에 {tag_txt}남아있을 수 있으니 있으면 알려주세요"
                            )
                        if sp_summary.channel_length_um is not None:
                            parts.append(f"L={sp_summary.channel_length_um}um (모든 .plt에 자동 반영)")
                        if sp_summary.is_2d_structure:
                            parts.append("2D 구조 — W(폭) 정보가 지오메트리에 없어 단위폭 W=1um을 모든 .plt에 자동 적용")
                        self.import_status.append(
                            ImportStatus(path, "sprocess", True, ", ".join(parts) or "인식된 정보 없음")
                        )
                    else:
                        summary = parse_sdevice_cmd(path)
                        # 파일명이 노드 번호 관례(n<N>_...)를 안 따르는 경우, 파일 내용 안의
                        # 자기참조 경로(예: Current = "n668_des.plt")에서 찾은 노드 번호로 대체
                        node_id = extract_node_id_from_filename(path.name) or summary.node_id_hint
                        if node_id:
                            self.cmd_summaries[node_id] = summary
                        self.import_status.append(ImportStatus(path, "cmd", True, "참고 정보 추출"))
                else:
                    self.import_status.append(ImportStatus(path, "unknown", False, "지원하지 않는 확장자"))
            except Exception as exc:  # 파일 하나의 실패가 나머지 임포트를 막지 않도록 격리
                self.import_status.append(ImportStatus(path, suffix.lstrip("."), False, str(exc)))

        # gtree가 나중에 로드된 경우, 이미 매핑된 .plt들에 소급 적용
        if self.gtree_project:
            for mapping in self.plt_mappings.values():
                if mapping.node_id and not mapping.split_attributes:
                    attrs = self.gtree_project.split_attributes_for_node(mapping.node_id)
                    if attrs:
                        mapping.split_attributes = dict(attrs)
                        # gtree의 split별 값은 sprocess의 "전체 고정값"보다 항상 우선하므로,
                        # sprocess가 먼저 채워놨더라도(source="sprocess") 덮어쓴다. 사용자가
                        # 직접 입력한 값(source="user")만은 절대 건드리지 않는다.
                        if mapping.length_um_source in ("none", "sprocess"):
                            length_from_gtree = _length_from_split_attributes(attrs)
                            if length_from_gtree is not None:
                                mapping.length_um = length_from_gtree
                                mapping.length_um_source = "gtree"

        # sprocess가 나중에 로드된 경우도 마찬가지로, 아직 길이를 안 채운 .plt에 소급 적용.
        # sprocess는 가장 낮은 우선순위라, 아직 아무것도 안 채워진 split에만("none") 적용한다
        # — gtree의 split별 값이나 사용자가 직접 입력한 값은 덮어쓰지 않는다.
        if self.sprocess_summary and self.sprocess_summary.channel_length_um is not None:
            for mapping in self.plt_mappings.values():
                if mapping.length_um_source == "none":
                    mapping.length_um = self.sprocess_summary.channel_length_um
                    mapping.length_um_source = "sprocess"

        # 폭(W)도 마찬가지로 소급 적용: 2D 구조로 확인되면 아직 안 채워진 .plt에 단위폭(1um)을 채운다.
        if self.sprocess_summary and self.sprocess_summary.is_2d_structure:
            for mapping in self.plt_mappings.values():
                if mapping.width_um is None:
                    mapping.width_um = 1.0

        # 극성 교차확인 문구도 마찬가지로 소급 적용. 이미 문구가 붙어있으면(전에 sprocess가
        # 있었을 때 이미 추가됨) 중복으로 덧붙이지 않는다.
        if self.sprocess_summary is not None:
            for status in self.import_status:
                if status.kind != "plt":
                    continue
                if "극성 일치" in status.message or "극성 불일치" in status.message:
                    continue
                mapping = self.plt_mappings.get(str(status.path))
                if mapping is None:
                    continue
                note = _polarity_cross_check_note(mapping.polarity, self.sprocess_summary)
                if note:
                    status.message += f" | {note}"

        self.importChanged.emit()

    def import_folder(self, folder: Path) -> None:
        """folder와 그 아래 모든 하위 폴더(예: SWB 프로젝트의 노드별 폴더)를 재귀적으로 뒤져
        .plt/.cmd/gtree.dat/테이블 파일을 한 번에 찾아 임포트한다."""
        folder = Path(folder)
        self.last_import_dir = folder
        save_last_import_dir(folder)
        candidates = sorted(
            p
            for p in folder.rglob("*")
            if p.is_file()
            and (p.suffix.lower() in PLT_SUFFIXES | TABLE_SUFFIXES | CMD_SUFFIXES or p.name.lower() == "gtree.dat")
        )
        # gtree.dat를 먼저 읽어야 .plt 임포트 시점에 split이 자동으로 채워진다
        candidates.sort(key=lambda p: 0 if p.name.lower() == "gtree.dat" else 1)
        self.import_paths(candidates)

    def refresh(self) -> None:
        if self.last_import_dir is not None:
            self.import_folder(self.last_import_dir)

    def remove_paths(self, paths: List[Path]) -> None:
        """Import 목록에서 지정한 파일들을 빼고, 그 파일에서 나온 매핑/참고 정보도 함께 정리한다.

        이미 만들어진 curve/추출 결과는 여기서 자동으로 다시 계산하지 않는다(다음 단계에서
        "Curve 만들기"/추출을 다시 실행하면 남아있는 파일만 반영됨) — 파일 목록 편집과 추출
        실행을 분리해두는 편이 예측하기 쉽다.
        """
        paths = [Path(p) for p in paths]
        target_keys = {str(p) for p in paths}
        target_names = {p.name.lower() for p in paths}
        for key in target_keys:
            self.imported_plt.pop(key, None)
            self.plt_mappings.pop(key, None)
            self.imported_tables.pop(key, None)
            self.table_mappings.pop(key, None)
        if "gtree.dat" in target_names:
            self.gtree_project = None
        for node_id, summary in list(self.cmd_summaries.items()):
            if summary.source_path is not None and str(summary.source_path) in target_keys:
                del self.cmd_summaries[node_id]
        self.import_status = [s for s in self.import_status if str(s.path) not in target_keys]
        self.importChanged.emit()

    def clear_all_imports(self) -> None:
        """임포트된 모든 파일과 그로부터 만들어진 매핑/참고 정보를 초기화한다."""
        self.imported_plt.clear()
        self.imported_tables.clear()
        self.gtree_project = None
        self.cmd_summaries.clear()
        self.import_status.clear()
        self.plt_mappings.clear()
        self.table_mappings.clear()
        self.importChanged.emit()

    def restore_last_session_folder(self) -> None:
        """프로그램을 다시 켰을 때, 지난번에 쓰던 폴더가 남아있으면 자동으로 다시 불러온다."""
        remembered = load_last_import_dir()
        if remembered is not None:
            self.import_folder(remembered)

    # ------------------------------------------------------------- mapping
    def build_curves(self) -> None:
        curves = CurveCollection()
        for key, mapping in self.plt_mappings.items():
            tf = self.imported_plt[key]
            if not (mapping.vg_col and mapping.id_col):
                continue
            device = DeviceMeta(
                device_id=mapping.device_id,
                polarity=mapping.polarity,
                width_um=mapping.width_um,
                length_um=mapping.length_um,
            )
            # 노드 번호가 있으면 split 라벨 맨 앞에 붙여서(예: "n668, Nd=1e15, ...") 어느
            # 파일/노드에서 나온 값인지 Comparison 화면에서 한눈에 구분할 수 있게 한다.
            # gtree.dat가 없어 split 조건이 비어있는 경우엔 이게 유일한 구분 수단이 된다.
            split_name = f"n{mapping.node_id}" if mapping.node_id else "default"
            split = SplitCondition(split_name=split_name, attributes=dict(mapping.split_attributes))
            for zi, zone in enumerate(tf.zones):
                try:
                    vg = zone.column(mapping.vg_col)
                    id_ = zone.column(mapping.id_col)
                except (KeyError, ValueError):
                    continue
                vd_val = None
                vd_arr = None
                if mapping.vd_col:
                    try:
                        vd_col_data = zone.column(mapping.vd_col)
                    except (KeyError, ValueError):
                        vd_col_data = None
                    if vd_col_data is not None:
                        if mapping.curve_type == CurveType.ID_VD:
                            vd_arr = vd_col_data
                        else:
                            vd_val = float(vd_col_data[0])
                curve_id = f"{Path(key).stem}_z{zi}"
                curves.add(
                    Curve(
                        curve_id=curve_id,
                        curve_type=mapping.curve_type,
                        device=device,
                        split=split,
                        vg=vg,
                        id_=id_,
                        vd=vd_val,
                        vd_array=vd_arr,
                        source_file=mapping.path,
                        raw_variables=tf.variables,
                        node_id=mapping.node_id,
                    )
                )
        self.curves = curves

        # 테이블(이미 추출된 파라미터)도 함께 정규화
        table_params: List[ExtractedParameter] = []
        for key, tmapping in self.table_mappings.items():
            df = self.imported_tables[key]
            if not tmapping.param_cols:
                continue
            for _, row in df.iterrows():
                split_label = str(row[tmapping.split_col]) if tmapping.split_col else "default"
                device_id = str(row[tmapping.device_col]) if tmapping.device_col else tmapping.default_device_id
                device = DeviceMeta(device_id=device_id, polarity=tmapping.polarity)
                split = SplitCondition(split_name=split_label)
                for col in tmapping.param_cols:
                    value = row[col]
                    try:
                        value = float(value)
                    except (TypeError, ValueError):
                        continue
                    table_params.append(
                        ExtractedParameter(
                            curve_id=None,
                            device=device,
                            split=split,
                            param_name=col,
                            value=value,
                            unit="",
                            method="imported",
                        )
                    )
        self.imported_table_params = table_params
        self.curvesBuilt.emit()

    # ---------------------------------------------------------- extraction
    def run_extraction(self) -> None:
        params, failures = extract_for_collection(self.curves, self.extraction_config)
        self.extracted_params = params
        self.extraction_failures = failures
        self.extractionCompleted.emit()

    @property
    def all_params(self) -> List[ExtractedParameter]:
        return self.extracted_params + self.imported_table_params

    def params_dataframe(self):
        return to_dataframe(self.all_params)

    def cmd_summary_for_curve(self, curve: Curve) -> Optional[SimulationSummary]:
        if curve.node_id is None:
            return None
        return self.cmd_summaries.get(curve.node_id)
