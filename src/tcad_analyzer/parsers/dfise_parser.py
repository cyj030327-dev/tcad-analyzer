"""Sentaurus의 DF-ISE ASCII xyplot(.plt) 파서.

Tecplot(TITLE/VARIABLES/ZONE) 포맷과 달리, DF-ISE는 구조가 훨씬 단순하다:

    Info { datasets = [ "col1" "col2" ... ] }
    Data { 숫자가 줄바꿈 무시하고 컬럼수의 배수개만큼 쭉 나열 }

ZONE 개념이 없어 파일 하나가 곧 곡선 하나이므로, 기존 Tecplot 파서가 쓰는
`TecplotFile`/`TecplotZone` 컨테이너에 zone 1개짜리로 담아 반환한다 — 이렇게 하면
컬럼 매핑/추출/GUI 쪽 코드를 포맷에 상관없이 그대로 재사용할 수 있다.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from .errors import TecplotParseError
from .tecplot_parser import TecplotFile, TecplotZone

_DATASETS_RE = re.compile(r"datasets\s*=\s*\[(.*?)\]", re.DOTALL)
_QUOTED_RE = re.compile(r'"([^"]*)"')
_DATA_BLOCK_RE = re.compile(r"Data\s*\{(.*)\}", re.DOTALL)


def looks_like_dfise(text: str) -> bool:
    """파일 앞부분만 보고 DF-ISE 포맷인지 가볍게 판별(포맷 자동감지용)."""
    head = text[:2000]
    return "datasets" in head and "Data" in text


def parse_dfise_file(path: Path) -> TecplotFile:
    path = Path(path)
    if not path.exists():
        raise TecplotParseError("파일이 존재하지 않습니다", path=path)

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        raise TecplotParseError(f"파일을 읽을 수 없습니다: {exc}", path=path) from exc

    m = _DATASETS_RE.search(text)
    if not m:
        raise TecplotParseError(
            "datasets 블록을 찾지 못했습니다. DF-ISE 형식이 맞는지 확인하세요", path=path
        )
    variables = _QUOTED_RE.findall(m.group(1))
    if not variables:
        raise TecplotParseError("컬럼 이름을 하나도 찾지 못했습니다", path=path)

    m = _DATA_BLOCK_RE.search(text)
    if not m:
        raise TecplotParseError(
            "Data 블록을 찾지 못했습니다. 파일이 덜 써졌을 수 있습니다", path=path
        )

    try:
        values = [float(tok) for tok in m.group(1).split()]
    except ValueError as exc:
        raise TecplotParseError(f"숫자로 변환할 수 없는 값이 있습니다: {exc}", path=path) from exc

    n = len(variables)
    if len(values) % n != 0:
        raise TecplotParseError(
            f"숫자 개수({len(values)})가 컬럼 수({n})로 나누어떨어지지 않습니다. "
            "파일이 덜 써졌거나(시뮬레이션 진행 중) 형식이 다를 수 있습니다",
            path=path,
        )
    if len(values) == 0:
        raise TecplotParseError("Data 블록에 값이 없습니다", path=path)

    data = np.array(values, dtype=float).reshape(-1, n)
    zone = TecplotZone(title=path.stem, variables=variables, data=data, raw_header={})
    return TecplotFile(title=path.stem, variables=variables, zones=[zone], source_path=path)
