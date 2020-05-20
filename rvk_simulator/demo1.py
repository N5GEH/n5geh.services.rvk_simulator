import sys
import pandas as pd
import csv
import time
import numpy as np
import ssl

# import demonstrator
import json

import paho.mqtt.client as mqttClient

################## Defines ###################

mqtt_username = "rvksim"
mqtt_password = "7TvpyxEQBsMHSHaF7E8m6Hd7Sux2mpQx"
mqtt_endpoint = "fiware.n5geh.de"
mqtt_port = 1026
TLS_CONNECTION = True

sub_topic = "/rvksim/lastgang/cmd"
pub_topic = "/rvksim/lastgang/attrs"

filepath = "./static_lastgang.dat"

# persistent data object
data = {}

DEBUGMODE = False
##############################################


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[INFO] Connected to broker")
    else:
        print("[INFO] Error, connection failed")


def subscribe(mqtt_client, topic):

    try:
        mqtt_client.subscribe(topic, 0)
        time.sleep(1)
        print("Subscribed to topic " + topic)
    except Exception as e:
        print("[Error] Could not subscribe to topic, error: {}".format(e))


def on_publish(client, userdata, result):
    print("data published")


def on_message(client, userdata, msg):
    print("Got message")

    modify_csv(msg, client)


def modify_csv(msg, client):
    # Convert Payload-JSON to Dict-JSON
    payload = json.loads(msg.payload)
    # Offset for max values between 5 and 15 kW
    offset = 1.5 - (float(payload["offset"]) / 255)
    print("Offset: ")
    print(offset)
    csv_data = data["csv_data"].copy()

    # Apply Offset to Dataframe
    for ind in csv_data.index:
        value = csv_data.loc[ind, 2] * offset
        csv_data.loc[ind, 2] = value
    # csv_data.to_csv(r"./csv_lastgang.dat", sep="    ", index=False, header=False)

    # Have to use numpy because of uncommon delimiter
    np.savetxt("./lastgang.dat", csv_data, delimiter="    ", fmt="%s")
    print("lastgang.dat written")
    json_buf = csv_data.to_json(path_or_buf=None)
    payload = json.loads(json_buf)
    client.publish(data["pub_topic"], str(payload["2"]))


def mock_csv():
    # Only for testing and debugging without mqtt

    offset = 1.0361
    csv_data = data["csv_data"].copy()
    print(csv_data)
    value = 0
    # Apply Offset to Dataframe
    for ind in csv_data.index:
        print(ind)
        print(csv_data[2][ind])
        value = csv_data.loc[ind, 2] * offset
        print(value)
        csv_data.loc[ind, 2] = value
        print(csv_data[2][ind])
    # csv_data.to_csv(r"./csv_lastgang.dat", sep="    ", index=False, header=False)
    np.savetxt("./debug_lastgang.dat", csv_data, delimiter="    ", fmt="%s")
    json_buf = csv_data.to_json(path_or_buf=None)
    type(json_buf)
    print(json_buf)


def main():
    if not DEBUGMODE:
        # DM = demonstrator.DummyDemonstrator("./config.json")
        # DM.main()
        client = mqttClient.Client()
        client.on_connect = on_connect
        client.on_message = on_message
        client.on_publish = on_publish
        client.username_pw_set(mqtt_username, password=mqtt_password)

        ####### TLS ########
        if TLS_CONNECTION:
            client.tls_set(tls_version=ssl.PROTOCOL_TLSv1_2)
            client.tls_insecure_set(False)
        #####################

        client.connect(mqtt_endpoint, port=mqtt_port)
        client.loop_start()
        subscribe(client, sub_topic)

    # Lastgang.dat to JSON style dataframe
    data["csv_data"] = pd.read_csv(filepath, engine="python", sep="    ", header=None)
    data["pub_topic"] = pub_topic

    if DEBUGMODE:
        mock_csv()

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()

