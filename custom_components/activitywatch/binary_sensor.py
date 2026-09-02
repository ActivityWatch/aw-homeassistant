"""Binary sensors for the ActivityWatch integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ActivityWatchConfigEntry, ActivityWatchCoordinator
from .entity import ActivityWatchEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ActivityWatchConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ActivityWatch binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        ActivityWatchActiveSensor(coordinator, host) for host in coordinator.hosts
    )


class ActivityWatchActiveSensor(ActivityWatchEntity, BinarySensorEntity):
    """Whether the host is actively being used (not AFK)."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    _attr_translation_key = "active"

    def __init__(self, coordinator: ActivityWatchCoordinator, host: str) -> None:
        super().__init__(coordinator, host)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{host}_active"

    @property
    def is_on(self) -> bool | None:
        if (host_data := self.host_data) is None:
            return None
        return host_data.active

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.host_data is not None
            and self.host_data.active is not None
        )
