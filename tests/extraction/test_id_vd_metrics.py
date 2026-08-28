import numpy as np
import pytest

from tcad_analyzer.extraction.config import ExtractionConfig
from tcad_analyzer.extraction.errors import ExtractionError
from tcad_analyzer.extraction.id_vd_metrics import extract_gds, extract_ron


def test_ron_recovers_known_linear_slope():
    slope = 2e-3  # A/V
    vd = np.linspace(0, 1.2, 121)
    id_ = slope * vd

    config = ExtractionConfig(ron_vd_range=(0.0, 0.2))
    ron = extract_ron(vd, id_, config)

    assert ron == pytest.approx(1.0 / slope, rel=1e-6)


def test_ron_default_range_uses_low_vd_region():
    slope_lin = 2e-3
    vd = np.linspace(0, 1.2, 121)
    # 선형영역 이후 살짝 휘어지게(포화 근사) 만들어도 기본 저Vd 구간만 보면 선형 기울기를 잡아야 한다
    id_ = np.where(vd < 0.3, slope_lin * vd, slope_lin * 0.3 + 0.0001 * (vd - 0.3))

    ron = extract_ron(vd, id_, ExtractionConfig())

    assert ron == pytest.approx(1.0 / slope_lin, rel=0.05)


def test_gds_recovers_known_saturation_slope():
    lam_slope = 5e-6  # A/V, 포화영역 기울기(출력컨덕턴스)
    vd = np.linspace(0, 1.2, 121)
    id_ = 1e-3 + lam_slope * vd

    config = ExtractionConfig(gds_vd_range=(1.0, 1.2))
    gds = extract_gds(vd, id_, config)

    assert gds == pytest.approx(lam_slope, rel=1e-6)


def test_ron_raises_on_insufficient_points():
    vd = np.array([0.0])
    id_ = np.array([0.0])

    with pytest.raises(ExtractionError):
        extract_ron(vd, id_, ExtractionConfig())


def test_ron_falls_back_to_full_data_when_window_has_too_few_points():
    # 지정한 저Vd 구간(0~0.05V) 안에는 점이 하나도 없지만, 전체 데이터로라도 계산해서
    # 값을 낸다 — 구간 안에 데이터가 부족하다고 곧바로 실패시키지 않는다.
    slope = 2e-3
    vd = np.array([0.5, 0.6, 0.7, 0.8])
    id_ = slope * vd

    config = ExtractionConfig(ron_vd_range=(0.0, 0.05))
    ron = extract_ron(vd, id_, config)

    assert ron == pytest.approx(1.0 / slope, rel=1e-6)


def test_ron_is_infinite_when_current_is_perfectly_flat():
    vd = np.linspace(0.0, 1.2, 20)
    id_ = np.full_like(vd, 1e-6)  # Vd가 변해도 전류가 전혀 안 변함

    ron = extract_ron(vd, id_, ExtractionConfig())

    assert np.isinf(ron)


def test_gds_falls_back_to_full_data_when_window_has_too_few_points():
    lam_slope = 5e-6
    vd = np.array([0.1, 0.2, 0.3, 0.4])
    id_ = 1e-3 + lam_slope * vd

    config = ExtractionConfig(gds_vd_range=(10.0, 20.0))  # 데이터 범위 밖 -> 구간 안 점 0개
    gds = extract_gds(vd, id_, config)

    assert gds == pytest.approx(lam_slope, rel=1e-6)
