"""Tests for the ActivityWatch config flow."""

from __future__ import annotations

import aiohttp
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.activitywatch.const import (
    CONF_HOSTS,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)

from .conftest import BASE_URL

USER_INPUT = {CONF_HOST: "1.2.3.4", CONF_PORT: 5600, CONF_SSL: False}


async def test_full_flow(
    hass: HomeAssistant, mock_aw_server: AiohttpClientMocker
) -> None:
    """Happy path: connect, pick hosts, create entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "hosts"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOSTS: ["myhost"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ActivityWatch (aw-server-host)"
    assert result["data"] == USER_INPUT
    assert result["options"][CONF_HOSTS] == ["myhost"]
    assert CONF_UPDATE_INTERVAL in result["options"]
    assert result["result"].unique_id == "test-device-id"


async def test_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Connection failure shows an error on the user form."""
    aioclient_mock.get(f"{BASE_URL}/info", exc=aiohttp.ClientError("boom"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_already_configured(
    hass: HomeAssistant, mock_aw_server: AiohttpClientMocker
) -> None:
    """The same aw-server (by device_id) can only be added once."""
    MockConfigEntry(
        domain=DOMAIN, data=USER_INPUT, unique_id="test-device-id"
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
