from pathlib import Path

from python.engine.runner import EngineRunner


def run_session_flow(root: Path, args):
    return EngineRunner(root, args).run()


