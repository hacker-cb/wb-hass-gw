import asyncio
import getopt
import logging
import os
import signal
from enum import Enum
from sys import argv

import yaml
from voluptuous import Required, Schema, MultipleInvalid, All, Any, Optional, Coerce

from wb_hass_gw.homeassistant import HomeAssistantConnector
from wb_hass_gw.wirenboard import WirenConnector

logging.getLogger().setLevel(logging.INFO)  # root

logger = logging.getLogger(__name__)

STOP = asyncio.Event()


# asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


class ConfigLogLevel(Enum):
    FATAL = 'FATAL'
    ERROR = 'ERROR'
    WARNING = 'WARNING'
    INFO = 'INFO'
    DEBUG = 'DEBUG'


LOGLEVEL_MAPPER = {
    ConfigLogLevel.FATAL: logging.FATAL,
    ConfigLogLevel.ERROR: logging.ERROR,
    ConfigLogLevel.WARNING: logging.WARNING,
    ConfigLogLevel.INFO: logging.INFO,
    ConfigLogLevel.DEBUG: logging.DEBUG,
}

config_schema = Schema({
    Optional('general', default={}): {
        Optional('loglevel', default=ConfigLogLevel.INFO): Coerce(ConfigLogLevel),
    },
    Required('wirenboard'): {
        Required('broker_host'): str,
        Optional('broker_port', default=1883): int,
        Optional('username'): str,
        Optional('password'): str,
        Optional('client_id', default='wb-hass-gw'): str,
        Optional('topic_prefix', default=''): str
    },
    Required('homeassistant'): {
        Required('broker_host'): str,
        Optional('broker_port', default=1883): int,
        Optional('username'): str,
        Optional('password'): str,
        Optional('client_id', default='wb-hass-gw'): str,
        Required('topic_prefix'): str,
        Optional('entity_prefix', default=''): str,
        Optional('discovery_topic', default='homeassistant'): str,
        Optional('status_topic', default='hass/status'): str,
        Optional('status_payload_online', default='online'): str,
        Optional('status_payload_offline', default='offline'): str,
        Optional('debounce', default={}) : {
            Optional('sensor', default=1000): int
        },
        Optional('subscribe_qos', default=0): int,
        Optional('publish_availability', default={}): {
            Optional('qos', default=0): int,
            Optional('retain', default=True): bool,
            Optional('publish_delay', default=1.0): float,
        },
        Optional('publish_state', default={}): {
            Optional('qos', default=0): int,
            Optional('retain', default=True): bool,
        },
        Optional('publish_config', default={}): {
            Optional('qos', default=0): int,
            Optional('retain', default=False): bool,
            Optional('publish_delay', default=1.0): float,
        },
        Optional('inverse', default=[]): [str],
        Optional('split_devices', default=[]): [str],
        Optional('split_entities', default=[]): [str]
    },
})


def ask_exit(*args):
    logger.info('Exiting')
    STOP.set()


async def main(conf):
    logging.basicConfig(level=LOGLEVEL_MAPPER[conf['general']['loglevel']])
    logging.getLogger('gmqtt').setLevel(logging.ERROR)  # don't need extra messages from mqtt

    wiren_conf = conf['wirenboard']
    hass_conf = conf['homeassistant']

    logger.info('Starting')
    wiren = WirenConnector(
        broker_host=wiren_conf['broker_host'],
        broker_port=wiren_conf['broker_port'],
        username=wiren_conf['username'] if 'username' in wiren_conf else None,
        password=wiren_conf['password'] if 'password' in wiren_conf else None,
        client_id=wiren_conf['client_id'],
        topic_prefix=wiren_conf['topic_prefix']
    )
    hass = HomeAssistantConnector(
        broker_host=hass_conf['broker_host'],
        broker_port=hass_conf['broker_port'],
        username=hass_conf['username'] if 'username' in hass_conf else None,
        password=hass_conf['password'] if 'password' in hass_conf else None,
        client_id=hass_conf['client_id'],
        topic_prefix=hass_conf['topic_prefix'],
        entity_prefix=hass_conf['entity_prefix'],
        discovery_topic=hass_conf['discovery_topic'],
        status_topic=hass_conf['status_topic'],
        status_payload_online=hass_conf['status_payload_online'],
        status_payload_offline=hass_conf['status_payload_offline'],
        debounce=hass_conf['debounce'],
        subscribe_qos=hass_conf['subscribe_qos'],
        availability_qos=hass_conf['publish_availability']['qos'],
        availability_retain=hass_conf['publish_availability']['retain'],
        availability_publish_delay=hass_conf['publish_availability']['publish_delay'],
        state_qos=hass_conf['publish_state']['qos'],
        state_retain=hass_conf['publish_state']['retain'],
        config_qos=hass_conf['publish_config']['qos'],
        config_retain=hass_conf['publish_config']['retain'],
        config_publish_delay=hass_conf['publish_config']['publish_delay'],
        inverse=hass_conf['inverse'],
        split_devices=hass_conf['split_devices'],
        split_entities=hass_conf['split_entities']
    )
    wiren.hass = hass
    hass.wiren = wiren

    await hass.connect()  # FIXME: handle connect exceptions
    await wiren.connect()  # FIXME: handle connect exceptions

    await STOP.wait()

    await hass.disconnect()
    await wiren.disconnect()


def usage():
    print('Usage:\n'
          'wb-hass-gw.py -c <config_file>')


if __name__ == '__main__':
    config_file = None
    try:
        opts, args = getopt.getopt(argv[1:], "hc:")
    except getopt.GetoptError:
        usage()
        exit(1)
    for opt, arg in opts:
        if opt == '-h':
            usage()
            exit()
        elif opt == '-c':
            config_file = arg
    if not config_file:
        usage()
        exit(1)

    try:
        with open(config_file) as f:
            config_file_content = f.read()
    except OSError as e:
        logger.error(e)
        exit(1)

    config = yaml.load(config_file_content, Loader=yaml.FullLoader)
    if not config:
        logger.error(f'Could not load conf "{config_file}"')
        exit(1)
    try:
        config = config_schema(config)
    except MultipleInvalid as e:
        logger.error('Config error')
        logger.error(e)
        exit(1)

    loop = asyncio.get_event_loop()

    loop.add_signal_handler(signal.SIGINT, ask_exit)
    loop.add_signal_handler(signal.SIGTERM, ask_exit)

    loop.run_until_complete(main(config))
