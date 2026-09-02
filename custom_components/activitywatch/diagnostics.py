"""Diagnostics support for the ActivityWatch integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import ActivityWatchConfigEntry

REDACTED = "**redacted**"


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ActivityWatchConfigEntry
) -> dict[str, Any]:
    """Return diagnostics with sensitive fields redacted."""
    coordinator = entry.runtime_data
    hosts: dict[str, Any] = {}
    for host, data in (coordinator.data or {}).items():
        host_dict = asdict(data)
        # Window titles can contain message contents, URLs, document names.
        if host_dict.get("current_title") is not None:
            host_dict["current_title"] = REDACTED
        host_dict["last_seen"] = (
            data.last_seen.isoformat() if data.last_seen else None
        )
        hosts[host] = host_dict
    return {
        "options": dict(entry.options),
        "hosts": hosts,
    }
