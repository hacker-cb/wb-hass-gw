import asyncio
import logging
import re

from wb_hass_gw.base_connector import BaseConnector
from wb_hass_gw.mappers import WirenControlType, WIREN_UNITS_DICT
from wb_hass_gw.wirenboard_registry import WirenBoardDeviceRegistry, WirenDevice, WirenControl

logger = logging.getLogger(__name__)


class WirenConnector(BaseConnector):
    hass = None
    _publish_delay_sec = 1  # Delay before publishing to ensure that we got all meta topics

    def __init__(self, broker_host, broker_port, username, password, client_id, topic_prefix):
        super().__init__(broker_host, broker_port, username, password, client_id)

        self._topic_prefix = topic_prefix

        self._device_meta_topic_re = re.compile(self._topic_prefix + r"/devices/([^/]*)/meta/([^/]*)")
        self._control_meta_topic_re = re.compile(self._topic_prefix + r"/devices/([^/]*)/controls/([^/]*)/meta/([^/]*)")
        self._control_state_topic_re = re.compile(self._topic_prefix + r"/devices/([^/]*)/controls/([^/]*)$")
        self._async_publish_tasks = {}  # We need async publish to wait that we go all meta from mqtt

    @staticmethod
    def _on_device_meta_change(device_id, meta_name, meta_value):
        device = WirenBoardDeviceRegistry().get_device(device_id)
        if meta_name == 'name':
            device.name = meta_value
        # print(f'DEVICE: {device_id} / {meta_name} ==> {meta_value}')

    def _on_control_meta_change(self, device_id, control_id, meta_name, meta_value):
        device = WirenBoardDeviceRegistry().get_device(device_id)
        control = device.get_control(control_id)

        # print(f'CONTROL: {device_id} / {control_id} / {meta_name} ==> {meta_value}')

        if meta_name == 'error':
            # publish availability separately. do not publish all device
            if control.apply_error(False if not meta_value else True):
                self.hass.publish_availability(device, control)
        else:
            has_changes = False
            if meta_name == 'order':
                return  # Ignore
            elif meta_name == 'type':
                try:
                    has_changes |= control.apply_type(WirenControlType(meta_value))
                    if control.type in WIREN_UNITS_DICT:
                        has_changes |= control.apply_units(WIREN_UNITS_DICT[control.type])
                except ValueError:
                    logger.warning(f'Unknown type for wirenboard control: {meta_value}')
            elif meta_name == 'readonly':
                has_changes |= control.apply_read_only(True if meta_value == '1' else False)
            elif meta_name == 'units':
                has_changes |= control.apply_units(meta_value)
            elif meta_name == 'max':
                has_changes |= control.apply_max(int(meta_value) if meta_value else None)
            if has_changes:
                self._async_publish_with_delay(device, control)

    def _async_publish_with_delay(self, device: WirenDevice, control: WirenControl):
        task_id = f"{device.id}_{control.id}"

        async def do_publish(d, c):
            await asyncio.sleep(self._publish_delay_sec)
            self.hass.publish_control(d, c)
            del self._async_publish_tasks[task_id]

        if task_id in self._async_publish_tasks:
            self._async_publish_tasks[task_id].cancel()
        loop = asyncio.get_event_loop()
        self._async_publish_tasks[task_id] = loop.create_task(do_publish(device, control))

    def _subscribe(self, client):
        client.subscribe(self._topic_prefix + '/devices/+/meta/+', qos=1)
        client.subscribe(self._topic_prefix + '/devices/+/controls/+/meta/+', qos=1)
        client.subscribe(self._topic_prefix + '/devices/+/controls/+', qos=1)

    async def _on_message(self, client, topic, payload, qos, properties):
        # print(f'RECV MSG: {topic}', payload)
        payload = payload.decode("utf-8")
        device_topic_match = self._device_meta_topic_re.match(topic)
        control_meta_topic_match = self._control_meta_topic_re.match(topic)
        control_state_topic_match = self._control_state_topic_re.match(topic)
        if device_topic_match:
            self._on_device_meta_change(device_topic_match.group(1), device_topic_match.group(2), payload)
        elif control_meta_topic_match:
            self._on_control_meta_change(control_meta_topic_match.group(1), control_meta_topic_match.group(2), control_meta_topic_match.group(3), payload)
        elif control_state_topic_match:
            device = WirenBoardDeviceRegistry().get_device(control_state_topic_match.group(1))
            control = device.get_control(control_state_topic_match.group(2))
            control.state = payload
            self.hass.set_control_state(device, control, payload)

    def set_control_state(self, device: WirenDevice, control: WirenControl, payload, retain):
        target_topic = f"{self._topic_prefix}/devices/{device.id}/controls/{control.id}/on"
        self._publish(target_topic, payload, qos=1, retain=retain)
