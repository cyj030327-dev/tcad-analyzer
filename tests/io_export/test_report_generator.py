import numpy as np

from tcad_analyzer.analysis import OptimizationProfile
from tcad_analyzer.io_export.report_generator import generate_html_report
from tcad_analyzer.models import (
    Curve,
    CurveType,
    DeviceMeta,
    ExtractedParameter,
    Polarity,
    SplitCondition,
)

DEVICE = DeviceMeta(device_id="N", polarity=Polarity.NMOS)


def _split(name: str) -> SplitCondition:
    return SplitCondition(split_name=name)


def _params():
    values = {
        "A": {"Ion": 10.0, "Ioff": 2.0, "SS": 90.0},
        "B": {"Ion": 5.0, "Ioff": 0.5, "SS": 80.0},
    }
    params = []
    for split_name, metrics in values.items():
        split = _split(split_name)
        for name, value in metrics.items():
            params.append(ExtractedParameter(None, DEVICE, split, name, value, unit="", method="test"))
    return params


def _curves():
    vg = np.linspace(0, 1, 20)
    curves = []
    for split_name in ("A", "B"):
        id_ = np.linspace(1e-12, 1e-6, 20)
        curves.append(
            Curve(
                curve_id=f"idvg_{split_name}",
                curve_type=CurveType.ID_VG,
                device=DEVICE,
                split=_split(split_name),
                vg=vg,
                id_=id_,
                vd=1.0,
            )
        )
    return curves


def test_generate_html_report_contains_summary_and_recommendation():
    text = generate_html_report(_params(), _curves(), profile=OptimizationProfile.BALANCED)

    assert "<html" in text
    assert "요약" in text
    assert "최적 소자 추천" in text
    assert "추천 split" in text
    # split 이름이 표 어딘가에 실제로 등장하는지 (완전히 빈 보고서가 아님을 확인)
    assert "A" in text and "B" in text


def test_generate_html_report_embeds_idvg_chart_as_base64_png():
    text = generate_html_report(_params(), _curves())

    assert "data:image/png;base64," in text


def test_generate_html_report_handles_no_curves_gracefully():
    # curve가 하나도 없어도(파라미터만 있는 경우) 죽지 않고, 그래프 절만 생략해야 한다.
    text = generate_html_report(_params(), [])

    assert "<html" in text
    assert "data:image/png;base64," not in text


def test_generate_html_report_handles_empty_params_gracefully():
    text = generate_html_report([], [])

    assert "<html" in text
    assert "데이터가 없습니다" in text or "표시할 데이터가 없습니다" in text
