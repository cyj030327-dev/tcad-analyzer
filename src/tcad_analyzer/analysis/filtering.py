"""목표 범위 안에 드는 split만 걸러내는 필터.

'최적 소자 추천'(ranking.py)이 순위를 매기는 것과 달리, 이건 단순히 "이 조건을
만족하는 것만 보여줘"라는 요청에 답한다. 예: Vth_CC가 0.35~0.45V 안에 들고
SS가 100mV/dec 이하인 split만.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import pandas as pd

from ..models import ExtractedParameter
from .ranking import build_split_metric_table


def filter_by_ranges(
    params: List[ExtractedParameter], criteria: Dict[str, Tuple[float, float]]
) -> pd.DataFrame:
    """criteria: {파라미터명: (최소값, 최대값)}.

    각 split의 해당 파라미터 평균값이 지정된 모든 조건의 [최소,최대] 범위(양끝 포함)에
    전부 들어오는 split만 남긴 표를 반환한다. 표의 컬럼은 criteria에 쓰인 파라미터들이고,
    행은 조건을 만족하는 split_label이다. 조건에 쓰인 파라미터가 데이터에 아예 없으면
    그 조건은 항상 불만족으로 처리되어(=결과 없음) 조용히 무시되지 않는다.
    """
    if not criteria:
        return pd.DataFrame()

    metric_names = list(criteria.keys())
    table = build_split_metric_table(params, metric_names)
    if table.empty:
        return table

    mask = pd.Series(True, index=table.index)
    for name, (lo, hi) in criteria.items():
        lo, hi = min(lo, hi), max(lo, hi)
        if name not in table.columns:
            mask &= False
            continue
        mask &= table[name].between(lo, hi)

    return table[mask]
