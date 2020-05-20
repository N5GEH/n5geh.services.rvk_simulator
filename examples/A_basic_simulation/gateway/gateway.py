from time import sleep
import numpy as np
import math
import random
from datetime import datetime, timedelta, timezone
import paho.mqtt.client as mqtt
import threading
import ssl

#import json   # only for debug of control_execute_schedule
#import requests
#import pycurl
#import httplib
#import urllib


import utils
import chpunit
import gasheater
import controlvalve
import heatingcurve
import storagetank
import timestep
import predict_thermal
import requests
import json
import platformcontroller

########################################################################

class GatewaySystem():
    """ simulator of the gateway box """

    # ==================================================================
    # constructor method with instance variables
    def __init__(self, t_initial):
        # initialize everyone
        # outputs
        self.p_atm = 0.1 * 1.01325  # in Pa
        self.t1 = self.t2 = self.t3 = self.t4 = self.t5 = self.t6 = self.t7 = self.t8 = self.t9 = self.t10 = t_initial
        self.t11 = self.t12 = self.t13 = self.t14 = self.t15 = self.t16 = self.t17 = self.t18 = self.t19 = self.t20 = t_initial
        self.t21 = self.t22 = self.t23 = self.t24 = self.t25 = self.t26 = self.t27 = self.t28 = self.t29 = self.t30 = t_initial
        self.V_1 = self.V_2 = self.V_3 = self.V_4 = 0.0  # in m3/s
        self.Z_1 = self.Z_2 = 0.0                        # double - gas consumption in ...
        self.Wh1 = self.Wh2 = self.Wh3 = 0.0             # double - electricity consumption/production in kWh
        # miscallenaous
        self.too_cold = 0                                # flag 0, 1
        self.t_initial = t_initial                       # double - temperature in °C
        # sending of monitoring data
        self.next_sending_timestamp = 0                  # time at which the data is to be sent to the platform
        # prediction
        self.next_prediction_timestamp = 0               # time at which the prediction of the energy vector is to be made
        self.prediction_time_step_in_s = 0               # time intervall at which the energy vector is to be produced
        self.output_horizon_in_h = 0                     # time horizont for which the forecast is to be made
        self.output_resolution_in_s = 0                  # resolution of the forecast in s
        # schedule
        self.current_schedule = 0                        # schedule := list of dicts
        self.schedule_changed = True                     # flag for schedule change
        self.tau_end = 0                                 # datetime - end of the current time slot
        self.tau_off = 0                                 # datetime - till this time the self.E_produced_in_kWh will supposedly reach schedule
        self.e_produced_in_kWh = 0                       # double - aggregated production already realised in this time slot
        self.e_to_prod_in_kWh = 0                        # double - envisioned production in this time slot
        self.production = []                             # list of dicts - contains production data for the last timestep
        self.sched_idx = -1                              # index in list of dicts
        # appliances
        self.storage_tank = 0                            # object
        self.chp = 0                                     # object
        self.boiler = 0                                  # object
        self.heizkurve = 0                               # object
        self.rod_stat = 0                                # double - value from 0 to 1. 0 is no power = no heat input into tank; 1 is full power input into tank
        self.tsm = 0                                     # object
        self.keep_chp_on = False   # control flag to keep operating CHP as long as possible
        self.keep_chp_off = False  # control flag to refrain from operating CHP as long as possible
        # control algorithm
        self.temp_dhw = 55.0   # minimal allowed temperature of the domestic hot water + temperature difference due to the cooling in the pipes
        self.temp_a_hp = 15.0  # boundary ambient air temperature for the heating period
        self.temp_hot = 70.0   # boundary heating water temperature  - hot water
        self.temp_warm = 50.0  # boundary heating water temperature  - warm water
        self.ctrl_option = 1   # defines how hard the schedule should be realised
                               # 1 - be conservative and do not allow the tank to unload completely ==> no risk of not reaching room or dhw temperature
                               # 2 - allow the storage tank to become fully unloaded ==> risk of not reaching the room or dhw temperature
        self.unload = False
        self.tank_state = 0
        self.dhw_prod = 0
        # provisioning and multi gateway platform mode
        self.time_data = {'valid': False}
        self.receiver_on = False
        self.demo_on = False
        # actual electricity consumption = the other electricity consumption = Wh3 - (Wh2 + Wh1)
        self.electricity_consumption_kWh = 0.0
        # mqtt configuration for sending data to the platform
        self.mqtt_client = 0
        self.mqtt_client_initialized = False
        self.mqtt_broker = 0
        self.mqtt_port_nr = 0
        self.mqtt_api_key = 0
        self.mqtt_sensor_name = 0
        self.mqtt_commands = 0
        self.mqtt_attributes = 0
        self.mqtt_client_name = 0
        # mqtt configuration for subscription to data from demonstrator
        self.got_demo_data = False
        self.tni = 0.0
        self.coef = 0.0
        #self.mqtt_client_name_cmd = 0
        self.q_in_kW = 0
        # Sperrzeiten
        self.sp_active = False
        self.sp_start = []
        self.sp_end = []
        # debug flag
        # 0 - no output, only warnings and errors; 1 - communication with platform; 2 - write files; 3 - calculation vs. sending frequency thats neededfor demo
        self.dbg = 0                                     # integer
        self.dbg_path = "."
#        #print('t1 = {}'.format(self.t1))
    #end __init__

    # ==================================================================

    def get_storage_tank(self):
        return self.storage_tank

    # ==================================================================

    def get_energy_left_to_tmax(self, tmax):
        return self.storage_tank.calc_energy_left_to_tmax(tmax)

    # ==================================================================

    def get_max_temp_of_chp(self):
        return self.chp.get_max_temp_of_chp()

    # ==================================================================

    def get_out_temp_of_gb(self):
        return self.boiler.get_out_temp()

    # ==================================================================

    def get_mstr_hk(self):
        return self.heizkurve.get_design_mass_flow()

    # ==================================================================

    def get_mstr_chp(self):
        return self.chp.get_mass_flow()

    # ==================================================================

    def get_mstr_gb(self):
        return self.boiler.calc_mass_flow()

    # ==================================================================

    def get_el_prod_kWh(self, therm_prod_kWh):
        return self.chp.get_el_prod_kWh(therm_prod_kWh)

    # ==================================================================

    def max_pred_temp_supply_heating_sys(self, t_a_min):
        return self.heizkurve.get_supply_temperature(t_a_min)

    # ==================================================================

    def get_return_temperature(self, t_a_pred):
        return self.heizkurve.get_return_temperature(t_a_pred)

    # ==================================================================

    def thermal_energy_that_can_be_got_from_storage(self, tmin):
        return self.storage_tank.calc_energy_above_tmin(tmin)

    # ==================================================================

#   obsolete function - to delete after check
    def get_temp_profile_in_storage(self):
        return self.storage_tank.output_temperatures()

    # ==================================================================

    def get_slice_vol(self):
        return self.storage_tank.get_slice_vol()

    # ==================================================================

    def get_max_thermal_rod_power(self):
        return self.storage_tank.get_max_thermal_rod_power()  # in kW

    # ==================================================================

    def get_max_th_tank_power(self):
        return self.storage_tank.get_max_th_tank_power(self.t22)  # in kW

    # ==================================================================

    def get_max_thermal_boiler_power(self):
        return self.boiler.get_max_thermal_boiler_power()  # in kW

    # ==================================================================

    def initialize_actual_time(self, real_time_send, start_sim_inh, end_sim_inh):
