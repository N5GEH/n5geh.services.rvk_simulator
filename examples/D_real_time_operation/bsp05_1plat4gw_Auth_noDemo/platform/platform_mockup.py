import paho.mqtt.client as mqtt
import utils
from datetime import datetime, timedelta, timezone
import predict_thermal
import platformcontroller
import math
import os
from time import sleep
import ssl

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
        # main procedure
        # initialize: pred, mqtt 
        (record_step_in_s, mqtt_attributes, multiple_gateways, mg_path, mg_croot) = self.initialize_components(self.config_file)

        if(multiple_gateways):
            # create one mqtt broker for all communications coming into and out of the platform
            self.mqtt_client = self.create_mqtt_client(self.mqtt_broker, self.mqtt_port_nr, self.mqtt_client_name, self.authentication, self.mqtt_username, self.mqtt_password, self.tls_connection)
            self.mqtt_client.loop_start()
            # initialize multi-gateway mode; gateways have to be in sensor mode to do so
            # platform will enforce its time on the gateways as long as 'calculation' -> 'platform_mode' -> 'real_time_send' is false
            (actual_time, real_time_send, provisioning_endpoint, sleep_time_in_s, time_step_in_s) = self.initialize_multiple_gws(self.config_file) 
            if(self.dbg == 1):
                print('real_time_send = {}'.format(real_time_send))
            self.ini_time_in_h = utils.convert_time_to_hours(actual_time)
            self.start_datetime = actual_time
            end_sim_inh = self.end_sim_inh
            start_sim_inh = self.start_sim_inh
            end_datetime = actual_time + timedelta(hours=(end_sim_inh - start_sim_inh))
            while self.loop_condition(self.simulation, actual_time, end_datetime):
                
                
                # 
                try:
                    # get list of gateways from Orion
                    prov_iot_devs = utils.list_registered_iot_devices_in_platform(provisioning_endpoint)  # dictionary
                    gateways = prov_iot_devs['devices']  # list of dicts
                    if(self.dbg == 1):
                        print('# of devices  = {}; '.format(prov_iot_devs['count']))
                    
                    # for each gateway that is provisioned with the platform - process it
                    for gw in gateways:
                        # data from Orion
                        gw_urn = gw['entity_name']                              # urn registered with platform by provisioning
                        gw_id = gw['device_id']                                 # id registered with platform by provisioning
                        gw_tag = utils.get_last_substring_of_urn(gw_urn, ':')   # string with the number at the end of urn 001 or 0001 or 00001 etc.
                        urn_base = self.mqtt_sensor_name[:-len(gw_tag)]         # string without end number = urn - gw_tag 

                        # match data from Orion to the data in file structure
                        # list of directories in directory defined by 'calculation' -> 'platform_mode' -> 'multiple_gateways_directory'
                        rvpps = os.listdir(mg_path)         # list of strings: 
                        match = False
                        for rvk in rvpps:                   # test all directories in the data structure
                            rvk_urn = '{}{}'.format(urn_base, rvk[len(mg_croot):])
                            rvk_id = rvk_urn
                            rvk_tag = rvk[len(mg_croot):]
                            if((gw_urn == rvk_urn) and (gw_id == rvk_id)):
                                match = True       # when number at the end of urn is equal to the number at the end of directory name
                                wyn_urn = rvk_urn
                                wyn_id = rvk_id
                                wyn_tag = rvk_tag
                                #if((gw_tag == rvk_tag) or (int(gw_tag) == int(rvk_tag))):
                                #    nickel = True
                                #else:
                                #    nickel = False
                        # end for rvk in rvpps:

                        if(match):
                            # the urn provisioned with platform has been found in the file structure
                            if(self.dbg == 1):
                                print('urn = {} '.format(gw_urn))
                            #print('the urn {} provisioned with platform has been found in the directory {}/{}{} of the file structure'.format(gw_urn, 
                            #      mg_path, mg_croot, wyn_tag))
                            # get config file of the registered gateway from the matching directory
                            config_file_path = '{}/{}{}/config.json'.format(mg_path, mg_croot, wyn_tag)
                            config_file = utils.check_and_open_json_file(config_file_path)
                            # check whether gateway has already been initialized in the platform
                            add_gw = True
                            for gwi in self.gw_list:     # look for the urn in the internal data structure of the platform
                                if(gw_urn == gwi['urn']):
                                    add_gw = False   # gateway with such urn is already in the self.gw_list
                                    act_gw = gwi
                            # add gw to self.gw_list if it is not yet there == initialize data structure in the platform that works with 
                            if(add_gw):
                                # create topics for mqtt communication with this gateway only
                                (mqtt_topic_cmd, mqtt_topic_attr) = self.configure_mqtt_client_from_config(config_file)
                                ## send initial data set consisting of actual_time and number 10.0 to the platform
                                ## only this makes the crate db create the needed tables - which in turn makes its query possible
                                ## db queries are needed for the rest of initialization 
                                ## (self.get_next_prediction_timestamp and self.pred.update_heat_consumption_from_crate in self.process_gw_on_platform)
                                #utils.send_ini_data_to_platform(mqtt_topic_attr, 10.0, actual_time, mqtt_client)
                                # create prediction object (predict_thermal.predict_Q) if it does not exist yet
                                if(len(self.gw_list) == 0):
                                    # first gateway uses the predefined data, 
                                    # that means that config file of first gateway has to contain the same system data as config file of the platform
                                    # thanks to this, the provisioning of the first gateway can be left in place, so that other modes of operation are still able to run 
                                    pred = self.pred
                                else:
                                    # it is not the very first gateway, so initialize its prediction module, and communication endpoint
                                    pred = self.initialize_thermal_prediction(config_file)
                                    crdb_endpoint = config_file['calculation']['platform_mode']['crdb_endpoint']
                                    crdb_endpoint_add = config_file['calculation']['platform_mode']['crdb_endpoint_add']
                                    crdb_username = config_file['calculation']['platform_mode']['crdb_username']
                                    crdb_direct_com = config_file['calculation']['platform_mode']['crdb_direct_com']
                                    pred.initialize_crate_db_connection(crdb_endpoint, crdb_endpoint_add, crdb_username, crdb_direct_com)
                                # determine the time stamp at which the update of the schedule in the new gateway has to take place
                                next_prediction_timestamp = self.get_next_prediction_timestamp(actual_time, config_file, pred, gw_urn)  # 
                                # create new gateway structure
                                new_gw = {'nr': gw_tag, 'urn': gw_urn, 'config': config_file, 'next_prediction_timestamp': next_prediction_timestamp, 
                                          'pred': pred, 'mqtt_client': self.mqtt_client, 'mqtt_topic_attr': mqtt_topic_attr, 'mqtt_topic_cmd': mqtt_topic_cmd}
                                # add the new gateway to the data structure
                                self.gw_list.append(new_gw)
                                # if the 'calculation' -> 'platform_mode' -> 'real_time_send' is false
                                # the time of gateway has to be synchronized with the time of the platform
                                # If it is true, every gateway can use its own clock as the differences 
                                # are expected to be neither significant nor crucial for the operation
                                if(not real_time_send):
                                    self.time_sync_gw_with_platform(new_gw, actual_time, start_sim_inh, end_sim_inh)
                                    # for the first gateway, that is already provisioned with the platform
                                    
                                act_gw = new_gw
                            # end if(add_gw)
                            
                            # if the gateway has match in files and in data structure - it has to be processed:
                            self.process_gw_on_platform(act_gw, actual_time)
                        
                        # end if(match):
                        
                        else:
                            # the urn provisioned with platform cannot be found in the file structure
                            print('the urn {} provisioned with platform cannot be found in the file structure'.format(gw_urn))
                        # end if(match): else:
                        
                    # end for gw in gateways:
                    
                    # keep internal list consistent with the list in the platform
                    for idx, my_gw in enumerate(self.gw_list):
                        my_urn = my_gw['urn']
                        # check whether urn is in the list
                        is_in = False
                        for gw in gateways:
                            gw_urn = gw['entity_name']
                            if(gw_urn == my_urn):
                                is_in = True
                        if(not is_in):
                            self.gw_list.pop(idx)
                    # end for idx, my_gw in enumerate(self.gw_list):
                    
                # end try
                
                except:
                    print('exception in platform')
                # end try: except:

                # determine the next timestep
                next_time_step = self.update_time(self.simulation, self.platform, actual_time, real_time_send, sleep_time_in_s, time_step_in_s)
                # proceed to the next timestep
                actual_time = next_time_step
                
            # end while self.loop_condition
            
        # end if(multiple_gateways):
            
        else:             # only one gateway
            # listen to rvk - initialize mqtt subscription - read times of every data set
            self.mqtt_client = self.create_mqtt_client(self.mqtt_broker, self.mqtt_port_nr, self.mqtt_client_name, self.authentication, self.mqtt_username, self.mqtt_password, self.tls_connection)
            self.subscribe_to_monitoring_data(self.mqtt_client, self.mqtt_api_key, self.mqtt_sensor_name, mqtt_attributes)
            self.mqtt_client.loop_forever()
            #self.mqtt_client.loop_start()
            # rest of the calculations takes place in self.receive_monitoring_data

        # end if(multiple_gateways): else:

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
        # authentication
        self.authentication = conf_plat['authentication']['activate']
        self.mqtt_username = conf_plat['authentication']['mqtt_username']
        self.mqtt_password = conf_plat['authentication']['mqtt_password']
        self.tls_connection = conf_plat['authentication']['tls_connection']
        
        
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

        # 0 - no info; 1 - init & communication; 2 - energy vector & schedule into files
        self.dbg = config_file['calculation']['platform_mode']['dbg_level']

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
        mypred = predict_thermal.predict_Q(n_day, n_values, precision_in_h, predef_loads_file_path, use_predef_loads, 
                   self.output_horizon_in_h, self.output_resolution_in_s, conf_powr, hk_tv, hk_tr, hk_ti, hk_ta, 
                   hk_qn, hk_n, hk_m, chp_tmax, gb_tmax, slice_volume, mstr_chp, mstr_gb, qmax_rod_el, eps_th_chp, 
                   eps_el_chp, open_weather_map_active)
        return mypred
    #end initialize_thermal_prediction
    # ==================================================================

    def initialize_multiple_gws(self, config_file):
        actual_time = self.initialize_actual_time(self.simulation, self.start_sim_inh, self.end_sim_inh)
        real_time_send = config_file['calculation']['platform_mode']['real_time_send']
        provisioning_endpoint = config_file['calculation']['platform_mode']['provisioning_endpoint']
        sleep_time_in_s = config_file['calculation']['platform_mode']['sleep_time_in_s']
        time_step_in_s = config_file['calculation']['platform_mode']['mgw_time_step_in_s']
        
        
        return (actual_time, real_time_send, provisioning_endpoint, sleep_time_in_s, time_step_in_s)
    # end initialize_multiple_gws

    # ==================================================================

    def update_time(self, simulation, platform, actual_time, real_time_send, sleep_time_in_s, time_step_in_s):
        # determines the next time step and returns it as a time stamp
        next_time_step = actual_time + timedelta(seconds=time_step_in_s) # this line is modified in comparison with gateway in order to avoid time step manager
        if simulation:
            if(platform):
                if(real_time_send):
                    #while datetime.now() < next_time_step:
                    #    sleep(1)
                    #return datetime.now()
                    sleep(time_step_in_s)
                    return (next_time_step)
                else:
                    sleep(sleep_time_in_s)
                    return (next_time_step)
            else:
                return (next_time_step)
        else:
            while datetime.now() < next_time_step:
                sleep(1)
            return datetime.now()
    #end update_time



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

    def time_sync_gw_with_platform(self, gw_dict, actual_time, start_sim_inh, end_sim_inh):
        # sends actual_time, start_sim_inh, end_sim_inh 
        # over mqtt topic mqtt_topic_cmd
        # to the gateway as a command 'time_sync'
        if(self.dbg == 1):
            print('ENTERed time_sync_gw_with_platform')
        client = gw_dict['mqtt_client']   # client already initialized
        topic = gw_dict['mqtt_topic_cmd']
        columns = []
        data_to_send = []
        
        columns.append('cmd_type')
        data_to_send.append('time_sync')
        
        columns.append('start_sim_inh')
        data_to_send.append(start_sim_inh)
        
        columns.append('end_sim_inh')
        data_to_send.append(end_sim_inh)
        
        columns.append('actual_time')
        data_to_send.append(actual_time)
        
        payloads = ['{}|{}'.format(c,d) for c, d in zip(columns, data_to_send)]
        
        if(self.dbg == 1):
            print('columns = {}'.format(columns))
            print('data_to_send = {}'.format(data_to_send))
            print('payloads = {}'.format(payloads))
        
        client.publish(topic,'|'.join(payloads))
        if((self.dbg == 1) or (self.dbg == 2)):
            print('published time sync to topic = {}'.format(topic))
    # end time_sync_gw_with_platform

    # ==================================================================

    def configure_mqtt_client_from_config(self, config_file):
        # mqtt broker
        #broker = config_file['calculation']['platform_mode']['mqtt_broker']
        #port_nr = config_file['calculation']['platform_mode']['mqtt_port_nr']
        #client_name = config_file['calculation']['platform_mode']['mqtt_client_name_attr']
        #mqtt_username = config_file['calculation']['platform_mode']['authentication']['mqtt_username']
        #mqtt_password = config_file['calculation']['platform_mode']['authentication']['mqtt_password']
        #tls_connection = config_file['calculation']['platform_mode']['authentication']['tls_connection']
        #authentication = config_file['calculation']['platform_mode']['authentication']['activate']
        #mqtt_client = self.create_mqtt_client(broker, port_nr, client_name, authentication, mqtt_username, mqtt_password, tls_connection)
        # topics for communication with gateway
        mqtt_api_key = config_file['calculation']['platform_mode']['mqtt_api_key']
        mqtt_sensor_name = config_file['calculation']['platform_mode']['mqtt_sensor_name']
        mqtt_attributes = config_file['calculation']['platform_mode']['mqtt_attributes']
        mqtt_commands = config_file['calculation']['platform_mode']['mqtt_commands']
        mqtt_topic_cmd = "/{}/{}/{}".format(mqtt_api_key, mqtt_sensor_name, mqtt_commands)
        mqtt_topic_attr = "/{}/{}/{}".format(mqtt_api_key, mqtt_sensor_name, mqtt_attributes)
        
        return (mqtt_topic_cmd, mqtt_topic_attr)
    # end configure_mqtt_client_from_config

    # ==================================================================

    def process_gw_on_platform(self, act_gw, actual_time):
        # trigger energy vector and schedule generation if time elapses for the gateway
        if(actual_time >= act_gw['next_prediction_timestamp']):  # 
            config_file = act_gw['config']
            self.fnr = self.fnr + 1
            prediction_time_step_in_s = config_file['prediction']['prediction_time_step_in_s']
            next_prediction_timestamp = actual_time + timedelta(seconds=prediction_time_step_in_s)
            act_gw['next_prediction_timestamp'] = next_prediction_timestamp
            
            weather_pred = self.pred.get_weather_prediction(actual_time, self.simulation, self.wetter_file, self.start_datetime, self.start_sim_inh, self.end_sim_inh, self.fnr)
            arch_option_1 = False
            act_time_in_h = utils.convert_time_to_hours(actual_time)-self.ini_time_in_h
            self.pred.update_heat_consumption_from_crate(actual_time, self.time_step_in_s, arch_option_1, device_id, self.fnr)
            last_t_profile = self.pred.get_last_storage_temp_profile_from_crate(actual_time, 2.0 * self.time_step_in_s, device_id)
            energy_vector = self.pred.predict_energy_vector(weather_pred, act_time_in_h, actual_time, self.start_datetime, 
                           self.start_sim_inh, self.end_sim_inh, self.output_horizon_in_h, self.output_resolution_in_s, last_t_profile, self.fnr)
            current_sched = platformcontroller.cloud_schedule_gen(actual_time, energy_vector, self.start_datetime, config_file)
            if(self.dbg == 2):
                print('\n\ngot schedule {}\n\n\n\n'.format(current_sched))
            platformcontroller.send_schedule_to_rvk(current_sched, self.mqtt_client, self.mqtt_api_key, self.mqtt_sensor_name, self.mqtt_commands, self.fnr)
            
        # end process_gw_on_platform

    # ==================================================================

    def get_next_prediction_timestamp(self, actual_time, config_file, pred, device_id):
        # gateway is introduced to the platform and it is not yet clear when its schedule has to be updated
        prediction_time_step_in_s = config_file['prediction']['prediction_time_step_in_s']   # intervall at which the schedule should be updated
        delta_in_seconds = config_file['calculation']['time_step_in_s']   # time step of simulation
        nr_of_rec_in_db = pred.number_crate_records_in_time_span(actual_time, prediction_time_step_in_s, 2 * delta_in_seconds, device_id)
        if(nr_of_rec_in_db > 0):  
            # there are some records for this gw in the time intervall 
            # starting at now-prediction_time_step_in_s-delta_in_seconds
            # and ending at now-prediction_time_step_in_s+delta_in_seconds
            # that means that historical data for this gatewayis already available, so the prediction can be started even now
            return actual_time
        else:
            # no historical data available for this gateway so that the data has to be produced first before prediction can take place
            return (actual_time + timedelta(seconds=prediction_time_step_in_s))
        # end get_next_prediction_timestamp

    # ==================================================================

    def subscribe_to_monitoring_data(self, client, apiKey, sensor_name, attributes):
        #apiKey = 'QKAAbMxLbv5TfhFxjTv4lhw92m'
        #sensor_name = 'urn:ngsi-ld:rvk:001'
        #attributes = 'attrs'
        #topic = "#"
        topic = "/{}/{}/{}".format(apiKey, sensor_name, attributes)
        client.subscribe(topic)  # subscribe
        #client.loop_start()
        if(self.dbg == 1):
            print('subscribed to topic = {}'.format(topic))
        # end subscribe_to_monitoring_data

    # ==================================================================

    def create_mqtt_client(self, broker, port_nr, client_name, authentication, mqtt_username, mqtt_password, tls_connection):
        if(self.dbg == 1):
            print('create client {}'.format(client_name))
        client = mqtt.Client(client_name)
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        #client.on_publish = self.on_publish
        client.on_disconnect = self.on_disconnect
        if(self.dbg == 1):
            print('connect client {} to broker'.format(client_name))
        if(authentication):
            client.username_pw_set(mqtt_username, password=mqtt_password)
            if tls_connection:
                client.tls_set(tls_version=ssl.PROTOCOL_TLSv1_2)
                client.tls_insecure_set(False)
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
        if(self.dbg ==1):
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
        if(self.dbg == 1):
            print("ON PUBLISH")
            print("received message =", str(message.payload.decode("utf-8")))
        # end on_publish

    # ==================================================================

    def time_condition_for_prediction(self, actual_time, pred):
        if(self.dbg == 1):
            print('time condition')
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
        wyn1 = str(message.payload.decode("utf-8")).split("|")
        if(self.dbg == 1):
            print(wyn1[94], wyn1[95])
        actual_time = datetime.fromtimestamp(float(wyn1[95]))
        # define start_datetime as soon as possible
        if(self.first):
            self.first = False
            self.start_datetime = actual_time
            self.ini_time_in_h = utils.convert_time_to_hours(actual_time)
            self.next_prediction_timestamp = actual_time
        # end if(self.first):
            
        # check whether time elapsed for prediction
        if(self.time_condition_for_prediction(actual_time, self.pred)):
            self.fnr = self.fnr + 1
            self.next_prediction_timestamp = actual_time + timedelta(seconds=self.prediction_time_step_in_s)
            weather_pred = self.pred.get_weather_prediction(actual_time, self.simulation, self.wetter_file, self.start_datetime, self.start_sim_inh, self.end_sim_inh, self.fnr)
            arch_option_1 = False
            act_time_in_h = utils.convert_time_to_hours(actual_time)-self.ini_time_in_h
            self.pred.update_heat_consumption_from_crate(actual_time, self.time_step_in_s, arch_option_1, device_id, self.fnr)
            # get the temperature profile of the storage tank directly from the last monitoring data set
            last_t_profile = [float(wyn1[3]),float(wyn1[5]),float(wyn1[7]),float(wyn1[9]),float(wyn1[11]),float(wyn1[13]),float(wyn1[15]),float(wyn1[17]),float(wyn1[19]),float(wyn1[21]),float(wyn1[23]),float(wyn1[25]),float(wyn1[27]),float(wyn1[29]),float(wyn1[31]),float(wyn1[33]),float(wyn1[35]),float(wyn1[37]),float(wyn1[39]),float(wyn1[41])]
            energy_vector = self.pred.predict_energy_vector(weather_pred, act_time_in_h, actual_time, self.start_datetime, self.start_sim_inh, self.end_sim_inh, self.output_horizon_in_h, self.output_resolution_in_s, last_t_profile, self.fnr)
            config_file = './config.json'
            current_sched = platformcontroller.cloud_schedule_gen(actual_time, energy_vector, self.start_datetime, config_file)
            if(self.dbg == 2):
                print('\n\ngot schedule {}\n\n\n\n'.format(current_sched))
            platformcontroller.send_schedule_to_rvk(current_sched, self.mqtt_client, self.mqtt_api_key, self.mqtt_sensor_name, self.mqtt_commands, self.fnr)
        # end receive_monitoring_data

    # ==================================================================

