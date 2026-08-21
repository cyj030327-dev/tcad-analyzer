"""6) Export 페이지: 파라미터/통계 테이블 CSV·Excel 저장."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from ...io_export import export_dataframe_csv, export_dataframe_excel
from ..controllers.project_controller import ProjectController


class ExportPage(QWidget):
    def __init__(self, controller: ProjectController, parent=None):
        super().__init__(parent)
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("추출된(+임포트된) 전체 파라미터 테이블을 내보냅니다."))

        row = QHBoxLayout()
        self.btn_csv = QPushButton("CSV로 내보내기...")
        self.btn_excel = QPushButton("Excel로 내보내기...")
        row.addWidget(self.btn_csv)
        row.addWidget(self.btn_excel)
        row.addStretch(1)
        layout.addLayout(row)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        layout.addStretch(1)

        self.btn_csv.clicked.connect(self._export_csv)
        self.btn_excel.clicked.connect(self._export_excel)

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "CSV로 저장", "extracted_parameters.csv", "CSV (*.csv)")
        if not path:
            return
        df = self.controller.params_dataframe()
        if df.empty:
            QMessageBox.warning(self, "내보낼 데이터 없음", "먼저 추출을 실행하세요.")
            return
        export_dataframe_csv(df, Path(path))
        self.status_label.setText(f"저장됨: {path}")

    def _export_excel(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Excel로 저장", "extracted_parameters.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        df = self.controller.params_dataframe()
        if df.empty:
            QMessageBox.warning(self, "내보낼 데이터 없음", "먼저 추출을 실행하세요.")
            return
        export_dataframe_excel(df, Path(path))
        self.status_label.setText(f"저장됨: {path}")