#    def initialize_actual_time(self, simulation, end_sim_inh):
        if real_time_send:
            return datetime.now()  # time in datetime format
        else:
            return (datetime.now() - timedelta(hours=(end_sim_inh - start_sim_inh)))  # time in datetime format
            #return (datetime.now() - timedelta(hours=end_sim_inh))  # time in datetime format

    #end initialize_actual_time

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

    def update_time(self, simulation, platform, actual_time, tsm, real_time_send, sleep_time_in_s, time_step_in_s):
        next_time_step = actual_time + timedelta(seconds=tsm.get_timestep())
        #print('now = {}, next = {}'.format(datetime.now(), next_time_step))
        if simulation:
            if(platform):
                if(real_time_send):
                    while datetime.now() < next_time_step:
                        sleep(0.1)
                    return datetime.now()
                    #sleep(time_step_in_s)
                    #return (next_time_step)
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

    def get_heater_rod_status(self, simulation, el_load_file, actual_time, start_datetime, start_sim_inh, end_sim_inh):
        """ returns the status between 0 = OFF and 1 = ON of the electrical rod heater """
        if simulation:
            # file based simulation - values are read from the file
            # file based simulation - values are read from the file
            #            hour_of_year = 1
            simtime = int(math.floor(((actual_time - start_datetime).seconds / (60.0 * 15.0)) + start_sim_inh * 60.0 / 15.0))  # simulationstime in quarters = 15 minutes slots
            if (simtime >= 35040):     # actual time exceeds the first year (there are 35 040 slots of 15 minutes in a year)
                simtime = simtime - math.floor(simtime / 35040) * 35040
            line1 = utils.get_significant_parts(el_load_file[simtime].rstrip().split(" "))
            y1 = float(utils.get_ith_column(2, line1))
            return y1    # as load from 0 to 1
        else:
            # real time calculation - values are received via MQTT? - dead for now
            return 0
        
    #end get_heater_rod_status

    # ==================================================================

    def get_dhw_minute_consumption(self, simulation, dhw_load_file, actual_time, start_datetime, start_sim_inh, end_sim_inh):
        # returns the volume of dhw consumption read from file dhw_load_file in m3/s
        # file dhw_load_file contains values in in dm3/min = liter/minute
        # simulation     - flag for real time or file based 
        # dhw_load_file  - file with dhw consumption in litres resolved for 525600 minutes of the year = 8760 h/a * 60 min/h
        # actual_time    - the current time or current simulation time in the datetime format
        # start_datetime - start of the calculations in datetime format
        # start_sim_inh  - only in simulation mode - the starting point of the simulation in hours - will be found in the wetter_file
        # end_sim_inh    - only in simulation mode - the end point of the simulation in hours - arbitrarily stated
        nn = len(dhw_load_file)  # = 525600 for the whole year
        # file based simulation - values are read from the file
        #            hour_of_year = 1
        simtime = int(math.floor(((actual_time - start_datetime).seconds / 60.0) + start_sim_inh * 60.0))  # simulationstime in minutes
        if (simtime >= nn):     # actual time exceeds the first year (there are 525 600 minutes in a year)
            simtime = simtime - math.floor(simtime / nn) * nn
        nn = len(dhw_load_file)
        if(int(simtime) > nn):
            simtime = int(simtime) % nn
        minute = int(dhw_load_file[simtime])
        return minute/60000.0    # in cubic meter per second = m3/s = dm3/min / (60 s/min * 1000 dm3/m39
        #
        #wyn = 0.0
        #if((actual_time-start_datetime).seconds >= (3600.0 * 48.0)):
            #wyn = minute / 60000.0    # in cubic meter per second = m3/s = dm3/min / (60 s/min * 1000 dm3/m3)
        #return wyn

    #end get_dhw_minute_consumption

    # ==================================================================

    def schedule_receiver(self, config_file_path):
        #print('STARTED RECEIVER')
        config_file = utils.check_and_open_json_file(config_file_path)
        # mqtt
        conf_plat = config_file['calculation']['platform_mode']
        #mqtt_broker = conf_plat['mqtt_broker']
        #mqtt_port_nr = conf_plat['mqtt_port_nr']
        mqtt_api_key = conf_plat['mqtt_api_key']
        mqtt_sensor_name = conf_plat['mqtt_sensor_name']
        mqtt_attributes = conf_plat['mqtt_attributes']
        mqtt_commands = conf_plat['mqtt_commands']
        dbg_level = conf_plat['dbg_level']
        #mqtt_client_name = 'rvk3'
        #mqtt_client_name = conf_plat['mqtt_client_name_cmd']
        #client = self.create_mqtt_client(mqtt_broker, mqtt_port_nr, mqtt_client_name)     # creates mqtt client
        #self.subscribe_to_schedule(self.mqtt_client, mqtt_api_key, mqtt_sensor_name, mqtt_commands) # subscribes to schedule topic
        # wait for the simulator to initialize and setup the mqtt client
        loop1 = True
        if(dbg_level == 1):
            print('[', end = '')
        while loop1:
            # when time settings arrive from platform, they set this flag to True 
            # see on_message and decode_schedule_from_ul_msg functions for cmd_type == 'time_sync'
            if(self.mqtt_client_initialized): 
                loop1 = False
            sleep(1)
            if(dbg_level == 1):
                print('.', end = '')
        # take over the settings of the platform and implement them
        if(dbg_level == 1):
            print(']')
        self.subscribe_to_schedule(self.mqtt_client, mqtt_api_key, mqtt_sensor_name, mqtt_commands) # subscribes to schedule topic
        try:
            if(dbg_level == 1):
                print('RECEIVER starts looping == listening')
            self.mqtt_client.loop_start()                                                             # listens for the schedule
            self.receiver_on = True
            if(dbg_level == 1):
                print('self.receiver_on = {}'.format(self.receiver_on))
            #self.mqtt_client.loop_forever()                                                             # listens for the schedule
        except KeyboardInterrupt:    # does not work for some unknown reason
            utils.my_thread_kill()
        except:
            utils.my_thread_kill()
        # end schedule_receiver

    # ==================================================================

    def demo_receiver(self, config_file_path):
        print('STARTED DEMO RECEIVER')
        config_file = utils.check_and_open_json_file(config_file_path)
        # mqtt
        conf_plat = config_file['calculation']['platform_mode']
        mqtt_broker = conf_plat['mqtt_broker']
        mqtt_port_nr = conf_plat['mqtt_port_nr']
        dbg_level = conf_plat['dbg_level']
        mqtt_client_name = config_file['calculation']['demonstrator_mode']['mqtt_client_name_receiver']  # rvk4
        mqtt_topic = config_file['calculation']['demonstrator_mode']['mqtt_topic']
        authentication = config_file['calculation']['demonstrator_mode']['authentication']['activate']
        mqtt_username = config_file['calculation']['demonstrator_mode']['authentication']['mqtt_username']
        mqtt_password = config_file['calculation']['demonstrator_mode']['authentication']['mqtt_password']
        tls_connection = config_file['calculation']['demonstrator_mode']['authentication']['tls_connection']
        loop1 = True
        while loop1:
            # when time settings arrive from platform, they set this flag to True 
            # see on_message and decode_schedule_from_ul_msg functions for cmd_type == 'time_sync'
            if(self.mqtt_client_initialized): 
                loop1 = False
            sleep(1)
        client = self.create_mqtt_client2(mqtt_broker, mqtt_port_nr, mqtt_client_name, authentication, mqtt_username, mqtt_password, tls_connection)     # creates mqtt client
        client.subscribe(mqtt_topic)  # subscribe
        try:
            #client.loop_forever()                                                             # listens for the schedule
            if(dbg_level == 1):
                print('DEMO RECEIVER at rvk starts looping == listening')
            client.loop_start()                                                             # listens for the schedule
            self.demo_on = True
            #    time.sleep(1)
        except KeyboardInterrupt:
            utils.my_thread_kill()
        except:
            utils.my_thread_kill()
        # end demo_receiver

    # ==================================================================

    def is_platform_mode_on(self, config_file_path):
        config_file = utils.check_and_open_json_file(config_file_path)
        if(config_file['calculation']['mode'] == 'simulation'):
            return False
        elif(config_file['calculation']['mode'] == 'platform'):
            return True
        else:
            print('EXCEPTION: wrong mode = {}'.format(config_file['calculation']['mode']))
            return False
        # end is_platform_mode_on

    # ==================================================================

    def is_demo_mode_on(self, config_file_path):
        config_file = utils.check_and_open_json_file(config_file_path)
        return config_file['calculation']['demonstrator_mode']['activated']

    # ==================================================================

    def main(self, config_file_path):
        #config_file_path = './config.json'
        print('main config_file_path = {}'.format(config_file_path))
        
        thread1 = threading.Thread(target=self.simulator, args=(config_file_path,))
        if(self.is_platform_mode_on(config_file_path)):
            thread2 = threading.Thread(target=self.schedule_receiver, args=(config_file_path,))
        if(self.is_demo_mode_on(config_file_path)):
            thread3 = threading.Thread(target=self.demo_receiver, args=(config_file_path,))

        # Will execute both in parallel
        thread1.start()
        if(self.is_platform_mode_on(config_file_path)):
            thread2.start()
        if(self.is_demo_mode_on(config_file_path)):
            thread3.start()

        # Joins threads back to the parent process, which is this program
        thread1.join()
        if(self.is_platform_mode_on(config_file_path)):
            thread2.join()
        if(self.is_demo_mode_on(config_file_path)):
            thread3.join()

        # end main

    # ==================================================================

    def simulator(self, config_file_path):
        print('STARTED SIMULATOR')

        # some configuration
        arch_option_1 = True  # True ==> create db gets asked in every timestep
        arch_option_1 = False  # False ==> create db gets asked only every three hours

        # read in configuration file
        config_file = utils.check_and_open_json_file(config_file_path)

        # initialisation of objects and variables
        (platform, simulation, time_step_in_s, record_step_in_s, start_sim_inh, end_sim_inh, wetter_file, 
         dhw_load_file, el_load_file, actual_time, F, tsm, tank, chp, kessel, cvalve, heizkurve, pred, 
         real_time_send, sleep_time_in_s, demonstrator, pred_res_in_s, powr_conf, heatc_conf, 
         multiple_gateways, provisioning_endpoint, device_id, 
         authentication, mqtt_username, mqtt_password, tls_connection, mqtt_topic_attr) = self.initialize_components(config_file)

        # MQTT initialization
        platform_client = 0
        if(platform):
            self.mqtt_client = self.create_mqtt_client(self.mqtt_broker, self.mqtt_port_nr, self.mqtt_client_name, 
                                authentication, mqtt_username, mqtt_password, tls_connection)     # creates mqtt client
            self.mqtt_client_initialized = True
        # end if(platform):

        # provisioning and time management
        if(multiple_gateways):
            
            if(self.dbg == 1):
                print('waiting for mqtt receiver to initialize')
            if(not self.receiver_on):
                loop1 = True
                while loop1:
                    if(self.receiver_on):
                        if(demonstrator):
                            if(self.demo_on):
                                loop1 = False
                        else:
                            loop1 = False
                    sleep(1)
                if(self.dbg == 1):
                    print('simulator sees self.receiver_on = {}'.format(self.receiver_on))
            if(self.dbg == 1):
                print('provisioning of gw: ')
            #provisioning_endpoint = 'http://iot-agent:4041/iot/devices'
            #provisioning_endpoint = "http://127.0.0.1:4041/iot/devices"
            # provision device with the platform
            # if the gateway has already been provisioned, you get an informative message but it does not spoil anything
            utils.provision_rvk(device_id, device_id, "rvk", provisioning_endpoint)
            # send initial data set consisting of actual_time and number 10.0 to the platform
            # only this makes the crate db create the needed tables - which in turn makes its query possible
            # db queries are needed for the rest of initialization 
            # (self.get_next_prediction_timestamp and self.pred.update_heat_consumption_from_crate in self.process_gw_on_platform)
            utils.send_ini_data_to_platform(mqtt_topic_attr, 10.0, actual_time, self.mqtt_client)
            # if the 'calculation' -> 'platform_mode' -> 'real_time_send' is false
            # the time of gateway has to be synchronized with the time of the platform
            # If it is true, every gateway can use its own clock as the differences 
            # are expected to be neither significant nor crucial for the operation
            if(self.dbg == 1):
                print('real_time_send = {}'.format(real_time_send))
            if(not real_time_send):
                # wait for the platform to send its time settings
                loop1 = True
                ijk = 0
                if(self.dbg == 1):
                    print('{} self.time_data = {}'.format(ijk, self.time_data))
                while loop1:
                    ijk = ijk + 1
                    # when time settings arrive from platform, they set this flag to True 
                    # see on_message and decode_schedule_from_ul_msg functions for cmd_type == 'time_sync'
                    if(self.time_data['valid']): 
                        loop1 = False
                    sleep(1)
                    if(self.dbg == 1):
                        print('Seconds left to undo provisioning and exit = {}; '.format(15 - ijk))
                    if(ijk > 15):
                        utils.undo_provisioning_and_exit(device_id, provisioning_endpoint)
                # take over the settings of the platform and implement them
                actual_time = self.time_data['actual_time']
                start_sim_inh = self.time_data['start_time_in_h']
                end_sim_inh = self.time_data['end_time_in_h']
                self.next_sending_timestamp = actual_time + timedelta(seconds=self.send_intervall_in_s)
                self.next_prediction_timestamp = actual_time + timedelta(seconds=self.prediction_time_step_in_s)
                self.tsm.set_end_time(actual_time)
                self.chp.reset_next_safe_turn_on(actual_time)
                self.boiler.reset_next_safe_turn_on(actual_time)
                self.storage_tank.update_act_time(actual_time)
                self.current_schedule = self.initialize_schedule(actual_time)
                if(self.dbg == 1):
                    print('self.time_data = {}'.format(self.time_data))
            # end if(not real_time_send):
            # else: # do nothing - both rvk and platform are using their system clocks and hopefully do not need to be synchronized
        # end if(multiple_gateways):

        # start standard calculation
        ini_time_in_h = utils.convert_time_to_hours(actual_time)
        last_record_time = actual_time  # time in datetime format
        print_time_in_h = 0
        start_datetime = actual_time
        end_datetime = actual_time + timedelta(hours=(end_sim_inh - start_sim_inh))
        #end_datetime = actual_time + timedelta(hours=end_sim_inh)
        print('actual_time = {} (in hours = {})'.format(actual_time,utils.convert_time_to_hours(actual_time)))
        print('start_datetime = {} (in hours = {})'.format(start_datetime,utils.convert_time_to_hours(start_datetime)))
        print('end_datetime = {} (in hours = {})'.format(end_datetime,utils.convert_time_to_hours(end_datetime)))
        #print('simulation = {} platform = {}'.format(simulation,platform))

        # header of permanent file with output data - stays there in all denug modes and all operaion modes
        self.write_header_output_file(F)
        print('modules initialized')

        # stats of this simulation run
        timestart = datetime.now()

        # Martin's code - do I need this? TODO - yes, needed for instant initialization of schedule calculation - might be useful in demo mode
        predict_thermal.file_name=open("./pred.txt","a")

        # debug data
        H = 0
        if(self.dbg == 2):
            H = open("{}/logrvk1.dat".format(self.dbg_path),"w")
        G = 0
        if(self.dbg == 2):
            G = open("{}/mylog.dat".format(self.dbg_path),"w")
            G.write(' all data sent from gateway.py to crate db \n')
            G.write(' utc time stamp time_in_h \n')
        if(self.dbg == 3):
            sendstart = datetime.now()
        
        # start main program loop
        while self.loop_condition(simulation, actual_time, end_datetime):
            # receive new schedule and realise it in practice
            self.control_execute_schedule(actual_time)
            # t_a
            if(demonstrator and self.got_demo_data):
                ambient_temp = self.tni - self.q_in_kW * self.coef  # = t_ni - Q/Q_n * (t_ni - t_na)
                self.got_demo_data = False
            else:
                ambient_temp = utils.get_ambient_temperature(simulation, wetter_file, actual_time, start_datetime, start_sim_inh, end_sim_inh)
            self.t30 = ambient_temp
            # dhw consumption
            self.V_1 = self.get_dhw_minute_consumption(simulation, dhw_load_file, actual_time, start_datetime, start_sim_inh, end_sim_inh)
            # cold water temperature
            self.t22 = 10.0
            # electrical rod heater:
            # electricity consumption of "other" consumers
            self.electricity_consumption_kWh = self.calc_el_cons_other(actual_time, powr_conf)
            #el_heat_status = self.get_heater_rod_status(simulation, el_load_file, actual_time, start_datetime, start_sim_inh, end_sim_inh)
            # status of electrical rod heater in the heat storage tank as double number from 0,0 to 1,0. (here "," is decimal sign)
            el_heat_status = self.rod_stat
            # time management
            act_time_in_h = utils.convert_time_to_hours(actual_time)-ini_time_in_h
            next_time_step = self.update_time(simulation, platform, actual_time, tsm, real_time_send, sleep_time_in_s, time_step_in_s)
            real_dt_in_s = (next_time_step - actual_time).seconds
            tank.update_act_time(act_time_in_h)  # used only for debugging
            # calculation
            self.one_iteration_step(tsm, tank, chp, kessel, cvalve, heizkurve, ambient_temp, el_heat_status, actual_time, heatc_conf)
            self.update_electricity_production_status(time_step_in_s, pred_res_in_s)
            # output control
            last_record_time = self.write_output_into_file(F, record_step_in_s, last_record_time, actual_time ,act_time_in_h ,ambient_temp ,chp ,kessel ,cvalve ,tank, tsm)  # at the end of the timestep
            # saving data for prediction algorithms
            if(self.time_condition_for_sending_monitoring(actual_time)):
                if(self.dbg == 3):
                    sendend = datetime.now()
                    #print('SENDING 2 plat in {}'.format(sendend - sendstart), end='')
                    print('SENDING 2 plat in {}'.format(sendend - sendstart))
                    sendstart = sendend
                self.next_sending_timestamp = actual_time + timedelta(seconds=self.send_intervall_in_s)
                if(platform):
                    self.send_data_to_platform(actual_time, act_time_in_h, chp, kessel, cvalve, tank, self.mqtt_client, G)
                    if(arch_option_1):
                        pred.update_heat_consumption_from_crate(actual_time, time_step_in_s, arch_option_1, device_id, 1)
                else:
                    self.save_data_for_prediction(pred, act_time_in_h, ambient_temp)
            
            ######################### PLATFORM - BEGIN - 1 #################
