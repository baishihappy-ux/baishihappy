from pathlib import Path

from python.engine.smart_session import run_smart_session


def run(root: Path, args):
    return run_smart_session(root, args)
