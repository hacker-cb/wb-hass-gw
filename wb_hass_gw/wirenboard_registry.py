import logging

from wb_hass_gw.mappers import WirenControlType

logger = logging.getLogger(__name__)


class WirenControl:
    type: WirenControlType = None
    read_only = False
    error = None
    units = None
    max = None
    state = None

    def __init__(self, control_id):
        self.id = control_id

    @property
    def debug_id(self):
        return self.id.lower().replace(" ", "_").replace("-", "_")

    def apply_type(self, t):
        if self.type == t:
            return False
        else:
            self.type = t
            return True

    def apply_read_only(self, read_only):
        if self.read_only == read_only:
            return False
        else:
            self.read_only = read_only
            return True

    def apply_error(self, error):
        if self.error == error:
            return False
        else:
            self.error = error
            return True

    def apply_units(self, units):
        if self.units == units:
            return False
        else:
            self.units = units
            return True

    def apply_max(self, max):
        if self.max == max:
            return False
        else:
            self.max = max
            return True

    def __str__(self) -> str:
        return f'Control [{self.id}] type: {self.type}, units: {self.units}, read_only: {self.read_only}, error: {self.error}, max: {self.max}, state: {self.state}'


class WirenDevice:
    name = None

    def __init__(self, device_id):
        self.id = device_id
        self._controls = {}

    @property
    def debug_id(self):
        return self.id.lower().replace(" ", "_").replace("-", "_")

    @property
    def controls(self):
        return self._controls

    def get_control(self, control_id) -> WirenControl:
        if control_id not in self._controls.keys():
            self._controls[control_id] = WirenControl(control_id)
            logger.debug(f'{self}: new control: {control_id}')
        return self._controls[control_id]

    def __str__(self) -> str:
        return f'Device [{self.id}] {self.name}'


class WirenBoardDeviceRegistry:
    _devices = {}

    local_device_id = 'wirenboard'
    local_device_name = 'Wirenboard'
    _local_devices = ('wb-adc', 'wbrules', 'wb-gpio', 'power_status', 'network', 'system', 'hwmon', 'buzzer', 'alarms')

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(WirenBoardDeviceRegistry, cls).__new__(cls)
        return cls.instance

    @property
    def devices(self):
        return self._devices

    def get_device(self, device_id) -> WirenDevice:
        if device_id not in self._devices.keys():
            self._devices[device_id] = WirenDevice(device_id)
            logger.debug(f'New device: {device_id}')

        return self._devices[device_id]

    def is_local_device(self, device):
        return device.id in self._local_devices
