import logging
from abc import ABC, abstractmethod

from gmqtt import Client as MQTTClient
from gmqtt.mqtt.constants import MQTTv311

logger = logging.getLogger(__name__)


class BaseConnector(ABC):

    def __init__(self, broker_host, broker_port, username, password, client_id):
        self._broker_host = broker_host
        self._broker_port = broker_port
        self._username = username
        self._password = password
        self._client_id = client_id

        self._client = MQTTClient(self._client_id)
        self._client.on_connect = self.__on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect
        self._client.on_subscribe = self._on_subscribe

    async def connect(self):
        if self._username and self._password:
            self._client.set_auth_credentials(self._username, self._password)
        await self._client.connect(self._broker_host, port=self._broker_port, version=MQTTv311)

    def disconnect(self):
        return self._client.disconnect()

    def __on_connect(self, client, flags, rc, properties):
        logger.info(f'Connected to {self._broker_host}')
        return self._on_connect(client)

    @abstractmethod
    def _on_message(self, client, topic, payload, qos, properties):
        pass

    def _on_subscribe(self, client, mid, qos, properties):
        logger.debug(f'Subscribed ({self._broker_host})')

    def _on_disconnect(self, packet, exc=None):
        logger.warning(f'Disconnected from {self._broker_host}')

    @abstractmethod
    def _on_connect(self, client):
        pass

    def _publish(self, message_or_topic, payload=None, qos=0, retain=False, **kwargs):
        if not self._client.is_connected:
            logger.warning(f"Client not ready ({self._broker_host})")
            return
        self._client.publish(message_or_topic, payload, qos, retain, **kwargs)

