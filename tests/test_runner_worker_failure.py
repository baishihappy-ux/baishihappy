import logging
import threading
import tempfile
import unittest
from pathlib import Path

from python.engine.runner import EngineRunner


class RunnerWorkerFailureTests(unittest.TestCase):
    def test_worker_entry_records_uncaught_failure_and_stops_run(self):
        with tempfile.TemporaryDirectory() as temp:
            runner = EngineRunner.__new__(EngineRunner)
            runner.stats_lock = threading.RLock()
            runner.worker_errors = []
            runner.stop_event = threading.Event()
            runner.paths = {"state": Path(temp)}
            runner.logger = logging.getLogger("test.runner.worker_failure")
            runner.logger.handlers = [logging.NullHandler()]
            runner.logger.propagate = False

            def crash(_worker_id, _max_total):
                raise RuntimeError("offline fixture crash")

            runner.worker_loop = crash
            runner._worker_entry(7, 0)

            self.assertTrue(runner.stop_event.is_set())
            self.assertEqual([{
                "worker_id": 7,
                "type": "RuntimeError",
                "message": "offline fixture crash",
            }], runner.worker_error_snapshot())


if __name__ == "__main__":
    unittest.main()
