"""Ion, Ioff, Ion/Ioff ratio 추출."""

from __future__ import annotations

from typing import Tuple

import numpy as np

from ..models import DeviceMeta, Polarity
from .config import ExtractionConfig
from .errors import ExtractionError


def extract_ion_ioff(
    vg: np.ndarray, id_: np.ndarray, config: ExtractionConfig, device: DeviceMeta
) -> Tuple[float, float, float]:
    """(Ion, Ioff, Ion/Ioff ratio)를 반환.

    on/off 기준 Vg를 지정하지 않으면 극성에 따라 곡선의 양 끝 Vg를 사용한다:
    NMOS는 Vg 최대값이 on, 최소값이 off. PMOS는 그 반대(Vg가 더 음수일수록 on).
    """
    vg = np.asarray(vg, dtype=float)
    abs_id = np.abs(np.asarray(id_, dtype=float))
    order = np.argsort(vg)
    vg_s = vg[order]
    abs_id_s = abs_id[order]

    if len(vg_s) < 2:
        raise ExtractionError("Ion/Ioff 계산을 위한 데이터 포인트가 부족합니다")

    if config.ion_vg is not None:
        ion_vg_point = config.ion_vg
    else:
        ion_vg_point = vg_s[-1] if device.polarity is Polarity.NMOS else vg_s[0]

    if config.ioff_vg is not None:
        ioff_vg_point = config.ioff_vg
    else:
        ioff_vg_point = vg_s[0] if device.polarity is Polarity.NMOS else vg_s[-1]

    ion = float(np.interp(ion_vg_point, vg_s, abs_id_s))
    ioff = float(np.interp(ioff_vg_point, vg_s, abs_id_s))

    if ioff <= 0:
        raise ExtractionError("Ioff가 0 이하라 Ion/Ioff ratio를 계산할 수 없습니다")

    ratio = ion / ioff
    return ion, ioff, ratio
