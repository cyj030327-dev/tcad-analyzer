"""추출/비교 결과 모델."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, TYPE_CHECKING

from .device import DeviceMeta
from .split import SplitCondition

if TYPE_CHECKING:
    import pandas as pd


@dataclass
class ExtractedParameter:
    """curve 하나(또는 외부 테이블 행 하나)에서 뽑아낸 파라미터 값 하나."""

    curve_id: Optional[str]
    device: DeviceMeta
    split: SplitCondition
    param_name: str  # 예: "Vth_CC", "Vth_SD", "SS", "Ion", "Ioff", "Ion_Ioff_ratio", "Ron", "gm", "gds", "DIBL"
    value: float
    unit: str
    method: str  # 예: "constant_current", "linear_extrapolation", "imported"
    method_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComparisonResult:
    """split별 비교 통계 결과."""

    param_name: str
    per_split_stats: "pd.DataFrame"
    raw_values: "pd.DataFrame"
