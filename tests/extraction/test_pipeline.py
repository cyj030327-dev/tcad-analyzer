import numpy as np

from tcad_analyzer.extraction.config import ExtractionConfig
from tcad_analyzer.extraction.pipeline import extract_for_collection, extract_parameters
from tcad_analyzer.models import Curve, CurveCollection, CurveType, DeviceMeta, Polarity, SplitCondition


def _id_vg_curve(curve_id, vth, split_attrs, vd=0.05):
    vg = np.linspace(-0.2, 1.2, 141)
    id_ = 1e-12 * np.exp((vg - vth) / 0.05)
    device = DeviceMeta(device_id="n", polarity=Polarity.NMOS)
    split = SplitCondition(attributes=split_attrs)
    return Curve(curve_id=curve_id, curve_type=CurveType.ID_VG, device=device, split=split, vg=vg, id_=id_, vd=vd)


def test_extract_parameters_returns_vth_ss_ion_ioff_gm():
    curve = _id_vg_curve("c1", 0.4, {"T": "900"})
    config = ExtractionConfig(cc_current_ref=1e-12, cc_normalize_by_wl=False)

    outcome = extract_parameters(curve, config)

    names = {p.param_name for p in outcome.parameters}
    assert {"Vth_CC", "SS", "Ion", "Ioff", "Ion_Ioff_ratio", "gm"} <= names
    assert outcome.failures == []


def test_extract_for_collection_isolates_curve_failures():
    good = _id_vg_curve("good", 0.4, {"T": "900"})
    # 포인트가 1개뿐이라 Vth/SS/Ion-Ioff/gm이 전부 진짜로 계산 불가능한(2개 미만) curve —
    # 기준전류가 범위 밖인 것 정도로는 더 이상 실패하지 않으므로(외삽으로 처리됨), 진짜
    # 계산 자체가 불가능한 경우로 실패를 유도해야 한다.
    bad_curve = Curve(
        curve_id="bad",
        curve_type=CurveType.ID_VG,
        device=DeviceMeta(device_id="n", polarity=Polarity.NMOS),
        split=SplitCondition(attributes={"T": "950"}),
        vg=np.array([0.4]),
        id_=np.array([1e-12]),
        vd=0.05,
    )

    curves = CurveCollection([good, bad_curve])
    config = ExtractionConfig(cc_current_ref=1e-12, cc_normalize_by_wl=False)

    params, failures = extract_for_collection(curves, config)

    # good curve는 bad curve의 실패에 영향받지 않고 온전히 성공해야 한다(격리 확인)
    assert any(p.curve_id == "good" and p.param_name == "SS" for p in params)
    assert not any(p.curve_id == "bad" for p in params)
    assert any(cid == "bad" for cid, _msg in failures)


def test_extract_parameters_warns_when_sweep_does_not_reach_off_region():
    # 실제 사례(게이트가 0V부터 시작해 진짜 off 영역을 못 보는 경우)를 일반화한 재현:
    # 스윕 전체가 이미 완전히 켜진(on) 영역이라 Ion/Ioff 비율이 몇 배 안 됨(수 decade는커녕).
    vg = np.linspace(15.0, 20.0, 51)
    id_ = 1e-6 * (1.0 + 0.001 * (vg - vg[0]))  # 사실상 평평한(이미 saturation인) 전류
    device = DeviceMeta(device_id="n", polarity=Polarity.NMOS)
    split = SplitCondition(attributes={"T": "900"})
    curve = Curve(curve_id="c1", curve_type=CurveType.ID_VG, device=device, split=split, vg=vg, id_=id_, vd=5.0)
    config = ExtractionConfig()

    outcome = extract_parameters(curve, config)

    assert outcome.warnings, "Ion/Ioff 비율이 작으면(=off 영역을 못 본 것으로 의심) 경고가 있어야 함"
    assert any("SS/Ioff" in name for name, _ in outcome.warnings)


def test_extract_parameters_warns_when_ss_fit_confidence_is_low():
    # 진짜 log-linear한 subthreshold 구간이 없는(노이즈만 있는) 곡선 -> SS의 R^2가 낮음
    rng = np.random.default_rng(1)
    vg = np.linspace(-0.2, 0.6, 60)
    id_ = np.abs(rng.normal(1e-14, 1e-15, size=vg.shape))
    device = DeviceMeta(device_id="n", polarity=Polarity.NMOS)
    split = SplitCondition(attributes={"T": "900"})
    curve = Curve(curve_id="c1", curve_type=CurveType.ID_VG, device=device, split=split, vg=vg, id_=id_, vd=0.05)

    outcome = extract_parameters(curve, ExtractionConfig())

    assert any(name == "SS" for name, _ in outcome.warnings)


def test_extract_parameters_no_warning_when_sweep_covers_off_region():
    curve = _id_vg_curve("c1", 0.4, {"T": "900"})  # vg: -0.2 ~ 1.2, Vth=0.4 -> 스윕이 Vth 아래도 포함
    config = ExtractionConfig(cc_current_ref=1e-12, cc_normalize_by_wl=False)

    outcome = extract_parameters(curve, config)

    assert outcome.warnings == []


