"""sdevice 명령 파일(.cmd) 참고 정보 추출기.

완전한 Scheme 문법 파서는 만들지 않는다. 정규식으로 다음 세 가지 핵심 정보만
"참고용"으로 뽑아 Curve Preview 화면에 표시한다:
  - Electrode 블록의 전극 이름 목록
  - Solve/Quasistationary 블록의 전압 스윕 대상 전극과 목표 전압
  - Physics 블록에 명시된 모델 이름 목록

이 정보는 추출 알고리즘이나 비교/랭킹 로직에는 전혀 관여하지 않는다. 인식하지 못한
부분은 에러로 취급하지 않고 조용히 생략한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

_GOAL_RE = re.compile(r'Goal\s*\{\s*[Nn]ame\s*=\s*"?([\w.]+)"?\s+[Vv]oltage\s*=\s*([\-\d.eE]+)')
_PHYSICS_BLOCK_RE = re.compile(r'Physics\s*(?:\([^)]*\))?\s*\{(.*?)\}', re.IGNORECASE | re.DOTALL)
# .cmd 파일명이 노드 번호 관례(n<N>_...)를 안 따르는 경우(예: "pp668_des.cmd")에 대비해,
# 파일 내용 중 "Current = "n668_des.plt"" 같은 자기참조 경로에서 노드 번호를 찾아내는 폴백.
# File { Grid = "n1_fps.tdr" ... } 처럼 "Current"가 아닌 다른 필드(Grid 등)는 이전 단계(mesh
# 생성 등)의 다른 노드를 가리킬 수 있으므로, 반드시 "Current" 필드에서만 찾아야 한다.
_NODE_ID_IN_CONTENT_RE = re.compile(r'Current\s*=\s*"[nN](\d+)_')


@dataclass
class SimulationSummary:
    electrodes: List[str] = field(default_factory=list)
    voltage_sweeps: List[str] = field(default_factory=list)  # 사람이 읽기 쉬운 요약 문자열
    physics_models: List[str] = field(default_factory=list)
    node_id_hint: Optional[str] = None  # 파일 내용에서 찾아낸 노드 번호(파일명이 관례를 안 따를 때 폴백용)
    source_path: Optional[Path] = None
    partially_recognized: bool = False

    def is_empty(self) -> bool:
        return not (self.electrodes or self.voltage_sweeps or self.physics_models)


def _extract_electrodes(text: str) -> List[str]:
    # Electrode { { Name="gate" ... } { Name="drain" ... } ... } 블록은 중첩 괄호를 쓰기 때문에
    # 정규식으로 블록 경계를 정확히 잡기보다, 전체 텍스트에서 Name= 패턴을 직접 탐색한다
    # (완전한 구조 파싱이 아닌 참고 정보 추출이 목적이므로 단순 접근으로 충분).
    names: List[str] = []
    for m in re.finditer(r'[Nn]ame\s*=\s*"?([\w.]+)"?', text):
        candidate = m.group(1)
        if candidate not in names:
            names.append(candidate)
    return names


def _extract_voltage_sweeps(text: str) -> List[str]:
    summaries: List[str] = []
    for m in _GOAL_RE.finditer(text):
        electrode, voltage = m.group(1), m.group(2)
        summaries.append(f"{electrode} -> {voltage}V")
    return summaries


def _extract_physics_models(text: str) -> List[str]:
    models: List[str] = []
    for block in _PHYSICS_BLOCK_RE.finditer(text):
        inner = block.group(1)
        for tok in re.findall(r'\b[A-Za-z][\w]*\b', inner):
            if tok not in models and tok not in ("Physics",):
                models.append(tok)
    return models


def parse_sdevice_cmd(path: Path) -> SimulationSummary:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        text = path.read_text(encoding="latin-1")
    except FileNotFoundError:
        return SimulationSummary(source_path=path, partially_recognized=True)

    electrodes = _extract_electrodes(text)
    voltage_sweeps = _extract_voltage_sweeps(text)
    physics_models = _extract_physics_models(text)
    node_match = _NODE_ID_IN_CONTENT_RE.search(text)

    summary = SimulationSummary(
        electrodes=electrodes,
        voltage_sweeps=voltage_sweeps,
        physics_models=physics_models,
        node_id_hint=node_match.group(1) if node_match else None,
        source_path=path,
        partially_recognized=not (electrodes and voltage_sweeps),
    )
    return summary
