"""Sensors for the ActivityWatch integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import ActivityWatchConfigEntry, ActivityWatchCoordinator, HostData
from .entity import ActivityWatchEntity


@dataclass(frozen=True, kw_only=True)
class ActivityWatchSensorDescription(SensorEntityDescription):
    """Describes an ActivityWatch sensor."""

    value_fn: Callable[[HostData], StateType | datetime]


SENSORS: tuple[ActivityWatchSensorDescription, ...] = (
    ActivityWatchSensorDescription(
        key="screen_time_today",
        translation_key="screen_time_today",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        value_fn=lambda data: data.screen_time_today,
    ),
    ActivityWatchSensorDescription(
        key="current_app",
        translation_key="current_app",
        value_fn=lambda data: data.current_app,
    ),
    # Window titles are the most sensitive data ActivityWatch collects
    # (they can contain message contents, document names, URLs), so this
    # entity is opt-in.
    ActivityWatchSensorDescription(
        key="current_window_title",
        translation_key="current_window_title",
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.current_title,
    ),
    ActivityWatchSensorDescription(
        key="last_seen",
        translation_key="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.last_seen,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ActivityWatchConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ActivityWatch sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        ActivityWatchSensor(coordinator, host, description)
        for host in coordinator.hosts
        for description in SENSORS
    )


class ActivityWatchSensor(ActivityWatchEntity, SensorEntity):
    """Sensor for one tracked host."""

    entity_description: ActivityWatchSensorDescription

    def __init__(
        self,
        coordinator: ActivityWatchCoordinator,
        host: str,
        description: ActivityWatchSensorDescription,
    ) -> None:
        super().__init__(coordinator, host)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{host}_{description.key}"
        )

    @property
    def native_value(self) -> StateType | datetime:
        if (host_data := self.host_data) is None:
            return None
        return self.entity_description.value_fn(host_data)
