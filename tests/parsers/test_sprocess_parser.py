import pytest

from tcad_analyzer.parsers.sprocess_parser import (
    detect_dopant_species,
    looks_like_sprocess,
    parse_sprocess_cmd,
    summarize_dopant_polarity,
)

REAL_STYLE_SPROCESS = """
math coord.ucs

set Tox    0.100
set Tigzo  0.050
set Tsd    0.050
set Tsub   0.100
set Nd     1e15

set Lch    10.0
set Lsd     3.0

line x location=0.0   spacing=0.02
line x location=$Tsub spacing=0.02

line y location=0.0    spacing=0.5

region Silicon
init field=Phosphorus concentration=1e20

contact name=gate bottom

deposit material=Oxide type=anisotropic thickness=$Tox

deposit material=PolySilicon type=anisotropic thickness=$Tigzo

select z=$Nd name=ArsenicConcentration store

select z=$Nd name=ArsenicActiveConcentration store

deposit material=Aluminum type=anisotropic thickness=$Tsd

contact name=source box Aluminum xlo=-1.0 xhi=0.0 ylo=0.0 yhi=$Lsd

grid remesh

struct tdr=n55_fps
"""

SIMPLEMOS_STYLE = """
line x location= 0    spacing= 0.01 tag= top
line x location= 0.15 spacing= 0.02
line x location= 1.0  spacing= 0.2  tag= bottom

line y location= 0.0      spacing= 0.1*0.25  tag= left
line y location= 0.5*0.25 spacing= 0.05*0.25
line y location= 2*0.25   spacing= 0.25      tag= right

region Silicon xlo= top xhi= bottom ylo= left yhi= right

init concentration= 1e+17 field= Boron slice.angle= 180 !DelayFullD

pdbSet Silicon Dopant DiffModel ChargedFermi

pdbSet Oxide Grid perp.add.dist 0.01e-4
diffuse time= 10 temperature= 950 O2

set oxidelayer [lindex [layers y=0 Oxide] 1]
puts "DOE: tox [format %.4f [expr [lindex $oxidelayer 1] - [lindex $oxidelayer 0]]]"

deposit PolySilicon type= anisotropic thickness= 0.1

mask name= poly left=-0.25/2 right= 0.25/2

etch PolySilicon type= anisotropic thickness= 0.12 mask= poly
etch Oxide type= anisotropic thickness= 0.02

implant Arsenic dose= 2e+14 energy= 30

deposit Nitride type= isotropic thickness= 0.3*0.25
etch  Nitride type= anisotropic thickness= 0.35*0.25

implant Phosphorus dose= 1e+15 energy= 15

diffuse time=1<s> temperature= 1000

deposit Aluminum type= anisotropic thickness= 0.05
mask name= contact left= 0.25*1.2
etch Aluminum type= anisotropic thickness= 0.1 mask= contact

transform reflect left

contact name= substrate bottom
contact name= source point y= -0.25*1.5 x= -0.010 replace
contact name= drain  point y= 0.25*1.5  x= -0.010 replace
contact name= gate   point y= 0         x= -0.050

struct tdr= n10 !Gas !interfaces
"""

SDEVICE_STYLE = """
File {
   Grid    = "n59_fps.tdr"
   Current = "n799_des.plt"
}

Electrode {
   { Name="gate"   Voltage=0.0 }
}

Solve {
   Coupled { Poisson Electron Hole }
}
"""


def test_looks_like_sprocess_detects_sprocess_script():
    assert looks_like_sprocess(REAL_STYLE_SPROCESS) is True


def test_looks_like_sprocess_rejects_sdevice_cmd():
    assert looks_like_sprocess(SDEVICE_STYLE) is False


def test_looks_like_sprocess_ignores_electrode_mentioned_only_in_comment():
    # sprocess 문법이지만, 설명용 주석 줄 안에서 "Electrode"라는 단어를 언급하는 경우
    # (예: sdevice .cmd와 이름을 맞춰야 한다는 설명) — 실제 Electrode { 블록이 없으므로
    # sdevice로 오분류되면 안 된다.
    text = (
        REAL_STYLE_SPROCESS
        + '\n# sdevice .cmd의 Electrode 블록도 반드시 이 이름과 맞춰야 한다.\n'
    )
    assert looks_like_sprocess(text) is True


