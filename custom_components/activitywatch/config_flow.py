"""Config flow for the ActivityWatch integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .api import ActivityWatchClient, ActivityWatchConnectionError
from .const import (
    CONF_HOSTS,
    CONF_UPDATE_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    LOGGER,
    RECENT_HOST_WINDOW,
)
from .coordinator import ActivityWatchConfigEntry, HostBuckets, discover_hosts

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_SSL, default=False): bool,
    }
)


def _hosts_schema(
    discovered: dict[str, HostBuckets], selected: list[str]
) -> vol.Schema:
    """Build a multi-select of hosts, most recently active first."""
    ordered = sorted(
        discovered.items(),
        key=lambda item: item[1].last_updated or dt_util.utc_from_timestamp(0),
        reverse=True,
    )
    options = [
        SelectOptionDict(value=host, label=host) for host, _ in ordered
    ]
    # Include previously selected hosts that no longer have buckets, so
    # reconfiguring never silently drops them.
    options.extend(
        SelectOptionDict(value=host, label=f"{host} (no buckets found)")
        for host in selected
        if host not in discovered
    )
    return vol.Schema(
        {
            vol.Required(CONF_HOSTS, default=selected): SelectSelector(
                SelectSelectorConfig(
                    options=options,
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                )
            )
        }
    )


def _recent_hosts(discovered: dict[str, HostBuckets]) -> list[str]:
    """Hosts with bucket activity within the recency window."""
    cutoff = dt_util.utcnow() - RECENT_HOST_WINDOW
    return [
        host
        for host, info in discovered.items()
        if info.last_updated is not None and info.last_updated > cutoff
    ]


class ActivityWatchConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._discovered: dict[str, HostBuckets] = {}
        self._server_hostname = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the aw-server connection details."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = ActivityWatchClient(
                async_get_clientsession(self.hass),
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input[CONF_SSL],
            )
            try:
                info = await client.get_info()
                buckets = await client.get_buckets()
            except ActivityWatchConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected error connecting to aw-server")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["device_id"])
                self._abort_if_unique_id_configured()
                self._data = user_input
                self._server_hostname = info.get("hostname", user_input[CONF_HOST])
                self._discovered = discover_hosts(buckets)
                if not self._discovered:
                    return self.async_abort(reason="no_hosts")
                return await self.async_step_hosts()
        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_hosts(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick which tracked hosts to expose as devices."""
        if user_input is not None and user_input[CONF_HOSTS]:
            return self.async_create_entry(
                title=f"ActivityWatch ({self._server_hostname})",
                data=self._data,
                options={
                    CONF_HOSTS: user_input[CONF_HOSTS],
                    CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
                },
            )
        return self.async_show_form(
            step_id="hosts",
            data_schema=_hosts_schema(self._discovered, _recent_hosts(self._discovered)),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ActivityWatchConfigEntry,
    ) -> ActivityWatchOptionsFlow:
        """Create the options flow."""
        return ActivityWatchOptionsFlow()


class ActivityWatchOptionsFlow(OptionsFlow):
    """Change tracked hosts and polling interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        entry = self.config_entry
        client = ActivityWatchClient(
            async_get_clientsession(self.hass),
            entry.data[CONF_HOST],
            entry.data[CONF_PORT],
            entry.data.get(CONF_SSL, False),
        )
        discovered: dict[str, HostBuckets] = {}
        try:
            discovered = discover_hosts(await client.get_buckets())
        except ActivityWatchConnectionError:
            LOGGER.warning("Could not fetch buckets while showing options")

        selected = entry.options.get(CONF_HOSTS, [])
        schema = _hosts_schema(discovered, selected).extend(
            {
                vol.Required(
                    CONF_UPDATE_INTERVAL,
                    default=entry.options.get(
                        CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=10,
                        max=3600,
                        step=1,
                        unit_of_measurement="s",
                        mode=NumberSelectorMode.BOX,
                    )
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