#            if(self.time_condition_for_prediction(actual_time, pred)):
#                print('\n\n\n\nP R E D I C T I O N\n\n\n\n')
#                if(self.dbg >= 2):
#                    G.flush()
#                    G.close()
#
#                    G = open("./mylog.dat","w")
#                    G.write(' all data sent from gateway.py to crate db \n')
#                    G.write(' utc time stamp time_in_h \n')
#                print(' weather prediction')
#                weather_pred = self.get_weather_prediction(actual_time, simulation, wetter_file, start_datetime, start_sim_inh, end_sim_inh)
#                if(platform and (not arch_option_1)):
#                    print('get data from crate')
#                    pred.update_heat_consumption_from_crate(actual_time, time_step_in_s, arch_option_1, device_id, fnr)
#                    energy_vector = 0
#                #elif(not platform):
#                last_t_profile = tank.output_temperatures()
#                energy_vector = pred.predict_energy_vector(weather_pred, act_time_in_h, actual_time, start_datetime, start_sim_inh, end_sim_inh, self.output_horizon_in_h, self.output_resolution_in_s, last_t_profile)
#                self.send_or_save_energy_vector(actual_time, energy_vector, start_datetime, platform, platform_client)
            ######################### PLATFORM - END - 1 ###################
            #if(self.dbg == 3):
            #    print(' time = {}'.format(actual_time))
            # proceed to the next timestep
            actual_time = next_time_step
            flag_big_time_step = tsm.has_timestep_ended(actual_time)  # redundant ?
            # show progress at prompt
            if((act_time_in_h-print_time_in_h) > 0.05 * (end_sim_inh - start_sim_inh)):
                print_time_in_h = act_time_in_h
                if(self.dbg != 3):
                    print('.', end = '', flush=True)
            #if(not real_time_send):
            #    sleep(sleep_time_in_s)
            # output to the file - end

        # end while self.loop_condition
        F.close()
        if(self.dbg == 2):
            G.close()
        if(self.dbg == 2):
            H.close()
        # duration of the calculation
        timeend = datetime.now()
        print('\ncalculation took = {} seconds'.format(timeend - timestart))

    #end simulator

    # ==================================================================

    def time_condition_for_sending_monitoring(self, actual_time):
        if(actual_time >= self.next_sending_timestamp):
            return True
        else:
            return False
    # end time_condition_for_sending_monitoring

    # ==================================================================

    def time_condition_for_prediction(self, actual_time, pred):
        if(actual_time >= self.next_prediction_timestamp):
            if(pred.get_q_write()):
                #print('now = {}; next time = {}'.format(actual_time, self.next_prediction_timestamp))
                return True
        return False

    #end time_condition_for_prediction

    # ==================================================================

    def send_or_save_energy_vector(self, actual_time, energy_vector, start_datetime, platform, platform_client):
        # send energy vector to platformcontroller and get the current schedule out of it
        if(self.dbg==2):
            H = open("./myenvec1.dat","w")
            H.write(' energy vector sent from platform  \n')
            H.write(' date  time  utc_time  time_in_h  P_el_min_in_W  P_el_max_in_W \n')
            for ln in energy_vector:
                H.write(' {} '.format(ln['time stamp']))
                H.write(' {} '.format(ln['time stamp'].replace(tzinfo=timezone.utc).timestamp()))
                H.write(' {} '.format(ln['time_in_h']))
                H.write(' {} '.format(ln['P_el_min_in_W']))
                H.write(' {} \n'.format(ln['P_el_max_in_W']))
            H.close()
        #
        self.next_prediction_timestamp = actual_time + timedelta(seconds=self.prediction_time_step_in_s)
        current_sched = platformcontroller.cloud_schedule_gen(actual_time, energy_vector, start_datetime)

        if(self.dbg==2):
            H = open("./myschedule1.dat","w")
            H.write(' schedule sent from platform  \n')
            H.write(' timestep_in_s = {} \n'.format(current_sched['timestep_in_s']))
            H.write(' active_schedule = {} \n'.format(current_sched['active schedule']))
            H.write(' date  time  utc_time  activation  energy_production_in_W \n')

            myvals = current_sched['values']

            for ln in myvals:
                H.write(' {} '.format(str(ln['time_stamp'])))
                H.write(' {} '.format(ln['time_stamp'].replace(tzinfo=timezone.utc).timestamp()))
                H.write(' {} '.format(str(ln['activation'])))
                H.write(' {}  \n'.format(ln['energy_production_in_W']))
            H.close()
            print('send_or_save_energy_vector : schedule written into myschedule1.dat')
        
        if(platform):
            platformcontroller.send_schedule_to_rvk(current_sched, platform_client)
        else:
            self.current_schedule = current_sched
            self.schedule_changed = True
        if((self.dbg == 2) or (self.dbg == 1)):
            print('\n\n\n\n ========= CHANGE SCHEDULE ======================\n\n\n\n')
    #end send_or_save_energy_vector

    # ==================================================================

    def request_weather_prediction_from_platform(self, actual_time):
        # holder for Ilya
        return list({'date':actual_time, 'time_in_h': 0.0, 'temp_in_C': 0.0})

    #end request_weather_prediction_from_platform

    # ==================================================================

    def write_header_output_file(self, F):
        F.write("# date  time  elapsed  t_a  t_1  t_2  t_3  t_4  t_5  t_6  t_7")
        F.write(" t_8  t_9  t_10  t_11  t_12  t_13  t_14  t_15  t_16")
        F.write(" t_17  t_18  t_19  t_20  t_21  t_22  t_23  t_24  t_25")
        F.write(" t_26  t_27  t_28  t_29  t_30  V_1  v_2  V_3  V_4")
        F.write(" Z_1  Z_2  Wh1  Wh2  Wh3  ")
        F.write("chp  boiler  control_valve  COLD  mstr_dhw  mstr_hw  el_heater  n_slice  tstep_in_s  \n")

        F.write("# dd.mm.yyyy  hh:mm:ss.micro_s  h  °C  °C  °C  °C  °C  °C  °C  °C")
        F.write(" °C  °C  °C  °C  °C  °C  °C  °C  °C")
        F.write(" °C  °C  °C  °C  °C  °C  °C  °C  °C")
        F.write(" °C  °C  °C  °C  °C  m3/s  m3/s  m3/s  m3/s")
        F.write(" m3/s  m3/s  kW  flag  kg/s  kg/s  kW  kW  0-1  kg/s  kg/s  0-1  h  s ")
        F.write(" 0-1  0-1  0-1  '1-5  0-1 \n")

        F.write("# date  time  elapsed  t_a  t_1  t_2  t_3  t_4  t_5  t_6  t_7")
        F.write("  t_8  t_9  t_10  t_11  t_12  t_13  t_14  t_15  t_16")
        F.write("  t_17  t_18  t_19  t_20  t_21  t_22  t_23  t_24  t_25")
        F.write("  t_26  t_27  t_28  t_29  t_30  V_1  v_2  V_3  V_4")
        F.write("  Z_1  Z_2  Wh1  Wh2  Wh3")
        F.write("  chp  boiler  control_valve  COLD  mstr_dhw  mstr_hw  el_heater  n_slice  tstep_in_s  ")
        F.write("self.unload keep_chp_on keep_chp_off  tank_state  dhw_prod  ")
        F.write("d_1  d_2  d_3  d_4  d_5  d_6  d_7")
        F.write("  d_8  d_9  d_10  d_11  d_12  d_13  d_14  d_15  d_16")
        F.write("  d_17  d_18  d_19  d_20  ")
        F.write("\n")

    #end write_header_output_file

    # ==================================================================

    def write_output_into_file(self, F, record_step_in_s, last_record_time, actual_time, act_time_in_h, ambient_temp, chp, kessel, cvalve, tank, tsm):
        [d1, d2, d3, d4, d5, d6, d7, d8, d9, d10, d11, d12, d13, d14, d15, d16, d17, d18, d19, d20] = tank.dhw_profile_temperatures()
        if((actual_time - last_record_time).total_seconds() >= record_step_in_s):
            F.write("  {}  {}  {}".format(actual_time,act_time_in_h,ambient_temp))
            F.write("  {}  {}  {}".format(self.t1,self.t2,self.t3))
            F.write("  {}  {}  {}".format(self.t4,self.t5,self.t6))
            F.write("  {}  {}  {}".format(self.t7,self.t8,self.t9))
            F.write("  {}  {}  {}".format(self.t10,self.t11,self.t12))
            F.write("  {}  {}  {}".format(self.t13,self.t14,self.t15))
            F.write("  {}  {}  {}".format(self.t16,self.t17,self.t18))
            F.write("  {}  {}  {}".format(self.t19,self.t20,self.t21))
            F.write("  {}  {}  {}".format(self.t22,self.t23,self.t24))
            F.write("  {}  {}  {}".format(self.t25,self.t26,self.t27))
            F.write("  {}  {}  {}".format(self.t28,self.t29,self.t30))
            F.write("  {}  {}  {}".format(self.V_1,self.V_2,self.V_3))
            F.write("  {}  {}  {}".format(self.V_4,self.Z_1,self.Z_2))
            F.write("  {}  {}  {}".format(self.Wh1,self.Wh2,self.Wh3))
            F.write("  {}  {}  {}".format(chp.get_status(),kessel.get_status(),cvalve.get_hub()))
            F.write("  {}  {}  {}".format(self.too_cold,tank.get_mstr_dhw(),tank.get_mstr_hw()))
            F.write("  {}  {}  {}".format(tank.get_el_heater_status(),tank.get_slice_wechsel_zeit_in_h(),tsm.get_timestep()))
            F.write("  {}  {}  {}".format(int(self.unload),int(self.keep_chp_on),int(self.keep_chp_off)))
            F.write("  {}  {}".format(int(self.tank_state), int(self.dhw_prod)))
            F.write("  {}  {}  {}".format(d1,d2,d3))
            F.write("  {}  {}  {}".format(d4,d5,d6))
            F.write("  {}  {}  {}".format(d7,d8,d9))
            F.write("  {}  {}  {}".format(d10,d11,d12))
            F.write("  {}  {}  {}".format(d13,d14,d15))
            F.write("  {}  {}  {}".format(d16,d17,d18))
            F.write("  {}  {}  ".format(d19,d20))
            F.write(" \n")
            #print('act_time= {}; last_rec = {}; Delta={}'.format(actual_time, last_record_time, (actual_time - last_record_time).total_seconds()))
            last_record_time = actual_time
        return last_record_time

    #end write_output_into_file

    # ==================================================================

    def send_data_to_platform(self, actual_time, act_time_in_h, chp, kessel, cvalve, tank, client, G):
        """ communication with platform - sends the set of monitoring data from RVK to the mqtt broker """
        #columns = [" 'T' 'iteration'",
        columns = ['iteration',
                  'T01_Sp01',
                  'T02_Sp02',
                  'T03_Sp03',
                  'T04_Sp04',
                  'T05_Sp05',
                  'T06_Sp06',
                  'T07_Sp07',
                  'T08_Sp08',
                  'T09_Sp09',
                  'T10_Sp10',
                  'T11_Sp11',
                  'T12_Sp12',
                  'T13_Sp13',
                  'T14_Sp14',
                  'T15_Sp15',
                  'T16_Sp16',
                  'T17_Sp17',
                  'T18_Sp18',
                  'T19_Sp19',
                  'T20_Sp20',
                  'T21_DomesticHotWater',
                  'T22_DomesticColdWater',
                  'T23_Supply_HeatingBeforeMixValve',
                  'T24_Return_HeatingCircuit',
                  'T25_Supply_HeatingCircuit',
                  'T26_Supply_CHPunit',
                  'T27_Return_CHPunit',
                  'T28_Supply_GasBoiler',
                  'T29_Return_GasBoiler',
                  'T30_AmbientAirTemperature',
                  'V01_ColdDrinkingWater',
                  'V02_HeatingCircuit',
                  'V03_CHPunit',
                  'V04_GasBoiler',
                  'Vgas01_MainMeter',
                  'Vgas02_CHPunit',
                  'Wh01_HeatSources',
                  'Wh02_HeaterRod',
                  'Wh03_MainMeter',
                  'chp_status',
                  'boiler_status',
                  'control_valve_hub',
                  'storage_tank_too_cold_status',
                  'mass_flow_dhw',
                  'mass_flow_heating_water',
                  'elctric_heater_status',
                  'turnover_time_of_one_seg_in_h']
        xtime = actual_time.replace(tzinfo=timezone.utc).timestamp()
        #myshft = 100000000.0
        #x1 = float(int(xtime/myshft))
        #x2 = float(int(xtime-x1*myshft))
        #x3 = xtime - int(xtime)
        (x1,x2,x3) = utils.decompose_utc_time_to_floats(xtime)
        
        
        data_to_send = []
