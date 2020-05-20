import paho.mqtt.client as mqtt
import utils
from datetime import datetime, timedelta, timezone
import predict_thermal
import platformcontroller
import math
import ssl
import threading
# extras for Stephan Wiemann - begin
import pandas as pd
import numpy as np
import csv
# extras for Stephan Wiemann - end 
import json


class DummyDemonstrator():
    """ simulator of the demonstrator that sends the heat consumption to the chosen rvk """
    def __init__(self, config_file_path):
        # general configuration
        self.config_file = utils.check_and_open_json_file(config_file_path)
        # mqtt configuration
        self.mqtt_client = 0
        self.mqtt_broker = 0
        self.mqtt_port_nr = 0
        self.mqtt_api_key = 0
        self.mqtt_sensor_name = 0
        self.mqtt_commands = 0
        self.authentication = False
        self.mqtt_username = 0
        self.mqtt_password = 0
        self.tls_connection = 0
        self.mqtt_client_name2 = 0
        self.mqtt_client_name = 0
        #self.sub_topic = 0
        self.wetter_file = 0
        # actual time
        self.first = True
        # prediction
        self.pred  = 0                                   # object - prediction
        self.next_prediction_timestamp = 0               # time at which the prediction of the energy vector is to be made
        self.prediction_time_step_in_s = 0               # time intervall at which the energy vector is to be produced
        self.output_horizon_in_h = 0                     # time horizont for which the forecast is to be made
        self.output_resolution_in_s = 0                  # resolution of the forecast in s
        # simulation variables
        self.simulation = False
        self.platform = False
        self.start_datetime = 0
        self.start_sim_inh = 0
        self.end_sim_inh = 0
        self.time_step_in_s = 0
        self.ini_time_in_h = 0
        # scaling of output from measured value to kW
        self.scaling_factor = 1.0
        self.scaling_offset = 0.0
        # data struct for managing load profiles - by Stephan Wiemann
        self.sub_topic = "" # mqtt topic for subscription to the potentiometer
        self.pub_topic = "" # mqtt topic for ?
        self.filepath = 0
        self.data = {} # "persistent data object"
        # debug flag
        self.dbg = 2
        # end __init__

    # ==================================================================

    def initialize_potent(self):
        self.mqtt_broker = self.config_file['calculation']['platform_mode']['mqtt_broker']
        self.mqtt_port_nr = self.config_file['calculation']['platform_mode']['mqtt_port_nr']
        #self.mqtt_client_name2 = self.config_file['calculation']['platform_mode']['client2_name']
        self.authentication = self.config_file['calculation']['platform_mode']['authentication']['activate']
        self.mqtt_username = self.config_file['calculation']['platform_mode']['authentication']['mqtt_username']
        self.mqtt_password = self.config_file['calculation']['platform_mode']['authentication']['mqtt_password']
        self.tls_connection = self.config_file['calculation']['platform_mode']['authentication']['tls_connection']
        #self.sub_topic = self.config_file['calculation']['platform_mode']['mqtt_topic_pott_sub']
        # programm of Stephan Wiemann
        self.sub_topic = self.config_file['calculation']['demonstrator_mode']['mqtt_topic_pott_sub']
        self.pub_topic = self.config_file['calculation']['demonstrator_mode']['mqtt_topic_pott_pub']
        self.filepath = self.config_file['calculation']['demonstrator_mode']['stat_load_profile_file']
        self.mqtt_client_name2 = self.config_file['calculation']['demonstrator_mode']['client2_name']
        self.data["csv_data"] = pd.read_csv(self.filepath, engine="python", sep="    ", header=None)
        self.data["pub_topic"] = self.pub_topic
    # end initialize_potent

    # ==================================================================

    def potentiometer_receiver(self, tag):
        print('entered {}'.format(tag))
        self.initialize_potent()
        print('{}: initialized'.format(tag))
        self.mqtt_client2 = self.create_mqtt_client2(self.mqtt_broker, self.mqtt_port_nr, self.mqtt_client_name2, self.authentication,
                                                     self.mqtt_username, self.mqtt_password, self.tls_connection)
        print('{}: created mqtt client {} with name {}'.format(tag, self.mqtt_client2, self.mqtt_client_name2))
        self.mqtt_client2.subscribe(self.sub_topic)
        print('{}: client {} subscribed to topic {}'.format(tag, self.mqtt_client_name2, self.sub_topic))
        self.mqtt_client2.loop_forever()
        # rest of the calculations takes place in self.
    # end potentiometer_receiver

    # ==================================================================

    def main(self):
        #config_file_path = './config.json'

        thread1 = threading.Thread(target=self.rvk_data_receiver, args=("rvk_data_receiver",))
        thread2 = threading.Thread(target=self.potentiometer_receiver, args=("potentiometer_receiver",))

        # Will execute both in parallel
        thread1.start()
        thread2.start()

        # Joins threads back to the parent process, which is this program
        thread1.join()
        thread2.join()
    # end main

    # ==================================================================

    def rvk_data_receiver(self, tag):
        print('entered {}'.format(tag))
        # initialize: pred, mqtt 
        (record_step_in_s, mqtt_attributes, authentication, mqtt_username, mqtt_password, tls_connection) = self.initialize_components(self.config_file)
        # listen to rvk - initialize mqtt subscription - read times of every data set
        self.mqtt_client = self.create_mqtt_client(self.mqtt_broker, self.mqtt_port_nr, self.mqtt_client_name, authentication, mqtt_username, mqtt_password, tls_connection, tag)
        self.subscribe_to_monitoring_data(self.mqtt_client, self.mqtt_api_key, self.mqtt_sensor_name, mqtt_attributes, tag)
        self.mqtt_client.loop_forever()
        #self.mqtt_client.loop_start()

        # rest of the calculations takes place in self.receive_monitoring_data
        # end rvk_data_receiver

    # ==================================================================

    def initialize_components(self, config_file):
        conf_calc = config_file['calculation']
        self.time_step_in_s = conf_calc['time_step_in_s']     # in seconds
        record_step_in_s = conf_calc['record_step_in_s'] # in seconds
        self.start_sim_inh = conf_calc['simulation_mode']['start_sim_in_hours']  # starting time of the simulation in h
        self.end_sim_inh = conf_calc['simulation_mode']['end_sim_in_hours']      # end time of the simulation in h
        # mqtt - subscriber that listens to actual date from rvk
        conf_plat = conf_calc['platform_mode']
        self.mqtt_broker = conf_plat['mqtt_broker']
        self.mqtt_port_nr = conf_plat['mqtt_port_nr']
        self.mqtt_api_key = conf_plat['mqtt_api_key']
        self.mqtt_sensor_name = conf_plat['mqtt_sensor_name']
        mqtt_attributes = conf_plat['mqtt_attributes']
        # mqtt - publisher that sends the measured heat consumption data to the rvk
        #self.mqtt_commands = conf_plat['mqtt_commands']
        self.mqtt_topic = conf_calc['demonstrator_mode']['mqtt_topic']
        self.mqtt_client_name = conf_calc['demonstrator_mode']['mqtt_client_name_sender']  # = 'demo1'
        self.wetter_file = utils.check_and_open_file(conf_calc['demonstrator_mode']['load_profile_file'])        # list of strings
        self.conf_file = config_file
        self.scaling_factor = conf_calc['demonstrator_mode']['scaling_factor']
        self.scaling_offset = conf_calc['demonstrator_mode']['scaling_offset']
        
        # prediction - global and output
        self.prediction_time_step_in_s = config_file['prediction']['prediction_time_step_in_s']
        #self.next_prediction_timestamp = actual_time + timedelta(seconds=self.prediction_time_step_in_s)
        self.output_horizon_in_h =  config_file['prediction']['output_horizon_in_h']
        self.output_resolution_in_s =  config_file['prediction']['output_resolution_in_s']
        # Martin's code
        #conf_pred = config_file['prediction']['heat']
        #conf_powr = config_file['prediction']['power']
        #self.pred = self.initialize_thermal_prediction(config_file)
        #predict_thermal.write_init(conf_pred['path_result'])
        
        sim_flag = conf_calc['mode']
        if(sim_flag == 'simulation'):
            self.simulation = True
            self.platform = False
        elif(sim_flag == 'platform'):
            self.simulation = True
            self.platform = True
        elif(sim_flag == 'multigw'):
            self.simulation = False
            self.platform = True
        else:
            self.simulation = False
            self.platform = False

        #crdb_endpoint = config['calculation']['platform_mode']['crdb_endpoint']
        #crdb_endpoint_add = config['calculation']['platform_mode']['crdb_endpoint_add']
        #crdb_username = config['calculation']['platform_mode']['crdb_username']
        #crdb_direct_com = config['calculation']['platform_mode']['crdb_direct_com']
        #self.pred.initialize_crate_db_connection(crdb_endpoint, crdb_endpoint_add, crdb_username, crdb_direct_com)
        
        # authentication
        authentication = config_file['calculation']['platform_mode']['authentication']['activate']
        mqtt_username = config_file['calculation']['platform_mode']['authentication']['mqtt_username']
        mqtt_password = config_file['calculation']['platform_mode']['authentication']['mqtt_password']
        tls_connection = config_file['calculation']['platform_mode']['authentication']['tls_connection']

        return (record_step_in_s, mqtt_attributes, authentication, mqtt_username, mqtt_password, tls_connection)
        # end initialize_components

    # ==================================================================

    def initialize_thermal_prediction(self, config_file):
        """ copyright by Martin Knorr """
        conf_pred = config_file['prediction']['heat']
        conf_powr = config_file['prediction']['power']
        # conf_pred
        n_day = conf_pred['n_day']
        n_values = conf_pred['n_values_per_day']
        precision_in_h = conf_pred['precision_in_h']
        use_predef_loads = conf_pred['use_predef_loads']
        predef_loads_file_path = conf_pred['path_loads']
        # heating curve
        conf_hk = config_file['components']['heating_curve']
        hk_ta = conf_hk['design_ambient_temperature_oC']
        hk_ti = conf_hk['design_indoor_temperature_oC']
        hk_tv = conf_hk['design_supply_temperature_oC']
        hk_tr = conf_hk['design_return_temperature_oC']
        hk_n = conf_hk['radiator_coefficient_n']
        hk_m = conf_hk['radiator_coefficient_m']
        hk_qn = conf_hk['design_heat_load_in_kW']
        # chp unit
        patm = utils.get_pressure_in_MPa()
        calcopt = utils.get_calc_option()
        eps_el_chp = config_file['components']['chp_unit']['electrical_efficiency']
        eps_th_chp = config_file['components']['chp_unit']['thermal_efficiency']
        qel_n_chp = config_file['components']['chp_unit']['max_electric_power_in_kW']
        chp_tinp = config_file['components']['chp_unit']['design_input_temperature_oC']
        chp_tmax = config_file['components']['chp_unit']['design_output_temperature_oC']
        qth_n_chp = eps_th_chp * qel_n_chp / eps_el_chp  # in kW
        mstr_chp = qth_n_chp / (utils.cp_fluid_water(0.5 * (chp_tmax + chp_tinp), patm, calcopt) * (chp_tmax - chp_tinp))  # in kg/s = kW / (kJ/kg/K * K)
        # gas boiler
        qth_n_gb = config_file['components']['gas_boiler']['max_thermal_power_in_kW']
        gb_tinp = config_file['components']['gas_boiler']['design_input_temperature_oC']
        gb_tmax = config_file['components']['gas_boiler']['design_output_temperature_oC']
        mstr_gb = qth_n_gb / (utils.cp_fluid_water(0.5 * (gb_tinp + gb_tmax), patm, calcopt) * (gb_tmax - gb_tinp))  # in kg/s = kW / (kJ/kg/K * K)  # in kg/s = kW / (kJ/kg/K * K)
        # storage tank
        effective_height = config_file['components']['storage_tank']['effective_heigth_in_m']
        inner_radius = config_file['components']['storage_tank']['inner_radius_tank_in_m']
        effective_pipe_volume = config_file['components']['storage_tank']['effective_coil_volume_in_m3']
        effective_volume = config_file['components']['storage_tank']['effective_volume_in_m3']
        if (effective_volume <= 0.0):
            effective_volume = math.pi * inner_radius * inner_radius * effective_height - effective_pipe_volume # in m3
        nr_calc = 20
        slice_volume = effective_volume / nr_calc  # in m3
        qmax_rod_el = config_file['components']['storage_tank']['power_heating_rod_in_kW']
        open_weather_map_active = config_file['calculation']['platform_mode']['open_weather_map_active']
        # conf_powr
        #print('\n initialize_thermal_prediction')
        #print('use_predef_loads = {}; {}'.format(use_predef_loads,type(use_predef_loads)))
        #print('predef_loads_file_path = {}; {}'.format(predef_loads_file_path,type(predef_loads_file_path)))
        return predict_thermal.predict_Q(n_day, n_values, precision_in_h, predef_loads_file_path, use_predef_loads, self.output_horizon_in_h, 
                   self.output_resolution_in_s, conf_powr, hk_tv, hk_tr, hk_ti, hk_ta, hk_qn, hk_n, hk_m, chp_tmax, gb_tmax, slice_volume, mstr_chp, 
                   mstr_gb, qmax_rod_el, eps_th_chp, eps_el_chp, open_weather_map_active)

    #end initialize_thermal_prediction
    # ==================================================================

    def subscribe_to_monitoring_data(self, client, apiKey, sensor_name, attributes, mytag):
        #apiKey = 'QKAAbMxLbv5TfhFxjTv4lhw92m'
        #sensor_name = 'urn:ngsi-ld:rvk:001'
        #attributes = 'attrs'
        #topic = "#"
        topic = "/{}/{}/{}".format(apiKey, sensor_name, attributes)
        client.subscribe(topic)  # subscribe
        #client.loop_start()
        print('{} subscribed to topic = {}'.format(mytag, topic))
        # end subscribe_to_monitoring_data

    # ==================================================================

    def create_mqtt_client(self, broker, port_nr, client_name, authentication, mqtt_username, mqtt_password, tls_connection, mytag):
        print('{} create client {}'.format(mytag, client_name))
        client = mqtt.Client(client_name)
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        client.on_publish = self.on_publish
        client.on_disconnect = self.on_disconnect
        print('{} connect client {} to broker'.format(mytag, client_name))
        if(authentication):
            client.username_pw_set(mqtt_username, password=mqtt_password)
            if tls_connection:
                client.tls_set(tls_version=ssl.PROTOCOL_TLSv1_2)
                client.tls_insecure_set(False)
        client.connect(broker, port=port_nr, keepalive=60, bind_address="")  # connect
        return client
        # end create_mqtt_client

    # ==================================================================

    def create_mqtt_client2(self, broker, port_nr, client_name, authentication, mqtt_username, mqtt_password, tls_connection):
        print('DEMO create client {}'.format(client_name))
        client = mqtt.Client(client_name)
        client.on_connect = self.on_connect
        client.on_message = self.on_message2
        client.on_publish = self.on_publish2
        client.on_disconnect = self.on_disconnect
        print('DEMO connect client {} to broker'.format(client_name))
        if(authentication):
            client.username_pw_set(mqtt_username, password=mqtt_password)
            if tls_connection:
                client.tls_set(tls_version=ssl.PROTOCOL_TLSv1_2)
                client.tls_insecure_set(False)
        client.connect(broker, port=port_nr, keepalive=60, bind_address="")  # connect
        return client
        # end create_mqtt_client2

    # ==================================================================

    def on_message(self, client, userdata, message):
        print('\nDEMO ON MESSAGE')
        self.receive_monitoring_data(message)
        # end on_message

    # ==================================================================

    def on_message2(self, client, userdata, message):
        print('\nDEMO ON MESSAGE 2')
        #wyn1 = str(message.payload.decode("utf-8")).split("|")
        #wyn1 = json.loads(message.payload.decode("utf-8"))
        #print(wyn1[0], wyn1[1])
        #print(wyn1, type(wyn1))
        self.modify_csv(message, self.mqtt_client2)
        # end on_message

    # ==================================================================

    def on_connect(self, client, userdata, flags, rc):
        print('ON CONNECT')
        if rc == 0:
            client.connected_flag = True
        else:
            print('Bad connection returned code {}'.format(rc))
            client.loop_stop()
        # end on_connect

    # ==================================================================

    def on_disconnect(self, client, userdata, rc):
        print('client has disconnected')
        # end on_disconnect

    # ==================================================================

    def on_publish(self, client, userdata, message):
        print("ON PUBLISH")
        #print("received message =", str(message.payload.decode("utf-8")))
        # end on_publish

    # ==================================================================

    def on_publish2(self, client, userdata, message):
        print("ON PUBLISH 2")
        #print("received message =", str(message.payload.decode("utf-8")))
        # end on_publish

    # ==================================================================

    def time_condition_for_prediction(self, actual_time, pred):
        #print('\n\n\ntime condition \n')
        #print(actual_time , self.next_prediction_timestamp, pred.get_q_write())
        if(actual_time >= self.next_prediction_timestamp):
            if(pred.get_q_write()):
                #print('now = {}; next time = {}'.format(actual_time, self.next_prediction_timestamp))
                return True
        return False
    # end time_condition_for_prediction

    # ==================================================================

    def receive_monitoring_data(self, message):
        # extract actual_time and trigger prediction_and_control once the thresold has been reached
        #print(message, type(message))
        # read the input file - here wetter_file - anew in every timestep, as it is changed externally by Stephan
        wet_file = utils.check_and_open_file(self.conf_file['calculation']['demonstrator_mode']['load_profile_file'])        # list of strings
        if (isinstance(wet_file,list)):        # use the wetter file only when reaing it was successfull
            self.wetter_file = wet_file        # list of strings
        
        wyn1 = str(message.payload.decode("utf-8")).split("|")
        #print('DEMO {} {}'.format(wyn1[94], wyn1[95]))
        #actual_time = utils.extract_time_stamp_from_string(wyn1[1])
        actual_time = datetime.fromtimestamp(float(wyn1[95]))
        #print('DEMO actual_time = {}'.format(actual_time))
        # define start_datetime as soon as possible
        if(self.first):
            self.first = False
            self.start_datetime = actual_time
            self.ini_time_in_h = utils.convert_time_to_hours(actual_time)
            self.next_prediction_timestamp = actual_time
            
        # whenever new time is received from rvk do the following
        act_time_in_h = utils.convert_time_to_hours(actual_time)-self.ini_time_in_h
        #print('act_time_in_h = {}'.format(act_time_in_h))
        # get heat load in kW from wetter_file
        q_in_kW = utils.get_jth_column_val(self.simulation, self.wetter_file, actual_time, self.start_datetime, self.start_sim_inh, self.end_sim_inh, 24, 1, 3)
        # send the heat load in kW to the rvk
        print('DEMO act_time = {}; q in kW from demo= {}, q in kW after scaling = {}'.format(actual_time, q_in_kW, q_in_kW * self.scaling_factor + self.scaling_offset))
        self.send_heat_load_to_rvk(actual_time, q_in_kW * self.scaling_factor + self.scaling_offset)
        # end receive_monitoring_data

    # ==================================================================

    def send_heat_load_to_rvk(self, time_stamp, heat_load_in_kW):
        topic = self.mqtt_topic
        #print('\nsend heat load to rvk\ndemo suscribed to topic {}'.format(topic))
        payloads = '{}|{}'.format(time_stamp.isoformat(),heat_load_in_kW)
        #print('demo created payload:{}'.format(payloads))
        #print('type(payloads) = {}; len(payloads) = {}'.format(type(payloads), len(payloads)))
        #platform_mqtt_client.publish(topic,'|'.join(payloads))
        set_qos = 0
        set_retain = False
        self.mqtt_client.publish(topic, payloads, set_qos, set_retain)
        print('demo published payloads {}'.format(payloads))
        # end send_heat_load_to_rvk

    # ==================================================================

    def modify_csv(self, msg, client):
        # Convert Payload-JSON to Dict-JSON
        payload = json.loads(msg.payload)
        # Offset for max values between 5 and 15 kW
        offset = 1.5 - (float(payload["offset"]) / 255)
        print("Offset: ")
        print(offset)
        csv_data = self.data["csv_data"].copy()
        
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
        client.publish(self.data["pub_topic"], str(payload["2"]))
        print('DEMO published {} at topic {}'.format(self.data["pub_topic"], str(payload["2"])))


    # ==================================================================



    # ==================================================================
