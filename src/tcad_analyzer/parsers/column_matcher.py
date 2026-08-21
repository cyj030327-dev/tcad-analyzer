"""변수명(컬럼명)으로부터 Vg/Id/Vd 등 역할을 추천 매칭한다.

Sentaurus는 변수명을 자유 형식으로 쓰기 때문("Gate Voltage", "gate OuterVoltage",
"GateVoltage (V)" 등) 완전 자동 판별은 신뢰할 수 없다. 여기서는 "추천"만 제공하고,
최종 확정은 GUI에서 사용자가 한다.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

# role -> 후보를 찾기 위한 정규식 패턴들 (우선순위 순서).
# DF-ISE 계열 출력은 전극마다 OuterVoltage/InnerVoltage, eCurrent/hCurrent/TotalCurrent처럼
# 컴포넌트별 컬럼이 여러 개 있고 대개 TotalCurrent/OuterVoltage보다 먼저 나열되는 경우가 있어,
# 더 구체적인(Total/Outer) 패턴을 먼저 시도해 엉뚱한 성분(예: 전자 전류만)이 뽑히지 않게 한다.
CANDIDATE_PATTERNS: Dict[str, List[str]] = {
    "Vg": [r"gate.*outer.*volt", r"gate.*volt", r"^v_?g\b", r"\bvg\b"],
    "Id": [r"drain.*total.*current", r"drain.*current", r"^i_?d\b", r"\bid\b"],
    "Vd": [r"drain.*outer.*volt", r"drain.*volt", r"^v_?d\b", r"\bvd\b"],
    "Is": [r"source.*total.*current", r"source.*current", r"^i_?s\b", r"\bis\b"],
    "Vs": [r"source.*outer.*volt", r"source.*volt", r"^v_?s\b", r"\bvs\b"],
}


def suggest_column_roles(variables: List[str]) -> Dict[str, Optional[str]]:
    """각 role에 대해 가장 그럴듯한 컬럼명을 추천. 없으면 None.

    같은 컬럼이 여러 role에 동시에 배정되지 않도록, 앞선 role에서 이미 선택된
    컬럼은 뒤 role의 후보에서 제외한다.
    """
    suggestions: Dict[str, Optional[str]] = {}
    used: set[str] = set()

    for role, patterns in CANDIDATE_PATTERNS.items():
        match: Optional[str] = None
        for pattern in patterns:
            regex = re.compile(pattern, re.IGNORECASE)
            for var in variables:
                if var in used:
                    continue
                if regex.search(var):
                    match = var
                    break
            if match:
                break
        suggestions[role] = match
        if match:
            used.add(match)

    return suggestions
