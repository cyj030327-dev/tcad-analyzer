"""이미 추출된 파라미터 테이블(CSV/Excel) 로더."""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from .errors import TableLoadError

_ENCODING_FALLBACKS = ("utf-8-sig", "cp949", "latin-1")


def _sniff_delimiter(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        return dialect.delimiter
    except csv.Error:
        return ","


def load_parameter_table(path: Path) -> pd.DataFrame:
    """.csv / .xlsx / .xls 파일을 읽어 DataFrame으로 반환.

    - 인코딩 자동 폴백 (utf-8-sig -> cp949 -> latin-1): 한글 컬럼명 대비
    - 구분자 자동 감지 (CSV)
    - 컬럼명 공백 정리, 완전 빈 행/열 제거
    """
    path = Path(path)
    if not path.exists():
        raise TableLoadError("파일이 존재하지 않습니다", path=path)

    suffix = path.suffix.lower()
    try:
        if suffix in (".xlsx", ".xls"):
            df = pd.read_excel(path, sheet_name=0)
        elif suffix == ".csv":
            df = _load_csv(path)
        else:
            raise TableLoadError(f"지원하지 않는 파일 형식입니다: {suffix}", path=path)
    except TableLoadError:
        raise
    except Exception as exc:  # pandas가 던지는 다양한 예외를 통일된 에러로 감싼다
        raise TableLoadError(f"파일을 읽는 중 오류가 발생했습니다: {exc}", path=path) from exc

    if df.empty:
        raise TableLoadError("빈 파일이거나 읽을 수 있는 데이터가 없습니다", path=path)

    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    df = df.reset_index(drop=True)
    return df


def _load_csv(path: Path) -> pd.DataFrame:
    last_error: Exception | None = None
    for enc in _ENCODING_FALLBACKS:
        try:
            with open(path, "r", encoding=enc) as f:
                sample = f.read(4096)
            delimiter = _sniff_delimiter(sample)
            return pd.read_csv(path, encoding=enc, sep=delimiter)
        except (UnicodeDecodeError, LookupError) as exc:
            last_error = exc
            continue
    raise TableLoadError(f"CSV 인코딩을 인식할 수 없습니다: {last_error}", path=path)
