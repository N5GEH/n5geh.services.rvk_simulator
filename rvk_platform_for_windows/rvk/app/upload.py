from time import sleep
import paho.mqtt.client as mqtt
import sys

apiKey = 'QKAAbMxLbv5TfhFxjTv4lhw92m'
sensor_name = 'urn:ngsi-ld:rvk:001'
attributes = 'attrs'

file = ''
if len(sys.argv) == 1:
    file = '/profiles/default.csv'
else:
    file = sys.argv[1]

def get_columns():
    f = open(file,'rt')
    line = f.readline()
    line = line.strip()
    f.close()
    return line.split(';')


topic = "/{}/{}/{}".format(apiKey, sensor_name, attributes)
columns = get_columns()

client = mqtt.Client('rvk')
client.connect('mqtt-broker', port=1883, keepalive=60, bind_address="")

H = open("./log_upload.dat","w")

while True:
    with open(file,'rt') as f:
        firstLine = True
        for l in f.readlines():
            if firstLine:
                firstLine = False
                continue
            data_row = list(map(float, l.strip().split(';')))
            payloads = ['{}|{}'.format(c,d) for c, d in zip(columns, data_row)]
            client.publish(topic,'|'.join(payloads))
            print(data_row[0])
            H.write("{}\n".format(data_row))
            sleep(1)

load_data()