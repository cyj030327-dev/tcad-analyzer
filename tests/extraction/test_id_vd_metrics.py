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
