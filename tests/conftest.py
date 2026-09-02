"""Fixtures for ActivityWatch integration tests."""

from __future__ import annotations

from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

BASE_URL = "http://1.2.3.4:5600/api/0"

INFO = {
    "hostname": "aw-server-host",
    "version": "v0.14.0",
    "testing": False,
    "device_id": "test-device-id",
}


def _iso(seconds_ago: float) -> str:
    from datetime import timedelta

    return (dt_util.utcnow() - timedelta(seconds=seconds_ago)).isoformat()


def buckets_fixture() -> dict:
    return {
        "aw-watcher-afk_myhost": {
            "id": "aw-watcher-afk_myhost",
            "type": "afkstatus",
            "hostname": "myhost",
            "last_updated": _iso(30),
        },
        "aw-watcher-window_myhost": {
            "id": "aw-watcher-window_myhost",
            "type": "currentwindow",
            "hostname": "myhost",
            "last_updated": _iso(30),
        },
        # A long-stale host: discovered but not preselected.
        "aw-watcher-afk_oldhost": {
            "id": "aw-watcher-afk_oldhost",
            "type": "afkstatus",
            "hostname": "oldhost",
            "last_updated": "2022-01-01T00:00:00+00:00",
        },
        # Irrelevant bucket types are ignored entirely.
        "aw-watcher-web-firefox": {
            "id": "aw-watcher-web-firefox",
            "type": "web.tab.current",
            "hostname": "myhost",
            "last_updated": _iso(30),
        },
    }


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in all tests."""


@pytest.fixture
def mock_aw_server(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Mock a live aw-server with one active host."""
    aioclient_mock.get(f"{BASE_URL}/info", json=INFO)
    aioclient_mock.get(f"{BASE_URL}/buckets/", json=buckets_fixture())
    aioclient_mock.get(
        f"{BASE_URL}/buckets/aw-watcher-afk_myhost/events?limit=1",
        json=[
            {
                "id": 1,
                "timestamp": _iso(60),
                "duration": 55.0,
                "data": {"status": "not-afk"},
            }
        ],
    )
    aioclient_mock.get(
        f"{BASE_URL}/buckets/aw-watcher-window_myhost/events?limit=1",
        json=[
            {
                "id": 2,
                "timestamp": _iso(10),
                "duration": 5.0,
                "data": {"app": "Firefox", "title": "Secret document - Firefox"},
            }
        ],
    )
    aioclient_mock.post(f"{BASE_URL}/query/", json=[12345.6])
    return aioclient_mock
