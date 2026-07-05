from pathlib import Path


def resolve_root(root=None) -> Path:
    return Path(root or ".").resolve()


def runtime_root(root: Path) -> Path:
    if root.name.lower() == "runtime":
        return root
    return root / "runtime"


def config_path(root: Path) -> Path:
    rr = runtime_root(root)
    return rr / "config" / "app_config.json"


def ensure_runtime_dirs(root: Path) -> dict:
    rr = runtime_root(root)
    paths = {
        "runtime": rr,
        "logs": rr / "logs",
        "output": rr / "output",
        "state": rr / "state",
        "config": rr / "config",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths
