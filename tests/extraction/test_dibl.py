import numpy as np
import pytest

from tcad_analyzer.extraction.config import ExtractionConfig
from tcad_analyzer.extraction.dibl import extract_dibl, find_dibl_pair
from tcad_analyzer.extraction.errors import ExtractionError
from tcad_analyzer.models import Curve, CurveType, DeviceMeta, Polarity, SplitCondition


def _make_curve(curve_id, vth, vd, i0=1e-12, tau=0.05):
    vg = np.linspace(-0.2, 1.2, 1401)
    id_ = i0 * np.exp((vg - vth) / tau)
    device = DeviceMeta(device_id="n", polarity=Polarity.NMOS)
    split = SplitCondition(split_name="s")
    return Curve(curve_id=curve_id, curve_type=CurveType.ID_VG, device=device, split=split, vg=vg, id_=id_, vd=vd)


def test_extract_dibl_matches_known_shift():
    vth_lin, vth_sat = 0.42, 0.38
    vd_lin, vd_sat = 0.05, 1.0
    curve_lin = _make_curve("lin", vth_lin, vd_lin)
    curve_sat = _make_curve("sat", vth_sat, vd_sat)

    config = ExtractionConfig(cc_current_ref=1e-12, cc_normalize_by_wl=False)
    dibl = extract_dibl(curve_lin, curve_sat, config, curve_lin.device)

    expected = (vth_lin - vth_sat) / (vd_sat - vd_lin) * 1000.0
    assert dibl == pytest.approx(expected, rel=0.02)


def test_extract_dibl_raises_when_vd_equal():
    curve_lin = _make_curve("lin", 0.4, 0.5)
    curve_sat = _make_curve("sat", 0.38, 0.5)
    config = ExtractionConfig(cc_current_ref=1e-12, cc_normalize_by_wl=False)

    with pytest.raises(ExtractionError):
        extract_dibl(curve_lin, curve_sat, config, curve_lin.device)


def test_find_dibl_pair_uses_observed_min_max_by_default():
    curves = [_make_curve("a", 0.4, 0.05), _make_curve("b", 0.4, 1.0), _make_curve("c", 0.4, 0.6)]
    config = ExtractionConfig()

    pair = find_dibl_pair(curves, config)

    assert pair is not None
    lo, hi = pair
    assert lo.curve_id == "a"
    assert hi.curve_id == "b"


def test_find_dibl_pair_uses_configured_targets():
    curves = [_make_curve("a", 0.4, 0.05), _make_curve("b", 0.4, 1.0), _make_curve("c", 0.4, 0.6)]
    config = ExtractionConfig(dibl_vd_pair=(0.55, 0.95))

    pair = find_dibl_pair(curves, config)

    assert pair is not None
    lo, hi = pair
    assert lo.curve_id == "c"
    assert hi.curve_id == "b"


def test_find_dibl_pair_returns_none_when_insufficient_curves():
    curves = [_make_curve("a", 0.4, 0.05)]
    assert find_dibl_pair(curves, ExtractionConfig()) is None
