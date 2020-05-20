from time import sleep
import numpy as np
import math
import random
from datetime import datetime, timedelta


import utils
import chpunit
import gasheater
import controlvalve
import heatingcurve
import storagetank
import timestep
import predict_thermal
import sys
import platformcontroller

########################################################################

class GatewaySystem():
    """ simulator of the gateway box """

    # ==================================================================
    # constructor method with instance variables
    def __init__(self, t_initial):
        # initialize everyone
        self.p_atm = 0.1 * 1.01325  # in Pa
        self.t1 = self.t2 = self.t3 = self.t4 = self.t5 = self.t6 = self.t7 = self.t8 = self.t9 = self.t10 = t_initial
        self.t11 = self.t12 = self.t13 = self.t14 = self.t15 = self.t16 = self.t17 = self.t18 = self.t19 = self.t20 = t_initial
        self.t21 = self.t22 = self.t23 = self.t24 = self.t25 = self.t26 = self.t27 = self.t28 = self.t29 = self.t30 = t_initial
        self.V_1 = self.V_2 = self.V_3 = self.V_4 = 0.0  # in m3/s
        self.Z_1 = self.Z_2 = 0.0
        self.Wh1 = self.Wh2 = self.Wh3 = 0.0
        self.too_cold = 0
        self.t_initial = t_initial
        self.next_prediction_timestamp = datetime.now()  # time at which the prediction of the energy vector is to be made
        self.prediction_time_step_in_s = 0               # time intervall at which the energy vector is to be produced
        self.output_horizont_in_h = 0                    # time horizont for which the forecast is to be made
        self.output_resolution_in_s = 0                    # time horizont for which the forecast is to be made
        self.current_schedule = 0
        self.storage_tank = 0
        self.chp = 0
        self.boiler = 0
        self.heizkurve = 0
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

    def get_el_prod_kWh(self, therm_prod_kWh):
        return self.chp.get_el_prod_kWh(therm_prod_kWh)

    # ==================================================================

    def max_pred_temp_supply_heating_sys(self, t_a_min):
        return self.heizkurve.get_supply_temperature(t_a_min)

    # ==================================================================

    def thermal_energy_that_can_be_got_from_storage(self, tmin):
        return self.storage_tank.calc_energy_above_tmin(tmin)
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

    def initialize_actual_time(self, simulation, start_sim_inh, end_sim_inh):
