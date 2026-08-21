"""소자 메타데이터 모델."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Polarity(str, Enum):
    """소자 극성. Vth 부호, |Id| 처리 방향 등에 쓰인다."""

    NMOS = "nmos"
    PMOS = "pmos"

    @property
    def sign(self) -> int:
        """관례상 Vth 부호: NMOS는 양수, PMOS는 음수로 보고하는 규칙에 사용."""
        return 1 if self is Polarity.NMOS else -1


@dataclass
class DeviceMeta:
    """분석 대상 소자 하나를 식별하는 메타데이터."""

    device_id: str
    polarity: Polarity
    width_um: Optional[float] = None
    length_um: Optional[float] = None

    @property
    def wl_ratio(self) -> Optional[float]:
        """W/L 비율. 폭/길이 정보가 모두 있을 때만 계산, 없으면 None(정규화 생략 신호)."""
        if self.width_um and self.length_um:
            return self.width_um / self.length_um
        return None
