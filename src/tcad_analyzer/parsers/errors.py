"""파서 공용 예외 계층. GUI 에러 다이얼로그에 그대로 표시 가능하도록 메시지에
파일 경로/라인 번호/원문 라인을 최대한 포함시킨다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


class ParseError(Exception):
    """모든 파싱 예외의 공통 베이스."""


class TecplotParseError(ParseError):
    def __init__(
        self,
        message: str,
        path: Optional[Path] = None,
        line_no: Optional[int] = None,
        raw_line: Optional[str] = None,
    ):
        self.path = path
        self.line_no = line_no
        self.raw_line = raw_line
        detail = message
        if path is not None:
            detail += f" (파일: {path})"
        if line_no is not None:
            detail += f" (라인 {line_no})"
        if raw_line is not None:
            detail += f"\n  원문: {raw_line!r}"
        super().__init__(detail)


class ColumnMappingError(ParseError):
    pass


class TableLoadError(ParseError):
    def __init__(self, message: str, path: Optional[Path] = None):
        self.path = path
        detail = message if path is None else f"{message} (파일: {path})"
        super().__init__(detail)


class GtreeParseError(ParseError):
    def __init__(self, message: str, path: Optional[Path] = None):
        self.path = path
        detail = message if path is None else f"{message} (파일: {path})"
        super().__init__(detail)
