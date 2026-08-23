"""Validated per-job Codex sandbox modes."""

from __future__ import annotations

from typing import Final


DEFAULT_SANDBOX_MODE: Final = "workspace-write"
SANDBOX_MODES: Final = frozenset(
    {
        "read-only",
        "workspace-write",
        "danger-full-access",
    }
)


class SandboxModeError(ValueError):
    """Raised when a job requests an unsupported sandbox mode."""


def validate_sandbox_mode(mode: str) -> str:
    """Return a supported mode, rejecting unknown values without fallback."""

    if not isinstance(mode, str) or mode not in SANDBOX_MODES:
        raise SandboxModeError(f"unsupported sandbox mode: {mode!r}")
    return mode
