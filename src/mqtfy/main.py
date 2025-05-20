import yaml
import logging
import paho.mqtt.client as mqtt
import requests
import json
import threading
import time
from pathlib import Path


def load_config(path='config.yaml'):
    if not Path(path).exists():
        print(f"Config file ({path}) could not be found! Exiting!")
        exit()
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
    NTFY_URL = config.get('ntfy_url', 'https://ntfy.sh')
    IGNORE_EVENTS = [item.strip().lower() for item in config.get('ignore_events', '').split(',') if item.strip()]
    
    RECEIVE_ONLY_MESSAGE = str_to_bool(config.get('receive_only_message', True))

    logger.debug(f"RECEIVE_ONLY_MESSAGE: {RECEIVE_ONLY_MESSAGE}")

    ALLOWED_SUBTOPICS = {
        entry['topic']: (entry['ntfy_user'], entry['ntfy_pass'])
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

        try:
            payload_json = msg.payload.decode()
            data = json.loads(payload_json)
            logger.debug(f"Receive JSON: {data}")
        except Exception as e:
            logger.error(f"Invalid JSON in Payload: {e}")
            return

        headers = data.get("headers")
        message = data.get("message")

        if not isinstance(headers, dict) or not isinstance(message, str):
            logger.warning(f"Message ignored – invalid format. headers: {headers}, message: {message}")
            return

        if topic_suffix in ALLOWED_SUBTOPICS:
            ntfy_user, ntfy_pass = ALLOWED_SUBTOPICS[topic_suffix]
            url = f"{NTFY_URL.rstrip('/')}/{topic_suffix}"

            try:
                resp = requests.post(
                    url,
                    headers=headers,
                    data=message.encode("utf-8"),
                    auth=(ntfy_user, ntfy_pass)
                )
                logger.info(f"Message to ntfy ({topic_suffix}) send: status={resp.status_code}")
            except Exception as e:
                logger.exception(f"Error sending to ntfy for '{topic_suffix}': {e}")
        else:
            logger.warning(f"Ignore unknown subtopic: '{topic_suffix}'")

    def listen_to_ntfy(subtopic, ntfy_user, ntfy_pass):
        while True:
            try:
                url = f"{NTFY_URL.rstrip('/')}/{subtopic}/json"
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

        for subtopic, (ntfy_user, ntfy_pass) in ALLOWED_SUBTOPICS.items():
            threading.Thread(target=listen_to_ntfy, args=(subtopic, ntfy_user, ntfy_pass), daemon=True).start()

        mqtt_client.loop_forever()
    except Exception as e:
        logger.exception(f"Failed to connect to MQTT broker: {e}")
