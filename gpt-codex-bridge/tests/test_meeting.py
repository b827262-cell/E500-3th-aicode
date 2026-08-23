from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from adapters.telegram import TelegramAdapter, split_telegram_message
from bridge.config import Settings
from bridge.meeting import MeetingRoomClient, MeetingRoomError
from bridge.queue import JobQueue


class FakeTelegramClient:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send_message(self, chat_id: str, text: str) -> None:
        self.sent.append((chat_id, text))


class FakeMeetingClient:
    def __init__(self, *, error: MeetingRoomError | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, dict | None]] = []

    def _raise(self) -> None:
        if self.error is not None:
            raise self.error

    async def health(self):
        self.calls.append(("health", None))
        self._raise()
        return {"status": "ok"}

    async def agents(self):
        self.calls.append(("agents", None))
        self._raise()
        return {"agents": ["hermes", "gpt", "gemini"]}

    async def ask(self, agent: str, payload: dict):
        self.calls.append((agent, payload))
        self._raise()
        return {"response": {"hermes": "HERMES_OK", "gpt": "GPT_OK", "gemini": "GEMINI_OK"}[agent]}

    async def all(self, payload: dict):
        self.calls.append(("all", payload))
        self._raise()
        return {"hermes": "H", "gpt": "G", "gemini": "Gemini"}

    async def roundtable(self, payload: dict):
        self.calls.append(("roundtable", payload))
        self._raise()
        return {
            "responses": {"hermes": "H", "gpt": "G", "gemini": "Gemini"},
            "summary": "S",
        }

    async def stop(self, payload: dict):
        self.calls.append(("stop", payload))
        self._raise()
        return {"response": "STOPPED"}

    async def reset(self, payload: dict):
        self.calls.append(("reset", payload))
        self._raise()
        return {"response": "RESET"}


def make_settings(directory: str, **extra: str) -> Settings:
    workspace = Path(directory) / "repo"
    workspace.mkdir()
    return Settings.from_env(
        {
            "CODEX_ALLOWED_WORKSPACES": str(workspace),
            "CODEX_DEFAULT_WORKSPACE": str(workspace),
            "TELEGRAM_BOT_TOKEN": "bot-secret",
            "TELEGRAM_ALLOWED_CHAT_ID": "42",
            "MEETING_ROOM_URL": "http://10.0.3.67:8000",
            "MEETING_API_TOKEN": "meeting-secret",
            **extra,
        },
        root_dir=Path(__file__).resolve().parents[1],
    )


def update(text: str) -> dict:
    return {
        "update_id": 1,
        "message": {
            "chat": {"id": 42},
            "from": {"id": 7},
            "text": text,
        },
    }


class MeetingHTTPClientTests(unittest.TestCase):
    def test_routes_payload_and_bearer_header(self) -> None:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            path = request.url.path
            if path == "/health":
                return httpx.Response(200, json={"status": "ok"})
            if path == "/api/agents":
                return httpx.Response(200, json={"agents": ["hermes", "gpt", "gemini"]})
            if path.endswith("/hermes"):
                return httpx.Response(200, json={"response": "HERMES_OK"})
            if path.endswith("/gpt"):
                return httpx.Response(200, json={"response": "GPT_OK"})
            if path.endswith("/gemini"):
                return httpx.Response(200, json={"response": "GEMINI_OK"})
            return httpx.Response(200, json={"hermes": "H", "gpt": "G", "gemini": "Gemini"})

        client = MeetingRoomClient(
            "http://10.0.3.67:8000",
            "meeting-secret",
            transport=httpx.MockTransport(handler),
        )
        payload = {"chat_id": 42, "user_id": 7, "message": "hello"}
        asyncio.run(client.health())
        asyncio.run(client.agents())
        asyncio.run(client.ask("hermes", payload))
        asyncio.run(client.ask("gpt", payload))
        asyncio.run(client.ask("gemini", payload))
        asyncio.run(client.all(payload))
        asyncio.run(client.roundtable(payload))
        asyncio.run(client.stop(payload))
        asyncio.run(client.reset(payload))

        self.assertEqual(
            [request.url.path for request in seen],
            [
                "/health",
                "/api/agents",
                "/api/ask/hermes",
                "/api/ask/gpt",
                "/api/ask/gemini",
                "/api/meeting/all",
                "/api/meeting/roundtable",
                "/api/meeting/stop",
                "/api/meeting/reset",
            ],
        )
        self.assertTrue(all(request.headers["authorization"] == "Bearer meeting-secret" for request in seen))
        for request in seen[2:]:
            self.assertEqual(json.loads(request.content), payload)
        self.assertEqual(client._timeout().connect, 5.0)
        self.assertEqual(client._timeout().read, 330.0)
        self.assertNotIn("meeting-secret", repr(client))

    def test_timeout_connection_refused_and_http_statuses_are_classified(self) -> None:
        async def timeout_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("read timed out", request=request)

        async def refused_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        for transport, kind in (
            (httpx.MockTransport(timeout_handler), "timeout"),
            (httpx.MockTransport(refused_handler), "unavailable"),
        ):
            client = MeetingRoomClient("http://meeting", "secret", transport=transport)
            with self.assertRaises(MeetingRoomError) as raised:
                asyncio.run(client.health())
            self.assertEqual(raised.exception.kind, kind)

        for status, kind in ((401, "auth"), (403, "auth"), (500, "internal")):
            client = MeetingRoomClient(
                "http://meeting",
                "secret",
                transport=httpx.MockTransport(lambda request, status=status: httpx.Response(status)),
            )
            with self.assertRaises(MeetingRoomError) as raised:
                asyncio.run(client.health())
            self.assertEqual(raised.exception.kind, kind)
            self.assertNotIn("secret", str(raised.exception))


