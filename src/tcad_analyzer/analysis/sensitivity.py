"""split의 공정변수(gtree.dat attributes 등)와 추출된 지표 사이의 민감도(상관관계) 분석.

"Nd를 올리면 Vth가 어떻게 바뀌는가" 같은 질문에 답하기 위한 기능. gtree.dat에서 읽은 split
attribute는 문자열로 저장돼 있으므로, 숫자로 해석 가능한 것만 골라 쓴다(예: split_name처럼
문자 그대로인 값은 제외). 같은 split 안에 curve가 여러 개 있으면(zone 여러 개 등) 지표값은
평균을 사용한다.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..models import ExtractedParameter
from .stats import to_dataframe


def _try_float(value: Optional[str]) -> Optional[float]:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _split_attributes(params: List[ExtractedParameter]) -> Dict[str, Dict[str, str]]:
    """split_label -> {attribute_name: raw_value} 매핑을 만든다."""
    result: Dict[str, Dict[str, str]] = {}
    for p in params:
        label = f"{p.device.device_id}: {p.split.label()}"
        result.setdefault(label, dict(p.split.attributes))
    return result


def numeric_attribute_names(params: List[ExtractedParameter]) -> List[str]:
    """숫자로 해석 가능한 값을 가진 split attribute 이름만 정렬해서 반환."""
    attrs_by_split = _split_attributes(params)
    names = set()
    for attrs in attrs_by_split.values():
        for name, raw in attrs.items():
            if _try_float(raw) is not None:
                names.add(name)
    return sorted(names)


def build_sensitivity_table(params: List[ExtractedParameter], metric_names: List[str]) -> pd.DataFrame:
    """split_label을 행으로, [숫자형 split attribute들] + [지표들]을 열로 갖는 넓은 표.

    한 split에 curve가 여러 개면 지표값은 평균을 사용한다. 요청한 지표가 없는 split은
    해당 칸이 NaN으로 남는다.
    """
    df = to_dataframe(params)
    if df.empty:
        return pd.DataFrame()

    metric_df = df[df["param_name"].isin(metric_names)]
    if metric_df.empty:
        return pd.DataFrame()
    wide = metric_df.pivot_table(index="split_label", columns="param_name", values="value", aggfunc="mean")

    attrs_by_split = _split_attributes(params)
    for name in numeric_attribute_names(params):
        wide[name] = [_try_float(attrs_by_split.get(label, {}).get(name)) for label in wide.index]

    return wide.reset_index()


def relationship_strength(r: float) -> str:
    """|r| 크기를 말로 옮긴다(통계 용어 대신 직관적인 강도 표현)."""
    abs_r = abs(r)
    if abs_r >= 0.7:
        return "강한"
    if abs_r >= 0.4:
        return "중간 정도의"
    if abs_r >= 0.2:
        return "약한"
    return "거의 없는"


def describe_relationship(attribute: str, metric: str, r: Optional[float]) -> str:
    """"Nd가 커질수록 SS도 커지는 강한 경향입니다 (r=0.65)." 같은 사람이 읽는 문장으로 변환.

    r이 None이거나(데이터 부족 등) NaN이면 관계를 판단할 수 없다는 문장을 돌려준다.
    """
    if r is None or r != r:  # r != r -> NaN 체크
        return f"{attribute}와(과) {metric}의 관계를 판단하기엔 데이터가 부족합니다."
    if abs(r) < 0.2:
        return f"{attribute}가 달라져도 {metric}은(는) 뚜렷하게 바뀌지 않는 것 같습니다 (r={r:.2f})."
    direction = f"{attribute}가 커질수록 {metric}도 같이 커지는" if r > 0 else f"{attribute}가 커질수록 {metric}은(는) 반대로 작아지는"
    strength = relationship_strength(r)
    return f"{direction} {strength} 경향입니다 (r={r:.2f})."


def compute_sensitivity_summary(params: List[ExtractedParameter], metric_names: List[str]) -> pd.DataFrame:
    """지표별로 묶어서(지표 하나당 여러 공정변수), 그 안에서는 |r| 내림차순으로 정렬한 요약표.

    "이 지표에는 어떤 공정변수가 가장 큰 영향을 주는가"를 지표 단위로 훑어보기 위함(예:
    SS를 좌우하는 변수 순위, 그다음 Ion을 좌우하는 변수 순위, ...). 데이터가 3개 미만이거나
    값이 전부 같은(=변화가 없어 상관계수가 정의되지 않는) 쌍은 건너뛴다. "설명" 칸에는
    원자료(r, n)와 별개로, 통계를 몰라도 읽을 수 있는 한 줄 해석을 같이 담는다.

    전체를 |r|만으로 한 번에 정렬하면 같은 지표(예: SS)의 결과가 표 여기저기로 흩어져서
    "이 지표는 뭐에 영향을 받는지" 읽기 어려워진다 — 그래서 지표별로 먼저 묶고, 그 안에서만
    영향이 큰 순서로 정렬한다.
    """
    table = build_sensitivity_table(params, metric_names)
    columns = ["metric", "attribute", "pearson_r", "n", "설명"]
    if table.empty:
        return pd.DataFrame(columns=columns)

    attr_names = numeric_attribute_names(params)
    rows = []
    for metric in metric_names:
        if metric not in table.columns:
            continue
        for attr in attr_names:
            if attr not in table.columns:
                continue
            sub = table[[attr, metric]].dropna()
            if len(sub) < 3 or sub[attr].nunique() < 2 or sub[metric].nunique() < 2:
                continue
            r = float(np.corrcoef(sub[attr], sub[metric])[0, 1])
            rows.append(
                {
                    "metric": metric,
                    "attribute": attr,
                    "pearson_r": r,
                    "n": len(sub),
                    "설명": describe_relationship(attr, metric, r),
                }
            )

    result = pd.DataFrame(rows, columns=columns)
    if not result.empty:
        metric_order = {name: i for i, name in enumerate(metric_names)}
        sort_key_metric = result["metric"].map(metric_order)
        sort_key_abs_r = result["pearson_r"].abs()
        result = (
            result.assign(_metric_order=sort_key_metric, _abs_r=sort_key_abs_r)
            .sort_values(["_metric_order", "_abs_r"], ascending=[True, False])
            .drop(columns=["_metric_order", "_abs_r"])
            .reset_index(drop=True)
        )
    return result
