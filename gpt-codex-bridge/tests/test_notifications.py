from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

from adapters.telegram import TelegramAdapter
from bridge.config import Settings
from bridge.queue import JobQueue


class FakeNotificationClient:
    def __init__(self, *, failures: int = 0, error: str = "temporary network failure") -> None:
        self.failures = failures
        self.error = error
        self.sent: list[tuple[str, str]] = []

    def send_message(self, chat_id: str, text: str) -> None:
        if self.failures:
            self.failures -= 1
            raise RuntimeError(self.error)
        self.sent.append((chat_id, text))


def make_settings(directory: str) -> Settings:
    workspace = Path(directory) / "repo"
    workspace.mkdir()
    return Settings.from_env(
        {
            "CODEX_ALLOWED_WORKSPACES": str(workspace),
            "CODEX_DEFAULT_WORKSPACE": str(workspace),
            "TELEGRAM_BOT_TOKEN": "bot-secret",
            "TELEGRAM_ALLOWED_CHAT_ID": "42",
        },
        root_dir=Path(__file__).resolve().parents[1],
    )


def finish_job(
    queue: JobQueue,
    settings: Settings,
    *,
    succeeded: bool,
    sandbox_mode: str = "workspace-write",
    error: str | None = None,
    exit_code: int = 0,
):
    job = queue.submit(
        chat_id=42,
        prompt="test notification",
        workspace=settings.default_workspace,
        sandbox_mode=sandbox_mode,
    )
    assert queue.claim_next() is not None
    queue.finish(
        job.id,
        succeeded=succeeded,
        report_path=None,
        error=error,
        exit_code=exit_code,
    )
    return job


class NotificationOutboxTests(unittest.TestCase):
    def test_historical_terminal_jobs_are_not_backfilled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "jobs.sqlite3"
            with sqlite3.connect(db) as connection:
                connection.execute(
                    """
                    CREATE TABLE jobs (
                        id TEXT PRIMARY KEY,
                        chat_id TEXT NOT NULL,
                        prompt TEXT NOT NULL,
                        workspace TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        started_at TEXT,
                        finished_at TEXT,
                        report_path TEXT,
                        error TEXT
                    )
                    """
                )
                connection.execute(
                    "INSERT INTO jobs (id, chat_id, prompt, workspace, status, created_at) "
                    "VALUES ('job-0123456789abcdef', '42', 'old', ?, 'succeeded', 'old')",
                    (directory,),
                )
                connection.commit()

            queue = JobQueue(db)
            self.assertEqual(queue.pending_notifications(), [])

    def test_succeeded_creates_exactly_one_pending_notification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(directory)
            queue = JobQueue(Path(directory) / "jobs.sqlite3")
            job = finish_job(queue, settings, succeeded=True, exit_code=0)

            notifications = queue.pending_notifications()
            self.assertEqual(len(notifications), 1)
            self.assertEqual(notifications[0].job_id, job.id)
            self.assertEqual(notifications[0].event_type, "succeeded")
            self.assertEqual(notifications[0].status, "pending")
            self.assertFalse(
                queue.finish(
                    job.id,
                    succeeded=True,
                    report_path=None,
                    error=None,
                    exit_code=0,
                )
            )
            self.assertEqual(len(queue.pending_notifications()), 1)

    def test_failed_creates_exactly_one_pending_notification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(directory)
            queue = JobQueue(Path(directory) / "jobs.sqlite3")
            job = finish_job(
                queue,
                settings,
                succeeded=False,
                sandbox_mode="read-only",
                error="Codex job failed",
                exit_code=7,
            )

            notifications = queue.pending_notifications()
            self.assertEqual(len(notifications), 1)
            self.assertEqual(notifications[0].job_id, job.id)
            self.assertEqual(notifications[0].event_type, "failed")
            self.assertEqual(queue.get(job.id).status, "failed")

    def test_worker_restart_does_not_lose_pending_notification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(directory)
            db = Path(directory) / "jobs.sqlite3"
            queue = JobQueue(db)
            finish_job(queue, settings, succeeded=True, exit_code=0)

            restarted_queue = JobQueue(db)
            notifications = restarted_queue.pending_notifications()
            self.assertEqual(len(notifications), 1)
            self.assertEqual(notifications[0].status, "pending")

    def test_telegram_success_marks_notification_sent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(directory)
            queue = JobQueue(Path(directory) / "jobs.sqlite3")
            job = finish_job(
                queue,
                settings,
                succeeded=True,
                sandbox_mode="read-only",
                exit_code=0,
            )
            client = FakeNotificationClient()
            adapter = TelegramAdapter(settings, queue, client)

            self.assertEqual(adapter.drain_notifications(), 1)
            notification = queue.get_notification(1)
            self.assertEqual(notification.status, "sent")
            self.assertIsNotNone(notification.sent_at)
            self.assertEqual(queue.pending_notifications(), [])
            self.assertEqual(len(client.sent), 1)
            chat_id, text = client.sent[0]
            self.assertEqual(chat_id, "42")
            self.assertIn("✅ Codex job completed", text)
            self.assertIn(f"Job: {job.id}", text)
            self.assertIn("Status: succeeded", text)
            self.assertIn("Sandbox: read-only", text)
            self.assertIn("Exit code: 0", text)
            self.assertIn(f"/result {job.id}", text)
            self.assertNotIn("changed_files", text)

    def test_temporary_telegram_failure_remains_retryable_and_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(directory)
            queue = JobQueue(Path(directory) / "jobs.sqlite3")
            job = finish_job(
                queue,
                settings,
                succeeded=False,
                sandbox_mode="danger-full-access",
                error="failure contains bot-secret",
                exit_code=9,
            )
            client = FakeNotificationClient(
                failures=1,
                error="temporary failure contains bot-secret",
            )
            adapter = TelegramAdapter(settings, queue, client)

            self.assertEqual(adapter.drain_notifications(), 0)
            notification = queue.get_notification(1)
            self.assertEqual(notification.status, "pending")
            self.assertEqual(notification.attempts, 1)
            self.assertNotIn("bot-secret", notification.last_error)
            self.assertIn("[REDACTED]", notification.last_error)

            self.assertEqual(adapter.drain_notifications(), 1)
            self.assertEqual(queue.get_notification(1).status, "sent")
            self.assertNotIn("bot-secret", client.sent[0][1])
            self.assertIn("Sandbox: danger-full-access", client.sent[0][1])
            self.assertIn("Error: failure contains [REDACTED]", client.sent[0][1])

    def test_adapter_restart_resends_pending_notification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(directory)
            db = Path(directory) / "jobs.sqlite3"
            queue = JobQueue(db)
            job = finish_job(queue, settings, succeeded=True, exit_code=0)
            first_adapter = TelegramAdapter(settings, queue, FakeNotificationClient())
            self.assertEqual(first_adapter.queue.pending_notifications()[0].job_id, job.id)

            restarted_queue = JobQueue(db)
            restarted_client = FakeNotificationClient()
            restarted_adapter = TelegramAdapter(settings, restarted_queue, restarted_client)
            self.assertEqual(restarted_adapter.drain_notifications(), 1)
            self.assertEqual(restarted_queue.get_notification(1).status, "sent")
            self.assertEqual(len(restarted_client.sent), 1)


if __name__ == "__main__":
    unittest.main()
