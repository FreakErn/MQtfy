# MQtfy - Ntfy Mqtt Gateway
Send MQTT Messages to send ntfy Notifications and subscribe to ntfy to send them to mqtt

## Installation

### Local
```bash
$ pip install mqtfy 
$ mqtfy # first run will end up in a error message, that you do not have a config. The script tries to download one for your version
# Update your config file (config.yaml)
$ mqtfy
```

### Docker
Todo

## Configuration

See example file (config.yaml.example).
Just do a:
```bash
cp config.yaml.example config.yaml
```
and edit the file to your needs.
```yaml
mqtt_host: "mqtt.local"             # MQTT Host
mqtt_port: 1883                     # MQTT Port
mqtt_user: "mqttuser"               # MQTT User (remove if not needed)
mqtt_pass: "mqttpass"               # MQTT Password (remove if not needed)
mqtt_topic: "mqtfy/"                # MQTT Topic
mqtt_client_id: "mqtfy"             # MQTT client id
ntfy_url: "https://ntfy.sh"         # ntfy url
log_level: "INFO"                   # Log lebvel
receive_only_message: True          # do you want the ntfy message (true) or the entire body (false)
ignore_events: keepalive, open      # some events are not really helpful

# subtopics to subscribe to (mqtt and ntfy)
subtopics:
  - topic: "foo"                    # ntfy topic
    ntfy_user: "user1"              # ntfy user for that topic
    ntfy_pass: "pass1"              # ntfy password for that user
  - topic: "bar"
    ntfy_url: "https://ntfy.example.com"  # optional - if not pressent, it uses the global configured ntfy_url
    ntfy_user: "user2"
    ntfy_pass: "pass2"
```
It might be a good idea to set `log_level` while you are configuring to `DEBUG`

## Usage

Create your configuration File and just run `mqtfy`

### MQTT -> ntfy
By default, MQtfy will listen to `mqtfy/`. MQtfy will send messages to the ntfy server by sending the message to `mqtfy/send/myTopic`. The Message content is a Json with all the attributes you want, just follow the [documentation](https://docs.ntfy.sh/publish/#publish-as-json).

The only exception is that the `topic` of the Message will be set/replaced by the part after `/mqtfy/send/`. In our example here the ntfy topic in the json will be set to `myTopic`.

To stay close to the documentation, here is an example:

```bash
mosquitto_pub -h mqtt.local -t "mqtfy/send/myTest" -m '{
    "topic": "WILL_BE_OVERWRITTEN_BY -> myTest    ⬆️",
    "message": "Disk space is low at 5.1 GB",
    "title": "Low disk space alert",
    "tags": ["warning","cd"],
    "priority": 4,
    "attach": "https://filesrv.lan/space.jpg",
    "filename": "diskspace.jpg",
    "click": "https://homecamera.lan/xasds1h2xsSsa/",
    "actions": [{ "action": "view", "label": "Admin panel", "url": "https://filesrv.lan/admin" }]
  }'
```
Or a simple version:
```bash
mosquitto_pub -h mqtt.local -t "mqtfy/send/myTest" -m '{
    "message": "Disk space is low at 5.1 GB"
  }'
```

Or even a more simplified version:
```bash
mosquitto_pub -h mqtt.local -t "mqtfy/send/myTest" -m 'Disk space is low at 5.1 GB'
```

### ntfy -> MQTT
All messages will be published into the topic `mqtfy/receive/ntfy-TOPIC`

## Todo
- [x] Allow Strings as ntfy messages (Simple version)
- [ ] Implement a switch to not publish mqtt messages which are sent by mqtfy (mqtt -> ntfy -> mqtt)
- [ ] Add default values which can be added for a topic into the configuration file (Eg. the topic doorbell could always get a tag 'bell' for a 🔔)