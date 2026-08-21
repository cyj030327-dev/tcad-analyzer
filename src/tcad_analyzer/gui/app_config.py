"""사용자 설정(마지막으로 임포트한 폴더 등)을 홈 디렉터리에 작은 JSON으로 저장/불러오기.

프로그램을 다시 켤 때마다 폴더를 새로 선택하지 않아도 되게 하려는 목적의 편의 기능이라,
읽기/쓰기 중 어떤 문제가 생기더라도(파일 손상, 권한 등) 조용히 무시하고 앱이 정상
동작하도록 한다 — 이 기능이 실패한다고 프로그램이 죽으면 안 된다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

_CONFIG_DIR = Path.home() / ".tcad_analyzer"
_CONFIG_PATH = _CONFIG_DIR / "config.json"


def load_last_import_dir() -> Optional[Path]:
    try:
        data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        path_str = data.get("last_import_dir")
    except (OSError, ValueError):
        return None
    if not path_str:
        return None
    path = Path(path_str)
    return path if path.is_dir() else None


def save_last_import_dir(path: Path) -> None:
    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _CONFIG_PATH.write_text(json.dumps({"last_import_dir": str(path)}), encoding="utf-8")
    except OSError:
        pass