def test_parse_sprocess_extracts_gate_oxide_thickness_and_permittivity(tmp_path):
    path = tmp_path / "pp55_fps.cmd"
    path.write_text(REAL_STYLE_SPROCESS, encoding="utf-8")

    summary = parse_sprocess_cmd(path)

    assert summary.gate_dielectric_material == "Oxide"
    assert summary.gate_oxide_thickness_um == 0.100
    assert summary.gate_oxide_rel_permittivity == 3.9


def test_parse_sprocess_extracts_channel_length(tmp_path):
    path = tmp_path / "pp55_fps.cmd"
    path.write_text(REAL_STYLE_SPROCESS, encoding="utf-8")

    summary = parse_sprocess_cmd(path)

    assert summary.channel_length_um == 10.0


def test_parse_sprocess_detects_2d_structure_when_no_z_lines(tmp_path):
    path = tmp_path / "pp55_fps.cmd"
    path.write_text(REAL_STYLE_SPROCESS, encoding="utf-8")

    summary = parse_sprocess_cmd(path)

    assert summary.is_2d_structure is True


def test_parse_sprocess_detects_3d_structure_when_z_lines_present(tmp_path):
    text_3d = REAL_STYLE_SPROCESS + "\nline z location=0.0 spacing=0.5\n"
    path = tmp_path / "pp55_fps.cmd"
    path.write_text(text_3d, encoding="utf-8")

    summary = parse_sprocess_cmd(path)

    assert summary.is_2d_structure is False


def test_parse_sprocess_extracts_node_id_hint_from_struct_tdr(tmp_path):
    path = tmp_path / "pp55_fps.cmd"
    path.write_text(REAL_STYLE_SPROCESS, encoding="utf-8")

    summary = parse_sprocess_cmd(path)

    assert summary.node_id_hint == "55"


def test_parse_sprocess_unknown_dielectric_leaves_permittivity_none(tmp_path):
    # 이름에 "oxide"가 들어있으면 비유전율은 몰라도 게이트 산화막 후보로는 인정한다
    text = REAL_STYLE_SPROCESS.replace("material=Oxide", "material=ExoticOxide")
    path = tmp_path / "pp55_fps.cmd"
    path.write_text(text, encoding="utf-8")

    summary = parse_sprocess_cmd(path)

    assert summary.gate_dielectric_material == "ExoticOxide"
    assert summary.gate_oxide_thickness_um == 0.100
    assert summary.gate_oxide_rel_permittivity is None


def test_parse_sprocess_detects_dopant_species_via_init_field_and_concentration_name(tmp_path):
    path = tmp_path / "pp55_fps.cmd"
    path.write_text(REAL_STYLE_SPROCESS, encoding="utf-8")

    summary = parse_sprocess_cmd(path)

    assert summary.dopant_species == ["arsenic", "phosphorus"]
    assert summary.dopant_polarity_hint == "n"


def test_detect_dopant_species_ignores_metal_electrode_material():
    # deposit material=Aluminum / contact ... Aluminum은 소스-드레인 금속 전극 재질이지,
    # 도핑용 도펀트가 아니다 — 도핑 명령(init field=, name=...Concentration)에 등장한
    # 이름만 도펀트로 인식해야 한다.
    text = (
        "deposit material=Aluminum type=anisotropic thickness=$Tsd\n"
        "contact name=source box Aluminum xlo=-1.0 xhi=0.0 ylo=0.0 yhi=$Lsd\n"
    )
    assert detect_dopant_species(text) == []


def test_detect_dopant_species_ignores_non_dopant_name_equals_values():
    text = 'contact name=gate bottom\nmask name=SD_mask segments= "0.0 1.0"\n'
    assert detect_dopant_species(text) == []


def test_detect_dopant_species_finds_implant_species():
    text = "implant species=Boron dose=1e15 energy=10\n"
    assert detect_dopant_species(text) == ["boron"]


def test_summarize_dopant_polarity_p_type():
    assert summarize_dopant_polarity(["boron", "indium"]) == "p"


