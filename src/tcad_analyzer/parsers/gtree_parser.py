"""Sentaurus Workbench `gtree.dat` 파서.

gtree.dat는 SWB 프로젝트의 실험 트리 정의 파일로, 스윕 변수명과 각 노드(실험) 번호별
변수값 조합을 담고 있다. 실제 포맷은 SWB 버전에 따라 다를 수 있으므로, 여기서는
현재까지 알려진 두 가지 흔한 표현 방식을 시도하고 실패하면 명확한 에러를 낸다.
실제 파일 샘플을 받으면 이 파서를 그에 맞춰 보정한다.

지원 시도 패턴:
  1) Tcl 스타일: `set gtree(1,Temperature) 900` / `set node(1,Temperature) {900}`
  2) 표(whitespace/tab) 스타일: 첫 줄이 헤더(node 컬럼 + 변수명들), 이후 각 줄이 노드 하나
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .errors import GtreeParseError

_TCL_SET_RE = re.compile(
    r'set\s+\S+\(\s*(?P<node>\d+)\s*,\s*(?P<var>[A-Za-z_][\w]*)\s*\)\s+\{?(?P<value>[^{}\n]*)\}?'
)
_NODE_ID_IN_FILENAME_RE = re.compile(r'[nN](\d+)_')

# 실제 Sentaurus Workbench가 쓰는 형식(swbtree). 크게 두 종류의 줄로 구성된다:
#   1) "flow" 정의 줄: <tool> <varname> "<기본값>" {값1 값2 ...}
#      예) sprocess Tigzo "0.030" {0.030 0.010 0.020 0.040 0.050}
#      값 목록이 비어있으면({}) 실제 스윕 변수가 아니라 도구 자체를 나타내는 구조적 항목이다
#      (예: "sprocess sprocess "" {}"). flow 줄이 나오는 순서 = 트리에서의 깊이(depth) 순서.
#   2) "tree" 줄: <depth> <node_id> <parent_id> {값} {시나리오} <상태>
#      예) 4 668 67 {1e18} {default} 0
#      한 노드의 전체 파라미터 조합을 알려면 parent_id를 따라 루트까지 올라가며,
#      각 깊이(depth)에 해당하는 변수명에 그 노드의 값을 대입해 모아야 한다.
_FLOW_LINE_RE = re.compile(r'^(\w+)\s+(\w+)\s+"([^"]*)"\s+\{([^}]*)\}', re.MULTILINE)
_TREE_LINE_RE = re.compile(r'^(\d+)\s+(\d+)\s+(\d+)\s+\{([^}]*)\}\s+\{([^}]*)\}\s+(-?\d+)', re.MULTILINE)


def _try_swb_tree_style(text: str) -> Optional[Dict[str, Dict[str, str]]]:
    flow_matches = _FLOW_LINE_RE.findall(text)
    if len(flow_matches) < 2:
        return None

    depth_to_varname: Dict[int, Optional[str]] = {}
    for depth, (_tool, varname, _default, values_str) in enumerate(flow_matches):
        depth_to_varname[depth] = varname if values_str.strip() else None

    tree_matches = _TREE_LINE_RE.findall(text)
    if not tree_matches:
        return None

    # node_id -> (depth, parent_id, value)
    tree_nodes: Dict[str, tuple] = {}
    for depth_s, node_id, parent_id, value_str, _scenario, _status in tree_matches:
        tree_nodes[node_id] = (int(depth_s), parent_id, value_str.strip())

    def resolve(start_id: str) -> Dict[str, str]:
        attrs: Dict[str, str] = {}
        current, seen = start_id, set()
        while current in tree_nodes and current not in seen:
            seen.add(current)
            depth, parent_id, value = tree_nodes[current]
            varname = depth_to_varname.get(depth)
            if varname and value:
                attrs[varname] = value
            current = parent_id
        return attrs

    nodes = {node_id: resolve(node_id) for node_id in tree_nodes}
    return nodes or None


@dataclass
class GtreeProject:
    variable_names: List[str] = field(default_factory=list)
    nodes: Dict[str, Dict[str, str]] = field(default_factory=dict)  # node_id -> {var: value}
    source_path: Optional[Path] = None

    def split_attributes_for_node(self, node_id: str) -> Optional[Dict[str, str]]:
        return self.nodes.get(node_id)


def _try_tcl_style(text: str) -> Optional[Dict[str, Dict[str, str]]]:
    nodes: Dict[str, Dict[str, str]] = {}
    for m in _TCL_SET_RE.finditer(text):
        node_id = m.group("node")
        var = m.group("var")
        value = m.group("value").strip()
        nodes.setdefault(node_id, {})[var] = value
    return nodes or None


def _try_table_style(lines: List[str]) -> Optional[Dict[str, Dict[str, str]]]:
    content_lines = [ln for ln in lines if ln.strip() and not ln.strip().startswith("#")]
    if len(content_lines) < 2:
        return None
    header = content_lines[0].split()
    if len(header) < 2:
        return None
    var_names = header[1:]
    nodes: Dict[str, Dict[str, str]] = {}
    for ln in content_lines[1:]:
        tokens = ln.split()
        if len(tokens) != len(header):
            continue
        node_id = tokens[0]
        nodes[node_id] = dict(zip(var_names, tokens[1:]))
    return nodes or None


def parse_gtree(path: Path) -> GtreeProject:
    path = Path(path)
    if not path.exists():
        raise GtreeParseError("파일이 존재하지 않습니다", path=path)

    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        text = path.read_text(encoding="latin-1")

    nodes = _try_swb_tree_style(text)
    if nodes is None:
        nodes = _try_tcl_style(text)
    if nodes is None:
        nodes = _try_table_style(text.splitlines())

    if nodes is None:
        raise GtreeParseError(
            "gtree.dat 형식을 인식하지 못했습니다. 실제 파일 샘플을 제공하면 파서를 조정할 수 있습니다.",
            path=path,
        )

    variable_names = sorted({var for attrs in nodes.values() for var in attrs})
    return GtreeProject(variable_names=variable_names, nodes=nodes, source_path=path)


def extract_node_id_from_filename(filename: str) -> Optional[str]:
    """`n1_des.plt`, `n12_des.cmd` 같은 관례적 파일명에서 노드 번호를 추출."""
    m = _NODE_ID_IN_FILENAME_RE.search(filename)
    return m.group(1) if m else None
