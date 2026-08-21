"""QMainWindow: 사이드바 네비게이션 + QStackedWidget으로 6단계 화면 전환."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QListWidget, QMainWindow, QStackedWidget, QWidget

from .controllers.project_controller import ProjectController
from .widgets.column_mapping_page import ColumnMappingPage
from .widgets.comparison_page import ComparisonPage
from .widgets.curve_preview_page import CurvePreviewPage
from .widgets.export_page import ExportPage
from .widgets.extraction_config_page import ExtractionConfigPage
from .widgets.import_page import ImportPage

PAGE_NAMES = [
    "1. Import",
    "2. Column Mapping",
    "3. Extraction Config",
    "4. Curve Preview",
    "5. Comparison",
    "6. Export",
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TCAD 소자 특성 분석기")
        self.resize(1200, 800)

        self.controller = ProjectController()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        self.nav_list = QListWidget()
        self.nav_list.addItems(PAGE_NAMES)
        self.nav_list.setMaximumWidth(180)
        layout.addWidget(self.nav_list)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.stack.addWidget(ImportPage(self.controller))
        self.stack.addWidget(ColumnMappingPage(self.controller))
        self.stack.addWidget(ExtractionConfigPage(self.controller))
        self.stack.addWidget(CurvePreviewPage(self.controller))
        self.stack.addWidget(ComparisonPage(self.controller))
        self.stack.addWidget(ExportPage(self.controller))

        self.nav_list.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav_list.setCurrentRow(0)
