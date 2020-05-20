import paho.mqtt.client as mqtt
import ssl
import json
import utils
#=======================================================================
# program that replaces te physical potentiometer
# it sends a value between 0 and 255 that emulates the signal from potentiometer
# to the topic sub_topic defined in the general section of this file
# demo1.py listens on this topic and uses the sent value to control the rest of simulation
#=======================================================================


# ----------------------------------------------------------------------

def initialize_components(config_file):
    mqtt_broker = config_file['calculation']['platform_mode']['mqtt_broker']
    mqtt_port_nr = config_file['calculation']['platform_mode']['mqtt_port_nr']
    # authentication
    authentication = config_file['calculation']['demonstrator_mode']['authentication']['activate']
    mqtt_username = config_file['calculation']['demonstrator_mode']['authentication']['mqtt_username']
    mqtt_password = config_file['calculation']['demonstrator_mode']['authentication']['mqtt_password']
    tls_connection = config_file['calculation']['demonstrator_mode']['authentication']['tls_connection']
    sub_topic = config_file['calculation']['demonstrator_mode']['mqtt_topic_pott_sub']

    return (authentication, mqtt_username, mqtt_password, tls_connection, mqtt_broker, mqtt_port_nr, sub_topic)

# ----------------------------------------------------------------------

def create_mqtt_client(broker, port_nr, client_name, authentication, mqtt_username, mqtt_password, tls_connection, mytag):
    print('{} create client {}'.format(mytag, client_name))
    client = mqtt.Client(client_name)
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_publish = on_publish
    client.on_disconnect = on_disconnect
    print('{} connect client {} to broker'.format(mytag, client_name))
    if(authentication):
        client.username_pw_set(mqtt_username, password=mqtt_password)
        if tls_connection:
            client.tls_set(tls_version=ssl.PROTOCOL_TLSv1_2)
            client.tls_insecure_set(False)
    client.connect(broker, port=port_nr, keepalive=60, bind_address="")  # connect
    return client
    # end create_mqtt_client
# ----------------------------------------------------------------------
# ==================================================================

def on_message(client, userdata, message):
    print('\nDEMO ON MESSAGE')
    # end on_message

# ==================================================================

def on_connect(client, userdata, flags, rc):
    print('ON CONNECT')
    if rc == 0:
        client.connected_flag = True
    else:
        print('Bad connection returned code {}'.format(rc))
        client.loop_stop()
    # end on_connect

# ==================================================================

def on_disconnect(client, userdata, rc):
    print('client has disconnected')
    # end on_disconnect

# ==================================================================

def on_publish(client, userdata, message):
    print("ON PUBLISH")
    #print("received message =", str(message.payload.decode("utf-8")))
    # end on_publish

# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------

#####mqtt_username = "rvksim"
#####mqtt_password = "7TvpyxEQBsMHSHaF7E8m6Hd7Sux2mpQx"
#####mqtt_endpoint = "fiware.n5geh.de"
#####mqtt_endpoint = "127.0.0.1"
#####mqtt_port = 1026
#####TLS_CONNECTION = True
#####TLS_CONNECTION = False
#####ACT_AUTH = False
#####
#####sub_topic = "/rvksim/lastgang/cmd"
#####pub_topic = "/rvksim/lastgang/attrs"
#####
#####filepath = "./static_lastgang.dat"
#####
###### persistent data object
#####data = {}


def main():
    mytag = "potenTIOmeter"
    config_file_path = "./config.json"
    config_file = utils.check_and_open_json_file(config_file_path)
    (authentication, mqtt_username, mqtt_password, tls_connection, mqtt_broker, mqtt_port_nr, sub_topic) = initialize_components(config_file)
    # listen to rvk - initialize mqtt subscription - read times of every data set
    mqtt_client_name = 'Potentiometer_1'
    mqtt_client = create_mqtt_client(mqtt_broker, mqtt_port_nr, mqtt_client_name, authentication, 
                                          mqtt_username, mqtt_password, tls_connection, mytag)


    myvalue = 127.5
    myvalue = 0.0
    myvalue = 255

    print('myvalue = {}'.format(myvalue))
    payload = json.dumps({"offset": myvalue})
    mqtt_client.publish(sub_topic, payload)
    print('{} published {} at topic {}'.format(mqtt_client_name, payload, sub_topic))

if __name__ == "__main__":
    main()
