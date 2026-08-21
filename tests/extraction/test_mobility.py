import numpy as np
import pytest

from tcad_analyzer.extraction.config import ExtractionConfig
from tcad_analyzer.extraction.errors import ExtractionError
from tcad_analyzer.extraction.mobility import extract_mobility_saturation, resolve_cox_f_cm2
from tcad_analyzer.models import DeviceMeta, Polarity

W_UM = 10.0
L_UM = 1.0
COX = 3.45e-8  # F/cm^2 (~100nm SiO2 근사)
MU_TRUE = 10.0  # cm^2/V*s
VTH = 2.0


def _saturation_curve(vg: np.ndarray, cox: float) -> np.ndarray:
    w_cm = W_UM * 1e-4
    l_cm = L_UM * 1e-4
    return (w_cm * cox * MU_TRUE) / (2 * l_cm) * np.clip(vg - VTH, 0, None) ** 2


def test_extract_mobility_recovers_known_value_with_direct_cox():
    vg = np.linspace(3.0, 20.0, 100)  # Vth(2V)보다 위에서만
    id_ = _saturation_curve(vg, COX)
    device = DeviceMeta(device_id="N", polarity=Polarity.NMOS, width_um=W_UM, length_um=L_UM)
    config = ExtractionConfig(mobility_cox_F_cm2=COX)

    mu = extract_mobility_saturation(vg, id_, config, device)

    assert mu == pytest.approx(MU_TRUE, rel=1e-6)


def test_extract_mobility_recovers_known_value_with_thickness_and_permittivity():
    thickness_nm = 100.0
    eps_r = 3.9
    eps0 = 8.854e-14
    cox_from_thickness = eps0 * eps_r / (thickness_nm * 1e-7)

    vg = np.linspace(3.0, 20.0, 100)
    id_ = _saturation_curve(vg, cox_from_thickness)
    device = DeviceMeta(device_id="N", polarity=Polarity.NMOS, width_um=W_UM, length_um=L_UM)
    config = ExtractionConfig(mobility_oxide_thickness_nm=thickness_nm, mobility_oxide_rel_permittivity=eps_r)

    assert resolve_cox_f_cm2(config) == pytest.approx(cox_from_thickness, rel=1e-9)
    mu = extract_mobility_saturation(vg, id_, config, device)
    assert mu == pytest.approx(MU_TRUE, rel=1e-6)


def test_direct_cox_takes_priority_over_thickness():
    config = ExtractionConfig(
        mobility_cox_F_cm2=1e-8, mobility_oxide_thickness_nm=50, mobility_oxide_rel_permittivity=20
    )
    assert resolve_cox_f_cm2(config) == 1e-8


def test_resolve_cox_none_when_nothing_configured():
    assert resolve_cox_f_cm2(ExtractionConfig()) is None


def test_extract_mobility_raises_when_cox_not_configured():
    vg = np.linspace(3.0, 20.0, 50)
    id_ = _saturation_curve(vg, COX)
    device = DeviceMeta(device_id="N", polarity=Polarity.NMOS, width_um=W_UM, length_um=L_UM)
    with pytest.raises(ExtractionError):
        extract_mobility_saturation(vg, id_, ExtractionConfig(), device)


def test_extract_mobility_raises_when_wl_missing():
    vg = np.linspace(3.0, 20.0, 50)
    id_ = _saturation_curve(vg, COX)
    device = DeviceMeta(device_id="N", polarity=Polarity.NMOS)  # W/L 없음
    config = ExtractionConfig(mobility_cox_F_cm2=COX)
    with pytest.raises(ExtractionError):
        extract_mobility_saturation(vg, id_, config, device)


def test_extract_mobility_raises_on_insufficient_points():
    vg = np.array([5.0, 6.0])
    id_ = _saturation_curve(vg, COX)
    device = DeviceMeta(device_id="N", polarity=Polarity.NMOS, width_um=W_UM, length_um=L_UM)
    config = ExtractionConfig(mobility_cox_F_cm2=COX)
    with pytest.raises(ExtractionError):
        extract_mobility_saturation(vg, id_, config, device)
