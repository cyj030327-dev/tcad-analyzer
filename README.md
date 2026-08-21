# TCAD 소자 특성 분석기

Synopsys Sentaurus TCAD 시뮬레이션(sdevice) 결과를 불러와 공정 조건(split)별로
Vth/SS/Ion/Ioff/Ron/gm/gds/DIBL 등 소자 성능 지표를 추출·비교하고, 목적(저전력/고성능/밸런스)에
맞는 "최적 소자"를 추천해주는 데스크톱 프로그램입니다.

## 설치

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## 실행

```powershell
.\.venv\Scripts\python.exe -m tcad_analyzer.app
```

## 개발용 더미 데이터 생성

실제 Sentaurus 출력 파일이 없어도 파서/추출/GUI를 테스트할 수 있도록, 그럴듯한 더미
`.plt`(Tecplot) 파일 + `gtree.dat` + `.cmd` 파일 + 이미 추출된 파라미터 CSV를 생성합니다.

```powershell
.\.venv\Scripts\python.exe scripts\generate_dummy_data.py --out sample_data --n-splits 3 --repeats 1
```

생성된 `sample_data/plt` 폴더를 프로그램의 "폴더 선택" 기능으로 불러오면 gtree.dat이
자동 인식되어 split 조건이 채워집니다.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## 배포용 exe 만들기

코드를 수정한 뒤 아래 스크립트를 다시 실행하면 `dist\TCAD_Analyzer.exe`가 새로 만들어집니다.
Python이 설치되어 있지 않은 다른 컴퓨터에도 이 파일 하나만 복사해서 실행할 수 있습니다
(처음 열 때 압축을 푸느라 몇 초 걸릴 수 있습니다).

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

내부적으로 PyInstaller를 씁니다(`requirements-dev.txt`에 포함). 진입점은 `run_app.py`인데,
`tcad_analyzer/app.py`는 패키지 내부 상대 임포트를 쓰기 때문에 PyInstaller가 직접 분석할 수
있는 패키지 밖의 얇은 런처가 따로 필요해서입니다 — 이 파일은 그대로 두고 건드리지 않아도 됩니다.

## 프로젝트 구조

```
src/tcad_analyzer/
├── parsers/      # .plt(Tecplot), gtree.dat, sdevice .cmd, CSV/Excel 파서
├── models/       # Curve, DeviceMeta, SplitCondition, ExtractedParameter
├── extraction/   # Vth(CC/Linear Extrapolation), SS, Ion/Ioff, Ron/gm/gds, DIBL
├── analysis/     # split별 통계, 상관관계, Pareto+프로파일 기반 "최적 소자 추천"
├── io_export/    # CSV/Excel/PNG export
└── gui/          # PySide6 GUI (Import → Column Mapping → Extraction Config →
                  #   Curve Preview → Comparison → Export)
scripts/generate_dummy_data.py   # 더미 데이터 생성
tests/                            # pytest 테스트 스위트
```

`parsers → models → extraction/analysis → gui` 순 단방향 의존이라, `extraction`/`analysis`는
GUI 없이도(pytest, 스크립트, 추후 CLI 등에서) 그대로 재사용할 수 있습니다.

## 실제 데이터 연결 시 참고

- `.plt` 파일명이 `n<번호>_des.plt` 관례를 따르면 같은 폴더의 `gtree.dat`, `n<번호>_des.cmd`와
  자동으로 매칭됩니다. 다른 명명 규칙을 쓰는 경우 Column Mapping 화면에서 수동으로 split을
  입력하면 됩니다.
- `gtree.dat` 파서는 두 가지 흔한 포맷(Tcl `set` 스타일, 공백 구분 테이블)을 시도합니다.
  실제 파일이 이 둘과 다르면 `src/tcad_analyzer/parsers/gtree_parser.py`를 그 포맷에 맞춰
  조정해야 합니다.
- **`.plt` 포맷은 Tecplot ASCII와 DF-ISE ASCII xyplot(`Info { datasets=[...] } Data { ... }`)
  둘 다 자동 감지해서 처리합니다** (`parsers/plt_loader.py`). Sentaurus 설정에 따라 둘 중 어느 쪽을
  써도 됩니다.
- 임포트 단계에서 각 `.plt`의 Vg(추정) 컬럼 범위가 너무 좁으면(예: transient 결과) "스윕 아닌 것
  같음" 경고가 붙습니다(`parsers/sweep_check.py`). Sentaurus Workbench가 노드 하나에서 여러 `.plt`를
  만드는 경우(예: drain ramp transient + `NewCurrentPrefix`로 이름 바꾼 뒤 gate ramp) 실제 분석에
  쓸 파일만 골라내는 데 도움이 됩니다.
- 게이트 스윕이 진짜 off(subthreshold) 영역까지 못 내려가서 Ion/Ioff 비율이 너무 작으면(기본
  기준: 1000배 미만), 추출 실패는 아니지만 "SS/Ioff 신뢰도가 낮다"는 경고가 붙습니다
  (`extraction/pipeline.py`의 `MIN_ON_OFF_RATIO_FOR_TRUE_OFF`).
