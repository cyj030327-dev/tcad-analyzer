import numpy as np
import pytest

from tcad_analyzer.extraction.config import ExtractionConfig
from tcad_analyzer.extraction.errors import ExtractionError
from tcad_analyzer.extraction.ss import extract_ss


def test_ss_recovers_known_value_on_pure_log_linear_curve():
    ss_target_mv = 80.0
    s_thermal = (ss_target_mv / 1000.0) / np.log(10)
    vg = np.linspace(-0.2, 0.6, 401)
    id_ = 1e-13 * np.exp((vg - 0.4) / s_thermal)

    ss_value, diag = extract_ss(vg, id_, ExtractionConfig())

    assert ss_value == pytest.approx(ss_target_mv, rel=0.02)
    assert diag["r2"] > 0.999
    assert diag["low_confidence"] is False


def test_ss_respects_manual_vg_range():
    ss_target_mv = 80.0
    s_thermal = (ss_target_mv / 1000.0) / np.log(10)
    vg = np.linspace(-0.2, 0.6, 401)
    id_ = 1e-13 * np.exp((vg - 0.4) / s_thermal)

    config = ExtractionConfig(ss_vg_range=(-0.1, 0.1))
    ss_value, diag = extract_ss(vg, id_, config)

    assert ss_value == pytest.approx(ss_target_mv, rel=0.02)
    assert diag["vg_range"][0] >= -0.1 - 1e-9
    assert diag["vg_range"][1] <= 0.1 + 1e-9


def test_ss_raises_when_no_positive_current():
    vg = np.linspace(-0.2, 0.6, 50)
    id_ = np.zeros_like(vg)

    with pytest.raises(ExtractionError):
        extract_ss(vg, id_, ExtractionConfig())


def test_ss_flags_low_confidence_on_noisy_flat_region():
    # 진짜 로그-선형 구간이 없는(거의 평평한 잡음) 곡선은 낮은 R^2로 표시돼야 한다
    rng = np.random.default_rng(0)
    vg = np.linspace(-0.2, 0.6, 60)
    id_ = np.abs(rng.normal(1e-14, 1e-15, size=vg.shape))

    ss_value, diag = extract_ss(vg, id_, ExtractionConfig())

    assert diag["r2"] < 0.98
    assert diag["low_confidence"] is True
