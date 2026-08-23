from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from bridge.worker import Worker, WorkerAlreadyRunning, WorkerLock


class WorkerLockTests(unittest.TestCase):
    def test_only_one_worker_lock_can_be_held(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "worker.lock"
            with WorkerLock(lock_path):
                with self.assertRaises(WorkerAlreadyRunning):
                    with WorkerLock(lock_path):
                        pass


if __name__ == "__main__":
    unittest.main()
