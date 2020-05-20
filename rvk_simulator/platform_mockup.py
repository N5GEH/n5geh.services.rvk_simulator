import paho.mqtt.client as mqtt
import utils
from datetime import datetime, timedelta, timezone
import predict_thermal
import platformcontroller
import math
import os


class DummyPlatform():
    """ simulator of the platform functionality """
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
        self.mqtt_client_name = 0
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
        self.mode = 0
        self.start_datetime = 0
        self.start_sim_inh = 0
        self.end_sim_inh = 0
        self.time_step_in_s = 0
        self.ini_time_in_h = 0
        # multiple gateways
        self.gw_list = []                       # list of dicts

        
        # debug flag
        self.dbg = 2
        self.fnr = 0
        # end __init__

    # ==================================================================

    def main(self):
        # initialize: pred, mqtt 
        (record_step_in_s, mqtt_attributes, multiple_gateways, mg_path, mg_croot) = self.initialize_components(self.config_file)
        if(multiple_gateways):
            # initialize multi-gateway mode; gateways have to be in sensor mode to 
            (actual_time) = self.initialize_multiple_gws(self.config_file)
            self.ini_time_in_h = utils.convert_time_to_hours(actual_time)
            self.start_datetime = actual_time
            end_sim_inh = self.end_sim_inh
            start_sim_inh = self.start_sim_inh
            end_datetime = actual_time + timedelta(hours=(end_sim_inh - start_sim_inh))
            while self.loop_condition(self.simulation, actual_time, end_datetime):
                
                #
                try:
                    # get list of gateways - now from file system, later from Orion
                    gateways = os.listdir(mg_path)  # list of strings
                    
                    urn_base = self.mqtt_sensor_name[:-len(mg_croot)]
                    # for each gateway keep track of it
                    for gw in gateways:
                        # get its number
                        #gw_nr = mqtt_sensor_name[-3:]
                        gw_nr = int(gw[len(mg_croot):])
                        # get its urn = mqtt_sensor_name from config file
                        myurn = '{}{}'.format(urn_base, gw[len(mg_croot):])
                        config_file_path = print('{}\\{}{}'.format(mg_path, mg_croot, gw))
                        print('config_file_path  = {}'.format(config_file_path))
                        config_file = utils.check_and_open_json_file(config_file_path)
                        self.process_gw_on_platform(gw_nr, myurn, config_file, actual_time)
                        
                        
                except:
                    print('exception in platform')
            
            
        else:             # only one gateway
            # listen to rvk - initialize mqtt subscription - read times of every data set
            self.mqtt_client = self.create_mqtt_client(self.mqtt_broker, self.mqtt_port_nr, self.mqtt_client_name)
            self.subscribe_to_monitoring_data(self.mqtt_client, self.mqtt_api_key, self.mqtt_sensor_name, mqtt_attributes)
            self.mqtt_client.loop_forever()
            #self.mqtt_client.loop_start()
            #client.loop_start()
            # rest of the calculations takes place in self.receive_monitoring_data


        # end main

    # ==================================================================

    def initialize_components(self, config_file):
        conf_calc = config_file['calculation']
        self.time_step_in_s = conf_calc['time_step_in_s']     # in seconds
        record_step_in_s = conf_calc['record_step_in_s'] # in seconds
        self.start_sim_inh = conf_calc['simulation_mode']['start_sim_in_hours']  # starting time of the simulation in h
        self.end_sim_inh = conf_calc['simulation_mode']['end_sim_in_hours']      # end time of the simulation in h
        self.wetter_file = utils.check_and_open_file(conf_calc['simulation_mode']['weather_file_path'])        # list of strings
        # mqtt
        conf_plat = conf_calc['platform_mode']
        self.mqtt_broker = conf_plat['mqtt_broker']
        self.mqtt_port_nr = conf_plat['mqtt_port_nr']
        self.mqtt_api_key = conf_plat['mqtt_api_key']
        self.mqtt_sensor_name = conf_plat['mqtt_sensor_name']
        mqtt_attributes = conf_plat['mqtt_attributes']
        self.mqtt_commands = conf_plat['mqtt_commands']
        self.mqtt_client_name = conf_plat['mqtt_client_name_plat']
        
        # prediction - global and output
        self.prediction_time_step_in_s = config_file['prediction']['prediction_time_step_in_s']
        #self.next_prediction_timestamp = actual_time + timedelta(seconds=self.prediction_time_step_in_s)
        self.output_horizon_in_h =  config_file['prediction']['output_horizon_in_h']
        self.output_resolution_in_s =  config_file['prediction']['output_resolution_in_s']
        # Martin's code
        conf_pred = config_file['prediction']['heat']
        conf_powr = config_file['prediction']['power']
        self.pred = self.initialize_thermal_prediction(config_file)
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
        self.mode = conf_calc['mode']

        crdb_endpoint = config_file['calculation']['platform_mode']['crdb_endpoint']
        crdb_endpoint_add = config_file['calculation']['platform_mode']['crdb_endpoint_add']
        crdb_username = config_file['calculation']['platform_mode']['crdb_username']
        crdb_direct_com = config_file['calculation']['platform_mode']['crdb_direct_com']
        self.pred.initialize_crate_db_connection(crdb_endpoint, crdb_endpoint_add, crdb_username, crdb_direct_com)

        multiple_gateways = config_file['calculation']['platform_mode']['multiple_gateways']
        mg_path = config_file['calculation']['platform_mode']['multiple_gateways_directory']
        mg_croot = config_file['calculation']['platform_mode']['multiple_gateways_croot']

        return (record_step_in_s, mqtt_attributes, multiple_gateways, mg_path, mg_croot)
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
        effective_pipe_volume = config_file['components']['storage_tank']['effective_coil_volume_in_m3']   # in m3 - water volume of the pipes of inner heat exchanger
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
        return predict_thermal.predict_Q(n_day, n_values, precision_in_h, predef_loads_file_path, use_predef_loads, 
                   self.output_horizon_in_h, self.output_resolution_in_s, conf_powr, hk_tv, hk_tr, hk_ti, hk_ta, 
                   hk_qn, hk_n, hk_m, chp_tmax, gb_tmax, slice_volume, mstr_chp, mstr_gb, qmax_rod_el, eps_th_chp, 
                   eps_el_chp, open_weather_map_active)

    #end initialize_thermal_prediction
    # ==================================================================

    def initialize_multiple_gws(self, config_file):
        actual_time = self.initialize_actual_time(self.simulation, self.start_sim_inh, self.end_sim_inh)
        
        
        return (actual_time)
    # end initialize_multiple_gws

    # ==================================================================

    def loop_condition(self, simulation, actual_time, end_datetime):
        if simulation:
            if actual_time > end_datetime:
                return False
            else:
                return True
        else:
            return True

    #end loop_condition
    # ==================================================================

    def initialize_actual_time(self, simulation, start_sim_inh, end_sim_inh):
