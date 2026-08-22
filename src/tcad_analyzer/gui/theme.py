"""숭실대학교 상징색(Pantone 308/3135/325)을 포인트로 쓰는 밝은 배경 테마.

숭실대 공식 홈페이지의 "전용 색상" 페이지는 Pantone 코드만 제공해서(HEX 미공개), 표준
Pantone->HEX 변환표로 근사한 값을 쓴다:
  - Pantone 308  -> #00587C (진한 남색-청록, 메인 포인트)
  - Pantone 3135 -> #008EAA (중간 톤 청록, 보조 포인트/hover)
  - Pantone 325  -> #64CCC9 (밝은 민트, 은은한 강조/선택 배경)

QApplication 전체에 적용하는 QSS(Qt Style Sheet) 하나로 구성한다. 위젯 개별 스타일을
따로 건드리지 않고 여기 하나만 고치면 전체 색감이 바뀌도록 유지한다.
"""

from __future__ import annotations

ACCENT_DARK = "#00587C"  # Pantone 308
ACCENT_MID = "#008EAA"  # Pantone 3135
ACCENT_LIGHT = "#64CCC9"  # Pantone 325

BG_MAIN = "#F5F8F9"
BG_PANEL = "#FFFFFF"
BG_HOVER = "#E4F2F4"
BG_SELECTED = ACCENT_LIGHT
TEXT_PRIMARY = "#1B2A2E"
TEXT_SECONDARY = "#5B6B6E"
TEXT_ON_ACCENT = "#FFFFFF"
BORDER = "#D8E1E3"

SSU_LIGHT_QSS = f"""
QWidget {{
    background-color: {BG_MAIN};
    color: {TEXT_PRIMARY};
    font-size: 10pt;
}}

QMainWindow {{
    background-color: {BG_MAIN};
}}

/* 왼쪽 사이드바 내비게이션 */
QListWidget {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 6px;
    outline: 0;
    padding: 4px;
}}
QListWidget::item {{
    padding: 8px 10px;
    border-radius: 4px;
    color: {TEXT_PRIMARY};
}}
QListWidget::item:hover {{
    background-color: {BG_HOVER};
}}
QListWidget::item:selected {{
    background-color: {ACCENT_DARK};
    color: {TEXT_ON_ACCENT};
}}

/* 버튼 */
QPushButton {{
    background-color: {ACCENT_DARK};
    color: {TEXT_ON_ACCENT};
    border: none;
    border-radius: 5px;
    padding: 6px 14px;
}}
QPushButton:hover {{
    background-color: {ACCENT_MID};
}}
QPushButton:pressed {{
    background-color: #00405A;
}}
QPushButton:disabled {{
    background-color: #B9C4C6;
    color: #EEF2F2;
}}

/* 입력 위젯 */
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 6px;
    selection-background-color: {ACCENT_LIGHT};
    selection-color: {TEXT_PRIMARY};
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border: 1px solid {ACCENT_MID};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT_LIGHT};
    selection-color: {TEXT_PRIMARY};
}}

/* 탭 */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    background-color: {BG_PANEL};
    top: -1px;
}}
QTabBar::tab {{
    background-color: {BG_MAIN};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 6px 14px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {BG_PANEL};
    color: {ACCENT_DARK};
    font-weight: 600;
}}
QTabBar::tab:hover {{
    background-color: {BG_HOVER};
}}

/* 표 */
QTableWidget, QTableView {{
    background-color: {BG_PANEL};
    alternate-background-color: {BG_MAIN};
    gridline-color: {BORDER};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT_LIGHT};
    selection-color: {TEXT_PRIMARY};
}}
QHeaderView::section {{
    background-color: {ACCENT_DARK};
    color: {TEXT_ON_ACCENT};
    padding: 5px;
    border: none;
    border-right: 1px solid {BG_PANEL};
}}

/* 그룹 박스 */
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 8px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {ACCENT_DARK};
}}

/* 체크박스/라디오 */
QCheckBox::indicator, QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {BORDER};
    background-color: {BG_PANEL};
}}
QCheckBox::indicator {{
    border-radius: 3px;
}}
QRadioButton::indicator {{
    border-radius: 7px;
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {ACCENT_DARK};
    border: 1px solid {ACCENT_DARK};
}}

/* 스크롤바 */
QScrollBar:vertical {{
    background: {BG_MAIN};
    width: 12px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {ACCENT_LIGHT};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ACCENT_MID};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {BG_MAIN};
    height: 12px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {ACCENT_LIGHT};
    border-radius: 5px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {ACCENT_MID};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

QLabel {{
    color: {TEXT_PRIMARY};
    background-color: transparent;
}}

QToolTip {{
    background-color: {ACCENT_DARK};
    color: {TEXT_ON_ACCENT};
    border: none;
    padding: 4px;
}}
"""
