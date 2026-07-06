from pathlib import Path

from python.engine.runner import EngineRunner


def run_smart_session(root: Path, args):
    runner = EngineRunner(root, args)
    return runner.run()


