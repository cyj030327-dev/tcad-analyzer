"""결과 내보내기: 파라미터/통계 테이블 CSV·Excel, 차트 PNG."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def export_dataframe_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, encoding="utf-8-sig")


def export_dataframe_excel(df: pd.DataFrame, path: Path) -> None:
    df.to_excel(path, index=False)


def export_figure_png(figure, path: Path, dpi: int = 150) -> None:
    figure.savefig(path, dpi=dpi, bbox_inches="tight")
