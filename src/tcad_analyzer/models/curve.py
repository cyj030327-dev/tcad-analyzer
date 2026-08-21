"""소자 특성 곡선(curve) 모델. Id-Vg, Id-Vd를 공통 구조로 표현한다."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Iterator, List, Optional

import numpy as np

from .device import DeviceMeta
from .split import SplitCondition


class CurveType(str, Enum):
    ID_VG = "id_vg"
    ID_VD = "id_vd"


@dataclass
class Curve:
    """하나의 측정/시뮬레이션 곡선.

    Id-Vg curve: vg가 스윕 변수, vd는 고정 bias(스칼라).
    Id-Vd curve: vd_array가 스윕 변수, vg는 고정 bias로 vg_bias에 담는다
                 (필드명은 vg로 통일하되 이 경우 스칼라 하나만 채워 넣는 방식 대신
                  vg는 항상 게이트 전압 배열/스칼라를 나타내도록 사용처에서 관례를 지킨다).
    """

    curve_id: str
    curve_type: CurveType
    device: DeviceMeta
    split: SplitCondition
    vg: np.ndarray
    id_: np.ndarray
    vd: Optional[float] = None
    vd_array: Optional[np.ndarray] = None
    source_file: Optional[Path] = None
    raw_variables: List[str] = field(default_factory=list)
    node_id: Optional[str] = None

    def __post_init__(self) -> None:
        self.vg = np.asarray(self.vg, dtype=float)
        self.id_ = np.asarray(self.id_, dtype=float)
        if self.vd_array is not None:
            self.vd_array = np.asarray(self.vd_array, dtype=float)
        if self.vg.shape != self.id_.shape:
            raise ValueError(
                f"Curve '{self.curve_id}': vg({self.vg.shape})와 id({self.id_.shape}) 길이가 다릅니다"
            )


class CurveCollection:
    """Curve들의 컬렉션. 필터링/split별 그룹핑을 제공."""

    def __init__(self, curves: Optional[List[Curve]] = None):
        self.curves: List[Curve] = list(curves) if curves else []

    def add(self, curve: Curve) -> None:
        self.curves.append(curve)

    def __len__(self) -> int:
        return len(self.curves)

    def __iter__(self) -> Iterator[Curve]:
        return iter(self.curves)

    def filter(
        self,
        curve_type: Optional[CurveType] = None,
        device_id: Optional[str] = None,
    ) -> "CurveCollection":
        result = self.curves
        if curve_type is not None:
            result = [c for c in result if c.curve_type == curve_type]
        if device_id is not None:
            result = [c for c in result if c.device.device_id == device_id]
        return CurveCollection(result)

    def group_by_split(self) -> Dict[tuple, List[Curve]]:
        """split 조건별로 묶는다. device_id를 키에 포함시켜, 서로 다른 소자(NMOS/PMOS 등)가
        우연히 같은 split 라벨(예: 동일 온도)을 가지더라도 하나의 그룹으로 섞이지 않게 한다."""
        groups: Dict[tuple, List[Curve]] = {}
        for c in self.curves:
            key = (c.device.device_id, c.split.key())
            groups.setdefault(key, []).append(c)
        return groups
