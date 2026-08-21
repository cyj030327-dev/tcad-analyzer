"""3) Extraction Config 페이지: Vth 방식, 기준전류, SS/Ion-Ioff/Ron-gds/DIBL 설정, 추출 실행."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ..controllers.project_controller import ProjectController


class ExtractionConfigPage(QWidget):
    def __init__(self, controller: ProjectController, parent=None):
        super().__init__(parent)
        self.controller = controller

        layout = QVBoxLayout(self)

        vth_box = QGroupBox("Vth 추출 방식")
        vth_layout = QVBoxLayout(vth_box)
        self.radio_cc = QRadioButton("Constant Current (CC)")
        self.radio_le = QRadioButton("Linear Extrapolation (SD)")
        self.radio_cc.setChecked(True)
        vth_layout.addWidget(self.radio_cc)

        cc_form = QFormLayout()
        self.cc_current_edit = QLineEdit("1e-7")
        self.cc_normalize_check = QCheckBox("W/L로 정규화")
        self.cc_normalize_check.setChecked(True)
        cc_form.addRow("기준전류 I_spec (A)", self.cc_current_edit)
        cc_form.addRow(self.cc_normalize_check)
        vth_layout.addLayout(cc_form)

        vth_layout.addWidget(self.radio_le)
        le_form = QFormLayout()
        self.le_vd_half_check = QCheckBox("Vd/2 보정 적용")
        self.le_vd_half_check.setChecked(True)
        le_form.addRow(self.le_vd_half_check)
        vth_layout.addLayout(le_form)
        layout.addWidget(vth_box)

        ss_box = QGroupBox("SS (Subthreshold Swing)")
        ss_form = QFormLayout(ss_box)
        self.ss_range_edit = QLineEdit()
        self.ss_range_edit.setPlaceholderText("비워두면 자동 검출, 예: -0.2,0.1")
        ss_form.addRow("Vg 구간 (수동, 선택)", self.ss_range_edit)
        layout.addWidget(ss_box)

        ionioff_box = QGroupBox("Ion / Ioff")
        ionioff_form = QFormLayout(ionioff_box)
        self.ion_vg_edit = QLineEdit()
        self.ion_vg_edit.setPlaceholderText("비워두면 극성에 따라 자동(최대/최소 Vg)")
        self.ioff_vg_edit = QLineEdit()
        self.ioff_vg_edit.setPlaceholderText("비워두면 극성에 따라 자동")
        ionioff_form.addRow("Ion 기준 Vg", self.ion_vg_edit)
        ionioff_form.addRow("Ioff 기준 Vg", self.ioff_vg_edit)
        layout.addWidget(ionioff_box)

        idvd_box = QGroupBox("Id-Vd 지표 (Ron / gds) & DIBL")
        idvd_form = QFormLayout(idvd_box)
        self.ron_range_edit = QLineEdit()
        self.ron_range_edit.setPlaceholderText("비워두면 자동(저Vd 20%), 예: 0,0.1")
        self.gds_range_edit = QLineEdit()
        self.gds_range_edit.setPlaceholderText("비워두면 자동(고Vd 20%), 예: 1.0,1.2")
        self.dibl_pair_edit = QLineEdit()
        self.dibl_pair_edit.setPlaceholderText("비워두면 관측된 최소/최대 Vd 사용, 예: 0.05,1.0")
        idvd_form.addRow("Ron 피팅 Vd 구간", self.ron_range_edit)
        idvd_form.addRow("gds 피팅 Vd 구간", self.gds_range_edit)
        idvd_form.addRow("DIBL 비교 Vd 쌍", self.dibl_pair_edit)
        layout.addWidget(idvd_box)

        mobility_box = QGroupBox("필드효과 이동도 μFE (포화영역, 선택 — 아래를 채워야 계산됩니다)")
        mobility_layout = QVBoxLayout(mobility_box)
        mobility_hint = QLabel(
            "Cox(산화막 커패시턴스)는 원본 데이터에 없어 직접 입력해야 합니다. "
            "Cox를 알면 그 값을, 모르면 산화막 두께+비유전율을 입력하세요(Cox가 있으면 그게 우선 사용됩니다). "
            "W/L은 Column Mapping에서 입력한 값을 그대로 씁니다."
        )
        mobility_hint.setWordWrap(True)
        mobility_layout.addWidget(mobility_hint)
        self.sprocess_hint_label = QLabel("")
        self.sprocess_hint_label.setWordWrap(True)
        mobility_layout.addWidget(self.sprocess_hint_label)
        mobility_form = QFormLayout()
        self.mobility_cox_edit = QLineEdit()
        self.mobility_cox_edit.setPlaceholderText("예: 3.45e-8 (F/cm^2)")
        self.mobility_thickness_edit = QLineEdit()
        self.mobility_thickness_edit.setPlaceholderText("예: 100 (nm)")
        self.mobility_permittivity_edit = QLineEdit()
        self.mobility_permittivity_edit.setPlaceholderText("예: SiO2=3.9, Al2O3=9, HfO2=~20")
        self.mobility_fit_range_edit = QLineEdit()
        self.mobility_fit_range_edit.setPlaceholderText("비워두면 자동(최대 기울기 지점), 예: 5,15")
        mobility_form.addRow("Cox 직접 입력 (F/cm^2)", self.mobility_cox_edit)
        mobility_form.addRow("산화막 두께 (nm)", self.mobility_thickness_edit)
        mobility_form.addRow("산화막 비유전율", self.mobility_permittivity_edit)
        mobility_form.addRow("sqrt(Id) 피팅 Vg 구간", self.mobility_fit_range_edit)
        mobility_layout.addLayout(mobility_form)
        layout.addWidget(mobility_box)

        run_row = QHBoxLayout()
        self.btn_run = QPushButton("추출 실행")
        run_row.addWidget(self.btn_run)
        run_row.addStretch(1)
        layout.addLayout(run_row)

        self.result_label = QLabel("아직 추출하지 않았습니다.")
        layout.addWidget(self.result_label)
        self.mobility_result_label = QLabel("")
        self.mobility_result_label.setWordWrap(True)
        layout.addWidget(self.mobility_result_label)
        self.failure_list = QListWidget()
        layout.addWidget(self.failure_list)

        self.btn_run.clicked.connect(self._on_run)
        self.controller.importChanged.connect(self._on_import_changed)

    def _on_import_changed(self) -> None:
        """sprocess 파일이 인식되면 Cox 계산에 필요한 산화막 두께/비유전율을 미리 채워준다.
        이미 사용자가 값을 입력해둔 칸은 덮어쓰지 않는다(직접 입력이 항상 우선)."""
        sp = self.controller.sprocess_summary
        if sp is None:
            self.sprocess_hint_label.setText("")
            return

        hints = []
        if sp.gate_oxide_thickness_um is not None:
            if not self.mobility_thickness_edit.text().strip():
                self.mobility_thickness_edit.setText(f"{sp.gate_oxide_thickness_um * 1000:.4g}")
            if sp.gate_oxide_rel_permittivity is not None and not self.mobility_permittivity_edit.text().strip():
                self.mobility_permittivity_edit.setText(str(sp.gate_oxide_rel_permittivity))
            hints.append(
                f"sprocess에서 산화막({sp.gate_dielectric_material}) 두께/비유전율을 자동으로 채웠습니다 "
                "— 필요하면 직접 수정하세요."
            )
        elif sp.oxide_grown_thermally:
            tag_txt = f" ('{', '.join(sp.doe_log_tags)}' 태그)" if sp.doe_log_tags else ""
            hints.append(
                "게이트 산화막이 열산화로 자란 것 같아 두께를 자동으로 못 채웠습니다 — 아래 두께/Cox를 "
                f"직접 입력하세요(sprocess 로그 파일에 계산된 값이{tag_txt} 남아있을 수 있습니다)."
            )
        if sp.is_2d_structure:
            hints.append("2D 구조라 폭(W) 정보가 지오메트리에 없어, 단위폭 W=1um을 모든 .plt에 자동 적용했습니다.")
        self.sprocess_hint_label.setText(" ".join(hints))

    def _current_config_kwargs(self) -> dict:
        kwargs = {
            "vth_method": "constant_current" if self.radio_cc.isChecked() else "linear_extrapolation",
            "cc_current_ref": _to_float(self.cc_current_edit.text(), 1e-7),
            "cc_normalize_by_wl": self.cc_normalize_check.isChecked(),
            "le_apply_vd_half_correction": self.le_vd_half_check.isChecked(),
            "ss_vg_range": _to_range(self.ss_range_edit.text()),
            "ion_vg": _to_float_or_none(self.ion_vg_edit.text()),
            "ioff_vg": _to_float_or_none(self.ioff_vg_edit.text()),
            "ron_vd_range": _to_range(self.ron_range_edit.text()),
            "gds_vd_range": _to_range(self.gds_range_edit.text()),
            "dibl_vd_pair": _to_range(self.dibl_pair_edit.text()),
            "mobility_cox_F_cm2": _to_float_or_none(self.mobility_cox_edit.text()),
            "mobility_oxide_thickness_nm": _to_float_or_none(self.mobility_thickness_edit.text()),
            "mobility_oxide_rel_permittivity": _to_float_or_none(self.mobility_permittivity_edit.text()),
            "mobility_fit_vg_range": _to_range(self.mobility_fit_range_edit.text()),
        }
        return kwargs

    def _on_run(self) -> None:
        from ...extraction import ExtractionConfig

        self.controller.extraction_config = ExtractionConfig(**self._current_config_kwargs())
        if len(self.controller.curves) == 0:
            QMessageBox.warning(self, "curve 없음", "먼저 Import/Column Mapping 단계에서 curve를 생성하세요.")
            return
        self.controller.run_extraction()
        self._refresh_result()

    def _refresh_result(self) -> None:
        n_ok = len(self.controller.extracted_params)
        n_fail = len(self.controller.extraction_failures)
        self.result_label.setText(f"파라미터 {n_ok}개 추출 완료, 실패 {n_fail}건")
        self._refresh_mobility_result()
        self.failure_list.clear()
        for cid, msg in self.controller.extraction_failures:
            self.failure_list.addItem(f"{cid}: {msg}")

    def _refresh_mobility_result(self) -> None:
        """이동도는 Cox를 설정 안 하면 조용히 건너뛰도록 만들어놔서(에러 스팸 방지), 계산이
        안 됐을 때 "왜 안 보이지" 하고 헷갈리기 쉽다 — 여기서 바로 상태를 알려준다."""
        from ...extraction import resolve_cox_f_cm2

        cox = resolve_cox_f_cm2(self.controller.extraction_config)
        if cox is None:
            self.mobility_result_label.setText(
                "이동도(μFE)는 계산되지 않았습니다 — 위 '필드효과 이동도' 항목에 Cox나 "
                "산화막 두께+비유전율을 입력하고 다시 추출하면 계산됩니다."
            )
            return

        n_mobility = sum(1 for p in self.controller.extracted_params if p.param_name == "Mobility_sat")
        if n_mobility > 0:
            self.mobility_result_label.setText(
                f"이동도(Mobility_sat) {n_mobility}개 계산됨 — Comparison 탭의 지표 목록에서 "
                "\"Mobility_sat\"을 선택하면 볼 수 있습니다."
            )
        else:
            self.mobility_result_label.setText(
                "Cox는 설정됐지만 이동도가 하나도 계산되지 않았습니다 — Column Mapping에서 "
                "W/L이 입력됐는지 확인하거나, 아래 실패 목록에서 사유를 확인하세요."
            )


def _to_float(text: str, default: float) -> float:
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def _to_float_or_none(text: str) -> Optional[float]:
    text = text.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_range(text: str):
    text = text.strip()
    if not text:
        return None
    parts = text.split(",")
    if len(parts) != 2:
        return None
    try:
        return (float(parts[0]), float(parts[1]))
    except ValueError:
        return None