#    def initialize_actual_time(self, simulation, end_sim_inh):
        if simulation:
            return (datetime.now() - timedelta(hours=(end_sim_inh - start_sim_inh)))  # time in datetime format
            #return (datetime.now() - timedelta(hours=end_sim_inh))  # time in datetime format
        else:
            return datetime.now()  # time in datetime format

    #end initialize_actual_time
    # ==================================================================

    def process_gw_on_platform(self, gw_nr, urn, config_file, actual_time):
        # check whether the urn is already registered
        add_gw = True
        for gw in self.gw_list:
            if(urn == gw['urn']):
                add_gw = False
        # add gw to self.gw_list if it is not yet there
        if(add_gw):
            if(len(self.gw_list) == 0):
                # first gateway uses the predefined data, 
                # that meand that config file of first gateway has to contain the same system data as config file of the platform
                pred = self.pred
            else:
                pred = self.initialize_thermal_prediction(config_file)
                crdb_endpoint = config_file['calculation']['platform_mode']['crdb_endpoint']
                crdb_endpoint_add = config_file['calculation']['platform_mode']['crdb_endpoint_add']
                crdb_username = config_file['calculation']['platform_mode']['crdb_username']
                crdb_direct_com = config_file['calculation']['platform_mode']['crdb_direct_com']
                pred.initialize_crate_db_connection(crdb_endpoint, crdb_endpoint_add, crdb_username, crdb_direct_com)
            next_prediction_timestamp = self.get_next_prediction_timestamp(actual_time, config_file, pred)  # ~
            new_gw = {'nr': gw_nr, 'urn': urn, 'config': config_file, 'next_prediction_timestamp': next_prediction_timestamp, 'pred': pred}
            gw_list.append(new_gw)

        # find gw in self.gw_list
        for gw in self.gw_list:
            if(urn == gw['urn']):
                act_gw = gw
        # trigger energy vector and schedule generation if time elapses for the gateway
        if(actual_time >= act_gw['next_prediction_timestamp']):  # 
            config_file = act_gw['config']
            self.fnr = self.fnr + 1
            prediction_time_step_in_s = config_file['prediction']['prediction_time_step_in_s']
            next_prediction_timestamp = actual_time + timedelta(seconds=prediction_time_step_in_s)
            act_gw['next_prediction_timestamp'] = next_prediction_timestamp
            
            #start_datetime = 
            # !!! still TODO 
            weather_pred = self.pred.get_weather_prediction(actual_time, self.simulation, self.wetter_file, self.start_datetime, self.start_sim_inh, self.end_sim_inh, self.fnr)
            ini_time_in_h = 1
            
            arch_option_1 = False
            act_time_in_h = utils.convert_time_to_hours(actual_time)-self.ini_time_in_h
            self.pred.update_heat_consumption_from_crate(actual_time, self.time_step_in_s, arch_option_1, self.fnr)
            last_t_profile = [float(wyn1[3]),float(wyn1[5]),float(wyn1[7]),float(wyn1[9]),float(wyn1[11]),float(wyn1[13]),float(wyn1[15]),float(wyn1[17]),float(wyn1[19]),float(wyn1[21]),float(wyn1[23]),float(wyn1[25]),float(wyn1[27]),float(wyn1[29]),float(wyn1[31]),float(wyn1[33]),float(wyn1[35]),float(wyn1[37]),float(wyn1[39]),float(wyn1[41])]
            energy_vector = self.pred.predict_energy_vector(weather_pred, act_time_in_h, actual_time, self.start_datetime, self.start_sim_inh, self.end_sim_inh, self.output_horizon_in_h, self.output_resolution_in_s, last_t_profile, self.fnr)
            current_sched = platformcontroller.cloud_schedule_gen(actual_time, energy_vector, self.start_datetime, config_file)
            print('\n\ngot schedule {}\n\n\n\n'.format(current_sched))
            platformcontroller.send_schedule_to_rvk(current_sched, self.mqtt_client, self.mqtt_api_key, self.mqtt_sensor_name, self.mqtt_commands, self.fnr)
            
        # end process_gw_on_platform

    # ==================================================================

    def get_next_prediction_timestamp(self, actual_time, config_file, pred):
        # gateway is introduced to the platform and it is not yet clear when its schedule has to be updated
        prediction_time_step_in_s = config_file['prediction']['prediction_time_step_in_s']   # intervall at which the schedule should be updated
        delta_in_seconds = config_file['calculation']['time_step_in_s']   # time step of simulation
        nr_of_rec_in_db = pred.number_crate_records_in_time_span(prediction_time_step_in_s, 2 * delta_in_seconds)
        if(nr_of_rec_in_db > 0):
            actual_time
        else:
            return (actual_time + prediction_time_step_in_s)
        

    # ==================================================================

    def subscribe_to_monitoring_data(self, client, apiKey, sensor_name, attributes):
        #apiKey = 'QKAAbMxLbv5TfhFxjTv4lhw92m'
        #sensor_name = 'urn:ngsi-ld:rvk:001'
        #attributes = 'attrs'
        #topic = "#"
        topic = "/{}/{}/{}".format(apiKey, sensor_name, attributes)
        client.subscribe(topic)  # subscribe
        #client.loop_start()
        print('subscribed to topic = {}'.format(topic))
        # end subscribe_to_monitoring_data

    # ==================================================================

    def create_mqtt_client(self, broker, port_nr, client_name):
        print('create client {}'.format(client_name))
        client = mqtt.Client(client_name)
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        #client.on_publish = self.on_publish
        client.on_disconnect = self.on_disconnect
        print('connect client {} to broker'.format(client_name))
        client.connect(broker, port=port_nr, keepalive=60, bind_address="")  # connect
        return client
        # end create_mqtt_client

    # ==================================================================

    def on_message(self, client, userdata, message):
        #print('\n\nON MESSAGE\n\n')
        self.current_schedule = self.receive_monitoring_data(message)
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
        print("received message =", str(message.payload.decode("utf-8")))
        # end on_publish

    # ==================================================================

    def time_condition_for_prediction(self, actual_time, pred):
        #print('\n\n\ntime condition \n')
        print(actual_time , self.next_prediction_timestamp, pred.get_q_write())
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
        wyn1 = str(message.payload.decode("utf-8")).split("|")
        #print("received message =", str(message.payload.decode("utf-8")))
        print(wyn1[94], wyn1[95])
        #actual_time = utils.extract_time_stamp_from_string(wyn1[1])
        actual_time = datetime.fromtimestamp(float(wyn1[95]))
        # define start_datetime as soon as possible
        if(self.first):
            self.first = False
            self.start_datetime = actual_time
            self.ini_time_in_h = utils.convert_time_to_hours(actual_time)
            self.next_prediction_timestamp = actual_time
            
        #print(actual_time, self.next_prediction_timestamp)
            
        # check whether time elapsed for prediction
        if(self.time_condition_for_prediction(actual_time, self.pred)):
            self.fnr = self.fnr + 1
            self.next_prediction_timestamp = actual_time + timedelta(seconds=self.prediction_time_step_in_s)
            weather_pred = self.pred.get_weather_prediction(actual_time, self.simulation, self.wetter_file, self.start_datetime, self.start_sim_inh, self.end_sim_inh, self.fnr)
            arch_option_1 = False
            act_time_in_h = utils.convert_time_to_hours(actual_time)-self.ini_time_in_h
            self.pred.update_heat_consumption_from_crate(actual_time, self.time_step_in_s, arch_option_1, self.fnr)
            last_t_profile = [float(wyn1[3]),float(wyn1[5]),float(wyn1[7]),float(wyn1[9]),float(wyn1[11]),float(wyn1[13]),float(wyn1[15]),float(wyn1[17]),float(wyn1[19]),float(wyn1[21]),float(wyn1[23]),float(wyn1[25]),float(wyn1[27]),float(wyn1[29]),float(wyn1[31]),float(wyn1[33]),float(wyn1[35]),float(wyn1[37]),float(wyn1[39]),float(wyn1[41])]
            energy_vector = self.pred.predict_energy_vector(weather_pred, act_time_in_h, actual_time, self.start_datetime, self.start_sim_inh, self.end_sim_inh, self.output_horizon_in_h, self.output_resolution_in_s, last_t_profile, self.fnr)
            config_file = './config.json'
            current_sched = platformcontroller.cloud_schedule_gen(actual_time, energy_vector, self.start_datetime, config_file)
            print('\n\ngot schedule {}\n\n\n\n'.format(current_sched))
            platformcontroller.send_schedule_to_rvk(current_sched, self.mqtt_client, self.mqtt_api_key, self.mqtt_sensor_name, self.mqtt_commands, self.fnr)
        # end receive_monitoring_data

    # ==================================================================



    # ==================================================================



    # ==================================================================
