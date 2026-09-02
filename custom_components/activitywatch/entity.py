"""Base entity for the ActivityWatch integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ActivityWatchCoordinator, HostData


class ActivityWatchEntity(CoordinatorEntity[ActivityWatchCoordinator]):
    """Entity tied to one tracked ActivityWatch host."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ActivityWatchCoordinator, host: str) -> None:
        super().__init__(coordinator)
        self._host = host
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.config_entry.unique_id}_{host}")},
            name=host,
            manufacturer="ActivityWatch",
            model="Tracked host",
            configuration_url=coordinator.client.server_url,
        )

    @property
    def host_data(self) -> HostData | None:
        """Return the coordinator data for this host."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._host)
