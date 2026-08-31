"""QMainWindow: 사이드바 네비게이션 + QStackedWidget으로 6단계 화면 전환."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QListWidget,
    QMainWindow,
    QScrollArea,
    QStackedWidget,
    QWidget,
)

from .controllers.project_controller import ProjectController
from .widgets.column_mapping_page import ColumnMappingPage
from .widgets.comparison_page import ComparisonPage
from .widgets.curve_preview_page import CurvePreviewPage
from .widgets.export_page import ExportPage
from .widgets.extraction_config_page import ExtractionConfigPage
from .widgets.import_page import ImportPage

def _scrollable(widget: QWidget) -> QScrollArea:
    """페이지 내용이 창 높이보다 길어지면(예: Extraction Config의 아래쪽 항목들) 그 페이지만
    스크롤해서 볼 수 있도록 감싼다. 6개 페이지 전부 여기서 한 번에 적용한다."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setWidget(widget)
    return scroll


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

        self.stack.addWidget(_scrollable(ImportPage(self.controller)))
        self.stack.addWidget(_scrollable(ColumnMappingPage(self.controller)))
        self.stack.addWidget(_scrollable(ExtractionConfigPage(self.controller)))
        self.stack.addWidget(_scrollable(CurvePreviewPage(self.controller)))
        self.stack.addWidget(_scrollable(ComparisonPage(self.controller)))
        self.stack.addWidget(_scrollable(ExportPage(self.controller)))

        self.nav_list.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav_list.setCurrentRow(0)
