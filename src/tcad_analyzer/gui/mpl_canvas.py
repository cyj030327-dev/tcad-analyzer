"""QWidget 안에 matplotlib Figure를 띄우는 얇은 래퍼."""

from __future__ import annotations

import matplotlib
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtWidgets import QVBoxLayout, QWidget

# 차트 제목/범례 등에 한글이 들어가는데, matplotlib 기본 폰트(DejaVu Sans)는 한글 글리프가
# 없어 네모 박스로 깨져 보인다. Windows에 기본 내장된 맑은 고딕으로 바꾸고, 한글 폰트에는
# 유니코드 마이너스 글리프가 없는 경우가 많아 음수 축 눈금이 깨지지 않도록 옵션도 끈다.
matplotlib.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False


class MplCanvas(QWidget):
    def __init__(self, parent=None, figsize=(6, 4)):
        super().__init__(parent)
        self.figure = Figure(figsize=figsize)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

    def clear(self) -> None:
        self.figure.clear()
        self.canvas.draw_idle()

    def draw(self) -> None:
        self.canvas.draw_idle()
