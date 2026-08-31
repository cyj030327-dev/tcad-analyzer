"""6) Export 페이지: 파라미터/통계 테이블 CSV·Excel 저장 + 요약 보고서(HTML) 자동 생성."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...analysis import OptimizationProfile
from ...io_export import export_dataframe_csv, export_dataframe_excel, generate_html_report
from ..controllers.project_controller import ProjectController

_PROFILE_ITEMS = [
    ("밸런스", OptimizationProfile.BALANCED),
    ("저전력", OptimizationProfile.LOW_POWER),
    ("고성능", OptimizationProfile.HIGH_PERFORMANCE),
]


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

        layout.addWidget(QLabel("표·그래프·최적 소자 추천을 한 파일로 묶은 요약 보고서(HTML)를 만듭니다:"))
        report_row = QHBoxLayout()
        report_row.addWidget(QLabel("추천 기준:"))
        self.report_profile_combo = QComboBox()
        self.report_profile_combo.addItems([label for label, _ in _PROFILE_ITEMS])
        report_row.addWidget(self.report_profile_combo)
        self.btn_report = QPushButton("보고서 생성 (HTML)...")
        report_row.addWidget(self.btn_report)
        report_row.addStretch(1)
        layout.addLayout(report_row)

        self.report_status_label = QLabel("")
        self.report_status_label.setWordWrap(True)
        layout.addWidget(self.report_status_label)
        layout.addStretch(1)

        self.btn_csv.clicked.connect(self._export_csv)
        self.btn_excel.clicked.connect(self._export_excel)
        self.btn_report.clicked.connect(self._generate_report)

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

    def _generate_report(self) -> None:
        params = self.controller.all_params
        if not params:
            QMessageBox.warning(self, "생성할 데이터 없음", "먼저 추출을 실행하세요.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "보고서로 저장", "tcad_report.html", "HTML (*.html)")
        if not path:
            return

        profile = dict(_PROFILE_ITEMS)[self.report_profile_combo.currentText()]
        html_text = generate_html_report(params, list(self.controller.curves), profile=profile)
        try:
            Path(path).write_text(html_text, encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "생성 실패", f"보고서를 저장하지 못했습니다: {exc}")
            return
        self.report_status_label.setText(f"보고서 생성됨: {path} (브라우저로 열어 확인하거나 인쇄 → PDF로 저장할 수 있습니다)")
