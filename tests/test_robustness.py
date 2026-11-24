"""Config-flow and client robustness regressions."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.activitywatch.const import CONF_HOSTS, CONF_UPDATE_INTERVAL, DOMAIN

from .conftest import BASE_URL, INFO, buckets_fixture

USER_INPUT = {CONF_HOST: "1.2.3.4", CONF_PORT: 5600, CONF_SSL: False}


async def test_info_without_device_id_shows_error_not_crash(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """/info lacking device_id must not crash the flow (KeyError outside try)."""
    aioclient_mock.get(f"{BASE_URL}/info", json={"hostname": "h", "version": "v0.11.0"})
    aioclient_mock.get(f"{BASE_URL}/buckets/", json=buckets_fixture())
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "missing_device_id"}


async def test_changed_ip_updates_existing_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Re-adding the same server at a new IP should update host, not silently abort."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "9.9.9.9", CONF_PORT: 5600, CONF_SSL: False},
        options={CONF_HOSTS: ["myhost"], CONF_UPDATE_INTERVAL: 60},
        unique_id=INFO["device_id"],
    )
    entry.add_to_hass(hass)
    aioclient_mock.get(f"{BASE_URL}/info", json=INFO)
    aioclient_mock.get(f"{BASE_URL}/buckets/", json=buckets_fixture())
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "1.2.3.4", "entry still points at the dead IP"


async def test_options_flow_rejects_empty_hosts(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Options flow should enforce >=1 host like the config flow does."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=USER_INPUT,
        options={CONF_HOSTS: ["myhost"], CONF_UPDATE_INTERVAL: 60},
        unique_id=INFO["device_id"],
    )
    entry.add_to_hass(hass)
    aioclient_mock.get(f"{BASE_URL}/buckets/", json=buckets_fixture())
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_HOSTS: [], CONF_UPDATE_INTERVAL: 60}
    )
    assert result["type"] is FlowResultType.FORM, f"accepted empty hosts: {result.get('data')}"
    assert result["errors"] == {CONF_HOSTS: "no_hosts_selected"}


async def test_malformed_json_becomes_update_failed(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A JSON-typed but undecodable body should surface as UpdateFailed."""
    from custom_components.activitywatch.api import ActivityWatchClient
    from custom_components.activitywatch.coordinator import ActivityWatchCoordinator
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    entry = MockConfigEntry(
        domain=DOMAIN, data=USER_INPUT,
        options={CONF_HOSTS: ["myhost"], CONF_UPDATE_INTERVAL: 60},
        unique_id=INFO["device_id"],
    )
    entry.add_to_hass(hass)
    aioclient_mock.get(
        f"{BASE_URL}/buckets/", text="{truncated", headers={"Content-Type": "application/json"}
    )
    client = ActivityWatchClient(async_get_clientsession(hass), "1.2.3.4", 5600)
    coord = ActivityWatchCoordinator(hass, entry, client)
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()


async def test_today_window_uses_local_midnight(
    hass: HomeAssistant, mock_aw_server: AiohttpClientMocker
) -> None:
    """The "today" query period starts at HA-local midnight, with offsets."""
    from custom_components.activitywatch.api import ActivityWatchClient
    from custom_components.activitywatch.coordinator import ActivityWatchCoordinator
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    await hass.config.async_set_time_zone("Pacific/Auckland")
    entry = MockConfigEntry(
        domain=DOMAIN, data=USER_INPUT,
        options={CONF_HOSTS: ["myhost"], CONF_UPDATE_INTERVAL: 60},
        unique_id=INFO["device_id"],
    )
    entry.add_to_hass(hass)
    client = ActivityWatchClient(async_get_clientsession(hass), "1.2.3.4", 5600)
    coord = ActivityWatchCoordinator(hass, entry, client)
    data = await coord._async_update_data()
    posted = [c for c in mock_aw_server.mock_calls if c[0] == "POST"][0][2]
    start, end = posted["timeperiods"][0].split("/")
    s = dt_util.parse_datetime(start)
    assert s == dt_util.start_of_local_day()
    assert s.utcoffset() is not None and dt_util.parse_datetime(end).utcoffset() is not None
    assert data["myhost"].screen_time_today == 12345.6
