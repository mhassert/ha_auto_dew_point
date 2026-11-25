
# Auto Dew Point

Auto Dew Point is a Home Assistant custom integration that creates dew-point
sensors for devices with exactly one temperature sensor and one humidity sensor.
It supports temperature sources in Celsius or Fahrenheit and humidity in percent;
calculated dew points are reported in Celsius. Devices with ambiguous source
sensors are skipped.

## Installation

Install with HACS, or copy `custom_components/auto_dew_point` into your Home
Assistant configuration's `custom_components` directory and restart Home
Assistant.

## Setup

In Home Assistant, go to **Settings → Devices & services → Add integration**,
then select **Auto Dew Point**. The integration discovers eligible devices
automatically; no additional options are required.
