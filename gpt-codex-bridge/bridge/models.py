"""Data models used by the persistent job runner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .sandbox import DEFAULT_SANDBOX_MODE, validate_sandbox_mode


@dataclass(frozen=True)
class Job:
    id: str
    chat_id: str
    prompt: str
    workspace: Path
    status: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    report_path: Path | None = None
    error: str | None = None
    exit_code: int | None = None
    sandbox_mode: str = DEFAULT_SANDBOX_MODE

    def __post_init__(self) -> None:
        validate_sandbox_mode(self.sandbox_mode)

    @classmethod
    def from_row(cls, row: object) -> "Job":
        data = dict(row)
        report = data.get("report_path")
        return cls(
            id=data["id"],
            chat_id=str(data["chat_id"]),
            prompt=data["prompt"],
            workspace=Path(data["workspace"]),
            status=data["status"],
            created_at=data["created_at"],
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            report_path=Path(report) if report else None,
            error=data.get("error"),
            exit_code=int(data["exit_code"]) if data.get("exit_code") is not None else None,
            sandbox_mode=data["sandbox_mode"],
        )


@dataclass(frozen=True)
class Notification:
    id: int
    job_id: str
    chat_id: str
    event_type: str
    status: str
    attempts: int
    created_at: str
    sent_at: str | None = None
    last_error: str | None = None

    @classmethod
    def from_row(cls, row: object) -> "Notification":
        data = dict(row)
        return cls(
            id=int(data["id"]),
            job_id=data["job_id"],
            chat_id=str(data["chat_id"]),
            event_type=data["event_type"],
            status=data["status"],
            attempts=int(data["attempts"]),
            created_at=data["created_at"],
            sent_at=data.get("sent_at"),
            last_error=data.get("last_error"),
        )
