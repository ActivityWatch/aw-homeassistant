"""Tests for ActivityWatch setup and entity states."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.activitywatch.const import (
    CONF_HOSTS,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4", CONF_PORT: 5600, CONF_SSL: False},
        options={CONF_HOSTS: ["myhost"], CONF_UPDATE_INTERVAL: 60},
        unique_id="test-device-id",
        title="ActivityWatch (aw-server-host)",
    )


async def setup_entry(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_entities(
    hass: HomeAssistant,
    mock_aw_server: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """Entities are created with the expected states."""
    await setup_entry(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    assert hass.states.get("binary_sensor.myhost_active").state == "on"
    assert hass.states.get("sensor.myhost_current_app").state == "Firefox"
    assert hass.states.get("sensor.myhost_last_seen").state is not None

    # Duration sensor: native seconds, displayed in hours via suggested unit.
    screen_time = hass.states.get("sensor.myhost_screen_time_today")
    assert screen_time is not None
    assert float(screen_time.state) == pytest.approx(12345.6 / 3600, rel=1e-3)

    # Privacy: the window title sensor exists but is disabled by default.
    assert hass.states.get("sensor.myhost_current_window_title") is None
    registry = er.async_get(hass)
    title_entity = registry.async_get_entity_id(
        "sensor", DOMAIN, "test-device-id_myhost_current_window_title"
    )
    assert title_entity is not None
    assert registry.async_get(title_entity).disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_unload(
    hass: HomeAssistant,
    mock_aw_server: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """The entry unloads cleanly."""
    await setup_entry(hass, config_entry)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED
