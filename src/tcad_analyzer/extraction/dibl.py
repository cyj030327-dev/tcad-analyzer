"""DIBL(Drain-Induced Barrier Lowering) 추출.

서로 다른 두 Vd(선형영역 Vd_lin, 포화영역 Vd_sat)에서 각각 CC 방식으로 Vth를 구해
DIBL = (Vth_lin - Vth_sat) / (Vd_sat - Vd_lin) [mV/V]를 계산한다.
같은 split 안에 Vd가 다른 두 Id-Vg curve가 모두 있어야 계산 가능하다.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from ..models import Curve, DeviceMeta
from .config import ExtractionConfig
from .errors import ExtractionError
from .vth import extract_vth_constant_current


def find_dibl_pair(curves: List[Curve], config: ExtractionConfig) -> Optional[Tuple[Curve, Curve]]:
    """같은 split의 Id-Vg curve 목록에서 DIBL 계산에 쓸 (저Vd curve, 고Vd curve) 쌍을 찾는다.

    config.dibl_vd_pair가 지정돼 있으면 그 값에 가장 가까운 Vd를 가진 curve들을 사용하고,
    없으면 관측된 Vd 중 최소/최대값을 사용한다. curve가 1개 이하이거나 Vd가 모두 같으면 None.
    """
    candidates = [c for c in curves if c.vd is not None]
    if len(candidates) < 2:
        return None

    if config.dibl_vd_pair is not None:
        target_lo, target_hi = sorted(config.dibl_vd_pair)
        lo_curve = min(candidates, key=lambda c: abs(c.vd - target_lo))
        hi_curve = min(candidates, key=lambda c: abs(c.vd - target_hi))
    else:
        lo_curve = min(candidates, key=lambda c: c.vd)
        hi_curve = max(candidates, key=lambda c: c.vd)

    if lo_curve.vd == hi_curve.vd:
        return None
    if lo_curve.vd > hi_curve.vd:
        lo_curve, hi_curve = hi_curve, lo_curve
    return lo_curve, hi_curve


def extract_dibl(curve_lin: Curve, curve_sat: Curve, config: ExtractionConfig, device: DeviceMeta) -> float:
    if curve_lin.vd is None or curve_sat.vd is None:
        raise ExtractionError("DIBL 계산에는 각 curve의 Vd 값이 필요합니다")
    if curve_lin.vd == curve_sat.vd:
        raise ExtractionError("DIBL 계산을 위한 두 Vd 조건이 동일합니다")

    vth_lin = extract_vth_constant_current(curve_lin.vg, curve_lin.id_, config, device)
    vth_sat = extract_vth_constant_current(curve_sat.vg, curve_sat.id_, config, device)

    dibl_v_per_v = (vth_lin - vth_sat) / (curve_sat.vd - curve_lin.vd)
    return float(dibl_v_per_v * 1000.0)  # V/V -> mV/V
