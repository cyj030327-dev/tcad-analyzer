"""PyInstaller가 패키징할 진입 스크립트.

`tcad_analyzer/app.py`는 패키지 내부에서 상대 임포트(`.gui.main_window`)를 쓰기 때문에,
그 파일 자체를 최상위 스크립트로 실행하면(예: PyInstaller가 직접 분석) 상대 임포트가 깨진다.
그래서 패키지 밖에 있는 이 얇은 런처를 대신 진입점으로 쓴다 — 일반 실행(`python run_app.py`)과
PyInstaller 빌드 모두 이 파일을 기준으로 하면 된다.
"""

import sys

from tcad_analyzer.app import main

if __name__ == "__main__":
    sys.exit(main())
