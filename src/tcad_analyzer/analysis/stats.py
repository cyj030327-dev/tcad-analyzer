"""ExtractedParameter 리스트 -> DataFrame 변환 및 split별 통계 요약."""

from __future__ import annotations

from typing import List

import pandas as pd

from ..models import ExtractedParameter


def to_dataframe(params: List[ExtractedParameter]) -> pd.DataFrame:
    """ExtractedParameter 리스트를 분석/시각화에 쓰기 좋은 long-form DataFrame으로 변환.

    split_label에는 device_id를 포함시켜, 서로 다른 소자가 우연히 같은 공정조건 라벨을
    갖더라도(예: NMOS/PMOS가 같은 온도 split) 비교/랭킹 단계에서 섞이지 않게 한다.
    """
    rows = []
    for p in params:
        rows.append(
            {
                "curve_id": p.curve_id,
                "device_id": p.device.device_id,
                "polarity": p.device.polarity.value,
                "split_label": f"{p.device.device_id}: {p.split.label()}",
                "param_name": p.param_name,
                "value": p.value,
                "unit": p.unit,
                "method": p.method,
            }
        )
    columns = ["curve_id", "device_id", "polarity", "split_label", "param_name", "value", "unit", "method"]
    return pd.DataFrame(rows, columns=columns)


def summarize_by_split(params: List[ExtractedParameter], param_name: str) -> pd.DataFrame:
    """특정 파라미터의 split별 mean/std/min/max/count 요약."""
    df = to_dataframe(params)
    subset = df[df["param_name"] == param_name]
    if subset.empty:
        return pd.DataFrame(columns=["split_label", "mean", "std", "min", "max", "count"])
    grouped = (
        subset.groupby("split_label")["value"]
        .agg(["mean", "std", "min", "max", "count"])
        .reset_index()
    )
    return grouped
