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


def test_raises_when_ioff_is_zero():
    vg = np.array([0.0, 1.0])
    id_ = np.array([0.0, 1e-3])
    device = DeviceMeta(device_id="n", polarity=Polarity.NMOS)

    with pytest.raises(ExtractionError):
        extract_ion_ioff(vg, id_, ExtractionConfig(), device)
