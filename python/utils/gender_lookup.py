import os
import re
import sys
from pathlib import Path


_GENDER_MAP = None


def lookup_gender(name: str) -> tuple[str, str]:
    first = _first_name(name)
    if not first:
        return "", ""
    value = _load_gender_map().get(first)
    if value == "M":
        return "M", "100"
    if value == "F":
        return "F", "0"
    return "", ""


def _first_name(name: str) -> str:
    match = re.search(r"[A-Za-z]+", str(name or ""))
    return match.group(0).lower() if match else ""


def _load_gender_map() -> dict:
    global _GENDER_MAP
    if _GENDER_MAP is not None:
        return _GENDER_MAP
    _GENDER_MAP = {}
    path = _find_gender_map_path()
    if not path:
        return _GENDER_MAP
    pattern = re.compile(r"'([a-z]+)'\s*:\s*'([^']+)'")
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = pattern.search(line)
        if not match:
            continue
        raw = match.group(2)
        if raw in {"男", "M"}:
            _GENDER_MAP[match.group(1)] = "M"
        elif raw in {"女", "F"}:
            _GENDER_MAP[match.group(1)] = "F"
    return _GENDER_MAP


def _find_gender_map_path() -> Path | None:
    candidates = []
    env_path = os.environ.get("GENDER_MAP_PATH")
    if env_path:
        candidates.append(Path(env_path))
    here = Path(__file__).resolve()
    project_root = here.parents[2]
    workspace_root = here.parents[3] if len(here.parents) > 3 else project_root.parent
    exe_dir = Path(sys.executable).resolve().parent
    bundle_dir = Path(getattr(sys, "_MEIPASS", exe_dir)).resolve()
    cwd = Path.cwd().resolve()
    candidates.extend([
        bundle_dir / "_gender_map.js",
        exe_dir / "_gender_map.js",
        exe_dir / "_internal" / "_gender_map.js",
        cwd / "_gender_map.js",
        cwd / "runtime" / "config" / "_gender_map.js",
    ])
    for root in [cwd, *cwd.parents[:5]]:
        candidates.append(root / "性别本地判断数据库 M（男）或 F（女）" / "_gender_map.js")
    candidates.extend([
        project_root / "runtime" / "config" / "_gender_map.js",
        project_root / "_gender_map.js",
        workspace_root / "性别本地判断数据库 M（男）或 F（女）" / "_gender_map.js",
    ])
    for path in candidates:
        if path.exists() and path.is_file():
            return path
    return None
