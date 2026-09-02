"""The ActivityWatch integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ActivityWatchClient
from .const import CONF_HOSTS, DOMAIN
from .coordinator import ActivityWatchConfigEntry, ActivityWatchCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: ActivityWatchConfigEntry
) -> bool:
    """Set up ActivityWatch from a config entry."""
    client = ActivityWatchClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data.get(CONF_SSL, False),
    )
    coordinator = ActivityWatchCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ActivityWatchConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant, entry: ActivityWatchConfigEntry
) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: ActivityWatchConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Allow removing devices for hosts that are no longer tracked."""
    tracked = {
        f"{entry.unique_id}_{host}" for host in entry.options.get(CONF_HOSTS, [])
    }
    return not any(
        identifier in tracked
        for domain, identifier in device_entry.identifiers
        if domain == DOMAIN
    )
