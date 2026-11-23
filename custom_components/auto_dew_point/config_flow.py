"""Config flow for Auto Dew Point."""

from typing import Any, override

from homeassistant import config_entries

from .const import DOMAIN


class AutoDewPointConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Auto Dew Point."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Create the single automatic discovery entry."""
        # Optional: Prevent adding the integration more than once
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="Auto Dew Point", data={})

        return self.async_show_form(step_id="user")
