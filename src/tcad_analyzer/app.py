"""QApplication 엔트리포인트. 실행: `python -m tcad_analyzer.app`"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .gui.main_window import MainWindow
from .gui.theme import SSU_LIGHT_QSS


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(SSU_LIGHT_QSS)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
