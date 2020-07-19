import logging
from enum import unique, Enum

logger = logging.getLogger(__name__)


@unique
class WirenControlType(Enum):
    """
    Wirenboard controls types
    Based on https://github.com/wirenboard/homeui/blob/master/conventions.md
    """
    # generic types
    switch = "switch"
    alarm = "alarm"
    pushbutton = "pushbutton"
    range = "range"
    rgb = "rgb"
    text = "text"
    value = "value"

    # special types
    temperature = "temperature"
    rel_humidity = "rel_humidity"
    atmospheric_pressure = "atmospheric_pressure"
    rainfall = "rainfall"
    wind_speed = "wind_speed"
    power = "power"
    power_consumption = "power_consumption"
    voltage = "voltage"
    water_flow = "water_flow"
    water_consumption = "water_consumption"
    resistance = "resistance"
    concentration = "concentration"
    heat_power = "heat_power"
    heat_energy = "heat_energy"

    # custom types
    current = "current"


WIREN_UNITS_DICT = {
    WirenControlType.temperature: '°C',
    WirenControlType.rel_humidity: '%',
    WirenControlType.atmospheric_pressure: 'millibar',
    WirenControlType.rainfall: 'mm per hour',
    WirenControlType.wind_speed: 'm/s',
    WirenControlType.power: 'watt',
    WirenControlType.power_consumption: 'kWh',
    WirenControlType.voltage: 'V',
    WirenControlType.water_flow: 'm³/hour',
    WirenControlType.water_consumption: 'm³',
    WirenControlType.resistance: 'Ohm',
    WirenControlType.concentration: 'ppm',
    WirenControlType.heat_power: 'Gcal/hour',
    WirenControlType.heat_energy: 'Gcal',
    WirenControlType.current: 'A',
}

_WIREN_TO_HASS_MAPPER = {
    WirenControlType.switch: None,  # see wirenboard_to_hass_type()
    WirenControlType.alarm: 'binary_sensor',
    WirenControlType.pushbutton: 'binary_sensor',
    WirenControlType.range: None,  # see wirenboard_to_hass_type()
    # WirenControlType.rgb: 'light', #TODO: add
    WirenControlType.text: 'sensor',
    WirenControlType.value: 'sensor',

    WirenControlType.temperature: 'sensor',
    WirenControlType.rel_humidity: 'sensor',
    WirenControlType.atmospheric_pressure: 'sensor',
    WirenControlType.rainfall: 'sensor',
    WirenControlType.wind_speed: 'sensor',
    WirenControlType.power: 'sensor',
    WirenControlType.power_consumption: 'sensor',
    WirenControlType.voltage: 'sensor',
    WirenControlType.water_flow: 'sensor',
    WirenControlType.water_consumption: 'sensor',
    WirenControlType.resistance: 'sensor',
    WirenControlType.concentration: 'sensor',
    WirenControlType.heat_power: 'sensor',
    WirenControlType.heat_energy: 'sensor',

    WirenControlType.current: 'sensor',
}


def wiren_to_hass_type(control):
    if control.type == WirenControlType.switch:
        return 'binary_sensor' if control.read_only else 'switch'
    elif control.type == WirenControlType.range:
        # return 'sensor' if control.read_only else 'light'
        # return 'sensor' if control.read_only else 'cover'
        return 'sensor' if control.read_only else None
    elif control.type in _WIREN_TO_HASS_MAPPER:
        return _WIREN_TO_HASS_MAPPER[control.type]
    return None


_unknown_types = []


def apply_payload_for_component(payload, device, control, control_topic, inverse: bool):
    hass_entity_type = wiren_to_hass_type(control)

    if inverse:
        _payload_on = '0'
        _payload_off = '1'
    else:
        _payload_on = '1'
        _payload_off = '0'

    if hass_entity_type == 'switch':
        payload.update({
            'payload_on': _payload_on,
            'payload_off': _payload_off,
            'state_on': _payload_on,
            'state_off': _payload_off,
            'state_topic': f"{control_topic}",
            'command_topic': f"{control_topic}/on",
        })
    elif hass_entity_type == 'binary_sensor':
        payload.update({
            'payload_on': _payload_on,
            'payload_off': _payload_off,
            'state_topic': f"{control_topic}",
        })
    elif hass_entity_type == 'sensor':
        payload.update({
            'state_topic': f"{control_topic}",
        })
        if control.type == WirenControlType.temperature:
            payload['device_class'] = 'temperature'
        if control.units:
            payload['unit_of_measurement'] = control.units
    # elif hass_entity_type == 'cover':
    #     if control.max is None:
    #         logger.error(f'{device}: Missing "max" for range: {control}')
    #         return
    #     payload.update({
    #         'tilt_status_topic': f"{control_topic}",
    #         'tilt_command_topic': f"{control_topic}/on",
    #         'tilt_min': 0,
    #         'tilt_max': control.max,
    #         'tilt_closed_value': 0,
    #         'tilt_opened_value': control.max,
    #     })
    # elif hass_entity_type == 'light':
    #     if control.max is None:
    #         logger.error(f'{device}: Missing "max" for light: {control}')
    #         return
    #     payload.update({
    #         'command_topic': f"{control_topic}/none",
    #         'brightness_state_topic': f"{control_topic}",
    #         'brightness_command_topic': f"{control_topic}/on",
    #         'brightness_scale': control.max
    #     })
    else:
        if not hass_entity_type in _unknown_types:
            logger.warning(f"No algorithm for hass type '{control.type.name}', hass: '{hass_entity_type}'")
            _unknown_types.append(hass_entity_type)
        return None

    return hass_entity_type
