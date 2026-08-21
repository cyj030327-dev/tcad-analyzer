"""임포트된 곡선이 실제로 '스윕'인지 가볍게 검사한다.

Sentaurus Workbench의 sdevice Solve 블록이 여러 단계(drain ramp -> transient,
NewCurrentPrefix로 이름 바꾼 뒤 gate ramp 등)로 구성된 경우, 노드 하나가 여러 .plt를
만들어내는데 그중 일부(예: 첫 ramp의 transient 결과)는 분석하려는 스윕(예: Id-Vg)이
아닐 수 있다. 파일명 규칙(예: "IdVg_" 접두사)에 의존하지 않고 데이터 자체로도 판별할
수 있도록, 스윕 변수 범위가 너무 좁거나 포인트가 너무 적으면 경고를 낸다.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np


def check_sweep(x: np.ndarray, min_points: int = 10, min_span: float = 0.5) -> Tuple[bool, str]:
    """(정상 스윕으로 보이는가, 사유) 반환. 문제 없으면 사유는 빈 문자열."""
    x = np.asarray(x, dtype=float)
    if x.size < min_points:
        return False, f"데이터 포인트가 너무 적습니다 ({x.size}개, 최소 {min_points}개 필요)"
    span = float(x.max() - x.min())
    if span < min_span:
        return False, f"스윕 변수 범위가 너무 좁습니다 ({span:.3f}V, 최소 {min_span}V 필요) — 다른 종류의 곡선(transient 등)일 수 있습니다"
    return True, ""
