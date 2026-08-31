"""전체 앱에 입히는 QSS(Qt Style Sheet) 테마.

사용자가 보여준 참고 목업(진한 네이비 헤더 + 화이트 배경 + 카드형 패널 + 깔끔한 표)에서,
이번 1차 작업 범위로 정한 "색상/카드 스타일"만 가져온다. 툴바 아이콘, 접이식 사이드바,
로그 콘솔창 같은 구조 변경은 다음 단계로 미뤄뒀다.

포인트 색은 사용자가 직접 지정한 청록빛 파랑(#0099cc 근처)을 쓴다.
"""

ACCENT = "#0099cc"
ACCENT_DARK = "#00789e"
ACCENT_LIGHT = "#e5f5fa"
BODY_BG = "#f4f6f9"
PANEL_BG = "#ffffff"
BORDER = "#dfe4ea"
TEXT = "#1f2933"
TEXT_MUTED = "#6b7684"

APP_QSS = f"""
QWidget {{
    background: {BODY_BG};
    color: {TEXT};
    font-size: 13px;
}}

/* ---------------------------------------------------------------- 사이드바 네비게이션 */
QListWidget {{
    background: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px;
    outline: 0;
}}
QListWidget::item {{
    padding: 8px 10px;
    border-radius: 5px;
    color: {TEXT};
}}
QListWidget::item:selected {{
    background: {ACCENT};
    color: white;
}}
QListWidget::item:hover:!selected {{
    background: {ACCENT_LIGHT};
}}

/* ---------------------------------------------------------------- 탭 */
QTabWidget::pane {{
    background: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_MUTED};
    padding: 7px 16px;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: {ACCENT_DARK};
    border-bottom: 2px solid {ACCENT};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT};
}}

/* ---------------------------------------------------------------- 카드(패널) 역할: 그룹박스/스크롤영역 */
QGroupBox {{
    background: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 14px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {ACCENT_DARK};
}}
QScrollArea {{
    border: none;
}}

/* ---------------------------------------------------------------- 버튼 */
QPushButton {{
    background: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 6px 14px;
    color: {TEXT};
}}
QPushButton:hover {{
    border-color: {ACCENT};
    color: {ACCENT_DARK};
}}
QPushButton:pressed {{
    background: {ACCENT_LIGHT};
}}
QPushButton:default {{
    background: {ACCENT};
    border-color: {ACCENT};
    color: white;
    font-weight: 600;
}}
QPushButton:default:hover {{
    background: {ACCENT_DARK};
}}

/* ---------------------------------------------------------------- 입력 위젯 */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 4px 6px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

/* ---------------------------------------------------------------- 표 */
QTableWidget {{
    background: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    gridline-color: {BORDER};
    selection-background-color: {ACCENT_LIGHT};
    selection-color: {TEXT};
}}
QHeaderView::section {{
    background: {ACCENT_LIGHT};
    color: {ACCENT_DARK};
    padding: 6px;
    border: none;
    border-bottom: 1px solid {BORDER};
    font-weight: 600;
}}
QTableWidget::item {{
    padding: 4px;
}}

/* ---------------------------------------------------------------- 체크박스 */
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
}}

/* ---------------------------------------------------------------- 스크롤바 */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ACCENT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""