def test_summarize_dopant_polarity_mixed_when_both_types_found():
    assert summarize_dopant_polarity(["arsenic", "boron"]) == "mixed"


def test_summarize_dopant_polarity_none_when_nothing_found():
    assert summarize_dopant_polarity([]) is None


def test_summarize_dopant_polarity_molecular_species_resolve_to_atomic_polarity():
    assert summarize_dopant_polarity(["bf2", "ph2"]) == "mixed"  # boron(p) + phosphorus(n)
    assert summarize_dopant_polarity(["ph2", "ash2"]) == "n"


def test_detect_dopant_species_supports_positional_implant_syntax():
    # "implant species=X" 뿐 아니라 "implant X dose=..."(species= 생략) 형태도 인식해야 한다
    assert detect_dopant_species("implant Arsenic dose= 2e+14 energy= 30\n") == ["arsenic"]


# ------------------------------------------------------ SimpleMOS 스타일(실리콘 MOSFET)


def test_simplemos_gate_oxide_not_found_because_thermally_grown(tmp_path):
    path = tmp_path / "pp10_fps.cmd"
    path.write_text(SIMPLEMOS_STYLE, encoding="utf-8")

    summary = parse_sprocess_cmd(path)

    # 게이트 산화막은 diffuse(...)O2(열산화)로 자라지, deposit thickness=로 만들어지지 않아서
    # 스크립트에 숫자로 된 두께가 없다 — 억지로 추측하지 않고 None으로 남아야 한다
    assert summary.gate_oxide_thickness_um is None
    assert summary.oxide_grown_thermally is True


def test_simplemos_detects_doe_log_tag_hint(tmp_path):
    path = tmp_path / "pp10_fps.cmd"
    path.write_text(SIMPLEMOS_STYLE, encoding="utf-8")

    summary = parse_sprocess_cmd(path)

    assert "tox" in summary.doe_log_tags


def test_simplemos_ignores_spacer_nitride_as_gate_dielectric(tmp_path):
    # Nitride는 게이트 전극(PolySilicon) 뒤에 스페이서로 증착되는 것이라, 게이트 산화막으로
    # 잘못 집어내면 안 된다(게이트 전극보다 먼저 나온 유전체만 후보로 인정하는 로직 검증)
    path = tmp_path / "pp10_fps.cmd"
    path.write_text(SIMPLEMOS_STYLE, encoding="utf-8")

    summary = parse_sprocess_cmd(path)

    assert summary.gate_dielectric_material != "Nitride"


def test_simplemos_channel_length_from_gate_mask(tmp_path):
    # set Lch류 변수가 없으니, mask name=poly left=-0.25/2 right=0.25/2 에서
    # (0.25/2) - (-0.25/2) = 0.25로 근사해야 한다
    path = tmp_path / "pp10_fps.cmd"
    path.write_text(SIMPLEMOS_STYLE, encoding="utf-8")

    summary = parse_sprocess_cmd(path)

    assert summary.channel_length_um == pytest.approx(0.25)


def test_simplemos_polarity_prioritizes_source_drain_implant_over_body_doping(tmp_path):
    # body(Boron, p형) + 소스/드레인(Arsenic/Phosphorus, n형)이 섞여 있는 표준 NMOS 구조.
    # 소자 극성은 소스/드레인 도핑으로 정해지므로 "mixed"가 아니라 "n"이어야 한다.
    path = tmp_path / "pp10_fps.cmd"
    path.write_text(SIMPLEMOS_STYLE, encoding="utf-8")

    summary = parse_sprocess_cmd(path)

    assert "boron" in summary.dopant_species  # body 도핑도 감지는 됨
    assert summary.dopant_polarity_hint == "n"  # 하지만 판단은 소스/드레인(n형) 기준


def test_simplemos_looks_like_sprocess():
    assert looks_like_sprocess(SIMPLEMOS_STYLE) is True


def test_simplemos_node_id_hint_from_struct_tdr(tmp_path):
    path = tmp_path / "pp10_fps.cmd"
    path.write_text(SIMPLEMOS_STYLE, encoding="utf-8")

    summary = parse_sprocess_cmd(path)

    assert summary.node_id_hint == "10"
