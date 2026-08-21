"""공정 조건(split) 모델.

split은 "이 곡선이 어떤 공정 조건 조합에서 나왔는가"를 나타낸다. 사용자마다 스윕하는
공정 변수(온도, 도즈, 산화막 두께 등)가 다르므로 자유 key-value(attributes)로 확장 가능하게
설계한다. gtree.dat가 있으면 attributes가 거기서 자동으로 채워지고, 없으면 GUI에서 수동 입력한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


@dataclass
class SplitCondition:
    lot: Optional[str] = None
    split_name: str = "default"
    attributes: Dict[str, str] = field(default_factory=dict)

    def key(self) -> Tuple:
        """dict key/groupby에 쓸 수 있는 해시 가능한 정규화된 튜플."""
        return (self.lot, self.split_name, tuple(sorted(self.attributes.items())))

    def label(self) -> str:
        """비교 화면 등에 표시할 사람이 읽기 쉬운 문자열."""
        parts = []
        if self.lot:
            parts.append(f"Lot={self.lot}")
        if self.split_name and self.split_name != "default":
            parts.append(self.split_name)
        parts.extend(f"{k}={v}" for k, v in sorted(self.attributes.items()))
        return ", ".join(parts) if parts else "default"
