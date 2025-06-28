import yaml
import logging
import paho.mqtt.client as mqtt
import requests
import json
import threading
import time

from json import JSONDecodeError
from pathlib import Path
from .config_loader import download_config_from_github, get_version


def load_config(path='config.yaml'):
    if not Path(path).exists():
        print(f"Config file ({path}) could not be found! Getting a fresh one!")
        tag_version = get_version()
        try:
            download_config_from_github(tag_version)
            print(f"Please update the config.yaml file for your environment and rerun mqtfy.")
            exit()
        except Exception as e:
            print(f"Sorry, config file {path} could not be downloaded, please go to 'https://github.com/FreakErn/MQtfy' and download a config File for this version ({tag_version})!")

    with open(path, 'r') as f:
        return yaml.safe_load(f)

def str_to_bool(value):
    return str(value).lower() in ("1", "true", "yes", "on")

def main():
    config = load_config()

    log_level_str = config.get('log_level', 'ERROR').upper()
    log_level = getattr(logging, log_level_str, logging.ERROR)
    logging.basicConfig(level=log_level, format='[%(asctime)s] %(levelname)s: %(message)s')
    logger = logging.getLogger(__name__)

    MQTT_HOST = config.get('mqtt_host', 'localhost')
    MQTT_PORT = config.get('mqtt_port', 1883)
    MQTT_USER = config.get('mqtt_user')
    MQTT_PASS = config.get('mqtt_pass')
    MQTT_TOPIC = config.get('mqtt_topic', 'mqtfy/')
    MQTT_CLIENT_ID = config.get('mqtt_client_id', 'mqtfy-client')
    MAIN_NTFY_URL = config.get('ntfy_url', 'https://ntfy.sh')
    IGNORE_EVENTS = [item.strip().lower() for item in config.get('ignore_events', '').split(',') if item.strip()]
    
    RECEIVE_ONLY_MESSAGE = str_to_bool(config.get('receive_only_message', True))

    logger.debug(f"RECEIVE_ONLY_MESSAGE: {RECEIVE_ONLY_MESSAGE}")

    ALLOWED_SUBTOPICS = {
                entry['topic']: (
            entry['ntfy_user'],
            entry['ntfy_pass'],
            entry.get('ntfy_url', MAIN_NTFY_URL)
        )
        for entry in config.get('subtopics', [])
    }

    def on_connect(client, userdata, flags, reasonCode, properties):
        if reasonCode == 0:
            logger.info('Successfully connected to the mqtt Broker.')
            client.subscribe(f"{MQTT_TOPIC}send/#")
            logger.debug(f"Subscribed: {MQTT_TOPIC}send/#")
        else:
            logger.error(f"Connection failed. ReasonCode={reasonCode}")

    def on_message(client, userdata, msg):
        topic_suffix = msg.topic[len(MQTT_TOPIC + "send/"):]

        payload_json = msg.payload.decode()
        data = {}
        try:
            data = json.loads(payload_json)
            logger.debug(f"Receive JSON: {data}")
        except JSONDecodeError as e:
            logger.debug(f"Use {payload_json} as string payload")
            data['message'] = payload_json

        data['topic'] = topic_suffix
        logger.debug(f"Output JSON: {data}")

        if topic_suffix in ALLOWED_SUBTOPICS:
            ntfy_user, ntfy_pass, ntfy_url = ALLOWED_SUBTOPICS[topic_suffix]
            url = f"{ntfy_url.rstrip('/')}"

            try:
                resp = requests.post(
                    url,
                    data=json.dumps(data),
                    auth=(ntfy_user, ntfy_pass)
                )
                logger.info(f"Message to ntfy ({topic_suffix}) send: status={resp.status_code}")
            except Exception as e:
                logger.exception(f"Error sending to ntfy for '{topic_suffix}': {e}")
        else:
            logger.warning(f"Ignore unknown subtopic: '{topic_suffix}'")

    def listen_to_ntfy(subtopic, ntfy_user, ntfy_pass, ntfy_url):
        logger.debug(f"Try to connect to {ntfy_url}")
        while True:
            try:
                url = f"{ntfy_url.rstrip('/')}/{subtopic}/json"
                with requests.get(url, stream=True, auth=(ntfy_user, ntfy_pass), timeout=90) as resp:
                    if resp.status_code == 200:
                        logger.info(f"Start JSON-Stream for {subtopic}")
                        for line in resp.iter_lines():
                            if line:
                                try:
                                    data = json.loads(line)
                                    event = data.get("event").lower()
                                    if event in IGNORE_EVENTS:
                                        #logger.debug(f"Event {event} on {subtopic} ignored")
                                        continue

                                    if RECEIVE_ONLY_MESSAGE:
                                        content = data.get("message")
                                    else:
                                        content = line.decode("UTF-8")
                                    if content:
                                        topic = f"{MQTT_TOPIC}receive/{subtopic}"
                                        mqtt_client.publish(topic, content)
                                        logger.info(f"Message Received from ntfy ans published to mqtt: {topic}")
                                except Exception as e:
                                    logger.warning(f"Error while processing JSON message: {e}")
                    else:
                        logger.warning(f"Subscribe to JSON-Stream failed for {subtopic} - Status: {resp.status_code}")
                        if resp.status_code in (401, 403):
                            logger.error(f"Connection to {url} with {ntfy_user} is not allowed!")
                            return
            except Exception as e:
                logger.warning(f"Error in JSON connection for {subtopic}: {e}")
            logger.info(f"Restarting JSON connection to {subtopic} in 5 seconds.")
            time.sleep(5)

    mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID, protocol=mqtt.MQTTv5)
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    try:
        logger.info(f"Connecting to MQTT-Broker {MQTT_HOST}:{MQTT_PORT}")
        mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        for subtopic, (ntfy_user, ntfy_pass, ntfy_url) in ALLOWED_SUBTOPICS.items():
            threading.Thread(target=listen_to_ntfy, args=(subtopic, ntfy_user, ntfy_pass, ntfy_url), daemon=True).start()

        mqtt_client.loop_forever()
    except Exception as e:
        logger.exception(f"Failed to connect to MQTT broker: {e}")