#        data_to_send.append(actual_time.isoformat())          #  1
        data_to_send.append(x2)          #  1
        #data_to_send.append(str(actual_time))          #  1
        data_to_send.append(self.t1)                #  2
        data_to_send.append(self.t2)                #  3
        data_to_send.append(self.t3)                #  4
        data_to_send.append(self.t4)                #  5
        data_to_send.append(self.t5)                #  6
        data_to_send.append(self.t6)                #  7
        data_to_send.append(self.t7)                #  8
        data_to_send.append(self.t8)                #  9
        data_to_send.append(self.t9)                # 10
        data_to_send.append(self.t10)               # 11
        data_to_send.append(self.t11)               # 12
        data_to_send.append(self.t12)               # 13
        data_to_send.append(self.t13)               # 14
        data_to_send.append(self.t14)               # 15
        data_to_send.append(self.t15)               # 16
        data_to_send.append(self.t16)               # 17
        data_to_send.append(self.t17)               # 18
        data_to_send.append(self.t18)               # 19
        data_to_send.append(self.t19)               # 20
        data_to_send.append(self.t20)               # 21
        data_to_send.append(self.t21)               # 22
        data_to_send.append(self.t22)               # 23
        data_to_send.append(self.t23)               # 24
        data_to_send.append(self.t24)               # 25
        data_to_send.append(self.t25)               # 26
        data_to_send.append(self.t26)               # 27
        data_to_send.append(self.t27)               # 28
        data_to_send.append(self.t28)               # 29
        data_to_send.append(self.t29)               # 30
        data_to_send.append(self.t30)               # 31
        data_to_send.append(self.V_1)               # 32
        data_to_send.append(self.V_2)               # 33
        data_to_send.append(self.V_3)               # 34
        data_to_send.append(self.V_4)               # 35
        data_to_send.append(self.Z_1)               # 36
        data_to_send.append(self.Z_2)               # 37
        data_to_send.append(self.Wh1)               # 38
        data_to_send.append(self.Wh2)               # 39
        data_to_send.append(self.Wh3)               # 40
        data_to_send.append(chp.get_status())       # 41
        data_to_send.append(kessel.get_status())    # 42
        data_to_send.append(cvalve.get_hub())       # 43
        data_to_send.append(self.too_cold)          # 44
        #data_to_send.append(tank.get_mstr_dhw())    # 45
        #data_to_send.append(tank.get_mstr_hw())     # 46
        #data_to_send.append(tank.get_el_heater_status()) # 47
        data_to_send.append(x1)    # 45
        data_to_send.append(x2)     # 46
        data_to_send.append(x3) # 47
        data_to_send.append(xtime) # 48
        #data_to_send.append(actual_time.replace(tzinfo=timezone.utc).timestamp()) # 49 ==> 48
        if(self.dbg == 2):
            #G.write('{} {} {} {} {} {}\n'.format(actual_time.replace(tzinfo=timezone.utc).timestamp(), actual_time, act_time_in_h,x1,x2,x3))
            #G.write('{} {} {} {} {} {}\n'.format(xtime, actual_time, act_time_in_h,x1,x2,x3))
            G.write('{}  {}  {}\n'.format(xtime, actual_time, data_to_send))
        #data_to_send.append(actual_time.replace(tzinfo=timezone.utc).timestamp()) # 49

        #apiKey = 'QKAAbMxLbv5TfhFxjTv4lhw92m'
        #sensor_name = 'urn:ngsi-ld:rvk:001'
        #attributes = 'attrs'
        apiKey = self.mqtt_api_key
        sensor_name = self.mqtt_sensor_name
        attributes = self.mqtt_attributes
        topic = "/{}/{}/{}".format(apiKey, sensor_name, attributes)
        #client = mqtt.Client('rvk')
        #client.connect('mqtt-broker', port=1883, keepalive=60, bind_address="")
        payloads = ['{}|{}'.format(c,d) for c, d in zip(columns, data_to_send)]
        client.publish(topic,'|'.join(payloads))
        if(self.dbg == 1):
            print('published data to topic = {}'.format(topic))
        #print(data_to_send)
        #if(not real_time_send):
        #    sleep(sleep_time_in_s)
        # end send_data_to_platform

    # ==================================================================

    def create_mqtt_client(self, broker, port_nr, client_name, authentication, mqtt_username, mqtt_password, tls_connection):
        # my broker == endpoint of Stephan Wiemann
        if(self.dbg == 1):
            print('create client {}'.format(client_name))
        client = mqtt.Client(client_name)
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        client.on_publish = self.on_publish
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

    def create_mqtt_client2(self, broker, port_nr, client_name, authentication, mqtt_username, mqtt_password, tls_connection):
        if(self.dbg == 1):
            print('DEMO create client {}'.format(client_name))
        client = mqtt.Client(client_name)
        client.on_connect = self.on_connect
        client.on_message = self.on_message2
        #client.on_publish = self.on_publish
        client.on_disconnect = self.on_disconnect
        if(self.dbg == 1):
            print('DEMO connect client2 {} to broker'.format(client_name))
        if(authentication):
            client.username_pw_set(mqtt_username, password=mqtt_password)
            if tls_connection:
                client.tls_set(tls_version=ssl.PROTOCOL_TLSv1_2)
                client.tls_insecure_set(False)
        client.connect(broker, port=port_nr, keepalive=60, bind_address="")  # connect
        return client
        # end create_mqtt_client2

    # ==================================================================

    def subscribe_to_schedule(self, client, apiKey, sensor_name, attributes):
        #apiKey = 'QKAAbMxLbv5TfhFxjTv4lhw92m'
        #sensor_name = 'urn:ngsi-ld:rvk:001'
        #attributes = 'cmd'   # HERE TO DO YET ASK STEPHAN what it was fiware tutorial mqtt
        #topic = "#"
        topic = "/{}/{}/{}".format(apiKey, sensor_name, attributes)
        client.subscribe(topic)  # subscribe
        #client.loop_start()
        if(self.dbg == 1):
            print('subscribed to topic = {}'.format(topic))
        # end subscribe_to_schedule

    # ==================================================================

    def decode_schedule_from_ul_msg(self, message):
        if(self.dbg == 1):
            print('ENTERed decode_schedule_from_ul_msg')
        isvalid = False
        content = False
        msg = str(message.payload.decode("utf-8")).split("|")  # list of strings

        if(self.dbg == 2):
            GG = open("{}/mysched.dat".format(self.dbg_path),"w")
            GG.write(' schedule received from the platform \n')
            GG.write(' {} '.format(msg))
            GG.close()

        sched = {}
        isvalid = False
        time_data = {'valid': False}
        if(self.dbg == 1):
            print('time_data VOR = {}'.format(time_data))
        
        cmd_type = msg[1]
        if(self.dbg == 1):
            print('cmd_type = {}'.format(cmd_type))
        
        if(cmd_type == 'schedule'):
            result_array = []
            times = msg[6::3]  # all time stamps
            flags = msg[7::3]  # all validity flags
            vals = msg[8::3]   # all values of electricity production
            if((len(times)==len(flags))and(len(times)==len(vals))and(len(flags)==len(vals))):
                if(len(times)>0):
                    content = True
                for ii in range(len(times)):
                    out_time = utils.extract_time_stamp_from_string(times[ii])
                    result_array.append({'time_stamp' : out_time, 'activation' : bool(flags[ii]) , 'energy_production_in_W' : float(vals[ii])})
            if((msg[2]=='timestep_in_s') and (msg[4]=='active schedule')):
                sched = {'timestep_in_s': float(msg[3]), 'active schedule': bool(msg[5]), 'values': result_array}
                if(content):
                    isvalid = True
        # end if(cmd_type == 'schedule'):

        elif(cmd_type == 'time_sync'):
            act_time = utils.extract_time_stamp_from_string(msg[7])
            time_data = {'start_time_in_h': float(msg[3]), 'end_time_in_h': float(msg[5]), 'actual_time': act_time, 'valid': True}
        # end elif(cmd_type == 'time_sync'):

        else:
            print('\n\n\n\n received invalid command from platform {}\n\n\n\n'.format(cmd_type))
        #self.control_execute_schedule()
        #return (isvalid, sched)
        if(self.dbg == 1):
            print('time_data NACH = {}'.format(time_data))
        return (cmd_type, isvalid, sched, time_data)
        # end decode_schedule_from_ul_msg

    # ==================================================================

    def on_message(self, client, userdata, message):
        # receives the schedule for rvk - or the times for simulation
        (cmd_type, isvalid, sched, time_data) = self.decode_schedule_from_ul_msg(message)
        #(isvalid, sched) = self.decode_schedule_from_ul_msg(message, placex)
        if(self.dbg == 2):
            print(isvalid, sched)
        if(cmd_type == 'schedule'):   # received the schedule
            if(isvalid):
                self.current_schedule = sched
                self.schedule_changed = True
            else:
                print('received an invalid schedule')
        #end if(cmd_type == 'schedule'):
        
        elif(cmd_type == 'time_sync'):   # received the times for simulation in multi gateway mode without real time operation
            self.time_data = time_data
        # end on_message

    # ==================================================================

    def on_message2(self, client, userdata, message):
        # receives heat production in the given time slot from the demonstrator
        if(self.dbg == 1):
            print('\n\nON MESSAGE 2 \n\n')
        msg = str(message.payload.decode("utf-8")).split("|")  # list of strings
        if(self.dbg == 1):
            print(msg,type(msg))
        time_stamp = utils.extract_time_stamp_from_string(msg[0])
        self.q_in_kW = float(msg[1])
        self.got_demo_data = True
        if(self.dbg == 1):
            print('got {} from demo1 at time {}'.format(self.q_in_kW, time_stamp))
        # end on_message2

    # ==================================================================

    def on_connect(self, client, userdata, flags, rc):
        if(self.dbg == 1):
            print('\n\nON CONNECT\n\n')
        if rc == 0:
            client.connected_flag = True
        else:
            print('Bad connection returned code {}'.format(rc))
            client.loop_stop()

    # ==================================================================

    def on_disconnect(self, client, userdata, rc):
        print('client has disconnected')

    # ==================================================================

    def on_publish(self, client, userdata, message):
        if(self.dbg == 1):
            print(".",  end = '')
        #print("ON PUBLISH {}".format(client))
        #print("received message =", str(message.payload.decode("utf-8")))

    # ==================================================================

    def initialize_components(self, config_file):
        conf_calc = config_file['calculation']
        time_step_in_s = conf_calc['time_step_in_s']     # in seconds
        record_step_in_s = conf_calc['record_step_in_s'] # in seconds
        self.dbg_path = config_file['calculation']['simulation_mode']['dbg_path']
        
        start_sim_inh = conf_calc['simulation_mode']['start_sim_in_hours']  # starting time of the simulation in h
        end_sim_inh = conf_calc['simulation_mode']['end_sim_in_hours']      # end time of the simulation in h
        wetter_file = utils.check_and_open_file(conf_calc['simulation_mode']['weather_file_path'])        # list of strings
        dhw_load_file = utils.check_and_open_file(conf_calc['simulation_mode']['dhw_profile_file_path']) # list of strings
        #el_load_file = utils.check_and_open_file(conf_calc['simulation_mode']['el_load_file_path'])  # list of strings
        el_load_file = 0

        real_time_send = conf_calc['platform_mode']['real_time_send']
        sleep_time_in_s = conf_calc['platform_mode']['sleep_time_in_s']

        sim_flag = conf_calc['mode']
        if(sim_flag == 'simulation'):
            simulation = True
            platform = False
        elif(sim_flag == 'platform'):
            simulation = True
            platform = True
        elif(sim_flag == 'multigw'):
            simulation = False
            platform = True
        else:
            simulation = False
            platform = False
        actual_time = self.initialize_actual_time(real_time_send, start_sim_inh, end_sim_inh)  # time in datetime format
        
        F = open(conf_calc['simulation_mode']['output_file_path'],"w")

        # mqtt
        conf_plat = conf_calc['platform_mode']
        self.mqtt_broker = conf_plat['mqtt_broker']
        self.mqtt_port_nr = conf_plat['mqtt_port_nr']
        self.mqtt_api_key = conf_plat['mqtt_api_key']
        self.mqtt_sensor_name = conf_plat['mqtt_sensor_name']
        self.mqtt_attributes = conf_plat['mqtt_attributes']
        self.mqtt_client_name = conf_plat['mqtt_client_name_attr']
        self.mqtt_commands = conf_plat['mqtt_commands']
        #self.mqtt_client_name_cmd = conf_plat['mqtt_client_name_cmd']

        conf_comp = config_file['components']
        tsm = timestep.timestepmanager(time_step_in_s, conf_comp['timestep_manager']['minimal_timestep_in_s'], actual_time)
        self.tsm = tsm

        chp = self.initialize_chp_unit(conf_comp['chp_unit'], actual_time)
        self.chp = chp
        kessel = self.initialize_gas_boiler(conf_comp['gas_boiler'], actual_time)
        self.boiler = kessel
        tank = self.initialize_storage_tank(conf_comp['storage_tank'], actual_time, tsm, self.dbg_path)
        self.storage_tank = tank
        cvalve = controlvalve.ThreeWayControlValve(conf_comp['control_valve']['initial_hub_position_0_1'])
        heizkurve = self.initialize_heating_curve(conf_comp['heating_curve'])
        self.heizkurve = heizkurve
        # prediction - global and output
        self.prediction_time_step_in_s = config_file['prediction']['prediction_time_step_in_s']
        self.next_prediction_timestamp = actual_time + timedelta(seconds=self.prediction_time_step_in_s)
        self.output_horizon_in_h =  config_file['prediction']['output_horizon_in_h']
        self.output_resolution_in_s =  config_file['prediction']['output_resolution_in_s']
        # sending of monitoring data to the platform
        self.send_intervall_in_s = config_file['calculation']['send_intervall_in_s']
        self.send_intervall_in_s = max(self.send_intervall_in_s, time_step_in_s)  # validity of the data
        self.next_sending_timestamp = actual_time + timedelta(seconds=self.send_intervall_in_s)

        # Martin's code
        conf_pred = config_file['prediction']['heat']
        pred_res_in_s = config_file['prediction']['power']['resolution_in_s']
        powr_conf = config_file['prediction']['power']
        pred = self.initialize_thermal_prediction(config_file)
        predict_thermal.write_init(conf_pred['path_result'])
        #if(platform):
            #crdb_endpoint = config_file['calculation']['platform_mode']['crdb_endpoint']
            #crdb_endpoint_add = config_file['calculation']['platform_mode']['crdb_endpoint_add']
            #crdb_username = config_file['calculation']['platform_mode']['crdb_username']
            #crdb_direct_com = config_file['calculation']['platform_mode']['crdb_direct_com']
            #pred.initialize_crate_db_connection(crdb_endpoint, crdb_endpoint_add, crdb_username, crdb_direct_com)

        # schedule
        self.current_schedule = self.initialize_schedule(actual_time)

        # demonstrator
        demonstrator = conf_calc['demonstrator_mode']['activated']

        # control
        heatc_conf = config_file['components']['heating_curve']

        # multi gateway mode
        multiple_gateways = config_file['calculation']['platform_mode']['multiple_gateways']
        provisioning_endpoint = config_file['calculation']['platform_mode']['provisioning_endpoint']
        #device_id = config_file['calculation']['platform_mode']['mqtt_sensor_name']
        device_id = self.mqtt_sensor_name
        
        # authentication
        authentication = config_file['calculation']['platform_mode']['authentication']['activate']
        mqtt_username = config_file['calculation']['platform_mode']['authentication']['mqtt_username']
        mqtt_password = config_file['calculation']['platform_mode']['authentication']['mqtt_password']
        tls_connection = config_file['calculation']['platform_mode']['authentication']['tls_connection']
        mqtt_topic_attr = "/{}/{}/{}".format(self.mqtt_api_key, device_id, self.mqtt_attributes)

        self.dbg = config_file['calculation']['simulation_mode']['dbg_level']

        return (platform, simulation, time_step_in_s, record_step_in_s, start_sim_inh, end_sim_inh, wetter_file, dhw_load_file, el_load_file, 
         actual_time, F, tsm, tank, chp, kessel, cvalve, heizkurve, pred, real_time_send, sleep_time_in_s, demonstrator, pred_res_in_s, 
         powr_conf, heatc_conf, multiple_gateways, provisioning_endpoint, device_id, authentication, mqtt_username, mqtt_password, tls_connection,
         mqtt_topic_attr)
        
        # end function initialize_components

    # ==================================================================

    def initialize_thermal_prediction(self, config_file):
        """ copyright by Martin Knorr """
        conf_pred = config_file['prediction']['heat']
        conf_powr = config_file['prediction']['power']
        # config_json
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
                  self.output_resolution_in_s, conf_powr, hk_tv, hk_tr, hk_ti, hk_ta, hk_qn, hk_n, hk_m, chp_tmax, gb_tmax, slice_volume, 
                  mstr_chp, mstr_gb, qmax_rod_el, eps_th_chp, eps_el_chp, open_weather_map_active)

    #end initialize_thermal_prediction

    # ==================================================================

    def initialize_schedule(self, actual_time):

        nn = int((self.output_horizon_in_h * 3600.0) // self.output_resolution_in_s)
        if((self.dbg == 1) or (self.dbg == 2)):
            print('\n\n initialize schedule. typ of n = {}; n = {}'.format(type(nn),nn))
        result_array = []
        for ii in range(nn):
            newx = {'time_stamp' : actual_time + timedelta(seconds = self.output_resolution_in_s * ii), 'activation' : False , 'energy_production_in_W' : (np.random.random()*2000.0 - 1000.0)}
            result_array.append(newx)
            #print(newx)
        schedule = {'timestep_in_s' : 900, 'active schedule' : False, 'values' : result_array}
        #print('result_array = {}'.format(result_array))
        #print('schedule = {}'.format(schedule))
        return schedule

    #end initialize_schedule

    # ==================================================================

    def initialize_heating_curve(self, config_json):
        design_ambient_temperature_oC = config_json['design_ambient_temperature_oC']
        design_indoor_temperature_oC = config_json['design_indoor_temperature_oC']
        design_supply_temperature_oC = config_json['design_supply_temperature_oC']
        design_return_temperature_oC = config_json['design_return_temperature_oC']
        radiator_coefficient_n = config_json['radiator_coefficient_n']
        radiator_coefficient_m = config_json['radiator_coefficient_m']
        design_heat_load_in_kW = config_json['design_heat_load_in_kW']
        
        self.tni = design_indoor_temperature_oC
        self.coef = (design_indoor_temperature_oC - design_ambient_temperature_oC) / design_heat_load_in_kW
        
        return heatingcurve.HeatingSystem(design_ambient_temperature_oC, design_indoor_temperature_oC, design_supply_temperature_oC, 
          design_return_temperature_oC, radiator_coefficient_n, radiator_coefficient_m, design_heat_load_in_kW)

    #end initialize_heating_curve

    # ==================================================================

    def initialize_gas_boiler(self, config_json, actual_time):
        thermal_efficiency = config_json['thermal_efficiency']
        max_thermal_power_in_kW = config_json['max_thermal_power_in_kW']
        initial_status_0_1 = config_json['initial_status_0_1']
        min_resting_time_in_s = config_json['min_resting_time_in_s']
        design_input_temperature_oC = config_json['design_input_temperature_oC']
        design_output_temperature_oC = config_json['design_output_temperature_oC']
        design_ambient_temperature_oC = config_json['design_ambient_temperature_oC']

        return gasheater.GasBoiler(thermal_efficiency, max_thermal_power_in_kW, initial_status_0_1, min_resting_time_in_s,
          design_input_temperature_oC, design_output_temperature_oC, design_ambient_temperature_oC, actual_time)

    #end initialize_gas_boiler

    # ==================================================================

    def initialize_chp_unit(self, config_json, actual_time):
        electrical_efficiency = config_json['electrical_efficiency']
        thermal_efficiency = config_json['thermal_efficiency']
        max_electric_power_in_kW = config_json['max_electric_power_in_kW']
        initial_status_0_1 = config_json['initial_status_0_1']
        min_resting_time_in_s = config_json['min_resting_time_in_s']
        design_input_temperature_oC = config_json['design_input_temperature_oC']
        design_output_temperature_oC = config_json['design_output_temperature_oC']
        design_ambient_temperature_oC = config_json['design_ambient_temperature_oC']
        
        return chpunit.ChpUnit(electrical_efficiency,thermal_efficiency,max_electric_power_in_kW,initial_status_0_1,
            min_resting_time_in_s, design_input_temperature_oC, design_output_temperature_oC, design_ambient_temperature_oC, actual_time)

    #end initialize_chp_unit

    # ==================================================================

    def initialize_storage_tank(self, config_json, actual_time, tsm, dbg_path):
        effective_heigth_in_m = config_json['effective_heigth_in_m']
        inner_radius_tank_in_m = config_json['inner_radius_tank_in_m']
        effective_coil_surface_in_m2 = config_json['effective_coil_surface_in_m2']
        effective_coil_volume_in_m3 = config_json['effective_coil_volume_in_m3']
        initial_temperature_in_oC = config_json['initial_temperature_in_oC']
        effective_volume = config_json['effective_volume_in_m3']
        if(initial_temperature_in_oC<(-273.15)):
            t_ini = self.t_initial
        else:
            t_ini = initial_temperature_in_oC
        alpha_losses_in_W_m2K = config_json['alpha_losses_in_W_m2K']
        power_heating_rod_in_kW = config_json['power_heating_rod_in_kW']
        initial_status_heating_rod_0_1 = config_json['initial_status_heating_rod_0_1']
        dbg_level = config_json['dbg_level']
        return storagetank.HeatStorageTank(effective_heigth_in_m, inner_radius_tank_in_m, effective_volume, 
               effective_coil_surface_in_m2, effective_coil_volume_in_m3,
               t_ini, alpha_losses_in_W_m2K, actual_time, power_heating_rod_in_kW,
               initial_status_heating_rod_0_1, tsm, 'implizit', 1, dbg_level, dbg_path) #

    #end initialize_storage_tank

    # ==================================================================

    def save_data_for_prediction(self, pred, act_time_in_h, ambient_temp):
        # Martin's code
        qHeat = self.V_2 * utils.rho_fluid_water(self.t24, self.p_atm, 1) * (self.t25 - self.t24)
        qDHW = self.V_1 * utils.rho_fluid_water(self.t22, self.p_atm, 1) * (self.t21 - self.t22)
        #pred.run_to_save_data(act_time_in_h+2, qHeat + qDHW, ambient_temp)
        pred.run_to_save_data(act_time_in_h, qHeat + qDHW, ambient_temp)
        
#        if (pred.get_q_write()):
#            predict_thermal.write_q(t[index],t_e_1day,q_1day,t_e_2day,q_2day)

    #end save_data_for_prediction

    # ==================================================================

    def free_sched(self):
        # resets the saved data for schedule calculation
        self.tau_end = 0                                 # datetime - end of the current time slot
        self.tau_off = 0                                 # datetime - till this time the self.E_produced_in_kWh will supposedly reach schedule
        self.e_produced_in_kWh = 0                       # double - aggregated production in this time slot
        self.e_to_prod_in_kWh = 0                        # double - envisioned production in this time slot
        self.production = []                             # list of dicts - contains production data for the last timestep
        #self.sched_idx = 0                               # index in list of dicts 
        # end free_sched

    # ==================================================================

    def calc_energy_prod_in_old_step(self, actual_time):
        # returns energy in kWh that has been produced for the time slot in the current schedule
        # during the validity of the old schedule
        # returned value should be mostly zero or close to it - as long as getting updated schedule does not take longer than a time step
        
        # find the \tau_start,new in the saved production data and integrate it up to actual time
        # tau_start _new
        tau_start = self.current_schedule['values'][0]['time_stamp'] - timedelta(seconds=self.output_resolution_in_s)
        Q_old_in_kWh = 0.0
        if (len(self.production) > 0):
            ii = 0
            # find index of the tau_start_new in the saved production
            while(self.production[ii]['time_stamp'] <= tau_start):
                ii += 1
            jj = ii
            
            while(self.production[ii]['time_stamp'] <= actual_time):
                ii += 1
                #Q_chp_el = self.Wh1
                #Q_rod_el = self.Wh2
                #Q_cons_el = self.Wh3 - self.Wh2 - self.Wh1
                #Q_old += Q_chp_el - Q_rod_el - Q_cons_el # = 2*Wh - Wh3 = Wh1 - Wh2 - Wh3 + Wh2 + Wh1 
                #Q_old += self.production[]
                Q_old_in_kWh = Q_old_in_kWh + self.production[ii]['Q_in_kWh']
        return Q_old_in_kWh
        # end calc_energy_prod_in_old_step

    # ==================================================================

    def get_val_from_sched(self, sched, actual_time):
        result_array = sched['values']
        ii = 0
        # find the position of actual_time in the current schedule
        while(result_array[ii]['time_stamp'] <= actual_time):
            ii += 1
        # return the data 
        valid_time = result_array[ii]['time_stamp']
        set_point_val = result_array[ii]['energy_production_in_W']
        is_active = result_array[ii]['activation']
        return (ii, valid_time, is_active, set_point_val)
        # end get_val_from_sched

    # ==================================================================

    def check_validity_of_sched(self, actual_time):
        # returns :
        # - index of the scheduled timeslot in the current valid schedule
        # - time stamp marking the end of the scheduled timeslot in datetime format
        # - the flag declaring whether the scheduled value is valid (True)
        # - the value of average electrical power to be produced within the scheduled time slot in W
        # if flag is True, the returned value might differ from zero W

        # is the whole schedule active?
        c1 = self.current_schedule['active schedule']
        # is the current schedule not outdated, i.e. is the last time stamp of schedule still biggeer than the actual time?
        values = self.current_schedule['values']
        c2 = (actual_time <= values[-1]['time_stamp'])

        if(c1 and c2):
            
            # time stamps in the schedule have to be ordered and monotonously growing
            ii = 0
            while (values[ii]['time_stamp'] < actual_time):
                ii = ii + 1
            
            # values to be returned
            valid_time = values[ii]['time_stamp']
            is_active = values[ii]['activation']
            value_in_W = values[ii]['energy_production_in_W']
        else:
            # either whole schedule is invalid or it is outdated
            ii = 0
            valid_time = actual_time - timedelta(seconds=10)
            is_active = False
            value_in_W = 0.0

        return (ii, valid_time, is_active, value_in_W)
        # end check_validity_of_sched

    # ==================================================================

    def check_feasibility_of_sched(self, actual_time):
        # returns True when the production/consumption can be attained
        # otherwise returns False
        prec_kWh = 0.0    # precision for the conditions, 0 means no errors are allowed
        is_valid = True   # result, first assumption

        q_netto_el_kWh = self.e_to_prod_in_kWh - self.e_produced_in_kWh # amount of energy left to produce
        t_netto_s = (self.tau_end - actual_time).seconds                # time left for production process

        # The installed electric power: for production and usage
        q_el_prod_kWh = self.chp.get_design_electric_output() * t_netto_s / 3600.0         # kWh = kW * s *h/3600s
        q_el_use_kWh =  self.storage_tank.get_max_thermal_rod_power() * t_netto_s / 3600.0 # kWh = kW * s *h/3600s


        # installed power:
        # is the installed electric power enough to cover the demand?
        # case 1: energy should be produced - is there enough time for the system to provide it based on the installed power?
        if((q_netto_el_kWh > 0.0) and (q_netto_el_kWh > q_el_prod_kWh + prec_kWh)):
            is_valid = False   # more energy should be PRODUCED than the installed power allows

        # case 2: energy should be consumed - is there enough time for the system to take it up based on the installed power?
        if((q_netto_el_kWh < 0.0) and (abs(q_netto_el_kWh) > q_el_use_kWh + prec_kWh)):
            is_valid = False   # more energy should be CONSUMED than the installed power allows

        # Sperrzeiten:
        # case 1: energy should be produced - is there enough time to produce it when the Sperrzeiten are taken into account?
        # can the installed power be used due to the minimal inactivation times
        if((q_netto_el_kWh > 0.0) and (not self.chp.get_status()) and (self.chp.get_next_safe_turn_on_time() > actual_time)):
        # produce el AND chp is off AND chp cannot be yet turned on
            t_left_s = (self.tau_end - self.chp.get_next_safe_turn_on_time()).seconds

            # check if there is any time left at all
            if(t_left_s < 0):
                is_valid = False   # there will be NO TIME LEFT to produce the required energy - due to minimal rest time of CHP unit
            
            # check if the time is enough to cover the demand with the installed power of CHP
            # expected production from the installed power of CHP:
            q_left_kWh = self.chp.get_design_electric_output() * t_left_s / 3600.0  # kWh = kW * s * h/s
            if(q_netto_el_kWh > q_left_kWh + prec_kWh):
                is_valid = False   # there will be NO TIME LEFT to produce the required energy - due to minimal rest time of CHP unit AND due to installed power

        # can the installed power be used due to the inactivation times defined by the network operator
        (is_relevant, ts, te, delta) = self.time_interval_intersects_sperrzeiten(actual_time, self.tau_end)
        q_left_kWh = self.chp.get_design_electric_output() * delta.seconds / 3600.0  # kWh = kW * s * h/s
        if ((is_relevant) and (q_netto_el_kWh > q_left_kWh + prec_kWh)):           # 
            print('X : throw exception: the schedule is not feasible due to Sperrzeiten')
            is_valid = False

        # determine heat produced due to the electricity production/consumption that has to be stored in the storage tank in kWh
        if(q_netto_el_kWh > 0.0):
            Q_th_kWh = self.chp.get_el_prod_kWh(q_netto_el_kWh)  # heat is produced by the CHP unit
        elif(q_netto_el_kWh < 0.0):
            Q_th_kWh = self.chp.get_design_electric_output() * t_netto_s / 3600.0  # heat is produced by the heating rod placed in the storage tank

        # how much heat can be stored in the storage tank?
        last_t_profile = self.storage_tank.output_temperatures()  # get temperature proil in the staorage tank
        tmax = self.chp.get_max_temp_of_chp()                     # get maximal temperature that is to be expected from CHP unit
        Q_pot_in_kWh = self.thermal_energy_that_can_be_put_in_storage(tmax, last_t_profile) # how much energy can be stored in (put into) storage tank

        # can the heat produced due to electricity production/consumption be accomodated in the storage tank?
        if(Q_th_kWh > Q_pot_in_kWh):
            is_valid = False  # storage tank cannot take up enough heat

        return is_valid
        # end check_feasibility_of_sched

    # ==================================================================
    def thermal_energy_that_can_be_put_in_storage(self, tmax, temp_profil):
        # returns thermal energy in kWh that can be still put into storage tank
        # tmax - maximal temperature of the storage tank in °C
        # return self.rvk.get_energy_left_to_tmax(tmax)
        # copied from storage_tank.calc_energy_left_to_tmax(self, tmax):
        # only values below tmax are integrated
        p_in_MPa = utils.get_pressure_in_MPa()
        calc_option = utils.get_calc_option()
        cpmax = utils.cp_fluid_water(tmax, p_in_MPa, calc_option)
        wyn = 0.0
        # Q in kWh = Dt * cp * V_i * rho_i  [ K * J/kg/K * m3 * kg/m3 * h/3600s * 1kW/1000W = kWh]
        for tx in temp_profil:
            cpx = utils.cp_fluid_water(tx, p_in_MPa, calc_option)
            rox = utils.rho_fluid_water(tx, p_in_MPa, calc_option)
            if(tmax >= tx):
                wyn = wyn + (tmax * cpmax - tx * cpx) * self.slice_volume * rox / (3600.0 * 1000.0)
        return wyn
        # end thermal_energy_that_can_be_put_in_storage

    # ==================================================================

    def thermal_energy_that_can_be_got_from_storage(self, tmin, temp_profil):
        # returns thermal energy in kWh that can be still put into storage tank
        # tmax - maximal temperature of the storage tank in °C
        # copied from storage_tank.calc_energy_above_tmin
        # only values above tmin are integrated
        p_in_MPa = utils.get_pressure_in_MPa()
        calc_option = utils.get_calc_option()
        cpmin = utils.cp_fluid_water(tmin, p_in_MPa, calc_option)
        wyn = 0.0
        # Q in kWh = Dt * cp * V_i * rho_i  [ K * J/kg/K * m3 * kg/m3 * h/3600s * 1kW/1000W = kWh]
        for tx in temp_profil:
            cpx = utils.cp_fluid_water(tx, p_in_MPa, calc_option)
            rox = utils.rho_fluid_water(tx, p_in_MPa, calc_option)
            if(tx >= tmin):
                wyn = wyn + (tx * cpx - tmin * cpmin) * self.slice_volume * rox / (3600.0 * 1000.0)
        return wyn
        # end thermal_energy_that_can_be_got_from_storage

    # ==================================================================

    def time_interval_intersects_sperrzeiten(self, t_start, t_end):
        # default results
        delta = t_end - t_start
        wyn = (False, t_start, t_end, delta)

        ts = t_start.time()   # ts is t_start in time format
        te = t_end.time()   # te is t_end in time format

        # is the Sperrzeiten are consistently defined
        if(self.sp_active):
            if(len(self.sp_start) == len(self.sp_end)):
                # check all Sperrzeiten for intersection
                for ii in range(self.sp_start):
                    tsi = utils.extract_hms_time_from_string(self.sp_start[ii])   # tsi is sp_start in time format
                    tei = utils.extract_hms_time_from_string(self.sp_end[ii])   # tse is sp_end in time format
                    if(not(((ts < tsi) and (te <= tsi)) or ((ts >= tei) and (te > tei)))):  # interval's borders are not outside of the Sperrzeit
                        if((ts >= tsi) and (ts < tei) and (te > tsi) and (te <= tei)):   # both start and end time false ==> within the Sperrzeit
                            te = ts   # no usable time in the interval - times become irrelevant
                            delta = te - ts
                        elif((ts >= tsi) and (ts < tei)):   # start time false ==> within the Sperrzeit
                            ts = tei
                            delta = te - ts
                        elif((te > tsi) and (te <= tei)):   # end time false ==> within the Sperrzeit
                            te = tsi
                            delta = te - ts
                        else:   # both times correct, Sperrzeit lies within the time interval- choose first possible intervall
                            #delta = (te - ts) - (tei - tsi)
                            delta = te - tei + tsi - ts
                            te = tsi   # ts remains unchanged
                        tswyn = t_start.replace(hour=ts.hour, minute=ts.minute, second = ts.second, microsecond=ts.microsecond)
                        tewyn = t_end.replace(hour=te.hour, minute=te.minute, second = te.second, microsecond=te.microsecond)
                        wyn = (True, tswyn, tewyn, delta)
            # end if(len(self.sp_start) == len(self.sp_end)):

            else:
                print('throw exception - Sperrzeiten sind falsch definiert')
            # end if(len(self.sp_start) == len(self.sp_end)): else:

        # end if(self.sp_active):

        # returns flag and first possible time interval in datetime format
        # end time_interval_intersects_sperrzeiten
        return wyn

    # ==================================================================

    def get_electricity_consumption_of_timestep_kWh(self, time_step_in_s, pred_res_in_s):
        # self.electricity_consumption_kWh - predicted electricity consumption within the time slot pred_res_in_s
        # time_step_in_s - length of the time step in seconds
        # pred_res_in_s - length of the time slot of prediction in seconds

        # return electricity consumption within the time step in kWh
        # kW = kWh * s/h / s 
        return self.electricity_consumption_kWh * time_step_in_s / pred_res_in_s
        # end get_electricity_consumption_of_timestep_kWh

    # ==================================================================

    def calc_el_cons_other(self, actual_time, powr_conf):
        type_of_prediction = powr_conf['type_of_prediction']
        if(type_of_prediction == 'SLP'):
            el_data = powr_conf['SLP']
            pred_res_in_s = powr_conf['resolution_in_s']
            data_set = utils.get_slp_data_set(actual_time, el_data, pred_res_in_s)
            # first element of the data_set is relevant for actual_time
            # returns value in kWh that represents the whole time slot of length pred_res_in_s
            # kWh = kW * s * h/3600s
            return data_set[0] * pred_res_in_s / 3600.0
        # end calc_el_cons_other

    # ==================================================================

    def control_execute_schedule(self, actual_time):
        # this procedure updates the current schedule when new data is received from the platform
        # it also sets the flags for the control mode (self.keep_chp_on and self.keep_chp_off) for an active schedule
        # the control algorithm that executes the schedule is to be found in procedure self.control_internal_1
        # This algorithm uses the flags set here to control all apliances
        sched = self.current_schedule  # get abbreviated name for better readability

        # check the change of schedule
        if(self.schedule_changed):
            Q_old_in_kWh = self.calc_energy_prod_in_old_step(actual_time)
            self.free_sched() # reset the schedule's history
            self.e_produced_in_kWh = Q_old_in_kWh
            self.schedule_changed = False
            self.tau_end = self.current_schedule['values'][0]['time_stamp']
            if(self.dbg == 2):
                print('end_tau = {}'.format(self.tau_end))

        # check the validity of the schedule in the given time step == actual_time
        (sch_idx, self.tau_end, is_active, value_in_W) = self.check_validity_of_sched(actual_time)

        # if schedule is active, set control flags for its execution
        if(is_active):
            # energy that is to be produced
            self.e_to_prod_in_kWh = value_in_W * self.output_resolution_in_s / 3600000.0  # in kWh = W * s * h/3600s * kW/1000W

            # check the feasibility of the schedule - is there enough time left to produce the requred energy 
            is_feasible = self.check_feasibility_of_sched(actual_time)
            if(not is_feasible):
                # send message to platform, that problems with schedule execution might arise 
                print('schedule value is infeasible')
            # execute the schedule
            if((self.e_to_prod_in_kWh<0.0) and(self.e_to_prod_in_kWh<self.e_produced_in_kWh)):
                # activate the consumer of electricity
                #self.rod_stat = self.storage_tank.get_max_thermal_rod_power() * self.tsm.get_timestep()
                self.chp.turn_off()    # turn on CHP if it is off
                self.rod_stat = 1.0    # power usage form 0 to 1; 0 is no power, 1 is full power.
                self.keep_chp_on = False
                self.keep_chp_off = True
            if((self.e_to_prod_in_kWh>0.0) and (self.e_to_prod_in_kWh>self.e_produced_in_kWh)):
                self.chp.turn_on()     # turn on CHP if it is off
                self.rod_stat = 0.0    # power usage form 0 to 1; 0 is no power, 1 is full power.
                self.keep_chp_on = True
                self.keep_chp_off = False
        else:
            self.rod_stat = 0.0
    #end control_execute_schedule

    # ==================================================================

    def update_electricity_production_status(self, time_step_in_s, pred_res_in_s):
            
        # update the production
        # electricity consumption of the building (= others) in kWh in this time step
        Q_cons_el_kWh = self.get_electricity_consumption_of_timestep_kWh(time_step_in_s, pred_res_in_s)
        # electricity production by the CHP unit in kWh in this time step
        Q_chp_el = self.chp.get_el_prod() * time_step_in_s / 3600.0  # kWh = kW * s * h/3600s
        # electricity consumption by the heating rod in the storage tank in kWh in this time step
        Q_rod_el = self.rod_stat * self.get_max_thermal_rod_power() * time_step_in_s / 3600.0  # kWh = kW * s * h/3600s
        # balance of the produced and used electrical energy in kWh
        delta_q_kWh = Q_chp_el - Q_rod_el - Q_cons_el_kWh
        # 
        self.e_produced_in_kWh = self.e_produced_in_kWh + delta_q_kWh
        self.e_to_prod_in_kWh = self.e_to_prod_in_kWh - delta_q_kWh
    # edn update_electricity_production_status

    # ==================================================================

    def condition_heating_1(self, t_a, t23, t25):
        # turn on all sources because sotrage tank has too low temperature to provide heat
        wyn = False
        if(t_a <= 15.0):       # heating period
            if(t23 < t25):     # tank water too cold to heat the building
                wyn = True
        return wyn
        # end condition_heating_1

    # ==================================================================

    def condition_heating_2(self, t2, t3, t21):
        # turn off all sources - because stoarge tank is loaded up
        wyn = False
        if((self.t2 > 45.0) or (self.t3 > 60.0)):       # storage tank is filled up with hot water
            if(t21 > 45.0):                             # DHW is warm enough
                wyn = True
        return wyn
        # end condition_heating_2
            

    # ==================================================================

    def condition_heating_3(self, t7, t21):
        # turn off only the gas boiler because storage tank is partially filled
        wyn = False
        if(t7 > 45.0):           # storage tank is partially filled
            if(t21 > 45.0):                             # DHW is warm enough
                wyn = True
        return wyn
        # end condition_heating_3

    # ==================================================================

    def ctrl_cond_heating_period(self):
        # heating period starts when ambient temperature is lower than 15.0 (= self.temp_a_hp)
        if(self.t30 <= self.temp_a_hp):
            return True
        else:
            return False
        # end ctrl_cond_heating_period

    # ==================================================================

    def ctrl_cond_dhw_warm_enough(self):
        # domestic hot water is warm enough when it is warmer than 55,0 grad Celcius (= self.temp_dhw)
        if(self.t21 >= self.temp_dhw):
            return True
        else:
            return False
        # end ctrl_cond_dhw_warm_enough

    # ==================================================================

    def ctrl_cond_storage_empty(self):
        # sorage tank is empty 
        # - if the temperature in its highest point is lower than the temperature required by the heating system
        # - if the temperature in its second highest point is lower than the threshold temperature of self.temp_warm
        # in the heating period the system has to be able to provide heat for heating system
        c1 = (self.t20 < self.t25) and self.ctrl_cond_heating_period()
        c2 = (self.t23 < self.t25) and self.ctrl_cond_heating_period()
        # at all times the system has to be able to provide hot water for dhw preparation
        c3 = (self.t19 < self.temp_warm) or (self.t20 < self.temp_warm)
        c4 = (self.t18 < self.temp_dhw) or (self.t19 < self.temp_dhw) or (self.t20 < self.temp_dhw)
        if(c1 or c2 or c3 or c4):
            return True
        else:
            return False
        # end ctrl_cond_storage_empty

    # ==================================================================

    def ctrl_cond_storage_full(self):
        # storage tank is full 
        # - when the temperature in its second lowest point is higher than threshold temperature of self.temp_warm
        # - when the temperature in its third lowest point is higher than threshold temperature of self.temp_hot
        if((self.t2 >= self.temp_warm) or (self.t3 >= self.temp_hot)):
            return True
        else:
            return False
        # end ctrl_cond_storage_full

    # ==================================================================

    def ctrl_cond_storage_almost_empty(self):
        # storage tank is almost empty 
        # - when heating water temperature in its fourth highest point is lower than the temperature required by the heating system
        c1 = (self.t17 < self.t25) and self.ctrl_cond_heating_period()
        # - when heating water temperature in its fourth highest point is lower than the temperature self.temp_warm
        c2 = (self.t17 < self.temp_warm)
        # - when heating water temperature in its fourth highest point is lower than the temperature self.temp_dhw
        c3 = (self.t17 < self.temp_dhw)
        if(c1 or c2 or c3):
            return True
        else:
            return False
        # end ctrl_cond_storage_almost_empty

    # ==================================================================

    def ctrl_cond_storage_almost_full(self):
        # storage tank is almost full
        # - when heating water temperature in its fourth lowest point is higher than or equal to self.temp_hot
        if(self.t4 >= self.temp_hot):
            return True
        else:
            return False
        # end ctrl_cond_storage_almost_full

    # ==================================================================

    def control_internal_1(self, heizkurve, kessel, chp, cvalve, t_a, actual_time, m4, heatc_conf):
        # --------------------------------------------------------------
        # HEATING PERIOD DETECTION
        if(self.ctrl_cond_heating_period()):            # heating period
            heizkurve.turn_on(t_a)
        else:
            heizkurve.turn_off()

        self.too_cold = 0
        self.V_2 = heizkurve.get_volume_flow()
        # ..............................................................
        # mass flow 
        m25 = utils.rho_fluid_water(self.t24, self.p_atm, 1) * self.V_2  # mass flow in heating circuit in kg/s
        #print('time = {}; type t23 = {}; type t25 = {}'.format(actual_time, type(self.t23), type(self.t25)))

        #chp_stat = 0 # status of chp unit 
        #gb_stat = 0  # status of gas boiler
        #hr_stat = 0  # status of electric heating rod in the storage tank

        # --------------------------------------------------------------
        # consistency check - DO NOT PRODUCE AND CONSUME ELECTRICITY AT THE SAME TIME - NO PRODUCTION FOR OWN USAGE
        if(self.keep_chp_off and self.keep_chp_on):  # both cannot be true at the same time
            self.keep_chp_off = False
            self.keep_chp_on = False

        # --------------------------------------------------------------
        # STATE OF THE STORAGE TANK
        # ..............................................................
        # state 1 = storage tank is too cold
        if(self.ctrl_cond_storage_empty()):
            self.tank_state = 1
            self.too_cold = 1
            # return temperature from the heating system - potentially to be overwritten
            self.t24 = self.calc_ret_temp_when_cold(heatc_conf, self.t30, m25, self.t20)
            # storage tank is empty, turn all possible heat sources on
            #..................................
                # TURN ON gas boiler
            gb_stat = 1
            #..................................
                # TURN ON chp unit
            chp_stat = 1
            
            if(self.keep_chp_off):   # consume electricity
                hr_stat = 1
            elif(self.keep_chp_on):   # produce as much electricity as possible
                hr_stat = 0
            else:
                hr_stat = 0
            self.unload = False
        # ..............................................................
        # state 2 = storage tank is almost empty
        elif(self.ctrl_cond_storage_almost_empty()):
            self.tank_state = 2
            # turn on additional heat source if its not already on
            if(self.keep_chp_on):      # produce electricity
                # two first cases concern for unloading
                if((chp.get_status() == 1) and (kessel.get_status() == 0)):
                    # CHP unit is already on, only gas heater can be turned on
                    #..................................
                        # TURN ON gas boiler
                    gb_stat = 1
                    chp_stat = 1
                elif((chp.get_status() == 0) and (kessel.get_status() == 1)):
                    gb_stat = 1
                    chp_stat = 1
                else:                       # when it's actually loading - leave everything as it is
                    if(chp.get_status() == 0):
                        chp_stat = 0
                    else:
                        chp_stat = 1
                    if(kessel.get_status() == 0):
                        gb_stat = 0
                    else:
                        gb_stat = 1
                hr_stat = 0
                
            elif(self.keep_chp_off):   # consume electricity
                # two first cases concern for unloading
                if((chp.get_status() == 1) and (kessel.get_status() == 0)):
                    gb_stat = 1
                    chp_stat = 1
                elif((chp.get_status() == 0) and (kessel.get_status() == 1)):
                    gb_stat = 1
                    if(self.ctrl_option == 1): # 1 - be conservative and do not allow the tank to unload completely ==> no risk of not reaching room temperature
                        chp_stat = 1
                    elif(self.ctrl_option == 2): # 2 - allow the storage tank to become fully unloaded ==> risk of not reaching the room temperature
                        chp_stat = 0
                else:                       # when it's actually loading - leave everything as it is
                    if(chp.get_status() == 0):
                        chp_stat = 0
                    else:
                        chp_stat = 1
                    if(kessel.get_status() == 0):
                        gb_stat = 0
                    else:
                        gb_stat = 1
                hr_stat = 1
            else:                      # no schedule interference - use only chp unit and gas boiler
                # two first cases concern for unloading
                if((chp.get_status() == 1) and (kessel.get_status() == 0)):
                    gb_stat = 1
                    chp_stat = 1
                elif((chp.get_status() == 0) and (kessel.get_status() == 1)):
                    chp_stat = 1
                    gb_stat = 1
                else:                       # when it's actually loading - leave everything as it is
                    if(chp.get_status() == 0):
                        chp_stat = 0
                    else:
                        chp_stat = 1
                    if(kessel.get_status() == 0):
                        gb_stat = 0
                    else:
                        gb_stat = 1
                hr_stat = 0
            self.unload = False
        # ..............................................................
        # state 3 = storage tank is almost full
        elif(self.ctrl_cond_storage_almost_full()):
            self.tank_state = 4
            # keep only one of the heat sources on depending on their actual status and constraints of the schedule
            if(self.unload):     # leave everything as it is
                    if(chp.get_status() == 0):
                        chp_stat = 0
                    else:
                        chp_stat = 1
                    if(kessel.get_status() == 0):
                        gb_stat = 0
                    else:
                        gb_stat = 1
            else:
                if(self.keep_chp_on):      # produce electricity
                    chp_stat = 1
                    gb_stat = 0
                    hr_stat = 0
                elif(self.keep_chp_off):   # consume electricity
                    chp_stat = 0
                    gb_stat = 0
                    hr_stat = 1
                else:                      # no schedule interference - use only chp unit and gas boiler
                    chp_stat = 1
                    gb_stat = 0
                    hr_stat = 0
            
        # ..............................................................
        # state 4 = storage tank is full
        elif(self.ctrl_cond_storage_full()):
            self.tank_state = 5
            # tank is full, turn off all possible heat sources
            chp_stat = 0
            gb_stat = 0
            hr_stat = 0
            hr_stat = 0
            self.unload = True
        # ..............................................................
        # state 5 = storage tank is being loaded/unloaded and the border of high and low temperatures is somewhere in the middle
        else:
            self.tank_state = 3

            if(self.keep_chp_on):      # produce electricity
                if(chp.get_status() == 0):     # turn it on 
                    chp_stat = 1
                else:
                    chp_stat = 1
                if(kessel.get_status() == 1):  # keep it as it is
                    gb_stat = 1
                else:
                    gb_stat = 0
                if(self.rod_stat > 0.0):       # turn it off
                    hr_stat = 0
                else:
                    hr_stat = 0
            
            elif(self.keep_chp_off):   # consume electricity
                if(chp.get_status() == 0):     # turn it off
                    chp_stat = 0
                else:
                    chp_stat = 0
                if(kessel.get_status() == 1):  # keep it as it is
                    gb_stat = 1
                else:
                    gb_stat = 0
                if(self.rod_stat > 0.0):       # turn it on
                    hr_stat = 1
                else:
                    hr_stat = 1
            
            else:                      # no schedule interference - use only chp unit and gas boiler
                if(chp.get_status() == 0):     # keep it as it is
                    chp_stat = 0
                else:
                    chp_stat = 1
                if(kessel.get_status() == 1):  # keep it as it is
                    gb_stat = 1
                else:
                    gb_stat = 0
                if(self.rod_stat > 0.0):       # turn it off
                    hr_stat = 0
                else:
                    hr_stat = 0
                
        # --------------------------------------------------------------
        # DOMESTIC HOT WATER PREPARATION
        # domestic hot water priority
        if(not self.ctrl_cond_dhw_warm_enough()):
            self.dhw_prod = 1
            # temperature of dhw has to be kept at all times regardless of the state of storage tank and occurence of heating period

            if(self.keep_chp_off):   # use up electricity
                if((kessel.get_status() == 0) or (gb_stat == 0)):
                    gb_stat = 1  # turn on gas boiler if it is off
                if((self.rod_stat == 0) or (self.rod_stat < 1.0) or (hr_stat == 0) or (hr_stat < 1.0)):
                    hr_stat = 1  # turn on electric heater if it is off and gas boiler is not enough to heat up the dhw
                else:
                    chp_stat = 1 # turn on chp unit if other measures do not suffice

            elif(self.keep_chp_on):  # produce electricity
                if((chp.get_status() == 0) or (chp_stat == 0)):
                    chp_stat = 1 # turn on chp unit if it is off
                if((kessel.get_status() == 0) or (gb_stat == 0)):
                    gb_stat = 1  # turn on gas boiler if it is off
                else:
                    hr_stat = 1  # turn on electric heater if it is off and other sources are not up to the task
                
            else:                    # no schedule interference - use only chp unit and gas boiler
                if((chp.get_status() == 0) or (chp_stat == 0)):
                    chp_stat = 1 # turn on chp unit if it is off
                if((kessel.get_status() == 0) or (gb_stat == 0)):
                    gb_stat = 1  # turn on gas boiler if it is off
        else:
            self.dhw_prod = 0
        #print('chp = {}, bg = {}, hr = {}'.format(chp.get_status(), kessel.get_status(), self.rod_stat))
        # --------------------------------------------------------------
        # APPLY THE SETTINGS
        # chp unit
        if(chp_stat == 0):
            wyn = chp.turn_off(actual_time)
        elif(chp_stat == 1):
            if(chp.get_status() == 0):
                #..................................
                    # TURN ON chp unit
                wyn = chp.turn_on(actual_time, self.t27)  # turn the chp unit on
                if (wyn[0] == False):
                    #H.write('Could not turn CHP unit on at time = {}. Time left to the next turn on = {} s. t23 < t25\n'.format(actual_time,wyn[4].seconds))
                    if(self.dbg != 3):
                        print('Could not turn CHP unit on at time = {}. Time left to the next turn on = {} s. t23 < t25'.format(actual_time,wyn[4].seconds))
            else:
                wyn = chp.get_chp()
        #print('TOO COLD, chp is off, t26 = {}; wyn[2] = {}; stat chp = {}; stat boiler = {}'.format(self.t26,wyn[2],chp.get_status(),kessel.get_status()))
        #print('chp.get_stat = {}; wyn = {}'.format(chp.get_status(), wyn))
        self.t26 = wyn[2]
        #self.t27 = wyn[1]
        chp.set_inp_temp(self.t27)               # temperature incoming from tank to chp
        m3 = wyn[3]
        self.V_3 = m3 / utils.rho_fluid_water(self.t26, self.p_atm, 1) # in m3/s = kg/s / kg/m3
            

        # gas boiler
        if(gb_stat == 0):
            wyn = kessel.turn_off(actual_time)
        elif(gb_stat == 1):
            if(kessel.get_status() == 0):
                #..................................
                    # TURN ON gas boiler
                wyn = kessel.turn_on(actual_time)  # turn the gas boiler on
                if (wyn[0] == False):
                    #H.write('Could not turn gas boiler on at time = {}. Time left to the next turn on = {} s. t23 < t25\n'.format(actual_time,wyn[4].seconds))
                    if(self.dbg != 3):
                        print('Could not turn gas boiler on at time = {}. Time left to the next turn on = {} s. t23 < t25'.format(actual_time,wyn[4].seconds))
            else:
                wyn = kessel.get_kessel()
        #print('t28 = {}; wyn[2] = {}'.format(self.t28,wyn[2]))
        self.t28 = wyn[2]
        #self.t29 = wyn[1]
        kessel.set_inp_temp(self.t29)
        m4 = wyn[3]
        self.V_4 = m4 / utils.rho_fluid_water(self.t29, self.p_atm, 1) # in m3/s = kg/s / kg/m3

        # heating rod in the storage tank
        if(hr_stat == 0):
            self.rod_stat = 0.0
        elif(hr_stat == 1):
            self.rod_stat = 1.0
        else:
            self.rod_stat = hr_stat

        # --------------------------------------------------------------
        # CALCULATE THE OUTPUTS: return (m23, m25, m4)
        cp25 = utils.cp_fluid_water(self.t25, self.p_atm, 1)
        cp24 = utils.cp_fluid_water(self.t24, self.p_atm, 1)
        cp23 = utils.cp_fluid_water(self.t23, self.p_atm, 1)
        if((self.t23 * cp23 - self.t24 * cp24) != 0.0):
            #        m23 + m_bypass = m25  ==> m_bypass = m25 - m23
            #        t23 * cp23 * m23 + t24 * cp24 * m_bypass = t25 * cp25 * m25
            #        t23 * cp23 * m23 + t24 * cp24 * (m25 - m23) = t25 * cp25 * m25
            #        m23 * (t23 * cp23 - t24 * cp24) = m25 * (t25 * cp25 - t24 * cp24)
            m23 = m25 * (self.t25 * cp25 - self.t24 * cp24) / (self.t23 * cp23 - self.t24 * cp24)
        else:
            m23 = 0.0
        if(m25 != 0.0):
            cvalve.set_hub(m23 / m25)
        #        t25 = (t23 * cp23 + m_bypass * cp24) / (m25 * cp24)
        else:
            m23 = 0.0
            cvalve.set_hub(0.0)
        
        return (m23, m25, m4)

    #end control_internal_1

    # ==================================================================

    def control_internal_2(self, chp, kessel, actual_time, m4):
        # controls - turn all off when the tank is fully loaded
        #if(str(type(self.t2))!="<class 'float'>"):
            #print('actual_time = {}; t2 = {}; t3 = {}'.format(actual_time, self.t2, self.t3))
        #if((self.t2 > 45.0) or (self.t3 > 60.0)):
        if(self.condition_heating_2(self.t2, self.t3, self.t21)):    # storage tank is loaded up - heat sources can be turned off
            if(chp.get_status() == 1):                   # turn off CHP unit only if it is on in the first place
                if((not self.keep_chp_on) or (self.keep_chp_on and kessel.get_status() == 0)):  # only when it's ok or the gas boiler is already off
                    wyn = chp.turn_off(actual_time)
                    self.t26 = wyn[2]
                    self.t27 = wyn[1]
                    m3 = wyn[3]
                    self.V_3 = m3 / utils.rho_fluid_water(self.t26, self.p_atm, 1) # in m3/s = kg/s / kg/m3
            if(kessel.get_status() == 1):
                wyn = kessel.turn_off(actual_time)
                self.t28 = wyn[2]
                self.t29 = wyn[1]
                m4 = wyn[3]
                self.V_4 = m4 / utils.rho_fluid_water(self.t28, self.p_atm, 1) # in m3/s = kg/s / kg/m3
            #print('t2>45||t3>60, turn OFF, chp = {}, kessel = {}'.format(chp.get_status(),kessel.get_status()))
        # controls - turn the gas heater off when the tank is more than half loaded
        #if(self.t7 > 45.0):
        if(self.condition_heating_3(self.t7, self.t21)):    # storage tank is partially filled, so that some heat sources can be turned off
            if(kessel.get_status() == 1):
                wyn = kessel.turn_off(actual_time)
                self.t28 = wyn[2]
                self.t29 = wyn[1]
                m4 = wyn[3]
                self.V_4 = m4 / utils.rho_fluid_water(self.t28, self.p_atm, 1) # in m3/s = kg/s / kg/m3
            #print('t7>45, turn OFF,  chp = {}, kessel = {}'.format(chp.get_status(),kessel.get_status()))
        # ..............................................................
        # 
        # 
        # storage tank
       #tank.calc_dhw_heat_exchange(time_step_in_s, t_in_dw , t_out_dw, mstr_dhw)
        # controls - turn on the chp unit and heater if the temperature of domestic hot water is too low
        if self.t21 < 45.0:
            # CHP unit is running already, or it should run as late as possible due to the demands of the schedule
            if ((chp.get_status()) or (self.keep_chp_off)):
                wyn = kessel.turn_on(actual_time)
                if (wyn[0] == False):
                    #H.write('Could not turn gas boiler on at time = {}. Time left to the next turn on = {} s. t21 < 45\n'.format(actual_time,wyn[4].seconds))
                    if(self.dbg != 3):
                        print('Could not turn gas boiler on at time = {}. Time left to the next turn on = {} s. t21 < 45'.format(actual_time,wyn[4].seconds))
                self.t28 = wyn[2]
                self.t29 = wyn[1]
                m4 = wyn[3]
                self.V_4 = m4 / utils.rho_fluid_water(self.t29, self.p_atm, 1) # in m3/s = kg/s / kg/m3
            #elif((self.keep_chp_off and (kessel.get_status())) or ()):   # 
            else:
                wyn = chp.turn_on(actual_time, self.t27)
                self.t26 = wyn[2]
                self.t27 = wyn[1]
                m3 = wyn[3]
                if (wyn[0] == False):
                    #H.write('Could not turn CHP on at time = {}. Time left to the next turn on = {} s. t21 < 45\n'.format(actual_time,wyn[4].seconds))
                    if(self.dbg != 3):
                        print('Could not turn CHP on at time = {}. Time left to the next turn on = {} s. t21 < 45'.format(actual_time,wyn[4].seconds))
                self.V_3 = m3 / utils.rho_fluid_water(self.t26, self.p_atm, 1) # in m3/s = kg/s / kg/m3
            #print('t21<45, turn ON, chp = {}, kessel = {}'.format(chp.get_status(),kessel.get_status()))
        elif self.t21 > 85.0:
            if(self.dbg != 3):
                print('alarm dhw too hot t = {}'.format(self.t21))
            #if(self.t21 > 85.0):
                #quit()
        
        
        #print('cond heat on = {}; cond 2 heat on = {}; cond 1 OFF = {}; cond 2 OFF = {}'.format(self.t23 < self.t25, self.t21 < 45.0, ((self.t2 > 45.0) or (self.t3 > 60.0)), self.t7 > 45.0))
        # ..............................................................

    #end control_internal_2

    # ==================================================================

    def calc_ret_temp_when_cold(self, heatc_conf, t_a, mstr, t_in):
        # returns the approximated return temperature from the heating system when the input temprature is too low to provide ehough energy to cover the heating load
        t_in_N = heatc_conf['design_supply_temperature_oC']
        t_out_N = heatc_conf['design_return_temperature_oC']
        t_i_N = heatc_conf['design_indoor_temperature_oC']
        t_a_N = heatc_conf['design_ambient_temperature_oC']
        mcp = utils.cp_fluid_water(t_in, utils.get_pressure_in_MPa(), utils.get_calc_option())
        Ak = mstr * mcp * (t_in_N - t_out_N) / (0.5 * (t_in_N + t_out_N) - t_i_N)
        AWkW = mstr * mcp * (t_in_N - t_out_N) / (t_i_N - t_a_N)
        A1 = Ak / (AWkW + Ak)
        A2 = mstr * mcp / Ak
        A3 = AWkW / (AWkW + Ak)
        B1 = (0.5 * A1 - 0.5 - A2) / (0.5 - 0.5 * A1 - A2)
        B2 = A3 / (0.5 - 0.5 * A1 - A2)
        return (t_in * B1 + t_a * B2)
        # end calc_ret_temp_when_cold

    # ==================================================================

    def one_iteration_step(self, tsm, tank, chp, kessel, cvalve, heizkurve, t_a, el_heat_status, actual_time, heatc_conf):
        """ one iteration step of the whole RVK system """
        #print('\n chp = {}; kessel = {}; t2 = {}; t3 = {}'.format(chp.get_status(), kessel.get_status(), self.t2, self.t3))
        # combined heat and power unit - link outputs
        wyn = chp.get_chp()
        #self.t27 = wyn[1]   # tin in °C        = self.t1 = wyn[t1]
        self.t26 = wyn[2]   # tout in °C       = chp.get_out_temp = wyn[2]
        m3 = wyn[3]         # mstr in kg/s 
        self.V_3 = m3 / utils.rho_fluid_water(self.t26, self.p_atm, 1)                     # volume flow incoming to chp from tank
        V_chp = chp.get_volume_flow_at_output()  # volume flow outoming from chp into tank
        # combined heat and power unit - link inputs
        chp.set_inp_temp(self.t27)               # temperature incoming from tank to chp

        # ..............................................................

        # gas boiler - link outputs
        wyn = kessel.get_kessel()
        #self.t29 = wyn[1]    # tin in °C - incoming into gas heater
        self.t28 = wyn[2]    # tout in °C - outcoming from gas heater
        m4 = wyn[3]          # mstr in kg/s - incoming into gas heater
        self.V_4 = kessel.get_volume_flow_at_input()
        V_kessel = kessel.get_volume_flow_at_output()
        # gas boiler - link inputs
        kessel.set_inp_temp(self.t29)
        #kessel.calc_mass_flow()

        # ..............................................................
        # at first no delay - just linking chp and heater
        # delay due to the seuence of commands ie equal to the Timestep length
        self.t27 = self.t1
        self.t29 = self.t1
        # ..............................................................

        # heating circuit
        self.t23 = self.t20  # no delay assumed
        #print('t20 = {}; t23 = {}'.format(self.t20, self.t23))
        self.t25 = heizkurve.get_supply_temperature(t_a)
        self.t24 = heizkurve.get_return_temperature(t_a)
        heizkurve.calc_volume_flow()

        # comprehensive control algorithm - it stays
        (m23, m25, m4) = self.control_internal_1(heizkurve, kessel, chp, cvalve, t_a, actual_time, m4, heatc_conf)

        m_bypass = m25 - m23
        rho23 = utils.rho_fluid_water(self.t23, self.p_atm, 1)
        V_23 = m23 / rho23   # in m3/s = kg/s / kg/m3
        #print('V_23 = {}; m23 = {}; rho23 = {}; t23 = {}'.format(V_23,m23, rho23, self.t23))
        m24 = m23
        rho24 = utils.rho_fluid_water(self.t24, self.p_atm, 1)
        V_24 = m24 / rho24
        
        # demand for domestic hot water
        m22 = self.V_1 * utils.rho_fluid_water(self.t22, self.p_atm, 1) # in kg/s = m3/s * kg/m3
        #m22 = 0.01  # kg/s
        # ..............................................................

        t_ambient = 15.0
        # storage tank - calculation
        tank.calculate_storage_tank_obj(tsm,  # time step manager
                                   self.t23,  # hk_inp_temp
                                       V_23,  # hk_inp_volfl_m3s
                                   self.t24,  # hk_out_temp
                                   self.t27,  # chp_inp_temp
                                   self.t26,  # chp_out_temp
                                   self.V_3,  # chp_inp_volfl_m3s
                                   self.t29,  # gb_inp_temp
                                   self.t28,  # gp_out_temp
                                   self.V_4,  # gb_inp_volfl_m3s
                                   self.t22,  # dhw_inp_temp
                                   self.t21,  # dhw_out_temp
                                   self.V_1,  # dhw_inp_volfl_m3s
                             el_heat_status,  # el_heat_status
                                actual_time,  # time in the timestamp format
                                  t_ambient)  # ambient temperature of the tank - defines heat losses to the outside
        
        self.t21 = tank.get_temp_dhw()
        #self.t27 = 
        #self.t29 = 
        #self.t23 = 
        
        # storage tank - linking
        [self.t1, self.t2, self.t3, self.t4, self.t5, self.t6, self.t7, self.t8, self.t9, self.t10, 
         self.t11, self.t12, self.t13, self.t14, self.t15, self.t16, self.t17, self.t18, self.t19, self.t20] = tank.output_temperatures()

        # ..............................................................
        # get rid of this part
        #self.control_internal_2(chp, kessel, actual_time, m4)
        # ..............................................................
        heizwert_in_MJ_per_kg = 50.0   # kg/m3 N   ~CH4
        gas_density = 0.79   # kg/m3 N             ~Erdgas
        Z_boiler = kessel.get_gas_mstr(heizwert_in_MJ_per_kg) / gas_density
        self.Z_2 = chp.get_gas_mstr(heizwert_in_MJ_per_kg) / gas_density
        self.Z_1 = self.Z_2 + Z_boiler
        
        self.Wh1 = -1.0 * chp.get_el_prod()
        self.Wh2 = tank.get_el_heater_consumption()
        self.Wh3 = self.Wh1 + self.Wh2 + self.electricity_consumption_kWh
        #print('END chp = {}; kessel = {}; heating = {}; t2 = {}; t3 = {};V1 = {}; V2 = {}; V3 = {}; V4 = {}; t_a = {}'.format(chp.get_status(), kessel.get_status(), heizkurve.get_status(), self.t2, self.t3, self.V_1, self.V_2, self.V_3, self.V_4, t_a))

    #end one_iteration_step
