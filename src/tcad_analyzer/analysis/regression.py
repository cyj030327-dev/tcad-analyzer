"""여러 공정변수를 동시에 넣어 지표를 설명하는 다중선형회귀.

Pearson r 기반 민감도(sensitivity.py)는 변수 하나씩 따로 보기 때문에, 변수들이 서로
얽혀서 같이 움직이면(예: DOE에서 Nd를 올릴 때 Nta도 같이 올라가게 설계됐다면) 한 변수의
"진짜" 영향과 다른 변수 때문에 생기는 "덤" 효과를 구분하지 못한다. 다중회귀는 나머지
변수를 고정한 채 이 변수 하나만 바뀌면 지표가 얼마나 바뀌는지(=순수 영향)를 추정한다.

표준화 회귀계수(beta): 변수마다 단위/스케일이 다르므로(예: Nd는 1e13~1e17, Tigzo는
0.01~0.05), 원래 스케일의 계수만으로는 "어떤 변수가 더 중요한지" 비교할 수 없다. 그래서
각 변수를 평균 0·표준편차 1로 표준화(z-score)한 뒤 회귀해서 나온 계수로 중요도를
비교한다 — 절댓값이 클수록 그 변수가 지표를 더 많이 흔든다는 뜻이다. Pearson r과 달리
[-1, 1]로 딱 정해진 범위는 아니다(변수끼리 강하게 얽혀 있으면 1을 넘을 수도 있다).

같은 모델의 원래 스케일 계수는 예측(what-if: "이 조건을 넣으면 값이 대략 얼마?")에 쓴다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..models import ExtractedParameter
from .sensitivity import build_sensitivity_table, numeric_attribute_names, relationship_strength


@dataclass
class RegressionResult:
    metric: str
    attribute_names: List[str]  # 실제로 모델에 들어간 변수(상수인 변수는 제외됨)
    intercept: float  # 원래 스케일 절편
    coefficients: Dict[str, float]  # 원래 스케일 계수(예측용)
    standardized_coefficients: Dict[str, float]  # 표준화 계수(중요도 비교용)
    r_squared: float
    n: int
    attribute_ranges: Dict[str, Tuple[float, float]] = field(default_factory=dict)  # 예측 입력 참고용

    def predict(self, values: Dict[str, float]) -> float:
        """what-if 예측. 모델에 쓰인 변수 전부에 값을 넣어야 한다."""
        missing = [a for a in self.attribute_names if a not in values]
        if missing:
            raise ValueError(f"다음 변수 값이 필요합니다: {', '.join(missing)}")
        y = self.intercept
        for name in self.attribute_names:
            y += self.coefficients[name] * values[name]
        return float(y)

    def ranked_attributes(self) -> List[str]:
        """표준화 계수 절댓값이 큰 순서로 변수 이름을 정렬."""
        return sorted(self.attribute_names, key=lambda a: abs(self.standardized_coefficients[a]), reverse=True)


def fit_multivariate_model(
    params: List[ExtractedParameter], metric: str, attribute_names: Optional[List[str]] = None
) -> Optional[RegressionResult]:
    """지표 하나를 여러 공정변수로 설명하는 다중선형회귀.

    데이터가 모델을 세우기에 부족하거나(자유도 부족), 유효한 변수가 하나도 없으면 None을
    반환한다 — 회귀 자체가 수학적으로 성립하지 않는 경우까지 억지로 숫자를 만들지는 않는다
    (다른 추출 함수들의 "안 되는 건 안 되는 대로 둔다" 원칙과 동일).
    """
    if attribute_names is None:
        attribute_names = numeric_attribute_names(params)
    if not attribute_names:
        return None

    table = build_sensitivity_table(params, [metric])
    if table.empty or metric not in table.columns:
        return None

    cols = [a for a in attribute_names if a in table.columns]
    if not cols:
        return None
    sub = table[cols + [metric]].dropna()
    # 값이 전혀 안 변하는(상수인) 변수는 표준화(0으로 나누기)가 안 되니 회귀에서 뺀다
    cols = [c for c in cols if sub[c].nunique() >= 2]
    if not cols or sub[metric].nunique() < 2:
        return None
    sub = sub[cols + [metric]]
    n = len(sub)
    if n < len(cols) + 2:  # 변수 개수 + 절편 + 최소 자유도 1
        return None

    x = sub[cols].to_numpy(dtype=float)
    y = sub[metric].to_numpy(dtype=float)

    x_mean = x.mean(axis=0)
    x_std = x.std(axis=0, ddof=0)
    x_z = (x - x_mean) / x_std

    y_mean = y.mean()
    y_std = y.std(ddof=0)
    y_z = (y - y_mean) / y_std

    beta_z, *_ = np.linalg.lstsq(x_z, y_z, rcond=None)
    standardized_coefficients = {name: float(b) for name, b in zip(cols, beta_z)}

    # 원래 스케일 계수는 raw 데이터로 lstsq를 다시 푸는 대신, 표준화 계수에서 대수적으로
    # 역산한다. 공정변수들끼리 스케일이 극단적으로 다르면(예: Nd~1e17 vs Tigzo~0.03)
    # raw 스케일 설계행렬의 조건수가 매우 커져서 lstsq가 수치적으로 불안정한 해를 내놓을
    # 수 있다(실제로 훈련 데이터에서조차 R²가 음수로 나오는 버그가 있었다 — 정상적인
    # 절편 포함 OLS라면 훈련 R²는 항상 0 이상이어야 하므로, 음수가 나온다는 것 자체가
    # 수치 불안정성의 신호였다). 반면 표준화된 쪽은 모든 변수가 비슷한 스케일(평균 0,
    # 표준편차 1)이라 훨씬 안정적이고, 두 표현은 수학적으로 동일한 모델이므로 여기서
    # 되돌려도 정확하다.
    coefficients = {name: float(y_std * b / s) for name, b, s in zip(cols, beta_z, x_std)}
    intercept = float(y_mean - sum(coefficients[name] * m for name, m in zip(cols, x_mean)))

    pred = intercept + x @ np.array([coefficients[name] for name in cols])
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y_mean) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0

    attribute_ranges = {name: (float(sub[name].min()), float(sub[name].max())) for name in cols}

    return RegressionResult(
        metric=metric,
        attribute_names=cols,
        intercept=intercept,
        coefficients=coefficients,
        standardized_coefficients=standardized_coefficients,
        r_squared=r_squared,
        n=n,
        attribute_ranges=attribute_ranges,
    )


def describe_regression_effect(attribute: str, metric: str, standardized_coef: float) -> str:
    """"다른 변수를 고정하면, Nd가 커질수록 Vth도 커지는 중간 정도의 순수한 영향을
    줍니다" 같은 문장으로 변환. describe_relationship과 달리 "다른 변수를 고정했을 때"라는
    조건을 명시해, 단순 상관관계(sensitivity.py)와 혼동하지 않게 한다.
    """
    if abs(standardized_coef) < 0.1:
        return f"다른 변수를 고정하면 {attribute}는 {metric}에 거의 영향이 없어 보입니다(표준화 계수={standardized_coef:.2f})."
    direction = f"{attribute}가 커질수록 {metric}도 같이 커지는" if standardized_coef > 0 else f"{attribute}가 커질수록 {metric}은(는) 반대로 작아지는"
    strength = relationship_strength(standardized_coef)
    return f"다른 변수를 고정하면, {direction} {strength} 순수한 영향을 줍니다(표준화 계수={standardized_coef:.2f})."


def build_regression_summary(
    params: List[ExtractedParameter], metric_names: List[str]
) -> pd.DataFrame:
    """지표별로 다중회귀 모델을 만들어, 표준화 계수 절댓값이 큰 변수 순으로 정리한 표.

    compute_sensitivity_summary(단순 상관)와 짝을 이루는 "여러 변수를 같이 고려한" 버전.
    """
    columns = ["metric", "attribute", "standardized_coef", "r_squared", "n", "설명"]
    rows = []
    for metric in metric_names:
        result = fit_multivariate_model(params, metric)
        if result is None:
            continue
        for attr in result.ranked_attributes():
            beta = result.standardized_coefficients[attr]
            rows.append(
                {
                    "metric": metric,
                    "attribute": attr,
                    "standardized_coef": beta,
                    "r_squared": result.r_squared,
                    "n": result.n,
                    "설명": describe_regression_effect(attr, metric, beta),
                }
            )
    return pd.DataFrame(rows, columns=columns)
