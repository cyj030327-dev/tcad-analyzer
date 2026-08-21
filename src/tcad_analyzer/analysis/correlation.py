"""파라미터간 상관관계 분석 (예: Vth vs SS)."""

from __future__ import annotations

from typing import List

import pandas as pd

from ..models import ExtractedParameter
from .stats import to_dataframe


def compute_correlation(params: List[ExtractedParameter], param_x: str, param_y: str) -> pd.DataFrame:
    """curve_id 기준으로 두 파라미터를 join한 long-form DataFrame(산점도용) + pearson_r(.attrs)을 반환.

    curve_id가 없는 값(예: DIBL, 외부 CSV에서 온 값)이 섞여 있으면 split_label 기준으로 폴백해서 join한다.
    param_x와 param_y가 같은 파라미터일 수도 있으므로(자기 자신과의 상관관계, 사실상 r=1),
    merge 시 컬럼명이 우연히 겹쳐 pandas가 자동으로 접미사(_x/_y)를 붙이는 것에 의존하지 않도록
    항상 내부적으로 고유한 임시 컬럼명을 쓰고 마지막에 param_x/param_y로 되돌린다.
    """
    df = to_dataframe(params)
    x_rows = df[df["param_name"] == param_x][["curve_id", "split_label", "value"]]
    y_rows = df[df["param_name"] == param_y][["curve_id", "split_label", "value"]]

    use_curve_id = (
        not x_rows.empty
        and not y_rows.empty
        and x_rows["curve_id"].notna().all()
        and y_rows["curve_id"].notna().all()
    )
    join_key = "curve_id" if use_curve_id else "split_label"

    x_df = x_rows[[join_key, "value"]].rename(columns={"value": "__value_x__"})
    y_df = y_rows[[join_key, "value"]].rename(columns={"value": "__value_y__"})
    merged = pd.merge(x_df, y_df, on=join_key)

    pearson_r = merged["__value_x__"].corr(merged["__value_y__"]) if len(merged) >= 2 else None

    if param_x == param_y:
        # 같은 파라미터끼리 비교하는 경우 결과 컬럼이 하나로 합쳐지는 것이 자연스럽다(값이 항상 동일).
        merged = merged[[join_key, "__value_x__"]].rename(columns={"__value_x__": param_x})
    else:
        merged = merged.rename(columns={"__value_x__": param_x, "__value_y__": param_y})

    merged.attrs["pearson_r"] = pearson_r
    return merged
