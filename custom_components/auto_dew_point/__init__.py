"""Auto Dew Point integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .sensor import DewPointConfigEntry

_PLATFORMS: list[Platform] = [Platform.SENSOR]


# HA-Hook
async def async_setup_entry(hass: HomeAssistant, entry: DewPointConfigEntry) -> None:
    """Set up automatic discovery for devices with temperature and humidity."""
    # Call async_setup_entry for all platforms, here: sensor.
    # The real magic happens in sensor.py
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)


# HA-Hook
async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload the integration."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, _PLATFORMS)
