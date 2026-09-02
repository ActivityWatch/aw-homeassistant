"""Data update coordinator for the ActivityWatch integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import ActivityWatchClient, ActivityWatchConnectionError
from .const import (
    AFK_BUCKET_TYPE,
    CONF_HOSTS,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    LOGGER,
    STALE_AFTER,
    WINDOW_BUCKET_TYPE,
)

type ActivityWatchConfigEntry = ConfigEntry[ActivityWatchCoordinator]

# Canonical AFK filter: sum the duration of all not-afk events.
SCREEN_TIME_QUERY = (
    'afk_events = query_bucket("{bucket}"); '
    'not_afk = filter_keyvals(afk_events, "status", ["not-afk"]); '
    "RETURN = sum_durations(not_afk);"
)


@dataclass
class HostBuckets:
    """Relevant bucket ids for a tracked host."""

    afk: str | None = None
    window: str | None = None
    last_updated: datetime | None = None


@dataclass
class HostData:
    """State of one tracked host."""

    hostname: str
    active: bool | None = None
    last_seen: datetime | None = None
    current_app: str | None = None
    current_title: str | None = None
    screen_time_today: float | None = None


def discover_hosts(buckets: dict[str, Any]) -> dict[str, HostBuckets]:
    """Map hostnames to their AFK/window buckets.

    A server can hold buckets for many hosts (including stale or synced ones),
    and a host can have multiple buckets of the same type; the most recently
    updated bucket per type wins.
    """
    hosts: dict[str, HostBuckets] = {}
    updated_at: dict[tuple[str, str], datetime] = {}
    for bucket_id, bucket in buckets.items():
        bucket_type = bucket.get("type")
        if bucket_type not in (AFK_BUCKET_TYPE, WINDOW_BUCKET_TYPE):
            continue
        hostname = bucket.get("hostname")
        if not hostname or hostname == "unknown":
            hostname = bucket_id.split("_", 1)[1] if "_" in bucket_id else None
        if not hostname:
            continue
        last_updated = dt_util.parse_datetime(bucket.get("last_updated") or "")
        if last_updated is None:
            last_updated = datetime.fromtimestamp(0, tz=dt_util.UTC)
        info = hosts.setdefault(hostname, HostBuckets())
        kind = "afk" if bucket_type == AFK_BUCKET_TYPE else "window"
        if last_updated >= updated_at.get((hostname, kind), datetime.fromtimestamp(0, tz=dt_util.UTC)):
            setattr(info, kind, bucket_id)
            updated_at[(hostname, kind)] = last_updated
        if info.last_updated is None or last_updated > info.last_updated:
            info.last_updated = last_updated
    return hosts


def _event_end(event: dict[str, Any]) -> datetime | None:
    """Return the end time of an event (timestamp + duration)."""
    timestamp = dt_util.parse_datetime(event.get("timestamp") or "")
    if timestamp is None:
        return None
    return timestamp + timedelta(seconds=event.get("duration") or 0)


class ActivityWatchCoordinator(DataUpdateCoordinator[dict[str, HostData]]):
    """Poll aw-server and derive per-host state."""

    config_entry: ActivityWatchConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ActivityWatchConfigEntry,
        client: ActivityWatchClient,
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
            ),
        )
        self.client = client
        self.hosts: list[str] = entry.options.get(CONF_HOSTS, [])

    async def _async_update_data(self) -> dict[str, HostData]:
        try:
            return await self._fetch()
        except ActivityWatchConnectionError as err:
            raise UpdateFailed(str(err)) from err

    async def _fetch(self) -> dict[str, HostData]:
        buckets = await self.client.get_buckets()
        discovered = discover_hosts(buckets)
        now = dt_util.utcnow()
        day_start = dt_util.start_of_local_day()
        timeperiod = f"{day_start.isoformat()}/{dt_util.now().isoformat()}"

        data: dict[str, HostData] = {}
        for host in self.hosts:
            host_data = HostData(hostname=host)
            data[host] = host_data
            info = discovered.get(host)
            if info is None:
                LOGGER.debug("No buckets found for host %s", host)
                continue

            if info.afk:
                events = await self.client.get_latest_events(info.afk)
                if events and (end := _event_end(events[0])) is not None:
                    host_data.last_seen = end
                    host_data.active = (
                        events[0].get("data", {}).get("status") == "not-afk"
                        and now - end < STALE_AFTER
                    )
                screen_time = await self.client.query(
                    SCREEN_TIME_QUERY.format(bucket=info.afk), [timeperiod]
                )
                if screen_time and isinstance(screen_time[0], (int, float)):
                    host_data.screen_time_today = float(screen_time[0])

            if info.window:
                if info.afk is None:
                    # Window-only host (e.g. mobile imports): derive activity
                    # from window event recency instead.
                    events = await self.client.get_latest_events(info.window)
                    if events and (end := _event_end(events[0])) is not None:
                        host_data.last_seen = end
                        host_data.active = now - end < STALE_AFTER
                        if host_data.active:
                            event_data = events[0].get("data", {})
                            host_data.current_app = event_data.get("app")
                            host_data.current_title = event_data.get("title")
                elif host_data.active:
                    events = await self.client.get_latest_events(info.window)
                    if events:
                        event_data = events[0].get("data", {})
                        host_data.current_app = event_data.get("app")
                        host_data.current_title = event_data.get("title")

        return data
