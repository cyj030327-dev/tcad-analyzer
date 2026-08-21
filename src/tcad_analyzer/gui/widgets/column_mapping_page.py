"""2) Column Mapping 페이지: Vg/Id/Vd 역할 매핑, 극성/W,L, split 조건, curve 생성."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from ...models import CurveType, Polarity
from ..controllers.project_controller import ProjectController


class ColumnMappingPage(QWidget):
    def __init__(self, controller: ProjectController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._current_key: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("왼쪽에서 파일을 선택해 컬럼 매핑을 확인/수정하세요."))

        body = QHBoxLayout()
        layout.addLayout(body)

        self.file_list = QListWidget()
        self.file_list.setMaximumWidth(280)
        body.addWidget(self.file_list)

        self.stack = QStackedWidget()
        body.addWidget(self.stack, 1)

        self._plt_form = self._build_plt_form()
        self._table_form = self._build_table_form()
        self.stack.addWidget(self._plt_form)
        self.stack.addWidget(self._table_form)

        bottom = QHBoxLayout()
        self.btn_apply_all = QPushButton("현재 Vg/Id/Vd·극성·W,L 설정을 모든 .plt 파일에 적용")
        self.btn_build = QPushButton("매핑 적용 (Curve 생성)")
        bottom.addWidget(self.btn_apply_all)
        bottom.addStretch(1)
        bottom.addWidget(self.btn_build)
        layout.addLayout(bottom)

        self.file_list.currentItemChanged.connect(self._on_select_file)
        self.btn_apply_all.clicked.connect(self._on_apply_all)
        self.btn_build.clicked.connect(self._on_build)
        self.controller.importChanged.connect(self._refresh_file_list)

    # ---------------------------------------------------------------- plt
    def _build_plt_form(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.curve_type_combo = QComboBox()
        self.curve_type_combo.addItems(["Id-Vg", "Id-Vd"])
        form.addRow("Curve 종류", self.curve_type_combo)

        self.vg_combo = QComboBox()
        self.id_combo = QComboBox()
        self.vd_combo = QComboBox()
        form.addRow("Vg 컬럼", self.vg_combo)
        form.addRow("Id 컬럼", self.id_combo)
        form.addRow("Vd 컬럼", self.vd_combo)

        self.polarity_combo = QComboBox()
        self.polarity_combo.addItems(["NMOS", "PMOS"])
        form.addRow("극성", self.polarity_combo)

        self.device_id_edit = QLineEdit()
        form.addRow("Device ID", self.device_id_edit)

        self.width_edit = QLineEdit()
        self.width_edit.setPlaceholderText("2D 구조면 sprocess 인식 시 1(단위폭)이 자동으로 채워집니다")
        self.length_edit = QLineEdit()
        form.addRow("Width (um, 선택)", self.width_edit)
        form.addRow("Length (um, 선택)", self.length_edit)

        self.split_attrs_edit = QPlainTextEdit()
        self.split_attrs_edit.setPlaceholderText("한 줄에 하나씩, key=value 형식\n예)\nTemperature=900\nRepeat=1")
        self.split_attrs_edit.setMaximumHeight(100)
        form.addRow("Split 조건", self.split_attrs_edit)

        for combo in (self.curve_type_combo, self.vg_combo, self.id_combo, self.vd_combo, self.polarity_combo):
            combo.currentIndexChanged.connect(self._save_current_plt_mapping)
        for edit in (self.device_id_edit, self.width_edit, self.length_edit):
            edit.editingFinished.connect(self._save_current_plt_mapping)
        self.split_attrs_edit.textChanged.connect(self._save_current_plt_mapping)

        return w

    # -------------------------------------------------------------- table
    def _build_table_form(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        form = QFormLayout()
        self.table_split_combo = QComboBox()
        self.table_device_combo = QComboBox()
        self.table_polarity_combo = QComboBox()
        self.table_polarity_combo.addItems(["NMOS", "PMOS"])
        form.addRow("Split 컬럼", self.table_split_combo)
        form.addRow("Device 컬럼 (선택, 없으면 극성 사용)", self.table_device_combo)
        form.addRow("기본 극성", self.table_polarity_combo)
        layout.addLayout(form)

        layout.addWidget(QLabel("파라미터로 사용할 컬럼 (체크):"))
        self.param_cols_list = QListWidget()
        layout.addWidget(self.param_cols_list)

        for combo in (self.table_split_combo, self.table_device_combo, self.table_polarity_combo):
            combo.currentIndexChanged.connect(self._save_current_table_mapping)
        self.param_cols_list.itemChanged.connect(self._save_current_table_mapping)

        return w

    # --------------------------------------------------------------- misc
    def _refresh_file_list(self) -> None:
        self.file_list.blockSignals(True)
        self.file_list.clear()
        for key, mapping in self.controller.plt_mappings.items():
            item = QListWidgetItem(f"[plt] {mapping.path.name}")
            item.setData(Qt.UserRole, ("plt", key))
            self.file_list.addItem(item)
        for key, mapping in self.controller.table_mappings.items():
            item = QListWidgetItem(f"[table] {mapping.path.name}")
            item.setData(Qt.UserRole, ("table", key))
            self.file_list.addItem(item)
        self.file_list.blockSignals(False)
        if self.file_list.count() > 0:
            self.file_list.setCurrentRow(0)

    def _on_select_file(self, current: Optional[QListWidgetItem], _previous) -> None:
        if current is None:
            return
        kind, key = current.data(Qt.UserRole)
        self._current_key = key
        if kind == "plt":
            self.stack.setCurrentWidget(self._plt_form)
            self._load_plt_mapping(key)
        else:
            self.stack.setCurrentWidget(self._table_form)
            self._load_table_mapping(key)

    def _load_plt_mapping(self, key: str) -> None:
        mapping = self.controller.plt_mappings[key]
        tf = self.controller.imported_plt[key]

        for combo in (self.vg_combo, self.id_combo, self.vd_combo):
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(tf.variables)
            combo.blockSignals(False)

        self.curve_type_combo.blockSignals(True)
        self.curve_type_combo.setCurrentIndex(0 if mapping.curve_type == CurveType.ID_VG else 1)
        self.curve_type_combo.blockSignals(False)

        self._set_combo_text(self.vg_combo, mapping.vg_col)
        self._set_combo_text(self.id_combo, mapping.id_col)
        self._set_combo_text(self.vd_combo, mapping.vd_col)

        self.polarity_combo.blockSignals(True)
        self.polarity_combo.setCurrentIndex(0 if mapping.polarity == Polarity.NMOS else 1)
        self.polarity_combo.blockSignals(False)

        self.device_id_edit.blockSignals(True)
        self.device_id_edit.setText(mapping.device_id)
        self.device_id_edit.blockSignals(False)

        self.width_edit.blockSignals(True)
        self.width_edit.setText("" if mapping.width_um is None else str(mapping.width_um))
        self.width_edit.blockSignals(False)
        self.length_edit.blockSignals(True)
        self.length_edit.setText("" if mapping.length_um is None else str(mapping.length_um))
        self.length_edit.blockSignals(False)

        self.split_attrs_edit.blockSignals(True)
        self.split_attrs_edit.setPlainText(
            "\n".join(f"{k}={v}" for k, v in mapping.split_attributes.items())
        )
        self.split_attrs_edit.blockSignals(False)

    @staticmethod
    def _set_combo_text(combo: QComboBox, text: Optional[str]) -> None:
        combo.blockSignals(True)
        if text is not None:
            idx = combo.findText(text)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        combo.blockSignals(False)

    def _save_current_plt_mapping(self) -> None:
        if self._current_key is None or self._current_key not in self.controller.plt_mappings:
            return
        mapping = self.controller.plt_mappings[self._current_key]
        mapping.curve_type = CurveType.ID_VG if self.curve_type_combo.currentIndex() == 0 else CurveType.ID_VD
        mapping.vg_col = self.vg_combo.currentText() or None
        mapping.id_col = self.id_combo.currentText() or None
        mapping.vd_col = self.vd_combo.currentText() or None
        mapping.polarity = Polarity.NMOS if self.polarity_combo.currentIndex() == 0 else Polarity.PMOS
        mapping.device_id = self.device_id_edit.text().strip() or "device"
        mapping.width_um = _to_float_or_none(self.width_edit.text())
        mapping.length_um = _to_float_or_none(self.length_edit.text())
        # 사용자가 직접 입력한 값이므로, 나중에 gtree/sprocess에서 값을 읽어와도(자동 채움은
        # 항상 사용자 입력보다 우선순위가 낮음) 이 값을 덮어쓰지 않도록 표시해둔다.
        mapping.length_um_source = "user"
        mapping.split_attributes = _parse_kv_lines(self.split_attrs_edit.toPlainText())

    def _on_apply_all(self) -> None:
        if self._current_key is None:
            return
        source = self.controller.plt_mappings.get(self._current_key)
        if source is None:
            return
        for mapping in self.controller.plt_mappings.values():
            mapping.vg_col = source.vg_col
            mapping.id_col = source.id_col
            mapping.vd_col = source.vd_col
            mapping.curve_type = source.curve_type
            mapping.polarity = source.polarity
            mapping.width_um = source.width_um
            mapping.length_um = source.length_um
            mapping.length_um_source = "user"  # 일괄 적용도 사용자의 명시적 선택이므로 보호 대상
        QMessageBox.information(self, "적용됨", "Vg/Id/Vd·극성·W,L 설정을 모든 .plt 파일에 적용했습니다.")

    def _load_table_mapping(self, key: str) -> None:
        mapping = self.controller.table_mappings[key]
        df = self.controller.imported_tables[key]
        columns = list(df.columns)

        for combo in (self.table_split_combo, self.table_device_combo):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("(없음)")
            combo.addItems(columns)
            combo.blockSignals(False)
        self._set_combo_text(self.table_split_combo, mapping.split_col or "(없음)")
        self._set_combo_text(self.table_device_combo, mapping.device_col or "(없음)")

        self.table_polarity_combo.blockSignals(True)
        self.table_polarity_combo.setCurrentIndex(0 if mapping.polarity == Polarity.NMOS else 1)
        self.table_polarity_combo.blockSignals(False)

        self.param_cols_list.blockSignals(True)
        self.param_cols_list.clear()
        for col in columns:
            item = QListWidgetItem(col)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if col in mapping.param_cols else Qt.Unchecked)
            self.param_cols_list.addItem(item)
        self.param_cols_list.blockSignals(False)

    def _save_current_table_mapping(self) -> None:
        if self._current_key is None or self._current_key not in self.controller.table_mappings:
            return
        mapping = self.controller.table_mappings[self._current_key]
        split_text = self.table_split_combo.currentText()
        device_text = self.table_device_combo.currentText()
        mapping.split_col = None if split_text == "(없음)" else split_text
        mapping.device_col = None if device_text == "(없음)" else device_text
        mapping.polarity = Polarity.NMOS if self.table_polarity_combo.currentIndex() == 0 else Polarity.PMOS
        mapping.param_cols = [
            self.param_cols_list.item(i).text()
            for i in range(self.param_cols_list.count())
            if self.param_cols_list.item(i).checkState() == Qt.Checked
        ]

    def _on_build(self) -> None:
        self._save_current_plt_mapping()
        self._save_current_table_mapping()
        self.controller.build_curves()
        QMessageBox.information(
            self,
            "완료",
            f"Curve {len(self.controller.curves)}개, 임포트된 파라미터 {len(self.controller.imported_table_params)}개를 생성했습니다.",
        )


def _to_float_or_none(text: str) -> Optional[float]:
    text = text.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_kv_lines(text: str) -> dict:
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        result[k.strip()] = v.strip()
    return result
