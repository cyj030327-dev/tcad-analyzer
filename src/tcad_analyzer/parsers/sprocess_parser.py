"""sprocess 명령 파일(지오메트리/공정 정의) 참고 정보 추출.

sdevice_cmd_parser.py와 마찬가지로 완전한 Tcl 파서는 만들지 않고, 정규식으로 이동도(μFE)
계산에 필요한 값들만 뽑아내는 참고용 파서다. 실제 프로젝트 두 개(IGZO TFT, 실리콘
SimpleMOS)를 비교해보니 같은 sprocess라도 문법 스타일이 꽤 다르다 — `material=` 키워드
유무, 두께가 변수(`$VAR`)인지 리터럴 숫자인지, `implant species=X` vs `implant X`(위치 인자)
등. 아래 정규식들은 최대한 두 스타일을 모두 받아들이게 만들었다:

- 게이트 산화막 재질/두께: `deposit [material=]<재질> ... thickness=[$]<값>` -> Cox 계산용.
  단, 아무 deposit이나 첫 번째로 잡으면 안 된다 — 게이트 전극(PolySilicon/금속)보다 먼저
  나온 유전체만 "게이트 산화막 후보"로 본다(실제 공정 순서상 게이트 산화막은 항상 게이트
  전극보다 먼저 만들어지고, 나중에 나오는 Nitride 등은 스페이서일 가능성이 커서다).
- 게이트 산화막이 `diffuse ... O2`(열산화)로 자라는 경우, 스크립트엔 두께가 숫자로 안
  적혀 있을 수 있다(시뮬레이션으로 계산됨) — 이 경우 "값을 못 찾았다"고 정직하게 알리고,
  스크립트가 `puts "DOE: tox ..."`처럼 로그에 값을 남기는 관례를 쓰면 그 태그 이름도 같이
  알려준다(로그 파일이 있으면 거기서 파싱할 수 있다는 힌트).
- 채널 길이: `set Lch value` 관례가 있으면 그걸 쓰고, 없으면 게이트 마스크의
  `mask name=poly left=<식> right=<식>`에서 (right - left)로 근사한다.
- `line z ...`가 하나도 없으면 2D 구조로 보고(W가 지오메트리에 아예 없음), 이 경우 Sentaurus의
  2D 시뮬레이션 관례상 폭은 보통 단위폭(1um)으로 취급한다는 것만 알려준다(값을 임의로
  확정하지는 않음 — 물리적 가정이라 사용자가 직접 결정하게 둔다).
- `struct tdr=n<번호>_...`에서 이 sprocess가 만드는 grid(tdr) 노드 번호(참고용)
- 도핑에 쓰인 도펀트 종류(예: Arsenic, Boron) -> n형/p형 힌트. 데이터(전류 부호) 기반 극성
  추정과 교차 확인하는 데 쓴다(둘 중 하나가 항상 맞다고 볼 순 없어 "참고"로만 취급).
  실리콘 MOSFET은 몸체(body, `init field=`)와 소스/드레인(`implant`)에 서로 다른 극성을
  같이 쓰는 게 정상이므로(예: p형 body + n형 소스/드레인 = NMOS), 소자의 극성은 몸체가
  아니라 소스/드레인(implant) 도핑으로 정해진다는 반도체 관례를 따라 implant 정보를 우선
  한다.

도펀트 종류/분류는 Sentaurus Process User Guide(T-2022.03)를 근거로 한다:
- Table 5 (p.95, "Species initialized and supported by Sentaurus Process"): sprocess가 인식하는
  전체 species 목록 — Aluminum, Antimony, Arsenic, Boron, Carbon, Fluorine, Gallium, Germanium,
  Indium, Nitrogen, Phosphorus, Silicon(원자종) + AsH2, BF2, B10H14, B18H22, BCl2, C2B10H12,
  C2B10H14, PH2(분자종, 원자종을 대신 실어나름)
- Table 12 / Table 15 (p.220, p.273, "Solution names"): Sentaurus가 전하상태(활성 도펀트 농도,
  BActive/AsActive/PActive/SbActive/InActive)까지 추적하는 표준 도펀트는 Boron, Arsenic,
  Phosphorus, Antimony, Indium 5종뿐이다 — 이 5종은 매뉴얼에 명시된 "확실한" 분류로 쓰고,
  n형/p형 자체는 주기율표상 5족(도너)/3족(억셉터)이라는 일반적인 반도체 물리로 판별한다
  (매뉴얼에 "n형/p형"이라는 표현이 대놓고 표로 나오지는 않는다). Table 5에는 있지만 이
  5종 활성 도펀트 세트엔 없는 Aluminum/Gallium도 3족이라 일반적으로 p형이지만, Sentaurus
  기본 활성 도펀트 취급 대상은 아니라 "확실치 않음"으로 구분해서 표시한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from .errors import TecplotParseError

_SET_VAR_RE = re.compile(r"^\s*set\s+(\w+)\s+([\-0-9.eE]+)\s*$", re.MULTILINE)
# material= 키워드가 있어도/없어도, thickness가 $변수여도/리터럴 숫자여도 모두 잡는다.
_DEPOSIT_RE = re.compile(
    r"\bdeposit\s+(?:material\s*=\s*)?\"?(\w+)\"?[^\n]*?\bthickness\s*=\s*\$?([\w.]+)",
    re.IGNORECASE,
)
# 게이트 전극(폴리실리콘/금속)이나 게이트 마스크가 나오는 지점 — 이보다 먼저 나온
# 유전체만 게이트 산화막 후보로 인정한다(그 뒤에 나오는 건 스페이서 등일 가능성이 큼).
_GATE_ELECTRODE_HINT_RE = re.compile(
    r"\bdeposit\s+(?:material\s*=\s*)?\"?(?:polysilicon|poly|metal|aluminum|tungsten|tin|copper|titanium)\b"
    r"|\bmask\s+name\s*=\s*\"?(?:poly|gate)\b",
    re.IGNORECASE,
)
_Z_LINE_RE = re.compile(r"^\s*line\s+z\s", re.MULTILINE | re.IGNORECASE)
_STRUCT_TDR_RE = re.compile(r"struct\s+tdr\s*=\s*n?(\d+)", re.IGNORECASE)
# 게이트 산화막이 열산화(thermal oxidation)로 자라는 경우 — 두께가 스크립트에 숫자로 없음
_THERMAL_OXIDATION_RE = re.compile(r"\bdiffuse\b[^\n]*?\b(?:dry\s*o2|wet\s*o2|o2|n2)\b", re.IGNORECASE)
# `puts "DOE: tox ..."`처럼 스크립트가 스스로 계산한 값을 로그에 남기는 SWB 관례
_DOE_LOG_TAG_RE = re.compile(r'puts\s+"DOE:\s*(\w+)', re.IGNORECASE)
# 게이트 길이를 `set Lch`류 변수 대신 게이트 마스크 left/right 폭으로 근사할 때 쓰는 패턴
_MASK_LEFT_RIGHT_RE = re.compile(
    r"\bmask\s+name\s*=\s*\"?(\w+)\"?[^\n]*?\bleft\s*=\s*([\-0-9.*/()]+)[^\n]*?\bright\s*=\s*([\-0-9.*/()]+)",
    re.IGNORECASE,
)
_SAFE_ARITH_RE = re.compile(r"^[\d.\s+\-*/()]+$")
_GATE_MASK_NAMES = {"poly", "gate", "polygate"}

_LCH_VAR_NAMES = ("Lch", "L_ch", "Lgate", "ChannelLength", "Lg")

# 알려진 게이트 유전체 재질의 비유전율(문헌 통상값, 근사). 여기 없는 재질이 감지되면
# 유전율은 채우지 않고 두께/재질명만 알려준다(사용자가 직접 값을 넣도록).
_DIELECTRIC_REL_PERMITTIVITY: Dict[str, float] = {
    "oxide": 3.9,
    "sio2": 3.9,
    "al2o3": 9.0,
    "hfo2": 20.0,
    "nitride": 7.5,
    "si3n4": 7.5,
    "ta2o5": 25.0,
    "zro2": 25.0,
    "y2o3": 15.0,
}

# sprocess_ug Table 12/15의 5대 "활성" 도펀트(전하상태까지 추적됨) -> 확실한 n형/p형 분류
_CERTAIN_N_TYPE_DOPANTS = {"arsenic", "phosphorus", "antimony"}
_CERTAIN_P_TYPE_DOPANTS = {"boron", "indium"}
# sprocess_ug Table 5엔 있지만 5대 활성 도펀트 세트엔 없는 3족 원소 — 일반 화학상 p형이지만
# Sentaurus 기본 활성 도펀트 취급 대상은 아니라서 "확실치 않음"으로 별도 표시
_LIKELY_P_TYPE_DOPANTS = {"aluminum", "gallium"}
# 도펀트 원자를 실어나르는 분자종(구현 시 그 원자와 같은 극성으로 취급)
_MOLECULAR_TO_ATOMIC_DOPANT = {
    "ash2": "arsenic",
    "ph2": "phosphorus",
    "bf2": "boron",
    "b10h14": "boron",
    "b18h22": "boron",
    "bcl2": "boron",
    "c2b10h12": "boron",
    "c2b10h14": "boron",
}
_ALL_DOPANT_TOKENS = _CERTAIN_N_TYPE_DOPANTS | _CERTAIN_P_TYPE_DOPANTS | _LIKELY_P_TYPE_DOPANTS | set(
    _MOLECULAR_TO_ATOMIC_DOPANT
)

# 도핑 관련 명령에서 종(species) 이름이 나오는 자리만 콕 집어서 본다. 텍스트 전체에서
# 알려진 도펀트 이름을 그냥 검색하면 "deposit material=Aluminum"(소스/드레인 금속 전극
# 재질일 뿐, 도핑과 무관) 같은 데서도 걸려 잘못된 극성 판단으로 이어질 수 있다.
## `init field=X ...`뿐 아니라 `init concentration=1e17 field=X ...`처럼 다른 인자가 먼저
# 나온 뒤 field=가 나오는 경우도 있어(인자 순서가 고정이 아님), "init"으로 시작하는 같은
# 줄 안에서 field=가 나오면 잡는다(줄바꿈 전까지만 봐서 다른 init 명령으로 안 번지게 함).
_INIT_FIELD_RE = re.compile(r"\binit\b[^\n]*?\bfield\s*=\s*\"?(\w+)\"?", re.IGNORECASE)
# `implant species=X` / `implant X dose=...`(위치 인자) 둘 다 받는다. 알려진 도펀트 목록과
# 교집합을 취해 걸러내므로 "implant tables=Default" 같은 것도 안전하게 무시된다.
_IMPLANT_SPECIES_RE = re.compile(r"\bimplant\s+(?:species\s*=\s*)?\"?(\w+)\"?", re.IGNORECASE)
# select/store 등에서 쓰이는 `name=<종>Concentration` / `name=<종>ActiveConcentration` 관례
_NAME_EQUALS_RE = re.compile(r"\bname\s*=\s*\"?(\w+)\"?", re.IGNORECASE)
_CONCENTRATION_SUFFIXES = ("activeconcentration", "concentration")


def _to_float_or_none(text: str) -> Optional[float]:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _safe_eval_arith(expr: str) -> Optional[float]:
    """`-0.25/2` 같은 단순 산술식만 안전하게 계산한다. 숫자/공백/+-*/() 외의 문자가 하나라도
    있으면(함수 호출, 변수 등) 계산을 포기하고 None을 반환 — 임의 코드 실행을 막기 위해서다."""
    expr = expr.strip()
    if not expr or not _SAFE_ARITH_RE.match(expr):
        return None
    try:
        return float(eval(expr, {"__builtins__": {}}, {}))  # noqa: S307 - 위에서 문자 화이트리스트로 제한함
    except Exception:
        return None


def _species_from_concentration_name(token: str) -> Optional[str]:
    """`ArsenicActiveConcentration`처럼 species 이름이 접두어로 붙은 식별자에서 species만 뽑는다.
    `Concentration`/`ActiveConcentration`로 끝나지 않으면(예: 전극 이름 `gate`, 마스크 이름
    `SD_mask`) None을 반환해 도핑과 무관한 name= 값을 걸러낸다."""
    low = token.lower()
    for suffix in _CONCENTRATION_SUFFIXES:
        if low.endswith(suffix) and len(low) > len(suffix):
            return low[: -len(suffix)]
    return None


def _dopant_polarity(species_lower: str) -> Optional[str]:
    """개별 도펀트 하나의 극성. "n" | "p" | None(비도펀트 공정용 원소 등)."""
    atomic = _MOLECULAR_TO_ATOMIC_DOPANT.get(species_lower, species_lower)
    if atomic in _CERTAIN_N_TYPE_DOPANTS:
        return "n"
    if atomic in _CERTAIN_P_TYPE_DOPANTS or atomic in _LIKELY_P_TYPE_DOPANTS:
        return "p"
    return None


def _collect_dopant_channels(text: str) -> Dict[str, Set[str]]:
    """도핑 명령 종류별로 감지된 도펀트 이름(소문자, 알려진 도펀트만)을 나눠 반환.

    "implant"(소스/드레인 등 이온주입) / "background"(`init field=`, `name=...Concentration`
    같은 몸체·배경 도핑) 두 채널로 나누는 이유는, 표준 MOSFET에서 소자의 실제 극성(NMOS/PMOS)은
    몸체 도핑이 아니라 소스/드레인 도핑으로 정해지기 때문이다.
    """
    implant = {m.group(1).lower() for m in _IMPLANT_SPECIES_RE.finditer(text)}
    background = {m.group(1).lower() for m in _INIT_FIELD_RE.finditer(text)}
    for m in _NAME_EQUALS_RE.finditer(text):
        species = _species_from_concentration_name(m.group(1))
        if species:
            background.add(species)
    return {
        "implant": {s for s in implant if s in _ALL_DOPANT_TOKENS},
        "background": {s for s in background if s in _ALL_DOPANT_TOKENS},
    }


def detect_dopant_species(text: str) -> List[str]:
    """텍스트에서 실제 도핑 명령(`init field=`, `implant`, `name=<종>Concentration`)에 쓰인
    도펀트 이름만 찾아 중복 없이(소문자로 정규화해) 반환한다. 알려진 도펀트 목록에 없는
    이름(전극/마스크 이름 등)은 자동으로 걸러진다."""
    channels = _collect_dopant_channels(text)
    return sorted(channels["implant"] | channels["background"])


def summarize_dopant_polarity(species_list: List[str]) -> Optional[str]:
    """감지된 도펀트들을 종합한 극성 힌트. "n" | "p" | "mixed"(n/p 둘 다 검출) | None(도펀트를
    하나도 못 찾음). 여러 채널을 구분하지 않는 단순 집계이므로, 소스/드레인 우선 판단이
    필요하면 parse_sprocess_cmd 내부의 채널별 판단을 대신 참고한다."""
    polarities = {p for p in (_dopant_polarity(s) for s in species_list) if p is not None}
    if not polarities:
        return None
    if len(polarities) > 1:
        return "mixed"
    return polarities.pop()


def _resolve_polarity_hint(channels: Dict[str, Set[str]]) -> Optional[str]:
    """implant(소스/드레인) 도핑이 있으면 그걸 우선한다 — 표준 MOSFET에서 트랜지스터의
    극성은 몸체(body) 도핑이 아니라 소스/드레인 도핑 종류로 정해지기 때문이다(예: p형
    body + n형 소스/드레인 = NMOS). implant 정보가 전혀 없으면(예: 이 프로젝트의 IGZO
    TFT처럼 별도 implant 없이 init/select만 쓰는 경우) 나머지 정보로 판단한다.
    """
    if channels["implant"]:
        return summarize_dopant_polarity(list(channels["implant"]))
    return summarize_dopant_polarity(list(channels["background"]))


def _detect_gate_length_from_mask(text: str) -> Optional[float]:
    """`set Lch` 같은 변수가 없을 때, 게이트 마스크의 left/right 폭으로 채널 길이를 근사."""
    for name, left_expr, right_expr in _MASK_LEFT_RIGHT_RE.findall(text):
        if name.lower() not in _GATE_MASK_NAMES:
            continue
        left_val = _safe_eval_arith(left_expr)
        right_val = _safe_eval_arith(right_expr)
        if left_val is None or right_val is None:
            continue
        length = abs(right_val - left_val)
        if length > 0:
            return length
    return None


@dataclass
class SprocessSummary:
    variables: Dict[str, float] = field(default_factory=dict)
    gate_dielectric_material: Optional[str] = None
    gate_oxide_thickness_um: Optional[float] = None
    gate_oxide_rel_permittivity: Optional[float] = None
    oxide_grown_thermally: bool = False  # True면 diffuse(...)O2 같은 열산화로 자란 것 같음(두께가 스크립트에 없을 수 있음)
    doe_log_tags: List[str] = field(default_factory=list)  # puts "DOE: <이름> ..." 관례로 남기는 값 이름(로그 파일 힌트)
    channel_length_um: Optional[float] = None
    is_2d_structure: Optional[bool] = None
    node_id_hint: Optional[str] = None
    dopant_species: List[str] = field(default_factory=list)
    dopant_polarity_hint: Optional[str] = None  # "n" | "p" | "mixed" | None
    source_path: Optional[Path] = None

    def is_empty(self) -> bool:
        return not (self.gate_oxide_thickness_um or self.channel_length_um)


_SDEVICE_BLOCK_RE = re.compile(r"\b(Electrode|Solve)\s*\{")
# sprocess는 `#`, sdevice는 `*`로 줄 주석을 쓴다 — 설명용 주석 안에서 우연히 "Electrode"
# 같은 단어를 언급해도(예: 이 파일이 sdevice .cmd와 어떻게 맞물리는지 적어두는 경우)
# 오탐이 안 나도록, 판별 전에 주석 줄은 미리 지운다.
_COMMENT_LINE_RE = re.compile(r"^\s*[#*].*$", re.MULTILINE)


def looks_like_sprocess(text: str) -> bool:
    """파일 앞부분만 보고 sprocess 지오메트리 스크립트인지 가볍게 판별(sdevice .cmd와 구분용).

    sdevice .cmd는 `Electrode {`/`Solve {`처럼 대문자로 시작하는 블록 키워드를 쓰는 반면,
    sprocess 스크립트는 `line x/y/z`, `deposit`, `struct tdr=` 같은 소문자 명령을 쓴다.
    """
    code_only = _COMMENT_LINE_RE.sub("", text)
    head = code_only[:4000]
    if _SDEVICE_BLOCK_RE.search(head):
        return False
    return bool(_STRUCT_TDR_RE.search(code_only)) or bool(re.search(r"^\s*line\s+[xyz]\s", head, re.MULTILINE))


def parse_sprocess_cmd(path: Path) -> SprocessSummary:
    path = Path(path)
    if not path.exists():
        raise TecplotParseError("파일이 존재하지 않습니다", path=path)
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        raise TecplotParseError(f"파일을 읽을 수 없습니다: {exc}", path=path) from exc

    variables = {name: float(val) for name, val in _SET_VAR_RE.findall(text)}
    summary = SprocessSummary(variables=variables, source_path=path)

    # 게이트 전극(폴리실리콘/금속)이 처음 나오는 위치보다 먼저 나온 유전체 증착만 게이트
    # 산화막 후보로 인정한다 — 그 뒤에 나오는 유전체 증착(예: 스페이서용 Nitride)까지
    # 게이트 산화막으로 잘못 집어내는 것을 막기 위해서다.
    boundary_match = _GATE_ELECTRODE_HINT_RE.search(text)
    boundary = boundary_match.start() if boundary_match else len(text)

    for match in _DEPOSIT_RE.finditer(text):
        if match.start() >= boundary:
            break
        material, thickness_ref = match.group(1), match.group(2)
        key = material.lower()
        if not (key in _DIELECTRIC_REL_PERMITTIVITY or "oxid" in key):
            continue
        thickness = variables.get(thickness_ref, _to_float_or_none(thickness_ref))
        if thickness is None:
            continue
        summary.gate_dielectric_material = material
        summary.gate_oxide_thickness_um = thickness
        summary.gate_oxide_rel_permittivity = _DIELECTRIC_REL_PERMITTIVITY.get(key)
        break

    if summary.gate_oxide_thickness_um is None and _THERMAL_OXIDATION_RE.search(text):
        # 두께 숫자를 스크립트에서 못 찾았지만, 열산화 공정이 있는 건 확인됨 — 실제 두께는
        # 시뮬레이션이 계산해서 로그에 남길 수 있으니(아래 doe_log_tags) 그쪽을 안내한다.
        summary.oxide_grown_thermally = True

    summary.doe_log_tags = sorted({m.group(1) for m in _DOE_LOG_TAG_RE.finditer(text)})

    for name in _LCH_VAR_NAMES:
        if name in variables:
            summary.channel_length_um = variables[name]
            break
    else:
        summary.channel_length_um = _detect_gate_length_from_mask(text)

    summary.is_2d_structure = not _Z_LINE_RE.search(text)

    m = _STRUCT_TDR_RE.search(text)
    if m:
        summary.node_id_hint = m.group(1)

    channels = _collect_dopant_channels(text)
    summary.dopant_species = sorted(channels["implant"] | channels["background"])
    summary.dopant_polarity_hint = _resolve_polarity_hint(channels)

    return summary