def test_extract_parameters_warns_when_cc_vth_is_extrapolated():
    curve = _id_vg_curve("c1", 0.4, {"T": "900"})
    # 데이터 최대 전류보다 훨씬 큰 기준전류 -> 더 이상 실패하지 않고 외삽 + 경고
    config = ExtractionConfig(cc_current_ref=1.0, cc_normalize_by_wl=False)

    outcome = extract_parameters(curve, config)

    assert any(p.param_name == "Vth_CC" for p in outcome.parameters)
    assert any(name == "Vth_CC" for name, _ in outcome.warnings)
    assert not any(name == "Vth" for name, _ in outcome.failures)


def test_extract_parameters_warns_when_ss_slope_is_exactly_flat():
    # log(Id)가 완전히 평평한(잡음도 없는) 구간 -> 기울기 0 -> SS가 inf로 계산되고 경고가 붙음
    vg = np.linspace(0.0, 1.0, 20)
    id_ = np.full_like(vg, 1e-9)
    device = DeviceMeta(device_id="n", polarity=Polarity.NMOS)
    split = SplitCondition(attributes={"T": "900"})
    curve = Curve(
        curve_id="c1",
        curve_type=CurveType.ID_VG,
        device=device,
        split=split,
        vg=vg,
        id_=id_,
        vd=0.05,
    )

    outcome = extract_parameters(curve, ExtractionConfig())

    ss_param = next(p for p in outcome.parameters if p.param_name == "SS")
    assert np.isinf(ss_param.value)
    assert any(name == "SS" for name, _ in outcome.warnings)


def test_extract_parameters_warns_when_ion_ioff_ratio_is_infinite():
    vg = np.array([0.0, 0.5, 1.0, 1.5, 2.0])
    id_ = np.array([0.0, 0.0, 1e-9, 1e-6, 1e-3])
    device = DeviceMeta(device_id="n", polarity=Polarity.NMOS)
    split = SplitCondition(attributes={"T": "900"})
    curve = Curve(
        curve_id="c1",
        curve_type=CurveType.ID_VG,
        device=device,
        split=split,
        vg=vg,
        id_=id_,
        vd=0.05,
    )

    outcome = extract_parameters(curve, ExtractionConfig())

    ratio_param = next(p for p in outcome.parameters if p.param_name == "Ion_Ioff_ratio")
    assert np.isinf(ratio_param.value)
    assert any(name == "Ion_Ioff_ratio" for name, _ in outcome.warnings)


def test_extract_parameters_warns_when_ron_slope_is_exactly_flat():
    vd_array = np.linspace(0.0, 1.2, 20)
    id_ = np.full_like(vd_array, 1e-6)  # Vd가 변해도 전류가 전혀 안 변함 -> 기울기 0
    vg = np.full_like(vd_array, 5.0)
    device = DeviceMeta(device_id="n", polarity=Polarity.NMOS)
    split = SplitCondition(attributes={"T": "900"})
    curve = Curve(
        curve_id="c1",
        curve_type=CurveType.ID_VD,
        device=device,
        split=split,
        vg=vg,
        id_=id_,
        vd_array=vd_array,
    )

    outcome = extract_parameters(curve, ExtractionConfig())

    ron_param = next(p for p in outcome.parameters if p.param_name == "Ron")
    assert np.isinf(ron_param.value)
    assert any(name == "Ron" for name, _ in outcome.warnings)


def test_extract_parameters_skips_mobility_when_cox_not_configured():
    curve = _id_vg_curve("c1", 0.4, {"T": "900"})
    outcome = extract_parameters(curve, ExtractionConfig())

    assert not any(p.param_name == "Mobility_sat" for p in outcome.parameters)
    assert not any(name == "Mobility_sat" for name, _ in outcome.failures)


def test_extract_parameters_computes_mobility_when_cox_and_wl_configured():
    vg = np.linspace(-0.2, 1.2, 141)
    id_ = 1e-12 * np.exp((vg - 0.4) / 0.05)
    device = DeviceMeta(device_id="n", polarity=Polarity.NMOS, width_um=10.0, length_um=1.0)
    split = SplitCondition(attributes={"T": "900"})
    curve = Curve(curve_id="c1", curve_type=CurveType.ID_VG, device=device, split=split, vg=vg, id_=id_, vd=0.05)
    config = ExtractionConfig(cc_current_ref=1e-12, cc_normalize_by_wl=False, mobility_cox_F_cm2=3.45e-8)

    outcome = extract_parameters(curve, config)

    mobility_params = [p for p in outcome.parameters if p.param_name == "Mobility_sat"]
    assert len(mobility_params) == 1
    assert mobility_params[0].value > 0
    assert mobility_params[0].unit == "cm2/Vs"


def test_extract_for_collection_computes_dibl_for_matching_split():
    lin = _id_vg_curve("lin", 0.42, {"T": "900"}, vd=0.05)
    sat = _id_vg_curve("sat", 0.38, {"T": "900"}, vd=1.0)
    curves = CurveCollection([lin, sat])
    config = ExtractionConfig(cc_current_ref=1e-12, cc_normalize_by_wl=False)

    params, failures = extract_for_collection(curves, config)

    dibl_params = [p for p in params if p.param_name == "DIBL"]
    assert len(dibl_params) == 1
