"""`.plt` 포맷 자동 감지 + 분기.

Sentaurus 출력은 Tecplot(TITLE/VARIABLES/ZONE) 스타일과 DF-ISE(datasets=[...] / Data {...})
스타일 두 가지가 실사용에서 관측됐다. 파일 내용을 살짝 들여다보고 어느 쪽인지 판별해
알맞은 파서로 분기하는 단일 진입점을 제공한다 — 이후 GUI/컨트롤러는 포맷을 신경쓰지 않고
`load_plt_file()`만 호출하면 된다.
"""

from __future__ import annotations

from pathlib import Path

from .dfise_parser import looks_like_dfise, parse_dfise_file
from .errors import TecplotParseError
from .tecplot_parser import TecplotFile, parse_tecplot_file


def sniff_plt_format(path: Path) -> str:
    """"tecplot" | "dfise" | "unknown" 중 하나를 돌려준다."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
    except OSError:
        return "unknown"
    if looks_like_dfise(text):
        return "dfise"
    if "VARIABLES" in text.upper() and "ZONE" in text.upper():
        return "tecplot"
    return "unknown"


def load_plt_file(path: Path) -> TecplotFile:
    fmt = sniff_plt_format(path)
    if fmt == "dfise":
        return parse_dfise_file(path)
    if fmt == "tecplot":
        return parse_tecplot_file(path)
    raise TecplotParseError(
        "알려진 .plt 형식(Tecplot ASCII 또는 DF-ISE xyplot)을 인식하지 못했습니다",
        path=Path(path),
    )