#    def initialize_actual_time(self, simulation, end_sim_inh):
        if simulation:
            return (datetime.now() - timedelta(hours=(end_sim_inh - start_sim_inh)))  # time in datetime format
            #return (datetime.now() - timedelta(hours=end_sim_inh))  # time in datetime format
        else:
            return datetime.now()  # time in datetime format

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

    def update_time(self, simulation, actual_time, tsm):
        next_time_step = actual_time + timedelta(seconds=tsm.get_timestep())
        if simulation:
            return (next_time_step)
        else:
            while datetime.now() < next_time_step:
                sleep(1)
            return datetime.now()

    #end update_time

    # ==================================================================

    def get_ambient_temperature(self, simulation, wetter_file, actual_time, start_datetime, start_sim_inh, end_sim_inh):
        # returns ambient air temperature as read from the wetter_file in the TRY04 format
        # simulation     - flag for real time or file based 
        # wetter_file    - file with weather parameters in TRY04 format
        # actual_time    - the current time or current simulation time in the datetime format
        # start_datetime - start of the calculations in datetime format
        # start_sim_inh  - only in simulation mode - the starting point of the simulation in hours - will be found in the wetter_file
        # end_sim_inh    - only in simulation mode - the end point of the simulation in hours - arbitrarily stated
        if simulation:
            # file based simulation - values are read from the file
            #            hour_of_year = 1
            condition = True
            simtime = ((actual_time - start_datetime).total_seconds() / 3600.0) + start_sim_inh  # simulationstime in h
            #print('actual_time ={}; start_datetime = {}; simtime = {}; start_sim_inh = {}'.format(actual_time, start_datetime, simtime, start_sim_inh))
            ii = 0
            while condition:
                line1 = utils.get_significant_parts(wetter_file[ii].rstrip().split(" "))
                hour = utils.get_time_in_hour(line1)
                condition = (hour < simtime)
                ii = ii + 1
                if (ii > 8760):
                    ii = 0
            if (ii == 0):
                ii = 8760
            else:
                ii = ii - 1
            jj = ii - 1
            if jj<0:
                jj = 8760 - 1
            line2 = utils.get_significant_parts(wetter_file[jj].rstrip().split(" "))
            x1 = hour
            x2 = utils.get_time_in_hour(line2)
            y1 = float(utils.get_ith_column(8, line1))
            y2 = float(utils.get_ith_column(8, line2))
            # time since the beginning of the start of the simulation in hours 
            return utils.linear_interpolation(simtime, x1, x2, y1, y2)
        else:
            # real time calculation - values are received via MQTT? - dead for now
            return 10.0

    #end get_ambient_temperature

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
        # simulation     - flag for real time or file based 
        # dhw_load_file  - file with dhw consumption in litres resolved for 525600 minutes of the year = 8760 h/a * 60 min/h
        # actual_time    - the current time or current simulation time in the datetime format
        # start_datetime - start of the calculations in datetime format
        # start_sim_inh  - only in simulation mode - the starting point of the simulation in hours - will be found in the wetter_file
        # end_sim_inh    - only in simulation mode - the end point of the simulation in hours - arbitrarily stated
        if simulation:
            # file based simulation - values are read from the file
            #            hour_of_year = 1
            simtime = int(math.floor(((actual_time - start_datetime).seconds / 60.0) + start_sim_inh * 60.0))  # simulationstime in minutes
            if (simtime >= 525600):     # actual time exceeds the first year (there are 525 600 minutes in a year)
                simtime = simtime - math.floor(simtime / 525600) * 525600
            nn = len(dhw_load_file)
            if(int(simtime) > nn):
                simtime = int(simtime) % nn
            minute = int(dhw_load_file[simtime])
            return minute/60000.0    # in cubic meter per second = m3/s = dm3/min / (60 s/min * 1000 dm3/m39
            #
            #wyn = 0.0
            #if((actual_time-start_datetime).seconds >= (3600.0 * 48.0)):
                #wyn = minute / 60000.0    # in cubic meter per second = m3/s = dm3/min / (60 s/min * 1000 dm3/m39
            #return wyn
        else:
            # real time calculation - values are received via MQTT? - dead for now
            return 0.1

    #end get_dhw_minute_consumption

    # ==================================================================

    def main(self):
        #print('internal main proc')
        config_file = utils.check_and_open_json_file('./config.json')
        #print('in main - type of config is {}'.format(type(config_file)))
        (simulation, time_step_in_s, record_step_in_s, start_sim_inh, end_sim_inh, wetter_file, dhw_load_file, el_load_file, actual_time, 
         F, tsm, tank, chp, kessel, cvalve, heizkurve, pred) = self.initialize_components(config_file)

        ini_time_in_h = utils.convert_time_to_hours(actual_time)
        last_record_time = actual_time  # time in datetime format
        print_time_in_h = 0
        start_datetime = actual_time
        end_datetime = actual_time + timedelta(hours=(end_sim_inh - start_sim_inh))
        #end_datetime = actual_time + timedelta(hours=end_sim_inh)
        print('actual_time = {} (in hours = {})'.format(actual_time,utils.convert_time_to_hours(actual_time)))
        print('start_datetime = {} (in hours = {})'.format(start_datetime,utils.convert_time_to_hours(start_datetime)))
        print('end_datetime = {} (in hours = {})'.format(end_datetime,utils.convert_time_to_hours(end_datetime)))

        self.write_header_output_file(F)
        #act_time_in_h = utils.convert_time_to_hours(actual_time)-ini_time_in_h
        #ambient_temp = self.get_ambient_temperature(simulation, wetter_file, actual_time, start_datetime, start_sim_inh, end_sim_inh)
        #self.write_output_into_file(F, actual_time,act_time_in_h,ambient_temp,chp,kessel,cvalve)  # first step

        
        print('modules initialized')
        # Martin's code
        predict_thermal.file_name=open("./pred.txt","a")
        timestart = datetime.now()
        H = open("./logrvk1.dat","w")
        G = open("./mylog.dat","w")
        G.write(' time load temp \n')
        
        while self.loop_condition(simulation, actual_time, end_datetime):
            # t_a
            ambient_temp = self.get_ambient_temperature(simulation, wetter_file, actual_time, start_datetime, start_sim_inh, end_sim_inh)
            self.t30 = ambient_temp
            # dhw consumption
            self.V_1 = self.get_dhw_minute_consumption(simulation, dhw_load_file, actual_time, start_datetime, start_sim_inh, end_sim_inh)
            # cold water temperature
            self.t22 = 10.0
            # electrical rod heater
            el_heat_status = self.get_heater_rod_status(simulation, el_load_file, actual_time, start_datetime, start_sim_inh, end_sim_inh)
            el_heat_status = 0.0
            # time management
            act_time_in_h = utils.convert_time_to_hours(actual_time)-ini_time_in_h
            next_time_step = self.update_time(simulation, actual_time, tsm)
            real_dt_in_s = (next_time_step - actual_time).seconds
            tank.update_act_time(act_time_in_h)
            # calculation
            self.one_iteration_step(tsm, tank, chp, kessel, cvalve, heizkurve, ambient_temp, el_heat_status, actual_time, H)
            # output control
            last_record_time = self.write_output_into_file(F, record_step_in_s, last_record_time, actual_time ,act_time_in_h ,ambient_temp ,chp ,kessel ,cvalve ,tank, tsm)  # at the end of the timestep
            # proceed to the next timestep
            actual_time = next_time_step
            flag_big_time_step = tsm.has_timestep_ended(actual_time)  # redundant ?
            # show progress at prompt
            if((act_time_in_h-print_time_in_h) > 0.05 * (end_sim_inh - start_sim_inh)):
                print_time_in_h = act_time_in_h
                print('.', end = '')
                #print('time = {}  (in hours = {}; {})'.format(actual_time, act_time_in_h, utils.convert_time_to_hours(actual_time)))
            #print('time = {}; act_time_in_h = {}; kessel = {}; mstr = {}; tinp = {}; tout = {}; Qhk = {}'.format(actual_time, act_time_in_h, kessel.get_status(), kessel.get_volume_flow_at_output(), kessel.get_inp_temp(), kessel.get_out_temp(), kessel.get_heat_output()))
            # saving data for prediction algorithms
            #print('main time = {} ; {}'.format(actual_time, act_time_in_h))
            self.save_data_for_prediction(pred, act_time_in_h, ambient_temp, G)
            if(self.time_condition_for_prediction(actual_time, pred)):
                #G.write(' weather prediction')
                #G.flush()
                weather_pred = self.get_weather_prediction(actual_time, simulation, wetter_file, start_datetime, start_sim_inh, end_sim_inh)
                #G.write(' --> energy vector')
                #G.flush()
                energy_vector = pred.predict_energy_vector(weather_pred, act_time_in_h, actual_time, start_datetime, start_sim_inh, end_sim_inh, self.output_horizont_in_h, self.output_resolution_in_s)
                #G.write('--> send or save')
                #G.flush()
                self.send_or_save_energy_vector(actual_time, energy_vector, start_datetime)
                #G.write('--> end\n')
                #G.flush()
            #self.control_execute_schedule(self.current_schedule, actual_time)
            
        # output to the file - end
        F.close()
        G.close()
        H.close()
        # duration of the calculation
        timeend = datetime.now()
        print('\ncalculation took = {} seconds'.format(timeend - timestart))

    #end main

    # ==================================================================

    def time_condition_for_prediction(self, actual_time, pred):
        if(actual_time >= self.next_prediction_timestamp):
            if(pred.get_q_write()):
                #print('now = {}; next time = {}'.format(actual_time, self.next_prediction_timestamp))
                return True
        return False

    #end time_condition_for_prediction

    # ==================================================================

    def send_or_save_energy_vector(self, actual_time, energy_vector, start_datetime):
        # send energy vector
        self.next_prediction_timestamp = actual_time + timedelta(seconds=self.prediction_time_step_in_s)
        schedule = platformcontroller.cloud_schedule_gen(actual_time, energy_vector, start_datetime)
    #end send_or_save_energy_vector

    # ==================================================================

    def get_weather_prediction(self, actual_time, simulation, wetter_file, start_datetime, start_sim_inh, end_sim_inh):
        if(simulation):
            # create unprecise prediction based upon data from weather file
            weather_pred = []
            horizont_time = actual_time + timedelta(hours=self.output_horizont_in_h)
            actual_time = actual_time + timedelta(seconds=self.output_resolution_in_s)
            sign = random.choice([-1, 1])
            #print('horizont_time = {}; actual_time = {}; sign = {}'.format(horizont_time, actual_time, sign))
            #print('timestep in s = {}; actual_time = {}; sign = {}'.format(self.output_resolution_in_s, actual_time, sign))
            while(actual_time <= horizont_time):
                # read ambient temperature from the weather file
                t_pred = self.get_ambient_temperature(simulation, wetter_file, actual_time, start_datetime, start_sim_inh, end_sim_inh)
                # calculate deviation from the temperature that will be simulated
                #simtime_in_h = ((actual_time - start_datetime).total_seconds() / 3600.0) + start_sim_inh  # simulationstime in h
                simtime_in_h = ((actual_time - start_datetime).total_seconds() / 3600.0)  # simulationstime in h
                deviation = sign * math.sqrt(simtime_in_h/24.0) * 3.0 + np.random.random() * 1.0
                # create output list
                weather_pred.append({'date':actual_time, 'time_in_h': simtime_in_h + start_sim_inh, 'temp_in_C': t_pred + deviation})
                #print('horizont_time = {}; actual_time = {}; t_pred = {}; deviation = {}'.format(horizont_time, actual_time, t_pred, deviation))
                actual_time = actual_time + timedelta(seconds=self.output_resolution_in_s)
        else:
            weather_pred = self.request_weather_prediction_from_platform(actual_time)
        #print('weather prediction = ')
        #for pred in weather_pred:
            #print(type(pred), pred)
        
        return weather_pred

    #end get_weather_prediction

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
        F.write(" m3/s  m3/s  kW  flag  kg/s  kg/s  kW  kW  0-1  kg/s  kg/s  0-1  h  s  \n")

        F.write("# date  time  elapsed  t_a  t_1  t_2  t_3  t_4  t_5  t_6  t_7")
        F.write("  t_8  t_9  t_10  t_11  t_12  t_13  t_14  t_15  t_16")
        F.write("  t_17  t_18  t_19  t_20  t_21  t_22  t_23  t_24  t_25")
        F.write("  t_26  t_27  t_28  t_29  t_30  V_1  v_2  V_3  V_4")
        F.write("  Z_1  Z_2  Wh1  Wh2  Wh3")
        F.write("  chp  boiler  control_valve  COLD  mstr_dhw  mstr_hw  el_heater  n_slice  tstep_in_s  ")
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

    def initialize_components(self, config_file):
        conf_calc = config_file['calculation']
        time_step_in_s = conf_calc['time_step_in_s']     # in seconds
        record_step_in_s = conf_calc['record_step_in_s'] # in seconds
        
        start_sim_inh = conf_calc['simulation_mode']['start_sim_in_hours']  # starting time of the simulation in h
        end_sim_inh = conf_calc['simulation_mode']['end_sim_in_hours']      # end time of the simulation in h
        wetter_file = utils.check_and_open_file(conf_calc['simulation_mode']['weather_file_path'])        # list of strings
        dhw_load_file = utils.check_and_open_file(conf_calc['simulation_mode']['dhw_profile_file_path']) # list of strings
        el_load_file = utils.check_and_open_file(conf_calc['simulation_mode']['el_load_file_path'])  # list of strings

        sim_flag = conf_calc['mode']
        if(sim_flag == 'simulation'):
            simulation = True
        else:
            simulation = False
        actual_time = self.initialize_actual_time(simulation, start_sim_inh, end_sim_inh)  # time in datetime format
        
        F = open(conf_calc['simulation_mode']['output_file_path'],"w")
        
        conf_comp = config_file['components']
        tsm = timestep.timestepmanager(time_step_in_s, conf_comp['timestep_manager']['minimal_timestep_in_s'], actual_time)

        chp = self.initialize_chp_unit(conf_comp['chp_unit'], actual_time)
        self.chp = chp
        kessel = self.initialize_gas_boiler(conf_comp['gas_boiler'], actual_time)
        self.boiler = kessel
        tank = self.initialize_storage_tank(conf_comp['storage_tank'], actual_time, tsm)
        self.storage_tank = tank
        cvalve = controlvalve.ThreeWayControlValve(conf_comp['control_valve']['initial_hub_position_0_1'])
        heizkurve = self.initialize_heating_curve(conf_comp['heating_curve'])
        self.heizkurve = heizkurve
        # prediction - global and output
        self.prediction_time_step_in_s = config_file['prediction']['prediction_time_step_in_s']
        self.next_prediction_timestamp = actual_time + timedelta(seconds=self.prediction_time_step_in_s)
        self.output_horizont_in_h =  config_file['prediction']['output_horizont_in_h']
        self.output_resolution_in_s =  config_file['prediction']['output_resolution_in_s']
        
        # Martin's code
        conf_pred = config_file['prediction']['heat']
        conf_powr = config_file['prediction']['power']
        pred = self.initialize_thermal_prediction(conf_pred, conf_powr)
        predict_thermal.write_init(conf_pred['path_result'])

        # schedule
        self.current_schedule = self.initialize_schedule(actual_time)

        return (simulation, time_step_in_s, record_step_in_s, start_sim_inh, end_sim_inh, wetter_file, dhw_load_file, el_load_file, actual_time, 
         F, tsm, tank, chp, kessel, cvalve, heizkurve, pred)
        
        
        # end function initialize_components

    # ==================================================================

    def initialize_thermal_prediction(self, config_json, conf_powr):
        """ copyright by Martin Knorr """
        # config_json
        n_day = config_json['n_day']
        n_values = config_json['n_values_per_day']
        precision_in_h = config_json['precision_in_h']
        use_predef_loads = config_json['use_predef_loads']
        predef_loads_file_path = config_json['path_loads']
        # conf_powr
        #print('\n initialize_thermal_prediction')
        #print('use_predef_loads = {}; {}'.format(use_predef_loads,type(use_predef_loads)))
        #print('predef_loads_file_path = {}; {}'.format(predef_loads_file_path,type(predef_loads_file_path)))
        return predict_thermal.predict_Q(n_day, n_values, precision_in_h, predef_loads_file_path, use_predef_loads, self.output_horizont_in_h, self.output_resolution_in_s, conf_powr, self)

    #end initialize_thermal_prediction

    # ==================================================================

    def initialize_schedule(self, actual_time):

        nn = int((self.output_horizont_in_h * 3600.0) // self.output_resolution_in_s)
        print('\n\n initialize schedule. typ of n = {}; n = {}'.format(type(nn),nn))
        result_array = []
        for ii in range(nn):
            newx = {'time_stamp' : actual_time + timedelta(seconds = self.output_resolution_in_s * ii), 'activation' : False , 'energy_production_in_W' : (np.random.random()*2000.0 - 1000.0)}
            result_array.append(newx)
            #print(newx)
        schedule = {'timestep_in_s' : 900, 'active schedule' : True, 'values' : result_array}
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

    def initialize_storage_tank(self, config_json, actual_time, tsm):
        effective_heigth_in_m = config_json['effective_heigth_in_m']
        inner_radius_tank_in_m = config_json['inner_radius_tank_in_m']
        effective_coil_surface_in_m2 = config_json['effective_coil_surface_in_m2']
        effective_coil_volume_in_m3 = config_json['effective_coil_volume_in_m3']
        initial_temperature_in_oC = config_json['initial_temperature_in_oC']
        if(initial_temperature_in_oC<(-273.15)):
            t_ini = self.t_initial
        else:
            t_ini = initial_temperature_in_oC
        alpha_losses_in_W_mK = config_json['alpha_losses_in_W_mK']
        power_heating_rod_in_W = config_json['power_heating_rod_in_W']
        initial_status_heating_rod_0_1 = config_json['initial_status_heating_rod_0_1']
        return storagetank.HeatStorageTank(effective_heigth_in_m,inner_radius_tank_in_m,effective_coil_surface_in_m2,effective_coil_volume_in_m3,
               t_ini,alpha_losses_in_W_mK, actual_time,power_heating_rod_in_W,initial_status_heating_rod_0_1, tsm, 'implizit',1) #
#initial_temperature, alpha_loss         , actual_time, el_heat_power        , el_heat_status   , timestepmanager, solverschema, elemtype):

    #end initialize_storage_tank

    # ==================================================================

    def save_data_for_prediction(self, pred, act_time_in_h, ambient_temp, G):
        # Martin's code
        qHeat = self.V_2 * utils.rho_fluid_water(self.t24, self.p_atm, 1) * (self.t25 - self.t24)
        qDHW = self.V_1 * utils.rho_fluid_water(self.t22, self.p_atm, 1) * (self.t21 - self.t22)
        q_write = pred.run_to_save_data(act_time_in_h+2, qHeat + qDHW, ambient_temp)
        
        G.write('{:10.5f} {:10.5f} {:10.5f}\n'.format(act_time_in_h, qHeat + qDHW, ambient_temp))
#        if (q_write):
#            predict_thermal.write_q(t[index],t_e_1day,q_1day,t_e_2day,q_2day)

    #end save_data_for_prediction

    # ==================================================================

    def control_execute_schedule(self, schedule, actual_time):
        if(schedule['active schedule']):
            #print('schedule is active')
            result_array = schedule['values']
            ii = 0
            while(result_array[ii]['time_stamp'] < actual_time):
                ii += 1
            set_point_val = result_array[ii]['energy_production_in_kW']
            
            #to_produce_in_kW = set_point_val + elektro_pred_in_kW
            
                
                
            
            
        #print('end of control execute schedule')
        

    #end control_execute_schedule

    # ==================================================================

    def control_internal_1(self, heizkurve, kessel, chp, cvalve, t_a, actual_time, m4, H):
        if(t_a<=15.0):                # heating period
            heizkurve.turn_on(t_a)
        else:
            heizkurve.turn_off()

        self.V_2 = heizkurve.get_volume_flow()
        # ..............................................................
        # mass flow 
        m25 = utils.rho_fluid_water(self.t24, self.p_atm, 1) * self.V_2  # mass flow in heating circuit in kg/s
        #print('time = {}; type t23 = {}; type t25 = {}'.format(actual_time, type(self.t23), type(self.t25)))
        if(t_a<=15.0):                # heating period
            #self.t25 = heizkurve.get2_supply_temperature(t_a)
            if self.t23 < self.t25:  # temp in storage is too low to heat the building´                self.too_cold = 1
                self.t24 = max(self.t24 - (self.t25 - self.t23),self.t22)   # return temperature from the heating system
                self.t25 = self.t23                           # supply temperature to the heating system is too low
                if chp.get_status() == 1 and self.t15 < self.t25:  # storage is almost empty even though the chp is already running
                    wyn = kessel.turn_on(actual_time)  # turn the gas boiler on
                    if (wyn[0] == False):
                        H.write('Could not turn gas boiler on at time = {}. Time left to the next turn on = {} s. t23 < t25\n'.format(actual_time,wyn[4].seconds))
                        #print('Could not turn gas boiler on at time = {}. Time left to the next turn on = {} s. t23 < t25'.format(actual_time,wyn[4].seconds))
                    #print('t28 = {}; wyn[2] = {}'.format(self.t28,wyn[2]))
                    self.t28 = wyn[2]
                    #self.t29 = wyn[1]
                    kessel.set_inp_temp(self.t29)
                    m4 = wyn[3]
                    if(wyn[0] == False):
                        print('ERROR 2 at time = {}'.format(actual_time))
                    self.V_4 = m4 / utils.rho_fluid_water(self.t29, self.p_atm, 1) # in m3/s = kg/s / kg/m3
                else:
                    wyn = chp.turn_on(actual_time)  # turn the chp unit on
                    if (wyn[0] == False):
                        H.write('Could not turn CHP unit on at time = {}. Time left to the next turn on = {} s. t23 < t25\n'.format(actual_time,wyn[4].seconds))
                        #print('Could not turn CHP unit on at time = {}. Time left to the next turn on = {} s. t23 < t25'.format(actual_time,wyn[4].seconds))
                    #print('TOO COLD, chp is off, t26 = {}; wyn[2] = {}; stat chp = {}; stat boiler = {}'.format(self.t26,wyn[2],chp.get_status(),kessel.get_status()))
                    self.t26 = wyn[2]
                    #self.t27 = wyn[1]
                    chp.set_inp_temp(self.t27)               # temperature incoming from tank to chp
                    m3 = wyn[3]
                    if (wyn[0] == False):
                        print('ERROR 1 at time = {}'.format(actual_time))
                    self.V_3 = m3 / utils.rho_fluid_water(self.t26, self.p_atm, 1) # in m3/s = kg/s / kg/m3
                #print('t23<t25, turn ON, chp = {}, kessel = {}'.format(chp.get_status(),kessel.get_status()))
                m23 = m25
                cvalve.set_hub(1.0)
            else:
                self.too_cold = 0
                cp25 = utils.cp_fluid_water(self.t25, self.p_atm, 1)
                cp24 = utils.cp_fluid_water(self.t24, self.p_atm, 1)
                cp23 = utils.cp_fluid_water(self.t23, self.p_atm, 1)
            #        m23 + m_bypass = m25  ==> m_bypass = m25 - m23
            #        t23 * cp23 * m23 + t24 * cp24 * m_bypass = t25 * cp25 * m25
            #        t23 * cp23 * m23 + t24 * cp24 * (m25 - m23) = t25 * cp25 * m25
            #        m23 * (t23 * cp23 - t24 * cp24) = m25 * (t25 * cp25 - t24 * cp24)
                m23 = m25 * (self.t25 * cp25 - self.t24 * cp24) / (self.t23 * cp23 - self.t24 * cp24)
            

            #        m_bypass = m25 * (1.0 - cvalve.get_hub)   # mass flow in bypass in kg/s
                if(m25!=0.0):
                    cvalve.set_hub(m23 / m25)
        #        t25 = (t23 * cp23 + m_bypass * cp24) / (m25 * cp24)
        else:             # no heating needed 
            self.too_cold = 0
            m23 = 0.0
            m25 = 0.0
            self.V_2 = 0.0
        return (m23, m25, m4)

    #end control_internal_1

    # ==================================================================

    def control_internal_2(self, chp, kessel, actual_time, m4, H):
        # controls - turn all off when the tank is fully loaded
        #if(str(type(self.t2))!="<class 'float'>"):
            #print('actual_time = {}; t2 = {}; t3 = {}'.format(actual_time, self.t2, self.t3))
        if((self.t2 > 45.0) or (self.t3 > 60.0)):
            if(chp.get_status() == 1):
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
        if(self.t7 > 45.0):
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
        # controls - turn the chp unit and heater if the temperature of domestic hot water is too low
        if self.t21 < 45.0:
            if chp.get_status():
                wyn = kessel.turn_on(actual_time)
                if (wyn[0] == False):
                    H.write('Could not turn gas boiler on at time = {}. Time left to the next turn on = {} s. t21 < 45\n'.format(actual_time,wyn[4].seconds))
                    #print('Could not turn gas boiler on at time = {}. Time left to the next turn on = {} s. t21 < 45'.format(actual_time,wyn[4].seconds))
                self.t28 = wyn[2]
                self.t29 = wyn[1]
                m4 = wyn[3]
                self.V_4 = m4 / utils.rho_fluid_water(self.t29, self.p_atm, 1) # in m3/s = kg/s / kg/m3
            else:
                wyn = chp.turn_on(actual_time)
                self.t26 = wyn[2]
                self.t27 = wyn[1]
                m3 = wyn[3]
                if (wyn[0] == False):
                    H.write('Could not turn CHP on at time = {}. Time left to the next turn on = {} s. t21 < 45\n'.format(actual_time,wyn[4].seconds))
                    #print('Could not turn CHP on at time = {}. Time left to the next turn on = {} s. t21 < 45'.format(actual_time,wyn[4].seconds))
                self.V_3 = m3 / utils.rho_fluid_water(self.t26, self.p_atm, 1) # in m3/s = kg/s / kg/m3
            #print('t21<45, turn ON, chp = {}, kessel = {}'.format(chp.get_status(),kessel.get_status()))
        elif self.t21 > 85.0:
            print('alarm dhw too hot t = {}'.format(self.t21))
            #if(self.t21 > 85.0):
                #quit()
        
        
        #print('cond heat on = {}; cond 2 heat on = {}; cond 1 OFF = {}; cond 2 OFF = {}'.format(self.t23 < self.t25, self.t21 < 45.0, ((self.t2 > 45.0) or (self.t3 > 60.0)), self.t7 > 45.0))
        # ..............................................................

    #end control_internal_2

    # ==================================================================

    def one_iteration_step(self, tsm, tank, chp, kessel, cvalve, heizkurve, t_a, el_heat_status, actual_time, H):
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

        ###
        (m23, m25, m4) = self.control_internal_1(heizkurve, kessel, chp, cvalve, t_a, actual_time, m4, H)

        m_bypass = m25 - m23
        rho23 = utils.rho_fluid_water(self.t23, self.p_atm, 1)
        V_23 = m23 / rho23   # in m3/s = kg/s / kg/m3
        #print('V_23 = {}; m23 = {}; rho23 = {}; t23 = {}'.format(V_23,m23, rho23, self.t23))
        m24 = m23
        rho24 = utils.rho_fluid_water(self.t24, self.p_atm, 1)
        V_24 = m24 / rho24
        
        # demand for domestic hot water
        m22 = self.V_1 * utils.rho_fluid_water(self.t22, self.p_atm, 1) # in kg/s = m3/s * kg/m3
        m22 = 0.01  # kg/s
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
        [self.t1, self.t2, self.t3, self.t4, self.t5, self.t6, self.t7, self.t8, self.t9, self.t10, self.t11, self.t12, self.t13, self.t14, self.t15, self.t16, self.t17, self.t18, self.t19, self.t20] = tank.output_temperatures()

        # ..............................................................

        self.control_internal_2(chp, kessel, actual_time, m4, H)
        # ..............................................................
        heizwert_in_MJ_per_kg = 50.0   # kg/m3 N   ~CH4
        gas_density = 0.79   # kg/m3 N             ~Erdgas
        Z_boiler = kessel.get_gas_mstr(heizwert_in_MJ_per_kg) / gas_density
        self.Z_2 = chp.get_gas_mstr(heizwert_in_MJ_per_kg) / gas_density
        self.Z_1 = self.Z_2 + Z_boiler
        
        self.Wh1 = -1.0 * chp.get_el_prod()
        self.Wh2 = tank.get_el_heater_consumption()
        self.Wh3 = self.Wh1 + self.Wh2
        #print('END chp = {}; kessel = {}; heating = {}; t2 = {}; t3 = {};V1 = {}; V2 = {}; V3 = {}; V4 = {}; t_a = {}'.format(chp.get_status(), kessel.get_status(), heizkurve.get_status(), self.t2, self.t3, self.V_1, self.V_2, self.V_3, self.V_4, t_a))

    #end one_iteration_step
