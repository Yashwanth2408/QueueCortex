"""Async client for the Trinity MCP server (support-ticket workspace).

Mirrors the verified read tools 1:1. Holds one long-lived MCP session,
opened once at app startup and reused for every call, with retry on
transient failures and a bounded concurrency semaphore so backfills/polls
never hammer Trinity with too many simultaneous calls.
"""

import json
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import Settings


class TrinityError(RuntimeError):
    pass


def _parse_result(result: Any) -> Any:
    if getattr(result, "isError", False):
        raise TrinityError(str(result.content))
    parts = []
    for block in result.content:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(text)
    if not parts:
        return None
    raw = "\n".join(parts)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


class TrinityClient:
    def __init__(self, settings: Settings, max_concurrency: int = 5):
        self._settings = settings
        self._session: ClientSession | None = None
        self._stack: AsyncExitStack | None = None
        self._sem = None
        self._max_concurrency = max_concurrency

    async def start(self) -> None:
        import asyncio

        self._sem = asyncio.Semaphore(self._max_concurrency)
        self._stack = AsyncExitStack()
        headers = {"Authorization": f"Bearer {self._settings.trinity_mcp_token}"}
        read, write, _ = await self._stack.enter_async_context(
            streamablehttp_client(self._settings.trinity_mcp_url, headers=headers)
        )
        session = await self._stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._session = session

    async def stop(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._session = None
        self._stack = None

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    )
    async def _call(self, name: str, arguments: dict[str, Any]) -> Any:
        assert self._session is not None, "TrinityClient.start() must be called first"
        async with self._sem:
            result = await self._session.call_tool(name, arguments)
        return _parse_result(result)

    async def whoami(self) -> dict:
        return await self._call("whoami", {})

    async def list_tickets(
        self,
        assigned_to: str | None = None,
        status: str | None = None,
        query: str | None = None,
        team: str | None = None,
        level: str | None = None,
        tags: list[str] | None = None,
        bucket_id: str | None = None,
        saved_inbox_id: str | None = None,
        sort_key: str | None = None,
        sort_dir: str = "desc",
        limit: int = 25,
        cursor: str | None = None,
    ) -> dict:
        args = {
            "assigned_to": assigned_to,
            "status": status,
            "query": query,
            "team": team,
            "level": level,
            "tags": tags,
            "bucket_id": bucket_id,
            "saved_inbox_id": saved_inbox_id,
            "sort_key": sort_key,
            "sort_dir": sort_dir,
            "limit": limit,
            "cursor": cursor,
        }
        return await self._call("list_tickets", {k: v for k, v in args.items() if v is not None})

    async def get_ticket(self, ticket_id: str) -> dict:
        return await self._call("get_ticket", {"ticket_id": ticket_id})

    async def get_ticket_messages(
        self,
        ticket_id: str,
        cursor: str | None = None,
        limit: int = 50,
        include_internal: bool = True,
    ) -> dict:
        args = {
            "ticket_id": ticket_id,
            "cursor": cursor,
            "limit": limit,
            "include_internal": include_internal,
        }
        return await self._call("get_ticket_messages", {k: v for k, v in args.items() if v is not None})

    async def ticket_counts(
        self, assigned_to: str | None = None, bucket_id: str | None = None, query: str | None = None
    ) -> dict:
        args = {"assigned_to": assigned_to, "bucket_id": bucket_id, "query": query}
        return await self._call("ticket_counts", {k: v for k, v in args.items() if v is not None})

    async def list_inboxes(self) -> dict:
        return await self._call("list_inboxes", {})

    async def list_agents(self, query: str | None = None, limit: int = 50) -> dict:
        args = {"query": query, "limit": limit}
        return await self._call("list_agents", {k: v for k, v in args.items() if v is not None})