class MeetingTelegramAdapterTests(unittest.TestCase):
    def _adapter(self, directory: str, meeting: FakeMeetingClient) -> tuple[TelegramAdapter, FakeTelegramClient]:
        settings = make_settings(directory)
        telegram = FakeTelegramClient()
        return TelegramAdapter(settings, JobQueue(Path(directory) / "jobs.sqlite3"), telegram, meeting), telegram

    def test_agent_all_roundtable_and_control_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            meeting = FakeMeetingClient()
            adapter, telegram = self._adapter(directory, meeting)
            for command in (
                "/hermes HERMES",
                "/gemini GEMINI",
                "/all all",
                "/roundtable table",
                "/agents",
                "/meeting-status",
                "/meeting-stop",
                "/meeting-reset",
            ):
                adapter.handle_update(update(command))

            text = "\n".join(reply for _, reply in telegram.sent)
            self.assertIn("☤ Hermes", text)
            self.assertIn("🟢 GPT", text)
            self.assertIn("🔵 Gemini", text)
            self.assertIn("📋 AI Meeting", text)
            self.assertIn("🎯 Summary", text)
            self.assertIn("Meeting Room: READY", text)
            self.assertEqual(meeting.calls[0][0], "hermes")
            self.assertEqual(meeting.calls[0][1], {"chat_id": "42", "user_id": "7", "message": "HERMES"})

    def test_partial_agent_response_is_safe_and_message_is_split(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            meeting = FakeMeetingClient()

            async def partial_all(payload: dict):
                return {"hermes": "H", "gpt": "G"}

            meeting.all = partial_all  # type: ignore[method-assign]
            adapter, telegram = self._adapter(directory, meeting)
            reply = adapter.handle_update(update("/all partial"))
            self.assertIn("🔵 Gemini\n（無回覆）", reply)

            long_text = "x" * 9000
            chunks = split_telegram_message(long_text)
            self.assertGreater(len(chunks), 1)
            self.assertTrue(all(len(chunk) <= 4096 for chunk in chunks))
            self.assertEqual("".join(chunks), long_text)

    def test_meeting_failures_do_not_crash_bot_or_leak_token(self) -> None:
        expected = {
            "unavailable": "AI Meeting Room unavailable",
            "auth": "Meeting Room authentication failed",
            "internal": "Meeting Room internal error",
            "timeout": "Meeting Room request timed out",
        }
        for kind, phrase in expected.items():
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                meeting = FakeMeetingClient(error=MeetingRoomError(kind))  # type: ignore[arg-type]
                adapter, telegram = self._adapter(directory, meeting)
                reply = adapter.handle_update(update("/hermes test"))
                self.assertIn(phrase, reply)
                self.assertNotIn("meeting-secret", "\n".join(text for _, text in telegram.sent))

        with tempfile.TemporaryDirectory() as directory:
            meeting = FakeMeetingClient(error=MeetingRoomError("unavailable"))
            adapter, _ = self._adapter(directory, meeting)
            reply = adapter.handle_update(update("/meeting-status"))
            self.assertIn("Meeting Room: OFFLINE", reply)

    def test_meeting_token_is_not_passed_to_codex_child_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MEETING_API_TOKEN": "meeting-secret"}, clear=False):
                settings = make_settings(directory)
                self.assertNotIn("MEETING_API_TOKEN", settings.codex_environment())
                self.assertNotIn("meeting-secret", repr(settings))


if __name__ == "__main__":
    unittest.main()
