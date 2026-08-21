import numpy as np

from tcad_analyzer.parsers.sweep_check import check_sweep


def test_valid_sweep_passes():
    vg = np.linspace(0, 20, 201)
    ok, reason = check_sweep(vg)
    assert ok is True
    assert reason == ""


def test_too_few_points_fails():
    vg = np.array([0.0, 0.1, 0.2])
    ok, reason = check_sweep(vg)
    assert ok is False
    assert "포인트" in reason


def test_narrow_span_fails_like_transient_drain_ramp():
    # gate가 거의 고정된 채(예: transient drain-ramp) 노이즈 수준으로만 흔들리는 경우
    gate = np.full(50, 0.0) + np.linspace(0, 0.01, 50)
    ok, reason = check_sweep(gate)
    assert ok is False
    assert "범위" in reason
