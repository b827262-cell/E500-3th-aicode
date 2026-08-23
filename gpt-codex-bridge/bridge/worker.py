"""Single worker process for durable Codex jobs."""

from __future__ import annotations

from contextlib import AbstractContextManager
import fcntl
import os
from pathlib import Path
import signal
import time

from .codex_runner import CodexRunner
from .config import Settings
from .queue import JobQueue


class WorkerAlreadyRunning(RuntimeError):
    """Raised when another worker owns the runner lock."""


class WorkerLock(AbstractContextManager["WorkerLock"]):
    def __init__(self, path: Path):
        self.path = Path(path)
        self._fd: int | None = None

    def __enter__(self) -> "WorkerLock":
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(self._fd)
            self._fd = None
            raise WorkerAlreadyRunning("another worker already owns the lock") from exc
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None


class Worker:
    def __init__(
        self,
        queue: JobQueue,
        runner: CodexRunner,
        *,
        poll_seconds: float = 1.0,
        lock_path: Path | None = None,
        sleep=time.sleep,
    ):
        self.queue = queue
        self.runner = runner
        self.poll_seconds = poll_seconds
        self.lock_path = lock_path or queue.db_path.with_suffix(".worker.lock")
        self._sleep = sleep

    def run_once(self) -> bool:
        job = self.queue.claim_next()
        if job is None:
            return False
        try:
            outcome = self.runner.run(job)
            self.queue.finish(
                job.id,
                succeeded=outcome.succeeded,
                report_path=outcome.report_path,
                error=None if outcome.succeeded else "Codex job failed",
                exit_code=outcome.exit_code,
            )
        except Exception:
            report_path = self.runner.internal_report(job, summary="Codex runner failed unexpectedly")
            self.queue.finish(
                job.id,
                succeeded=False,
                report_path=report_path,
                error="Codex runner failed unexpectedly",
                exit_code=-1,
            )
        return True

    def run_forever(self, stop_event=None) -> None:
        with WorkerLock(self.lock_path):
            self.queue.requeue_running()
            while stop_event is None or not stop_event.is_set():
                if not self.run_once():
                    self._sleep(self.poll_seconds)


def main() -> int:
    settings = Settings.from_env()
    settings.ensure_runtime_dirs()
    queue = JobQueue(settings.queue_db)
    runner = CodexRunner(settings)
    stop = __import__("threading").Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    Worker(queue, runner, poll_seconds=settings.worker_poll_seconds).run_forever(stop)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
