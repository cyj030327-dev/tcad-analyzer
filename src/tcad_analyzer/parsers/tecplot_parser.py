"""Sentaurus TCAD가 출력하는 Tecplot ASCII(.plt) 곡선 파일 파서.

가정하는 표준 구조:

    TITLE = "..."
    VARIABLES = "Gate Voltage (V)" "Drain Current (A)" "Drain Voltage (V)"
    ZONE T="split1" I=101 F=POINT
    0.0000e+00  1.234e-12  5.000e-01
    ...
    ZONE T="split2" I=101 F=POINT
    ...

실제 Sentaurus 출력은 버전/설정에 따라 다음이 달라질 수 있어 견고하게 처리한다:
  - VARIABLES가 여러 줄에 걸침, 변수명에 공백/괄호/단위 포함
  - ZONE 헤더의 키=값 순서/유무가 다양함 (T=, I=, F=POINT 또는 DATAPACKING=POINT)
  - 공백/탭 구분, 지수표기 `1.0E-12` / `1.0e-12` / `1.0D-12`(Fortran) 혼재
  - 파일 하나에 여러 ZONE
  - Windows CRLF, 비-UTF8 인코딩
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from .errors import TecplotParseError

logger = logging.getLogger(__name__)

_TITLE_RE = re.compile(r'^\s*TITLE\s*=\s*"(.*)"\s*$', re.IGNORECASE)
_VARIABLES_START_RE = re.compile(r'^\s*VARIABLES\s*=', re.IGNORECASE)
_ZONE_START_RE = re.compile(r'^\s*ZONE\b', re.IGNORECASE)
_QUOTED_RE = re.compile(r'"([^"]*)"')
_ZONE_KV_RE = re.compile(r'(\w+)\s*=\s*(?:"([^"]*)"|(\S+))')
_COMMENT_RE = re.compile(r'^\s*[#!]')


@dataclass(frozen=True)
class TecplotZone:
    title: Optional[str]
    variables: List[str]
    data: np.ndarray  # shape (n_points, n_vars)
    raw_header: Dict[str, str] = field(default_factory=dict)

    def column(self, name: str) -> np.ndarray:
        """변수명으로 컬럼을 가져온다. 못 찾으면 KeyError."""
        idx = self.variables.index(name)
        return self.data[:, idx]


@dataclass(frozen=True)
class TecplotFile:
    title: Optional[str]
    variables: List[str]
    zones: List[TecplotZone]
    source_path: Path


def _to_float(token: str) -> float:
    # Fortran식 지수표기(1.0D-12) 보정
    normalized = token.replace("D", "E").replace("d", "e")
    return float(normalized)


def _read_lines(path: Path) -> List[str]:
    encodings = ("utf-8-sig", "latin-1")
    last_error: Optional[Exception] = None
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc) as f:
                return f.readlines()
        except UnicodeDecodeError as exc:  # pragma: no cover - latin-1은 사실상 실패하지 않음
            last_error = exc
            continue
    raise TecplotParseError(f"파일 인코딩을 인식할 수 없습니다: {last_error}", path=path)


def _parse_zone_header(line: str) -> Dict[str, str]:
    header: Dict[str, str] = {}
    # "ZONE" 키워드 이후 부분만 파싱
    rest = _ZONE_START_RE.sub("", line, count=1)
    for m in _ZONE_KV_RE.finditer(rest):
        key = m.group(1).upper()
        value = m.group(2) if m.group(2) is not None else m.group(3)
        header[key] = value
    return header


def parse_tecplot_file(path: Path) -> TecplotFile:
    path = Path(path)
    if not path.exists():
        raise TecplotParseError("파일이 존재하지 않습니다", path=path)

    lines = _read_lines(path)
    if not all(line.strip() == "" or _COMMENT_RE.match(line) for line in lines[:1]) and not lines:
        raise TecplotParseError("빈 파일입니다", path=path)

    title: Optional[str] = None
    variables: List[str] = []
    zones: List[TecplotZone] = []

    i = 0
    n = len(lines)

    # 1) TITLE / VARIABLES 헤더 파싱 (ZONE 만나기 전까지)
    while i < n:
        raw = lines[i]
        stripped = raw.strip()
        if stripped == "" or _COMMENT_RE.match(stripped):
            i += 1
            continue
        if _ZONE_START_RE.match(stripped):
            break
        m = _TITLE_RE.match(stripped)
        if m:
            title = m.group(1)
            i += 1
            continue
        if _VARIABLES_START_RE.match(stripped):
            # VARIABLES = 이후, ZONE 라인 나오기 전까지를 모두 이어붙여 따옴표 문자열 추출
            var_text_parts = [_VARIABLES_START_RE.sub("", stripped, count=1)]
            i += 1
            while i < n and not _ZONE_START_RE.match(lines[i].strip()):
                nxt = lines[i].strip()
                if nxt and not _COMMENT_RE.match(nxt):
                    var_text_parts.append(nxt)
                i += 1
            var_text = " ".join(var_text_parts)
            found = _QUOTED_RE.findall(var_text)
            if found:
                variables = [v.strip() for v in found]
            else:
                variables = [v for v in var_text.split() if v]
            continue
        # 인식 못하는 헤더 라인은 건너뜀 (DATASETAUXDATA 등 부가 정보)
        i += 1

    if not variables:
        raise TecplotParseError(
            "VARIABLES 헤더를 찾지 못했습니다. Tecplot 포맷이 맞는지 확인하세요", path=path
        )

    n_vars = len(variables)
    if len(set(variables)) != n_vars:
        raise TecplotParseError(f"VARIABLES에 중복된 컬럼명이 있습니다: {variables}", path=path)

    # 2) ZONE 반복 파싱
    while i < n:
        stripped = lines[i].strip()
        if stripped == "" or _COMMENT_RE.match(stripped):
            i += 1
            continue
        if not _ZONE_START_RE.match(stripped):
            i += 1
            continue

        header = _parse_zone_header(stripped)
        zone_title = header.get("T")
        declared_i = header.get("I")
        line_no_of_zone = i + 1
        i += 1

        rows: List[List[float]] = []
        while i < n and not _ZONE_START_RE.match(lines[i].strip()):
            raw_line = lines[i]
            stripped_data = raw_line.strip()
            if stripped_data == "" or _COMMENT_RE.match(stripped_data):
                i += 1
                continue
            tokens = stripped_data.split()
            if len(tokens) != n_vars:
                raise TecplotParseError(
                    f"데이터 라인의 컬럼 수({len(tokens)})가 VARIABLES 수({n_vars})와 다릅니다",
                    path=path,
                    line_no=i + 1,
                    raw_line=raw_line.rstrip("\n"),
                )
            try:
                rows.append([_to_float(t) for t in tokens])
            except ValueError as exc:
                raise TecplotParseError(
                    f"숫자로 변환할 수 없는 값이 있습니다: {exc}",
                    path=path,
                    line_no=i + 1,
                    raw_line=raw_line.rstrip("\n"),
                ) from exc
            i += 1

        if not rows:
            raise TecplotParseError(
                "ZONE에 데이터가 없습니다", path=path, line_no=line_no_of_zone
            )

        if declared_i is not None:
            try:
                declared_n = int(declared_i)
                if declared_n != len(rows):
                    logger.warning(
                        "ZONE(%s)의 선언된 I=%s와 실제 데이터 라인 수(%d)가 다릅니다. "
                        "실제 라인 수를 사용합니다.",
                        zone_title,
                        declared_i,
                        len(rows),
                    )
            except ValueError:
                pass

        data = np.array(rows, dtype=float)
        zones.append(TecplotZone(title=zone_title, variables=variables, data=data, raw_header=header))

    if not zones:
        raise TecplotParseError("ZONE을 하나도 찾지 못했습니다", path=path)

    return TecplotFile(title=title, variables=variables, zones=zones, source_path=path)
