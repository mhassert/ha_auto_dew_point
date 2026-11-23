"""Automatically created dew point sensors for Zigbee2MQTT devices."""

import logging
import math
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, Platform, UnitOfTemperature
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import get_device_class, get_unit_of_measurement
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class EmptyState:
    """no extra state."""


type DewPointConfigEntry = ConfigEntry[EmptyState]


# HA-Hook
async def async_setup_entry(
    hass: HomeAssistant,
    entry: DewPointConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor platform from a config entry."""
    known_unique_ids: set[str] = set()

    @callback
    def _handle_entity_registry_updated(
        event: Event[er.EventEntityRegistryUpdatedData],
    ) -> None:
        """React to newly registered and changed entities."""
        if event.data["action"] not in ["create", "update"]:
            return

        entity_id = event.data["entity_id"]
        entity_reg = er.async_get(hass)
        entity_entry = entity_reg.async_get(entity_id)

        #
        # Ignore create event for dew point sensors belonging to our DOMAIN.
        # Note: confusingly, the meaning of platform and domain are opposite here.
        if (
            entity_entry is not None
            and entity_entry.platform != DOMAIN
            and entity_entry.domain == Platform.SENSOR
            and entity_entry.device_class
            in (SensorDeviceClass.TEMPERATURE, SensorDeviceClass.HUMIDITY)
            and entity_entry.device_id is not None
        ):
            device_reg = dr.async_get(hass)
            device = device_reg.async_get(entity_entry.device_id)
            if device is not None:
                inspect_device(device, hass, async_add_entities, known_unique_ids)

    entry.async_on_unload(
        hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED, _handle_entity_registry_updated
        )
    )
    scan_all_devices(hass, async_add_entities, known_unique_ids)


def scan_all_devices(
    hass: HomeAssistant,
    async_add_entities: AddConfigEntryEntitiesCallback,
    known_unique_ids: set[str],
) -> None:
    """Scan all devices and inspect them."""
    device_reg = dr.async_get(hass)

    _LOGGER.info("Scanning all devices")
    for device in list(device_reg.devices):
        inspect_device(device, hass, async_add_entities, known_unique_ids)


def inspect_device(
    device: dr.AnyDeviceEntry,
    hass: HomeAssistant,
    async_add_entities: AddConfigEntryEntitiesCallback,
    known_unique_ids: set[str],
) -> None:
    """
    Create a dew point entity for this device.

    Only create it when the device has exactly one source of each type.
    """
    entity_reg = er.async_get(hass)

    _LOGGER.info("Scanning device %s", device.name)

    unique_temperature_entity: er.RegistryEntry | None = None
    unique_humidity_entity: er.RegistryEntry | None = None
    entities_of_device: list[er.RegistryEntry] = er.async_entries_for_device(
        entity_reg, device.id, include_disabled_entities=True
    )
    for entity in entities_of_device:
        _LOGGER.info(
            "Scanning entity %s (integration=%s, kind=%s)",
            entity.entity_id,
            entity.platform,
            entity.domain,
        )
        if entity.domain != Platform.SENSOR:
            continue

        if entity.platform == DOMAIN:
            # the dew point sensor itself is a temperature sensor.
            # ignore it as a temperature source, if it already exists in the registry.
            _LOGGER.info("Existing dew point sensor %s skipped", entity.entity_id)
            continue

        # This attribute is searched in State, then in entity.device_class,
        # then entity.original_device_class
        device_class = get_device_class(hass, entity.entity_id)
        unit = get_unit_of_measurement(hass, entity.entity_id)

        if device_class == SensorDeviceClass.TEMPERATURE and unit in (
            UnitOfTemperature.CELSIUS,
            UnitOfTemperature.FAHRENHEIT,
        ):
            if unique_temperature_entity is None:
                unique_temperature_entity = entity
            else:
                # temperature sensor is ambiguous.
                _LOGGER.info(
                    "Multiple temperature sensors found: %s and %s, skipping device %s",
                    entity.entity_id,
                    unique_temperature_entity.entity_id,
                    device.name,
                )
                unique_temperature_entity = None
                return
        elif device_class == SensorDeviceClass.HUMIDITY and unit == PERCENTAGE:
            if unique_humidity_entity is None:
                unique_humidity_entity = entity
            else:
                # humidity is ambiguous
                _LOGGER.info(
                    "Multiple humidity sensors found: %s and %s, skipping device %s",
                    entity.entity_id,
                    unique_humidity_entity.entity_id,
                    device.name,
                )
                unique_humidity_entity = None
                return

    if unique_temperature_entity is not None and unique_humidity_entity is not None:
        create_dew_point_sensor(
            hass,
            device,
            unique_temperature_entity,
            unique_humidity_entity,
            async_add_entities,
            known_unique_ids,
        )


def create_dew_point_sensor(
    hass: HomeAssistant,
    device: dr.AnyDeviceEntry,
    temperature_entity: er.RegistryEntry,
    humidity_entity: er.RegistryEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    known_unique_ids: set[str],
) -> None:
    """Create one dew point entity only when a device has exactly one of each source."""
    entity_reg = er.async_get(hass)

    unique_id = f"{temperature_entity.unique_id}_{humidity_entity.unique_id}_dew_point"
    if unique_id in known_unique_ids:
        _LOGGER.info(
            "Dew point sensor uid is active: %s, skipping device %s",
            unique_id,
            device.name,
        )
        return

    temperature_unit = temperature_entity.unit_of_measurement
    if temperature_unit is None:
        return

    # Manually pre-register entity with device-id so it is used in building
    # the enitity_id.
    entity_reg.async_get_or_create(
        domain=Platform.SENSOR,
        platform=DOMAIN,
        unique_id=unique_id,
        device_id=device.id,
        has_entity_name=True,
        object_id_base="dewpoint",
        translation_key="dew_point",
    )

    async_add_entities(
        [
            AutoDewPointSensor(
                device.id,
                unique_id,
                temperature_entity.entity_id,
                humidity_entity.entity_id,
                temperature_unit,
            )
        ],
        update_before_add=True,
    )
    known_unique_ids.add(unique_id)


class AutoDewPointSensor(SensorEntity):
    """A dew point sensor attached to the source Zigbee2MQTT device."""

    _attr_has_entity_name = True
    _attr_translation_key = "dew_point"
    _attr_icon = "mdi:water-thermometer"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        device_id: str,
        unique_id: str,
        temperature_entity: str,
        humidity_entity: str,
        temperature_unit: str,
    ) -> None:
        """Init calculated dew point sensor."""
        # ha attributes
        self._attr_unique_id = unique_id
        self._attr_extra_state_attributes = {
            "temperature_entity": temperature_entity,
            "humidity_entity": humidity_entity,
            "calculation": "Magnus formula",
        }
        self._attr_native_value: float | None = None

        # custom attributes
        self._temperature_entity = temperature_entity
        self._humidity_entity = humidity_entity
        self._temperature_unit = temperature_unit
        self._target_device_id = device_id
        self._unsub_temperature: CALLBACK_TYPE | None = None
        self._unsub_humidity: CALLBACK_TYPE | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Listen to both source entities."""
        await super().async_added_to_hass()

        entity_reg = er.async_get(self.hass)
        if self.entity_id is not None:
            entity_reg.async_update_entity(
                self.entity_id,
                device_id=self._target_device_id,
            )

        self._unsub_temperature = async_track_state_change_event(
            self.hass, [self._temperature_entity], self._async_source_changed
        )
        self._unsub_humidity = async_track_state_change_event(
            self.hass, [self._humidity_entity], self._async_source_changed
        )
        self._update_value()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Remove source listeners."""
        if self._unsub_temperature:
            self._unsub_temperature()
        if self._unsub_humidity:
            self._unsub_humidity()
        await super().async_will_remove_from_hass()

    @callback
    def _async_source_changed(self, _event: Event[EventStateChangedData]) -> None:
        self._update_value()
        self.async_write_ha_state()

    @callback
    def _update_value(self) -> None:
        """Calculate dew point in Celsius using the Magnus approximation."""
        temperature_state = self.hass.states.get(self._temperature_entity)
        humidity_state = self.hass.states.get(self._humidity_entity)
        try:
            if temperature_state is None or humidity_state is None:
                self._attr_native_value = None
                return
            temperature = float(temperature_state.state)
            humidity = float(humidity_state.state)
            if not math.isfinite(temperature) or not math.isfinite(humidity):
                self._attr_native_value = None
                return
            if not 0 < humidity <= 100:
                self._attr_native_value = None
                return
            if self._temperature_unit == UnitOfTemperature.FAHRENHEIT:
                temperature = (temperature - 32) * 5 / 9

            a, b = 17.62, 243.12
            gamma = math.log(humidity / 100.0) + (a * temperature) / (b + temperature)
            self._attr_native_value = round((b * gamma) / (a - gamma), 2)
        except TypeError, ValueError, ZeroDivisionError, OverflowError:
            self._attr_native_value = None
