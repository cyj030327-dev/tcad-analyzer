import numpy as np
import pytest

from tcad_analyzer.extraction.config import ExtractionConfig
from tcad_analyzer.extraction.errors import ExtractionError
from tcad_analyzer.extraction.vth import (
    extract_gm_max,
    extract_vth_constant_current,
    extract_vth_linear_extrapolation,
)
from tcad_analyzer.models import DeviceMeta, Polarity


def test_cc_recovers_known_vth_on_pure_exponential_curve():
    vth_true = 0.42
    i0 = 1e-12
    tau = 0.05
    vg = np.linspace(-0.2, 1.2, 1401)
    id_ = i0 * np.exp((vg - vth_true) / tau)

    device = DeviceMeta(device_id="test", polarity=Polarity.NMOS)
    config = ExtractionConfig(cc_current_ref=i0, cc_normalize_by_wl=False)

    vth = extract_vth_constant_current(vg, id_, config, device)

    assert vth == pytest.approx(vth_true, abs=2e-3)


def test_cc_normalizes_by_wl_ratio():
    vth_true = 0.4
    i0 = 1e-12
    tau = 0.05
    vg = np.linspace(-0.2, 1.2, 1401)
    id_ = i0 * np.exp((vg - vth_true) / tau)

    # W/L=2 -> 기준전류가 2배가 되어 더 높은 전류(=더 큰 Vg) 지점에서 Vth를 잡아야 한다
    device = DeviceMeta(device_id="test", polarity=Polarity.NMOS, width_um=2.0, length_um=1.0)
    config = ExtractionConfig(cc_current_ref=i0, cc_normalize_by_wl=True)

    vth = extract_vth_constant_current(vg, id_, config, device)
    expected = vth_true + tau * np.log(2.0)

    assert vth == pytest.approx(expected, abs=2e-3)


def test_cc_extrapolates_above_measured_range_instead_of_failing():
    # "안 되는 건 안 되는 거지만"(2점 미만처럼 진짜 계산 불가능한 경우만 실패), 기준전류가
    # 범위 밖이라는 이유만으로는 실패시키지 않고 가장 가까운 두 점으로 직선을 연장한다.
    vg = np.linspace(-0.2, 1.2, 100)
    id_ = 1e-12 * np.exp((vg - 0.4) / 0.05)

    device = DeviceMeta(device_id="test", polarity=Polarity.NMOS)
    config = ExtractionConfig(cc_current_ref=1.0, cc_normalize_by_wl=False)  # 데이터 최대 전류보다 훨씬 큼

    vth = extract_vth_constant_current(vg, id_, config, device)

    # 더 큰 전류를 요구했으니 외삽 방향도 Vg가 더 커지는 쪽이어야 한다
    assert vth > vg.max()
    assert np.isfinite(vth)


def test_cc_extrapolates_below_measured_range_instead_of_failing():
    vg = np.linspace(-0.2, 1.2, 100)
    id_ = 1e-12 * np.exp((vg - 0.4) / 0.05)

    device = DeviceMeta(device_id="test", polarity=Polarity.NMOS)
    config = ExtractionConfig(cc_current_ref=1e-20, cc_normalize_by_wl=False)  # 데이터 최소 전류보다 훨씬 작음

    vth = extract_vth_constant_current(vg, id_, config, device)

    assert vth < vg.min()
    assert np.isfinite(vth)


def test_cc_raises_when_fewer_than_two_points():
    device = DeviceMeta(device_id="test", polarity=Polarity.NMOS)
    config = ExtractionConfig(cc_current_ref=1e-12, cc_normalize_by_wl=False)

    with pytest.raises(ExtractionError):
        extract_vth_constant_current(np.array([0.0]), np.array([1e-12]), config, device)


def test_linear_extrapolation_recovers_exact_vth_on_pure_linear_curve():
    vth_true = 0.4
    k = 1e-4
    vg = np.linspace(-0.2, 1.2, 1401)
    id_ = k * np.clip(vg - vth_true, 0, None)

    config = ExtractionConfig(le_fit_vg_range=(0.6, 1.0), le_apply_vd_half_correction=False)

    vth = extract_vth_linear_extrapolation(vg, id_, vd=None, config=config)

    assert vth == pytest.approx(vth_true, abs=1e-6)


def test_linear_extrapolation_applies_vd_half_correction():
    vth_true = 0.4
    k = 1e-4
    vg = np.linspace(-0.2, 1.2, 1401)
    id_ = k * np.clip(vg - vth_true, 0, None)

    config = ExtractionConfig(le_fit_vg_range=(0.6, 1.0), le_apply_vd_half_correction=True)

    vth = extract_vth_linear_extrapolation(vg, id_, vd=0.1, config=config)

    assert vth == pytest.approx(vth_true - 0.05, abs=1e-6)


def test_gm_max_matches_known_slope():
    k = 1e-4
    vth_true = 0.4
    vg = np.linspace(-0.2, 1.2, 1401)
    id_ = k * np.clip(vg - vth_true, 0, None)

    gm = extract_gm_max(vg, id_)

    assert gm == pytest.approx(k, rel=1e-3)


def test_linear_extrapolation_works_with_exactly_two_points():
    # 최소 요구치를 3개에서 2개로 낮췄다 — 2개면 직선 하나는 정의할 수 있으므로 성공해야 한다
    vg = np.array([0.5, 0.6])
    id_ = np.array([1e-5, 2e-5])

    vth = extract_vth_linear_extrapolation(vg, id_, vd=None, config=ExtractionConfig())

    assert np.isfinite(vth)


def test_linear_extrapolation_raises_with_single_point():
    with pytest.raises(ExtractionError):
        extract_vth_linear_extrapolation(
            np.array([0.5]), np.array([1e-5]), vd=None, config=ExtractionConfig()
        )


def test_gm_max_works_with_exactly_two_points():
    gm = extract_gm_max(np.array([0.5, 0.6]), np.array([1e-5, 2e-5]))
    assert gm == pytest.approx(1e-4, rel=1e-6)


def test_gm_max_raises_with_single_point():
    with pytest.raises(ExtractionError):
        extract_gm_max(np.array([0.5]), np.array([1e-5]))
