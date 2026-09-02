"""Minimal async client for the aw-server REST API.

Deliberately read-only and limited to the endpoints this integration needs.
Intended to be extracted into an async aw-client library before a Home
Assistant core submission.
"""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import quote

import aiohttp

REQUEST_TIMEOUT = 15


class ActivityWatchError(Exception):
    """Base error for aw-server communication."""


class ActivityWatchConnectionError(ActivityWatchError):
    """Could not reach or talk to aw-server."""


class ActivityWatchClient:
    """Thin async wrapper around the aw-server REST API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        ssl: bool = False,
    ) -> None:
        self._session = session
        scheme = "https" if ssl else "http"
        self.server_url = f"{scheme}://{host}:{port}"
        self.base_url = f"{self.server_url}/api/0"

    async def _request(
        self, method: str, path: str, json_data: dict[str, Any] | None = None
    ) -> Any:
        url = f"{self.base_url}{path}"
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                response = await self._session.request(method, url, json=json_data)
                response.raise_for_status()
                return await response.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ActivityWatchConnectionError(
                f"Error communicating with aw-server at {self.base_url}: {err}"
            ) from err

    async def get_info(self) -> dict[str, Any]:
        """Return server info (hostname, version, device_id)."""
        return await self._request("GET", "/info")

    async def get_buckets(self) -> dict[str, Any]:
        """Return all buckets on the server, keyed by bucket id."""
        return await self._request("GET", "/buckets/")

    async def get_latest_events(
        self, bucket_id: str, limit: int = 1
    ) -> list[dict[str, Any]]:
        """Return the most recent events in a bucket."""
        return await self._request(
            "GET", f"/buckets/{quote(bucket_id)}/events?limit={limit}"
        )

    async def query(self, query: str, timeperiods: list[str]) -> list[Any]:
        """Run a query against the aw-server query API."""
        return await self._request(
            "POST", "/query/", {"query": [query], "timeperiods": timeperiods}
        )
