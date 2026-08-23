"""Async client and response helpers for the remote TUF A16 meeting room."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx


MeetingErrorKind = Literal["unavailable", "auth", "internal", "timeout", "http"]


class MeetingRoomError(RuntimeError):
    """A safe, user-facing classification of a Meeting Room request failure."""

    def __init__(self, kind: MeetingErrorKind, status_code: int | None = None) -> None:
        self.kind = kind
        self.status_code = status_code
        super().__init__(kind)


@dataclass(frozen=True)
class MeetingRoomClient:
    """Call the remote Meeting Room without starting any local agent."""

    base_url: str
    api_token: str | None = field(repr=False)
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 330.0
    transport: httpx.AsyncBaseTransport | None = None

    def _timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            timeout=self.read_timeout_seconds,
            connect=self.connect_timeout_seconds,
        )

    def _headers(self) -> dict[str, str]:
        # Keep the header construction local to the request. It is never logged,
        # included in an exception, or placed in a Telegram response.
        return {"Authorization": f"Bearer {self.api_token or ''}"}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout(),
                transport=self.transport,
            ) as client:
                response = await client.request(
                    method,
                    url,
                    headers=self._headers(),
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise MeetingRoomError("timeout") from exc
        except (httpx.ConnectError, httpx.NetworkError, OSError) as exc:
            raise MeetingRoomError("unavailable") from exc

        if response.status_code in (401, 403):
            raise MeetingRoomError("auth", response.status_code)
        if response.status_code >= 500:
            raise MeetingRoomError("internal", response.status_code)
        if not 200 <= response.status_code < 300:
            raise MeetingRoomError("http", response.status_code)

        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {"response": response.text}

    async def health(self) -> Any:
        return await self._request("GET", "/health")

    async def ask(self, agent: str, payload: dict[str, Any]) -> Any:
        return await self._request("POST", f"/api/ask/{agent}", payload=payload)

    async def all(self, payload: dict[str, Any]) -> Any:
        return await self._request("POST", "/api/meeting/all", payload=payload)

    async def roundtable(self, payload: dict[str, Any]) -> Any:
        return await self._request("POST", "/api/meeting/roundtable", payload=payload)

    async def agents(self) -> Any:
        return await self._request("GET", "/api/agents")

    async def stop(self, payload: dict[str, Any]) -> Any:
        return await self._request("POST", "/api/meeting/stop", payload=payload)

    async def reset(self, payload: dict[str, Any]) -> Any:
        return await self._request("POST", "/api/meeting/reset", payload=payload)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, Mapping):
        for key in ("response", "answer", "text", "content", "output", "message"):
            if key in value:
                result = _text(value[key])
                if result:
                    return result
    return ""


def _agent_aliases(agent: str) -> tuple[str, ...]:
    return (agent, agent.lower(), agent.upper(), agent.capitalize())


def _find_agent(value: Any, agent: str) -> str:
    if isinstance(value, Mapping):
        for key in _agent_aliases(agent):
            if key in value:
                found = _text(value[key])
                if found:
                    return found
        for key in ("response", "responses", "result", "results", "replies", "agents", "data"):
            if key in value:
                found = _find_agent(value[key], agent)
                if found:
                    return found
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, Mapping):
                label = str(item.get("agent", item.get("name", item.get("model", "")))).lower()
                if label == agent.lower():
                    found = _text(item)
                    if found:
                        return found
            found = _find_agent(item, agent)
            if found:
                return found
    return ""


def agent_replies(value: Any) -> dict[str, str]:
    """Extract known agent replies while tolerating partial server responses."""

    return {agent: _find_agent(value, agent) for agent in ("hermes", "gpt", "gemini")}


def response_text(value: Any) -> str:
    """Extract a useful text response from several compatible JSON shapes."""

    direct = _text(value)
    if direct:
        return direct
    if isinstance(value, list):
        parts = [_text(item) for item in value]
        return "\n".join(part for part in parts if part)
    return ""


def summary_text(value: Any) -> str:
    if isinstance(value, Mapping):
        for key in ("summary", "conclusion", "synthesis"):
            found = _text(value.get(key))
            if found:
                return found
        for key in ("response", "result", "data"):
            if key in value:
                found = summary_text(value[key])
                if found:
                    return found
    return ""


def meeting_payload(*, chat_id: Any, user_id: Any, message: str) -> dict[str, Any]:
    """Build the minimum common request contract for all POST routes."""

    return {"chat_id": chat_id, "user_id": user_id, "message": message}
