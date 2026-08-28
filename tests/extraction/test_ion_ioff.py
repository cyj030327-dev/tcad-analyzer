import math

import numpy as np
import pytest

from tcad_analyzer.extraction.config import ExtractionConfig
from tcad_analyzer.extraction.errors import ExtractionError
from tcad_analyzer.extraction.ion_ioff import extract_ion_ioff
from tcad_analyzer.models import DeviceMeta, Polarity

VG = np.array([-0.2, 0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2])
ID = np.array([1e-14, 1e-13, 1e-12, 1e-10, 1e-8, 1e-6, 1e-4, 1e-2])


def test_nmos_default_uses_max_vg_for_ion_min_for_ioff():
    device = DeviceMeta(device_id="n", polarity=Polarity.NMOS)
    ion, ioff, ratio = extract_ion_ioff(VG, ID, ExtractionConfig(), device)

    assert ion == pytest.approx(1e-2)
    assert ioff == pytest.approx(1e-14)
    assert ratio == pytest.approx(1e-2 / 1e-14)


def test_pmos_default_uses_min_vg_for_ion_max_for_ioff():
    device = DeviceMeta(device_id="p", polarity=Polarity.PMOS)
    ion, ioff, ratio = extract_ion_ioff(VG, ID, ExtractionConfig(), device)

    assert ion == pytest.approx(1e-14)
    assert ioff == pytest.approx(1e-2)


def test_explicit_ion_ioff_vg_override():
    device = DeviceMeta(device_id="n", polarity=Polarity.NMOS)
    config = ExtractionConfig(ion_vg=0.6, ioff_vg=0.0)

    ion, ioff, ratio = extract_ion_ioff(VG, ID, config, device)

    assert ion == pytest.approx(1e-8)
    assert ioff == pytest.approx(1e-13)


def test_ratio_is_infinite_when_ioff_is_zero():
    # Ioff가 정확히 0으로 측정되면 비율은 수학적으로 무한대다 — 실패시키지 않고 그 자체를
    # 값으로 낸다("항상 값이 나온다"는 방향으로 설계 변경, 안 되는 걸 억지로 그럴듯한
    # 가짜 숫자로 꾸미는 게 아니라 정직하게 inf로 표시).
    vg = np.array([0.0, 1.0])
    id_ = np.array([0.0, 1e-3])
    device = DeviceMeta(device_id="n", polarity=Polarity.NMOS)

    ion, ioff, ratio = extract_ion_ioff(vg, id_, ExtractionConfig(), device)

    assert ioff == 0.0
    assert ion == pytest.approx(1e-3)
    assert math.isinf(ratio)


def test_raises_when_fewer_than_two_points():
    device = DeviceMeta(device_id="n", polarity=Polarity.NMOS)
    with pytest.raises(ExtractionError):
        extract_ion_ioff(np.array([0.0]), np.array([1e-3]), ExtractionConfig(), device)
