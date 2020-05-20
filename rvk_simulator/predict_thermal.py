# -*- coding: utf-8 -*-
"""
Created: 21.05.2019

@author: Martin Knorr

thermal demand prediction
"""

import time
import requests
import json
from datetime import datetime, timedelta, timezone
import utils
import random
import math
import numpy as np
from crate import client


# read and split data from a file
def read_data(name_loads):
    file_name=open(name_loads,"r")     # open input file, read mode
#    file_name=open("loads_test01.txt","r")     # open input file, read mode
    file_data=file_name.readlines()     # read data in a list
#    for i in file_data:
#        print(i)
    file_name.close()
    result=[]
    for i in file_data:
        a=i.replace('\t',' ')            # delete tabs
        b=a.replace('\n',' ')            # delete line feeds
        result.append(b)

    del result[0]                       # delete first line
    t=[]; q=[]; t_e=[]
    for i in result:
        t_h, q_h, t_e_h = i.split()                                 # split line in values
        t_h, q_h, t_e_h = float(t_h), float(q_h), float(t_e_h)      # convert in numbers
        t.append(t_h); q.append(q_h); t_e.append(t_e_h)             # add to list

    return (t,q,t_e)

# read predicted temperatures from a file
def read_temp(name_temp):
    file_name=open(name_temp,"r")       # open input file, read mode
#    file_name=open("temp_test01.txt","r")       # open input file, read mode
    file_data=file_name.readlines()     # read data in a list
#    for i in file_data:
#        print(i)
    file_name.close()
    result=[]
    for i in file_data:
        a=i.replace('\t',' ')            # delete tabs
        b=a.replace('\n',' ')            # delete line feeds
        result.append(b)

    del result[0]                       # delete first line
    t=[]; t_e_pred=[]
    for i in result:
        t_h, t_e_pred = i.split()                               # split line in values
        t_h, t_e_pred = float(t_h), float(t_e_pred)             # convert in numbers
        t.append(t_h); t_e.append(t_e_pred)                     # add to list

    return (t,t_e)

# write results in a file
def write_init(name_write):
    # delete or create output - file
    file_name = open(name_write,"w")
    file_name.write("time   t_e_1day    q_1day     t_e_2day    q_2day    m_c    n_c\n")
    file_name.close()

# write results in a file
def write_q(name_write,t,q_1day,t_e_1day,q_2day,t_e_2day,m_c,n_c):
    file_name=open(name_write,"a")      # open output file, append mode
    q_1day = round(q_1day,1)
    q_2day = round(q_2day,1)
    text=str(t) + "   " + str(q_1day) + "   " + str(t_e_1day) + "   " + str(q_2day) + "   " + str(t_e_2day)
    text=text + "   " + str(m_c) + "   " + str(n_c)
    file_name.write(text)
    file_name.write("\n")
    file_name.close()


#------------------------------------------------------------------------------------------

class predict_Q():
    """ copyright by Martin Knorr """
    def __init__(self, n_day, n_values, eps, predef_loads_file_path, use_predef_loads, output_horizon_in_h, output_resolution_in_s, conf_powr,
                 hk_tv, hk_tr, hk_ti, hk_ta, hk_qn, hk_n, hk_m, chp_tmax, gb_tmax, slice_volume, mstr_chp, mstr_gb, qmax_rod_el, 
                 eps_th_chp, eps_el_chp, open_weather_map_active):

        self.n_day = n_day          # number of past days considered
        self.n_values = n_values    # number of values per day
        self.dt=24//n_values        # time step in hours
        self.count = 0              # counter for values between call of prediction
        self.c_tot = 0              # counter for values total
        self.c_day = 0              # counter for saved days
        self.q = 0                  # actual heat
        self.t_e = 0                # actual external temperature
        self.q_s = [[0] * n_values for i in range(n_day)]           # array for heat
        self.t_e_s = [[0] * n_values for i in range(n_day)]         # array for external temperatures
        # changes - Wojtek Kozak
        self.q_write = False        # flag - is the thermal prediction possible
        self.eps = eps              # precision of time calculation in hours
        self.act_hour = 0.0 + self.dt
        self.use_predef_loads = use_predef_loads
        self.predef_loads_file_path = predef_loads_file_path
        if(use_predef_loads):
            self.predef_loads = utils.check_and_open_file(predef_loads_file_path)
            self.predefine_thermal_loads_from_file()
        #print('has broken')
        self.output_horizon_in_h = output_horizon_in_h
        self.output_resolution_in_s = output_resolution_in_s
        # conf_powr - configuration of electricity demand prediction
        self.type_of_prediction = conf_powr['type_of_prediction']
        if(self.type_of_prediction == 'SLP'):
            self.el_data = conf_powr['SLP']
            self.slp_resolution_in_s = conf_powr['resolution_in_s']
        #self.rvk = rvk
        # heating curve
        self.hk_tv = hk_tv
        self.hk_tr = hk_tr
        self.hk_ti = hk_ti
        self.hk_ta = hk_ta
        self.hk_qn = hk_qn
        self.hk_n = hk_n
        self.hk_m = hk_m
        self.mstr_hk = hk_qn / (utils.cp_fluid_water(0.5 * (hk_tv + hk_tr), utils.get_pressure_in_MPa(), 1) * (hk_tv - hk_tr))  # kg/s = kW / (kJ/kg/K * K)
        # chp unit
        self.chp_tmax = chp_tmax
        self.mstr_chp = mstr_chp
        self.eps_th_chp = eps_th_chp
        self.eps_el_chp = eps_el_chp
        # gas boiler
        self.gb_tmax = gb_tmax
        self.mstr_gb = mstr_gb
        # storage tank
        self.slice_volume = slice_volume
        self.qmax_rod_el = qmax_rod_el
        # crate connection
        self.cursor = 0
        self.request_endpoint = 0
        # sources for weather prediction
        self.open_weather_map_active = open_weather_map_active
        # debug modus
        self.dbg = 2
        # end __init__

#=======================================================================
    
        
#=======================================================================

    def predefine_thermal_loads_from_file(self):
        #print(type(self.predef_loads),type(self.predef_loads[0]))
        for li in self.predef_loads[1:]:
            line1 = utils.get_significant_parts(li.rstrip().split(" "))
            time = float(utils.get_ith_column(1, line1))
            load = float(utils.get_ith_column(2, line1))
            t_a = float(utils.get_ith_column(3, line1))
            self.run_to_save_data(time,load,t_a)
            if(self.get_q_write()):
                #print('should break')
                break
        if(not self.get_q_write()):
            print('throw exception')
            print('severe ERROR')
            print('Data in file {} is too short to cover the initialization of class predict_Q'.format(self.predef_loads_file_path))
            print('Check whether the times in file and in simulation are consistent.')
    # end predefine_thermal_loads_from_file

#=======================================================================

    def run(self,t_act,q_act,t_e_act,t_e_1day,t_e_2day,eps):
        # t_act - actual time in hours
        # q_act - actual heat load of the system in W or kW ?
        # t_e_act - ambient air temperature in grad Celcius
        # t_e_1day - ambient air temperature one day before the actual time in grad Celcius
        # t_e_2day - ambient air temperature two days before the actual time in grad Celcius
        # eps - precision of time calculation in hours

        # set output values, if not calculated
        q_1day = 0
        q_2day = 0
        q_write = False
        m_c = 0
        n_c = 0
        # save values from reading
        self.q = self.q + q_act
        self.t_e = self.t_e + t_e_act
        self.count = self.count + 1
        self.c_tot = self.c_tot + 1
        # decission if prediction shall start
        if ((t_act / self.dt) - (t_act // self.dt)) < eps:
            # ----- fill and shift array ----------------------------------------------------------------------
            # calculate day time
            day = int(t_act / 24)
            t_day = t_act - day * 24

            # shift matrix after a day
            if ((t_day < 0.01) and (self.c_tot > 1)):
                self.c_day = self.c_day + 1
                #print("shift")
                self.q_s=self.q_s[1:] + self.q_s[0:1]
                self.t_e_s=self.t_e_s[1:] + self.t_e_s[0:1]

            # add value to array
            cd = int(t_day / self.dt)                       # counter time in day
            self.q = self.q / self.count
            self.q_s[self.n_day - 1][cd] = self.q           # array for heat
            self.t_e = self.t_e / self.count                # average temperature for time period
            self.t_e_s[self.n_day - 1][cd] = self.t_e       # array for external temperature

            #print(self.c_tot)
            #print(self.q_s)
            #print(self.t_e_s)

            # reset values for time period integration
            self.t_e = 0
            self.q = 0
            self.count = 0

            # ------ perform prediction -----------
            if self.c_day >= self.n_day:                            # start if enough data is saved
                q_write = True
                # calculate average value from past days
                q_m = 0
                t_e_m = 0
                for i in range(0,self.n_day):
                    q_m = q_m + self.q_s[i][cd]
                    t_e_m = t_e_m + self.t_e_s[i][cd]
                q_m = q_m / self.n_day
                t_e_m = t_e_m / self.n_day

                # calculate parameters of linear curve
                a_1 = 0                                             # parameter
                a_2 = 0
                for i in range(0,self.n_day):
                    a_1 = a_1 + ((self.t_e_s[i][cd] - t_e_m) * (self.q_s[i][cd] - q_m))
                    a_2 = a_2 + (self.t_e_s[i][cd] - t_e_m) ** 2
                try:                                                # prevent ZeroDivision
                    m_c = a_1 / a_2                                 # slope of curve
                except:
                    m_c = 0
                n_c = q_m - m_c * t_e_m                             # absolute element curve

                # calculate predicted heat values
                q_1day = m_c * t_e_1day + n_c
                q_2day = m_c * t_e_2day + n_c

        return (q_write, q_1day, q_2day, m_c, n_c)

#=======================================================================

    def run_to_save_data(self,t_act,q_act,t_e_act):
        # changes - Wojtek Kozak
        """ saves data from simulation and reports with (q_write == True) as soon as the prediction is possible """
        # t_act - actual time in hours
        # q_act - actual heat load of the system in W or kW ? - does not matter
        # t_e_act - ambient air temperature in grad Celcius
        # t_e_1day - ambient air temperature one day before the actual time in grad Celcius
        # t_e_2day - ambient air temperature two days before the actual time in grad Celcius
        # eps - precision of time calculation in hours

        #print(t_act,q_act,t_e_act)
        # save values from reading
        self.q = self.q + q_act
        self.t_e = self.t_e + t_e_act
        self.count = self.count + 1
        self.c_tot = self.c_tot + 1
        # calculate averages and save the value for the last full hour
        if ((t_act / self.dt) - (t_act // self.dt)) < self.eps:
        #if(t_act >= self.act_hour):
            self.act_hour = self.act_hour + self.dt
            # fill array
            # calculate day time
            day = t_act // 24          # number of the day
            t_day = t_act - day * 24   # hour of the day
            # add value to array
            cd = int(t_day / self.dt)                       # counter time in day
            self.q = self.q / self.count
            self.t_e = self.t_e / self.count                # average temperature for time period

            self.q_s[self.n_day - 1][cd] = self.q           # array for heat
            self.t_e_s[self.n_day - 1][cd] = self.t_e       # array for external temperature

            #G.write('\n t_act = {}; cd = {}; t_day = {}; day = {}'.format(t_act, cd, t_day, day))

            #G.write('\n q_write = {}'.format(self.q_write))
            #G.write('\nself.t_e = {}'.format(self.t_e_s))
            #G.write('\nself.q_s = {}'.format(self.q_s))

            # ----- fill and shift array ----------------------------------------------------------------------

            # shift matrix after a day - does it really work?
            if ((t_day < self.eps) and (self.c_tot > 1)):
                self.c_day = self.c_day + 1
                self.q_s=self.q_s[1:] + self.q_s[0:1]
                self.t_e_s=self.t_e_s[1:] + self.t_e_s[0:1]
                #print("SHIFT")
                #G.write("\n\n SHIFT")
                #G.write('\nt_act = {}; day = {}; t_day = {}'.format(t_act,day,t_day))
                #G.write('\n q_write = {}'.format(self.q_write))
                #G.write('\nself.t_e = {}'.format(self.t_e_s))
                #G.write('\nself.q_s = {}'.format(self.q_s))


            #print(self.c_tot)
            #print(self.q_s)
            #print(self.t_e_s)

            # reset values for time period integration
            self.t_e = 0
            self.q = 0
            self.count = 0

            # ------ perform prediction -----------
            if self.c_day >= self.n_day:                            # start if enough data is saved
                self.q_write = True
                #G.write('\n \n Q_WRITE')
                #G.write('\n q_write = {}'.format(self.q_write))
                #G.write('\nself.t_e = {}'.format(self.t_e_s))
                #G.write('\nself.q_s = {}'.format(self.q_s))
        #return self.q_write
        # end run_to_save_data

#=======================================================================

    def run_to_predict_thermal_loads(self, weather_pred, output_horizon_in_h, output_resolution_in_s, t_act, actual_time, start_datetime, start_sim_inh, end_sim_inh, fnr):
        """ calculates the list of predicted thermal loads of the system in W"""
        t_a_min = 200.0
        thermal_load_1 = []
        thermal_load_prediction = []
        horizont_time = actual_time + timedelta(hours=output_horizon_in_h)
        act_time_1 = actual_time
        act_time_2 = actual_time
        #while(actual_time <= horizont_time):
        n_steps = int(output_horizon_in_h // self.dt)
        #print('actual_time = {}; horizont = {} h ; Zeitschritt = {} h ; n_steps = {}'.format(actual_time, horizont_time, self.dt, n_steps))
        for step in range(n_steps):
            # read ambient temperature from the weather file
            act_time_1 = act_time_1 + timedelta(hours=self.dt)
            simtime_in_h = ((act_time_1 - start_datetime).total_seconds() / 3600.0) + start_sim_inh  # simulationstime in h
            day = t_act // 24          # number of the day
            t_day = t_act - day * 24   # hour of the day
            # add value to array
            #cd = int(t_day / self.dt)                       # counter time in day
            # create output list
            t_day = t_day + step * self.dt
            if (t_day >= 24.0):
                t_day = t_day - 24.0
            cd = int(t_day / self.dt)                       # counter time in day
            # calculate average value from past days
            q_m = 0
            t_e_m = 0
            for i in range(0,self.n_day):
                q_m = q_m + self.q_s[i][cd]
                t_e_m = t_e_m + self.t_e_s[i][cd]
            q_m = q_m / self.n_day
            t_e_m = t_e_m / self.n_day

            # calculate parameters of linear curve
            a_1 = 0                                             # parameter
            a_2 = 0
            for i in range(0,self.n_day):
                a_1 = a_1 + ((self.t_e_s[i][cd] - t_e_m) * (self.q_s[i][cd] - q_m))
                a_2 = a_2 + (self.t_e_s[i][cd] - t_e_m) ** 2
            try:                                                # prevent ZeroDivision
                m_c = a_1 / a_2                                 # slope of curve
            except:
                m_c = 0
            n_c = q_m - m_c * t_e_m                             # absolute element curve

            # determine ambient temperature from weather prediction
            #t_e_1day = utils.interpolate_value_from_list_of_dicts(value1, tag_of_val1, list_of_dicts, tag_of_result)
            t_e_1day = utils.interpolate_value_from_list_of_dicts(simtime_in_h, 'time_in_h', weather_pred, 'temp_in_C')

            # calculate predicted heat values
            q_1day = m_c * t_e_1day + n_c
                
            q_pred = q_1day
            thermal_load_1.append({'date':act_time_1, 'time_in_h': simtime_in_h, 'q_in_W': q_pred})
        
        #n_steps = int(output_horizon_in_h * 3600.0 // output_resolution_in_s)
        #n_day = int(output_horizon_in_h // self.n_values)
        #n_steps = self.n_values * n_day
        n_steps = int((output_horizon_in_h * 3600.0) // output_resolution_in_s)
        for step in range(n_steps):
            act_time_2 = act_time_2 + timedelta(seconds=output_resolution_in_s)
            simtime_in_h = ((act_time_2 - start_datetime).total_seconds() / 3600.0) + start_sim_inh  # simulationstime in h
            q_pred = utils.interpolate_value_from_list_of_dicts(simtime_in_h, 'time_in_h', thermal_load_1, 'q_in_W')
            thermal_load_prediction.append({'date':act_time_2, 'time_in_h': simtime_in_h, 'q_in_W': q_pred})
            #thermal_load_prediction.append({act_time_2: q_pred})
            #print('actual_time = {}; simtime in h = {}; q_pred = {}'.format(act_time_2, simtime_in_h, q_pred))
        if(self.dbg > 0):
            H = open("./thermal_pred_"+str(fnr)+".dat","w")
            H.write(' original \n')
            H.write(' index ; time stamp ; time in h ; thermal load in W\n')
            for idx,elem in enumerate(thermal_load_1):
                H.write('{}  {}  {:11.3f}  {:9.2f}\n'.format(idx,elem['date'],elem['time_in_h'],elem['q_in_W']))
            H.write(' adapted \n')
            H.write(' index ; time stamp ; time in h ; thermal load in W\n')
            for idx,elem in enumerate(thermal_load_prediction):
                H.write('{}  {}  {:11.3f}  {:9.2f}\n'.format(idx,elem['date'],elem['time_in_h'],elem['q_in_W']))
            H.close()
        return thermal_load_prediction
        # end run_to_predict_thermal_loads

#=======================================================================

    def run_to_predict_electric_loads(self, actual_time, output_horizon_in_h, start_datetime, start_sim_inh, fnr):
        # returns predicted electrical load in W
        #if(utils.it_is_summer(actual_time)):
        #    # summer time from 15.05 to 14.09
        #    season = self.el_data['summer time']
        #elif(utils.it_is_winter(actual_time)):
        #    # winter time from 1.11 to 20.03
        #    season = self.el_data['winter time']
        #else:
        #    # transition period from 21.03 to 14.05 and from 15.09 to 31.10
        #    season = self.el_data['transition period']
        #if(actual_time.isoweekday() in range(1, 5)):
        #    data_set = season['workday']
        #elif(actual_time.isoweekday() == 6):
        #    data_set = season['Saturday']
        #else:
        #    data_set = season['Sunday']
        ##print('data_set = {}'.format(data_set))

        act_time_1 = actual_time
        act_time_2 = actual_time

        el_load_pred1 = []
        # get the data_set of expected loads that starts with the time slot relevant for the actual_time
        data_set = utils.get_slp_data_set(actual_time, self.el_data, self.slp_resolution_in_s)

        for index, elem in enumerate(data_set):
            act_time_1 = act_time_1 + timedelta(seconds=self.slp_resolution_in_s)
            simtime_in_h = ((act_time_1 - start_datetime).total_seconds() / 3600.0) + start_sim_inh  # simulationstime in h
            el_load_pred1.append({'date': act_time_1, 'time_in_h': simtime_in_h, 'q_in_W': 1000.0*elem})     # load in W
            
        #print('actual time = {}'.format(actual_time))
        #print(el_load_pred1)
        # interpolationof the electrical load onto the required resolution of the energy vector
        electric_load_prediction = []
        
        n_steps = int(self.output_horizon_in_h * 3600.0 // self.output_resolution_in_s)
        #print('self.slp_resolution_in_s = {}'.format(self.output_resolution_in_s))
        for step in range(n_steps):
            act_time_2 = act_time_2 + timedelta(seconds=self.output_resolution_in_s)
            simtime_in_h = ((act_time_2 - start_datetime).total_seconds() / 3600.0) + start_sim_inh  # simulationstime in h
            q_pred = utils.interpolate_value_from_list_of_dicts(simtime_in_h, 'time_in_h', el_load_pred1, 'q_in_W')
            electric_load_prediction.append({'date': act_time_2, 'time_in_h': simtime_in_h, 'q_in_W': q_pred})
            #electric_load_prediction.append({act_time_2: q_pred})
        
        
        if(self.dbg > 0):
            H = open("./electrc_pred_"+str(fnr)+".dat","w")
            H.write(' original \n')
            H.write(' index ; time stamp ; time in h ; electric load in W\n')
            for idx,elem in enumerate(el_load_pred1):
                H.write('{}  {}  {:11.3f}  {:9.2f}\n'.format(idx,elem['date'],elem['time_in_h'],elem['q_in_W']))
            H.write(' adapted \n')
            H.write(' index ; time stamp ; time in h ; electric load in W\n')
            for idx,elem in enumerate(electric_load_prediction):
                H.write('{}  {}  {:11.3f}  {:9.2f}\n'.format(idx,elem['date'],elem['time_in_h'],elem['q_in_W']))
            H.close()
        return electric_load_prediction
        # end run_to_predict_electric_loads

#=======================================================================

    def get_q_write(self):
        # changes - Wojtek Kozak
        return self.q_write

#=======================================================================

    def predict_loads(self):
        # changes - Wojtek Kozak
        # calculate average value from past days
        q_m = 0
        t_e_m = 0
        for i in range(0,self.n_day):
            q_m = q_m + self.q_s[i][cd]
            t_e_m = t_e_m + self.t_e_s[i][cd]
        q_m = q_m / self.n_day
        t_e_m = t_e_m / self.n_day
        # calculate parameters of linear curve
        a_1 = 0                                             # parameter
        a_2 = 0
        for i in range(0,self.n_day):
            a_1 = a_1 + ((self.t_e_s[i][cd] - t_e_m) * (self.q_s[i][cd] - q_m))
            a_2 = a_2 + (self.t_e_s[i][cd] - t_e_m) ** 2
        try:                                                # prevent ZeroDivision
            m_c = a_1 / a_2                                 # slope of curve
        except:
            m_c = 0
        n_c = q_m - m_c * t_e_m                             # absolute element curve

        # calculate predicted heat values
        q_1day = m_c * t_e_1day + n_c
        q_2day = m_c * t_e_2day + n_c
        return (q_1day, q_2day)

    # ==================================================================

    def max_pred_temp_supply_heating_sys(self, t_a_min):
        # returns maximal expected supply temperature in °C of the heating system.
        #DeltaT = self.design_supply_temp - self.design_return_temp
        DeltaT = self.hk_tv - self.hk_tr
        #DTmn = 0.5 * (self.design_supply_temp + self.design_return_temp) - self.design_indoor_temp
        DTmn = 0.5 * (self.hk_tv + self.hk_tr) - self.hk_ti
        #phi = (self.design_indoor_temp - ambient_temperature) / (self.design_indoor_temp - self.design_ambient_temp)
        phi = (self.hk_ti - t_a_min) / (self.hk_ti - self.hk_ta)
        if(phi<0.0):
            phi=0.0
        #phi2 = phi ** (1.0 / (1.0 + self.n_coefficient))
        phi2 = phi ** (1.0 / (1.0 + self.hk_n))
        #self.supply_temp = self.design_indoor_temp + 0.5 * phi * DeltaT + phi2 * DTmn
        t_sup_max = self.hk_ti + 0.5 * phi * DeltaT + phi2 * DTmn
        return t_sup_max
        # end max_pred_temp_supply_heating_sys

    # ==================================================================

    def get_max_temp_of_chp(self):
        # returns the maximal expected temperature of water coming from CHP unit to storage tank
        print('PRED: get_max_temp_of_chp')
        return self.chp_tmax
        # end get_max_temp_of_chp

    # ==================================================================

    def get_out_temp_of_gb(self):
        # returns the maximal expected temperature of water coming from gas boiler into storage tank
        print('PRED: get_out_temp_of_gb')
        return self.gb_tmax
        # end get_out_temp_of_gb


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

    # obsolete function - to delete after check
    def get_temp_profile_in_storage(self):
        #returns temperature profile from storage tank
        return self.rvk.get_temp_profile_in_storage()
        # end get_temp_profile_in_storage

    # ==================================================================

    def update_temp_profile_tank(self, m_st, m_chp, m_gb, t_chp_out, t_gb_out, t_prof, vol, dtau, t_a_pred):
        p_in_MPa = utils.get_pressure_in_MPa()
        calc_opt = utils.get_calc_option()
        t_mix = (m_chp * t_chp_out + m_gb * t_gb_out) / m_st
        nl = len(t_prof)
        wyn = []
        #
        if(m_st > 0.0):   # flow down from above (from 20 to 0)
            for idx,elem in enumerate(t_prof):
                t_out = t_prof[idx]
                cp_out = utils.cp_fluid_water(t_out, p_in_MPa, calc_opt)
                rho = utils.rho_fluid_water(t_out, p_in_MPa, calc_opt)
                mass = rho * vol
                if(idx == (nl-1)):
                    t_in = t_mix
                else:
                    t_in = t_prof[idx + 1]
                cp_in = utils.cp_fluid_water(t_in, p_in_MPa, calc_opt)
                wyn.append(m_st * dtau * (t_in * cp_in - t_out * cp_out)/(mass * cp_out))
        #
        else:             # flow up from below (from 0 to 20)
            for idx,elem in enumerate(t_prof):
                t_out = t_prof[idx]
                cp_out = utils.cp_fluid_water(t_out, p_in_MPa, calc_opt)
                rho = utils.rho_fluid_water(t_out, p_in_MPa, calc_opt)
                mass = rho * vol
                if(idx == 0):
                    t_in = self.rvk.get_return_temperature(t_a_pred)
                else:
                    t_in = t_prof[idx + 1]
                cp_in = utils.cp_fluid_water(t_in, p_in_MPa, calc_opt)
                wyn.append(m_st * dtau * (t_in * cp_in - t_out * cp_out)/(mass * cp_out))
        #
        return wyn
        # end update_temp_profile_tank

    # ==================================================================

    def calc_min_el_production(self, minp_Q_st_inp, minp_Q_st_extr, pred_el_kWh, pred_th_kWh, t_prof, t_a_pred):
        # 0. read the inputs
        Q_st_inp = minp_Q_st_inp
        Q_st_extr = minp_Q_st_extr
        Q_pred_th = pred_th_kWh
        Q_pred_el = pred_el_kWh
        p_in_MPa = utils.get_pressure_in_MPa()
        calc_opt = utils.get_calc_option()
        t_chp_in = t_prof[0]
        cp_chp_in = utils.cp_fluid_water(t_chp_in, p_in_MPa, calc_opt)
        t_chp_out = self.get_max_temp_of_chp()
        cp_chp_out = utils.cp_fluid_water(t_chp_out, p_in_MPa, calc_opt)
        t_gb_in = t_chp_in
        cp_gb_in = cp_chp_in
        t_gb_out = self.get_out_temp_of_gb()
        cp_gb_out = utils.cp_fluid_water(t_chp_out, p_in_MPa, calc_opt)
        m_chp = self.mstr_chp   # in kg/s
        m_gb = self.mstr_gb     # in kg/s
        # 1. It is assumed that all appliances are turned off
        Q_chp_th = 0.0
        Q_chp_el = 0.0
        Q_gb = 0.0
        Q_rod_max = self.qmax_rod_el * self.output_resolution_in_s / 3600.0  # in kWh
        Q_rod_el = 0.0
        # 
        # HEATING ROD
        # if thermal input from heating rod will not exceed the tank's capacity or can be used up by predicted consumption
        # or if storage tank is empty and cannot cover the predicted demand
        if((Q_rod_max <= (Q_st_inp + Q_pred_th)) or (Q_st_extr < Q_pred_th)): # turn the heating rod on
            Q_rod_th = min(Q_rod_max, Q_st_inp + Q_pred_th)
        else:                                   # turn the heating rod off
            Q_rod_th = 0.0
        #
        # GAS BOILER
        # if heat production of rod and reserve in tank are too small to cover predicted load 
        if(Q_st_extr + Q_rod_th < Q_pred_th):   # turn the gas boiler on
            Q_gb = min(self.output_resolution_in_s * m_gb * (t_gb_in*cp_gb_in - t_gb_out*cp_gb_out)/3600000.0, Q_st_inp + Q_pred_th - Q_rod_th)
        else:                                   # turn the gas boiler off
            Q_gb = 0.0
        #
        # CHP UNIT
        # if heat production of rod, boiler and reserve in tank are too small to cover predicted demand
        if(Q_st_extr + Q_rod_th + Q_gb < Q_pred_th):
            Q_chp_th = min(self.output_resolution_in_s * m_chp * (t_chp_in*cp_chp_in - t_chp_out*cp_chp_out)/3600000.0, Q_st_inp + Q_pred_th - Q_rod_th - Q_gb)
        else:
            Q_chp_th = 0.0
        #
        # calculate electric production
        Q_chp_el = self.eps_el_chp * Q_chp_th / self.eps_th_chp
        #Q_chp_el = self.rvk.get_el_prod_kWh(Q_chp_th)
        Q_rod_el = Q_rod_th
        # balance of the heat storage tank
        Delta_Qst = Q_chp_th + Q_gb + Q_rod_th - Q_pred_th
        Q_st_inp = Q_st_inp - Delta_Qst
        Q_st_extr = Q_st_extr + Delta_Qst
        # mass balance of the heat storage tank
        m_st = m_chp + m_gb - self.mstr_hk
        # temperature profile in the heat storage tank
        #vol = self.rvk.get_slice_vol()
        t_prof = self.update_temp_profile_tank(m_st, m_chp, m_gb, t_chp_out, t_gb_out, t_prof, self.slice_volume, self.output_resolution_in_s, t_a_pred)
        Q_ev_min = Q_chp_el - Q_rod_el - Q_pred_el
        return (Q_ev_min, Q_st_inp, Q_st_extr, Q_pred_el, Q_rod_el, Q_chp_el, t_prof)
        #return ((- pred_el_kWh - rod_el_tank + chp_el_prod), minp_thrm_can_be_put_in, minp_Q_st_extr, pred_el_kWh, rod_el_tank, chp_el_prod)
         
        # end calc_min_el_production

    # ==================================================================

    def calc_max_el_production(self, maxp_Q_st_inp, maxp_Q_st_extr, pred_el_kWh, pred_th_kWh, t_prof, t_a_pred):
        # 0. read the inputs
        Q_st_inp = maxp_Q_st_inp
        Q_st_extr = maxp_Q_st_extr
        Q_pred_th = pred_th_kWh
        Q_pred_el = pred_el_kWh
        p_in_MPa = utils.get_pressure_in_MPa()
        calc_opt = utils.get_calc_option()
        t_chp_in = t_prof[0]
        cp_chp_in = utils.cp_fluid_water(t_chp_in, p_in_MPa, calc_opt)
        t_chp_out = self.get_max_temp_of_chp()
        cp_chp_out = utils.cp_fluid_water(t_chp_out, p_in_MPa, calc_opt)
        t_gb_in = t_chp_in
        cp_gb_in = cp_chp_in
        t_gb_out = self.get_out_temp_of_gb()
        cp_gb_out = utils.cp_fluid_water(t_chp_out, p_in_MPa, calc_opt)
        m_chp = self.mstr_chp   # in kg/s
        m_gb = self.mstr_gb     # in kg/s
        # 1. It is assumed that all appliances are turned off
        Q_chp_max = self.output_resolution_in_s * m_chp * (t_chp_in*cp_chp_in - t_chp_out*cp_chp_out)/3600000.0
        Q_chp_th = 0.0
        Q_chp_el = 0.0
        Q_gb = 0.0
        Q_rod_th = 0.0
        Q_rod_el = 0.0
        # 
        # 2. calculate thermal production of all components
        # CHP UNIT
        # if thermal input from CHP unit will not exceed the tank's capacity or can be used up by predicted consumption
        # or if storage tank is empty and cannot cover the predicted demand
        if((Q_chp_max <= (Q_st_inp + Q_pred_th)) or (Q_st_extr < Q_pred_th)): # turn the CHP unit on
            Q_chp_th = min(Q_chp_max, Q_st_inp + Q_pred_th)
        else:                                   # turn the CHP unit off
            Q_chp_th = 0.0
        #
        # GAS BOILER
        # if heat production of CHP and reserve in tank are too small to cover predicted load 
        if(Q_st_extr + Q_chp_th < Q_pred_th):   # turn the gas boiler on
            Q_gb = min(self.output_resolution_in_s * m_gb * (t_gb_in*cp_gb_in - t_gb_out*cp_gb_out)/3600000.0, Q_st_inp + Q_pred_th - Q_chp_th)
        else:                                   # turn the gas boiler off
            Q_gb = 0.0
        #
        # HEATING ROD
        # if heat production of CHP, boiler and reserve in tank are too small to cover predicted demand
        if(Q_st_extr + Q_chp_th + Q_gb < Q_pred_th):
            Q_rod_th = min(self.qmax_rod_el * self.output_resolution_in_s / 3600.0, Q_st_inp + Q_pred_th - Q_chp_th - Q_gb)
        else:
            Q_rod_th = 0.0
        #
        # 3. calculate electric production and/or consumption
        Q_chp_el = self.eps_el_chp * Q_chp_th / self.eps_th_chp   # CHP unit
        #Q_chp_el = self.rvk.get_el_prod_kWh(Q_chp_th)   # CHP unit
        Q_rod_el = Q_rod_th                             # heating rod
        # 4. balance of the heat storage tank
        Delta_Qst = Q_chp_th + Q_gb + Q_rod_th - Q_pred_th
        Q_st_inp = Q_st_inp - Delta_Qst
        Q_st_extr = Q_st_extr + Delta_Qst
        # 5. mass balance of the heat storage tank
        m_st = m_chp + m_gb - self.mstr_hk
        # 6. temperature profile in the heat storage tank
        #vol = self.rvk.get_slice_vol()
        t_prof = self.update_temp_profile_tank(m_st, m_chp, m_gb, t_chp_out, t_gb_out, t_prof, self.slice_volume, self.output_resolution_in_s, t_a_pred)
        Q_ev_max = Q_chp_el - Q_rod_el - Q_pred_el
        return (Q_ev_max, Q_st_inp, Q_st_extr, Q_pred_el, Q_rod_el, Q_chp_el, t_prof)
        #
        #return ((chp_el_prod - pred_el_kWh), maxp_Q_st_inp, maxp_Q_st_extr, chp_el_prod, pred_el_kWh)
        # end calc_max_el_production

    # ==================================================================

    def predict_energy_vector(self, weather_pred, t_act, actual_time, start_datetime, start_sim_inh, end_sim_inh, output_horizon_in_h, output_resolution_in_s, last_t_profile, fnr):
        print(' EV: got into energy vector preparation')
        thermal_load_prediction = self.run_to_predict_thermal_loads(weather_pred, output_horizon_in_h, output_resolution_in_s, t_act, actual_time, start_datetime, start_sim_inh, end_sim_inh, fnr)
        print(' EV: got thermal load pred')
        electric_load_prediction = self.run_to_predict_electric_loads(actual_time, output_horizon_in_h, start_datetime, start_sim_inh, fnr)
        print(' EV: got electric load pred')
        min_electric_prod = []
        max_electric_prod = []
        # calc storage space left in tank
        print(' EV: got self.get_max_temp_of_chp() = {}'.format(self.get_max_temp_of_chp()))
        #minp_thrm_can_be_put_in = self.thermal_energy_that_can_be_put_in_storage(self.get_max_temp_of_chp())  # in kWh
        minp_Q_st_inp = self.thermal_energy_that_can_be_put_in_storage(self.get_max_temp_of_chp(), last_t_profile)  # in kWh
        print(' EV: got minp_Q_st_inp = {}'.format(minp_Q_st_inp))
        #maxp_thrm_can_be_put_in = minp_Q_st_inp                           # in kWh
        maxp_Q_st_inp = minp_Q_st_inp                                      # in kWh
        # calc heating energy left in tank
        t_a_min = utils.min_val_in_list_of_dicts('temp_in_C', weather_pred)  # minimal predicted ambient temperature in °C
        print(' EV: got t_a_min = {}'.format(t_a_min))
        tv_max = self.max_pred_temp_supply_heating_sys(t_a_min)                # maximal expected supply temperature in °C
        print(' EV: got tv_max = {}'.format(tv_max))
        #minp_thrm_left_in_tank = self.thermal_energy_that_can_be_got_from_storage(tv_max)
        minp_Q_st_extr = self.thermal_energy_that_can_be_got_from_storage(tv_max, last_t_profile)
        print(' EV: got minp_Q_st_extr = {}'.format(minp_Q_st_extr))
        #maxp_thrm_left_in_tank = minp_Q_st_extr
        maxp_Q_st_extr = minp_Q_st_extr
        # temperature profile
        minp_t_prof = last_t_profile
        print(' EV: got minp_t_prof = {}'.format(minp_t_prof))
        maxp_t_prof  = minp_t_prof
        # debugging
        # time management
        time_stamp = actual_time + timedelta(hours=self.output_horizon_in_h)
        # for each timestep until the time horizont do
        ii = 0
        print('\n\nGE GE GE\n\n')
        if(self.dbg > 0):
            G = open("./debug_"+str(fnr)+".dat","w")
            G.write(' original \n')
            G.write(' act_date  act_time  horizont_date  horizont_time ')
            G.write(' index  minp_Q_st_inp  maxp_Q_st_inp  minp_Q_st_extr  maxp_Q_st_extr ')
            G.write(' pred_el_kWh1  rod_el_tank1  chp_el_prod2  pred_el_kWh2  \n')
            #G.close()
            H = open("./bsp_profile_"+str(fnr)+".dat","w")
            H.write(' t_a,min = {} \n'.format(t_a_min))
            H.write(' tv_max = {} \n'.format(tv_max))
            H.write(' minp_Q_st_extr = {} \n'.format(minp_Q_st_extr))
            H.write(' maxp_Q_st_inp = {} \n'.format(maxp_Q_st_inp))
            H.write(' t_storage = {} \n'.format(last_t_profile))
            H.write(' {} t_storage = {} \n'.format(type(minp_t_prof), minp_t_prof))
            H.close()
            print('\n\n\n\n temperature profile of storage tank saved \n\n\n\n')
        kk = 0
        energy_vector = []
        while (actual_time < time_stamp):
            kk = kk+1
            # time management
            actual_time = actual_time + timedelta(seconds=self.output_resolution_in_s)
            print('EV: {}; actual_time = {}, '.format(kk,actual_time))
            t_a_pred = utils.get_tab_from_list_of_dicts('date', actual_time, 'temp_in_C', weather_pred, timedelta(seconds=self.output_resolution_in_s), True, ii) * self.output_resolution_in_s / (3600.0 * 1000.0) # in kWh
            print('EV: t_a_pred = {}, '.format(t_a_pred))
            pred_el_kWh = utils.get_tab_from_list_of_dicts('date', actual_time, 'q_in_W', electric_load_prediction, timedelta(seconds=self.output_resolution_in_s), True, ii) * self.output_resolution_in_s / (3600.0 * 1000.0) # in kWh
            print('EV: pred_el_kWh = {}, '.format(pred_el_kWh))
            pred_th_kWh = utils.get_tab_from_list_of_dicts('date', actual_time, 'q_in_W', thermal_load_prediction, timedelta(seconds=self.output_resolution_in_s), True, ii) * self.output_resolution_in_s / (3600.0 * 1000.0)   # in kWh
            print('EV: pred_th_kWh = {}, '.format(pred_th_kWh))
            # calc energy vector
            (minp_ev, minp_Q_st_inp, minp_Q_st_extr, pred_el_kWh1, rod_el_tank1, chp_el_prod1, minp_t_prof) = self.calc_min_el_production(minp_Q_st_inp, minp_Q_st_extr, pred_el_kWh, pred_th_kWh, minp_t_prof, t_a_pred)
            print('EV: minp_ev = {}, '.format(minp_ev))
            (maxp_ev, maxp_Q_st_inp, maxp_Q_st_extr, pred_el_kWh2, rod_el_tank2, chp_el_prod2, maxp_t_prof) = self.calc_max_el_production(maxp_Q_st_inp, maxp_Q_st_extr, pred_el_kWh, pred_th_kWh, maxp_t_prof, t_a_pred)
            print('EV: maxp_ev = {}, '.format(maxp_ev))
            min_electric_prod.append({'time stamp' : actual_time, 'P_avg_el_in_kWh' : minp_ev})
            max_electric_prod.append({'time stamp' : actual_time, 'P_avg_el_in_kWh' : maxp_ev})
            if(self.dbg > 0):
                G.write('{}  {}  '.format(actual_time,time_stamp))
                G.write('{}  {:9.3f}  '.format(ii,minp_Q_st_inp))
                G.write('{:9.3f}  {:11.3f}'.format(maxp_Q_st_inp, minp_Q_st_extr))
                G.write('{:11.3f}  {}  '.format(maxp_Q_st_extr, pred_el_kWh1))
                G.write('{}  {}  '.format(rod_el_tank1, chp_el_prod1))
                G.write('{}  {}\n'.format(chp_el_prod2, pred_el_kWh2))
            ii = ii + 1
            min_W = minp_ev *3600.0 * 1000.0 / self.output_resolution_in_s   # W = kWh * 1000W/kW * 3600s/h / s
            max_W = maxp_ev *3600.0 * 1000.0 / self.output_resolution_in_s   # W = kWh * 1000W/kW * 3600s/h / s
            simtime_in_h = ((actual_time - start_datetime).total_seconds() / 3600.0) + start_sim_inh  # simulationstime in h
            energy_vector.append({'time stamp': actual_time, 'time_in_h' : simtime_in_h, 'P_el_min_in_W': min_W , 'P_el_max_in_W': max_W})
            #print('finished {}'.format(ii))
        #energy_vector = {'time stamp': actual_time, 'P_el_min_in_W': min_electric_prod, 'P_el_max_in_W': max_electric_prod}
        if(self.dbg > 0):
            G.close()
        if(self.dbg > 0):
            H = open("./energy_vec_"+str(fnr)+".dat","w")
            H.write(' original \n')
            H.write('index  "time stamp"  "time stamp"  "time in h"  "min production W"  "max production W" "pred_el_1"  "rod_el_1"  "chp_el_1"  "chp_el_2"  "pred_el_2"\n')
            for idx,elem in enumerate(energy_vector):
                H.write('{}  {}  {:9.3f}  {:11.3f}  {:11.3f}\n'.format(idx,elem['time stamp'], elem['time_in_h'],elem['P_el_min_in_W'],elem['P_el_max_in_W']))
            H.close()
        print('X')
        #sleep(15)
        return energy_vector
        # end predict_energy_vector

    # ==================================================================
    def initialize_crate_db_connection(self, crdb_endpoint, crdb_endpoint_add, crdb_username, crdb_direct_com):
        """ initializes connection and returns connection cursor """
        self.crdb_direct_com = crdb_direct_com
        if crdb_direct_com:
            # direct connection to crate db - returns cursor
            connection = client.connect(crdb_endpoint, timeout=50, error_trace=True, username=crdb_username)
            self.cursor = connection.cursor()
            print('initialize_crate_db_connection: connection = {}, cursor = {}'.format(connection, self.cursor))
        else:
            # indirect connection to crate db via Orion / quantum leap - define data needed for request
            self.request_endpoint = '{}{}'.format(crdb_endpoint, crdb_endpoint_add)
            print('initialize_crate_db_connection: request endpoint = {}'.format(self.request_endpoint))
            
        # end initialize_crate_db_connection

    # ==================================================================
    def update_heat_consumption_from_crate(self, actual_time, time_step_in_s, arch_option_1, fnr):
        """ 
        # gets data from crate db
        # calculates from it the heat flows needed by Martin's function 
        # and passes them as result 
        """
        # define period of time for which data is to be requested
        if(arch_option_1):
            #
            horizont_in_s = time_step_in_s
        else:
            # 
            horizont_in_s = 24.0 * self.n_day * 3600.0
        start_time = actual_time - timedelta(seconds=horizont_in_s)  # get data for the last self.n_day days
        end_time = actual_time + timedelta(seconds=(0.5 * 3600.0 * self.dt)) # until the current time - add offset for newest data coming in

        #start_time = utils.extract_time_stamp_from_string('2020-02-09T17:11:28.656490')
        #end_time = utils.extract_time_stamp_from_string('2020-02-09T17:13:04.656490')
        stt = start_time.replace(tzinfo=timezone.utc).timestamp()
        ett = end_time.replace(tzinfo=timezone.utc).timestamp()
        # workaround for problems with saving utc timestamp in iteration - aim is to replace next two lines with: start_time=stt; end_time=ett
        #start_time = utils.build_small_utc_time_from_full_one(stt)
        #end_time = utils.build_small_utc_time_from_full_one(ett)
        start_time = stt  # utc
        end_time = ett
        selects = "SELECT turnover_time_of_one_seg_in_h,t30_ambientairtemperature,t21_domestichotwater,t22_domesticcoldwater,v01_colddrinkingwater,t25_supply_heatingcircuit,t24_return_heatingcircuit,v02_heatingcircuit,mass_flow_dhw,mass_flow_heating_water,elctric_heater_status,turnover_time_of_one_seg_in_h FROM mtopeniot.etrvk"
        wheres = "WHERE turnover_time_of_one_seg_in_h>={} AND turnover_time_of_one_seg_in_h<={}".format(start_time, end_time)
        orders = "ORDER BY turnover_time_of_one_seg_in_h"
        sqlquery = "{} {} {}".format(selects, wheres, orders)
        
        p_in_MPa = utils.get_pressure_in_MPa()
        calc_opt = utils.get_calc_option()
        
        if(self.crdb_direct_com):
        # getting data directly from crate db
            #horizont_in_s = 120.0
            avg_period_in_s = 3600.0 * self.dt
            #start_time = actual_time - timedelta(seconds=(horizont_in_s+0.5*self.dt*3600.0))
            avg_time = start_time + timedelta(seconds=avg_period_in_s)
            #
            if(self.dbg == 2):
                print('\n\n\n\n\n\n\n\n\n\n\n ----------- WAIT FOR CRATE --------------- \n\n\n\n\n\n\n\n\n')
                #time.sleep(5)
                print('\n\n\n\n\n\n\n\n\n\n\n -------------- GET DATA ------------------ \n\n\n\n\n\n\n\n\n')
                H = open("./crate_"+str(fnr)+".dat","w")
                H.write(' usable (within given time bounds) data received from crate db  \n')
                H.write(' actual_time = {} / {} utc\n'.format(actual_time,actual_time.replace(tzinfo=timezone.utc).timestamp()))
                H.write(' avg_period_in_s = {} / {} timedelta\n'.format(avg_period_in_s,timedelta(seconds=avg_period_in_s)))
                H.write(' rec used_rec raw_utc time_stamp actual_time \n')
                G = open("./crate_all_"+str(fnr)+".dat","w")
                G.write(' all data received from crate db \n')
                G.write(' actual_time = {} / {} utc\n'.format(actual_time,actual_time.replace(tzinfo=timezone.utc).timestamp()))
                G.write(' avg_period_in_s = {} / {} timedelta\n'.format(avg_period_in_s,timedelta(seconds=avg_period_in_s)))
                G.write(' rec rec_used raw_utc time_stamp actual_time \n')
                rec_nr = 0
                used_rec = 0
            # 
            # sql query to the data base 
            self.cursor.execute(sqlquery)
            result = self.cursor.fetchone()
            if(self.dbg == 2):
                H.write('start time = {}  ({}); end time = {} ({}); period in s = {}\n'.format(start_time, start_time.replace(tzinfo=timezone.utc).timestamp(), start_time + timedelta(seconds=horizont_in_s), (start_time + timedelta(seconds=horizont_in_s)).replace(tzinfo=timezone.utc).timestamp(), timedelta(seconds=horizont_in_s)))
                H.flush()
            while result != None:
                mytstamp = self.time_and_one_record_from_db(result, p_in_MPa, calc_opt)
                if(self.dbg == 2):
                    #print('data from CRATE: time stamp = {}  ;  {}  ; {}  ; {}'.format(mytstamp, xutc, result[0], type(result[0])))
                    rec_nr = rec_nr + 1
                    #G.write('{}  {}  {}  {}  {}\n'.format(rec_nr, used_rec, mytstamp, xutc, result))
                    G.write('{}  {}  {}  {}  {}  {}  {}  {}  {}\n'.format(rec_nr, used_rec, mytstamp, stt, mytstamp, ett, (xutc >= stt), (xutc <= ett), result))
                    G.flush()
                actual_time = start_time
                if(self.dbg == 2):
                    used_rec = used_rec + 1
                    H.write('{}  {}  {}  {}  {}  {}  {}  {}  {}\n'.format(rec_nr, used_rec, mytstamp, stt, mytstamp, ett, (xutc >= stt), (xutc <= ett), result))
                    H.flush()
                    #print('x = {}  used x = {}'.format(rec_nr, used_rec))
                    #print(' used data ------------------------ time stamp = {}'.format(mytstamp))

                result = self.cursor.fetchone()
                # end while loop - while result != None:
            print('\n -------------- GOT DATA FROM CRATE ------------------ \n\n\n\n\n\n\n\n\n')
            if(self.dbg == 2):
                H.close()
                G.close()
            ############################################################
            # get last temperature profile
            #myquery = "SELECT iteration,T01_Sp01,T02_Sp02,T02_Sp03,T02_Sp04,T02_Sp05,T02_Sp06,T02_Sp07,T02_Sp08,T02_Sp09,T10_Sp10,T10_Sp11,T10_Sp12,T10_Sp13,T10_Sp14,T10_Sp15,T10_Sp16,T10_Sp17,T10_Sp18,T10_Sp19,T20_Sp20 FROM mtopeniot.etrvk"
            

        else:
        # getting data from crate using orion context broker
            payload = {'stmt': sqlquery}
            headers = {'Content-Type': 'application/json'}
            r = requests.post(self.request_endpoint, data=json.dumps(payload), headers=headers )
            ant = r.json()
            try:
                result = ant['rows']
                mytstamp = self.time_and_one_record_from_db(result, p_in_MPa, calc_opt)
            except:
                print('Error = {}'.format(ant['error']))

            print('\n -------------- GOT DATA FROM ORION ------------------ \n\n\n\n\n\n\n\n\n')
        # end update_heat_consumption_from_crate

    # ==================================================================

    def number_crate_records_in_time_span(self, prediction_time_step_in_s, delta_in_seconds):
        start_time = actual_time - timedelta(seconds=(prediction_time_step_in_s + delta_in_seconds))  # 
        end_time = actual_time - timedelta(seconds=(prediction_time_step_in_s + delta_in_seconds)) # 
        stt = start_time.replace(tzinfo=timezone.utc).timestamp()
        ett = end_time.replace(tzinfo=timezone.utc).timestamp()
        start_time = stt  # utc
        end_time = ett
        selects = "SELECT turnover_time_of_one_seg_in_h,t30_ambientairtemperature,t21_domestichotwater,t22_domesticcoldwater,v01_colddrinkingwater,t25_supply_heatingcircuit,t24_return_heatingcircuit,v02_heatingcircuit,mass_flow_dhw,mass_flow_heating_water,elctric_heater_status,turnover_time_of_one_seg_in_h FROM mtopeniot.etrvk"
        wheres = "WHERE turnover_time_of_one_seg_in_h>={} AND turnover_time_of_one_seg_in_h<={}".format(start_time, end_time)
        orders = "ORDER BY turnover_time_of_one_seg_in_h"
        sqlquery = "{} {} {}".format(selects, wheres, orders)
        payload = {'stmt': sqlquery}
        headers = {'Content-Type': 'application/json'}
        r = requests.post(self.request_endpoint, data=json.dumps(payload), headers=headers )
        ant = r.json()
        try:
            return len(ant['rows'])
        except:
            return -1
        # end number_crate_records_in_time_span

    # ==================================================================

    def time_and_one_record_from_db(self, result, p_in_MPa, calc_opt):
        # result - list / tuple of reasults from the query to database

        # ambient ar temperature
        t30_ambientairtemperature = result[1]
        # heat consumption for domestic hot water - get the data
        t21_domestichotwater = result[2]
        t22_domesticcoldwater = result[3]
        v01_colddrinkingwater = result[4]
        cp_dhw = utils.cp_fluid_water(0.5 * (t22_domesticcoldwater + t21_domestichotwater), p_in_MPa, calc_opt)
        rho_dhw = utils.rho_fluid_water(t22_domesticcoldwater, p_in_MPa, 1)
        # kg/m3 * m3/s * J/kg/K * K * s = J
        q_dhw = rho_dhw * v01_colddrinkingwater * cp_dhw * (t21_domestichotwater - t22_domesticcoldwater) * time_step_in_s
        # heat consumption for heating system - get the data
        t25_supply_heatingcircuit = result[5]
        t24_return_heatingcircuit = result[6]
        v02_heatingcircuit = result[7]
        cp_hk = utils.cp_fluid_water(0.5 * (t24_return_heatingcircuit + t25_supply_heatingcircuit), p_in_MPa, calc_opt)
        rho_hk = utils.rho_fluid_water(t24_return_heatingcircuit, p_in_MPa, 1)
        # kg/m3 * m3/s * J/kg/K * K * s = J
        q_hk = rho_hk * v02_heatingcircuit * cp_hk * (t25_supply_heatingcircuit - t24_return_heatingcircuit) * time_step_in_s
        # time stamp
        x1 = result[8]
        x2 = result[9]
        x3 = result[10]
        xutc = utils.build_full_utc_time_from_elements(x1, x2, x3)
        #mytstamp = datetime.utcfromtimestamp(float(xutc))
        # aggregate the data in the needed resolution

        t_act = xutc.hour                                  # t_act - actual time in hours
        q_act = (q_dhw + q_hk)/time_step_in_s              # q_act - actual heat load of the system in W 
        t_e_act = t30_ambientairtemperature                # t_e_act - ambient air temperature in grad Celcius
        # add aggregated data to the data structure for predict_thermal.py
        self.run_to_save_data(t_act,q_act,t_e_act)

        return xutc
        # end time_and_one_record_from_db

    # ==================================================================

    def get_weather_prediction(self, actual_time, simulation, wetter_file, start_datetime, start_sim_inh, end_sim_inh, fnr):
        if(not self.open_weather_map_active):
            # create unprecise prediction based upon data from weather file
            if(self.dbg == 2):
                H = open("./myweatherf"+str(fnr)+".dat","w")
                H.write(' weather forecast and its components  \n')
                H.write(' date  time  utc_time  time_in_h  file  systematic_a random_a forecast \n')
                
            weather_pred = []
            horizont_time = actual_time + timedelta(hours=self.output_horizon_in_h)
            actual_time = actual_time + timedelta(seconds=self.output_resolution_in_s)
            sign = random.choice([-1, 1])
            #print('horizont_time = {}; actual_time = {}; sign = {}'.format(horizont_time, actual_time, sign))
            #print('WEATHER: timestep in s = {}; actual_time = {}; sign = {}'.format(self.output_resolution_in_s, actual_time, sign))
            while(actual_time <= horizont_time):
                # read ambient temperature from the weather file
                t_pred = utils.get_ambient_temperature(simulation, wetter_file, actual_time, start_datetime, start_sim_inh, end_sim_inh)
                # calculate deviation from the temperature that will be simulated
                #simtime_in_h = ((actual_time - start_datetime).total_seconds() / 3600.0) + start_sim_inh  # simulationstime in h
                simtime_in_h = ((actual_time - start_datetime).total_seconds() / 3600.0)  # simulationstime in h
                syst_dev = sign * math.sqrt(simtime_in_h/self.output_horizon_in_h) * 3.0 
                deviation = syst_dev + np.random.random() * 1.0
                # create output list
                weather_pred.append({'date':actual_time, 'time_in_h': simtime_in_h + start_sim_inh, 'temp_in_C': t_pred + deviation})
                if(self.dbg>=2):
                    H.write(' {} '.format(actual_time))
                    H.write(' {} '.format(actual_time.replace(tzinfo=timezone.utc).timestamp()))
                    H.write(' {} '.format(simtime_in_h))
                    H.write(' {} '.format(t_pred))  # data from wetter.dat file
                    H.write(' {} '.format(syst_dev))  # systematic deviation
                    H.write(' {} '.format(deviation - syst_dev))  # random deviation
                    H.write(' {} \n'.format(t_pred + deviation))  # whole forecast

                actual_time = actual_time + timedelta(seconds=self.output_resolution_in_s)
        # end if(not self.open_weather_map_active):
        else:
            weather_pred = self.request_weather_prediction_from_platform(actual_time)
        #print('weather prediction = ')
        #for pred in weather_pred:
            #print(type(pred), pred)
        if(self.dbg>=2):
            H.close()
        return weather_pred

    #end get_weather_prediction


# ==================================================================

    def request_weather_prediction_from_platform(self, actual_time):
        return 1

# ==================================================================
# read configuration file
#with open('pred_therm_config.json') as json_file:
#    data = json.load(json_file)
#
#t,q,t_e = read_data(data['path_loads'])
#t_pred, t_e_pred = read_temp(data['path_temp'])

#write_init(data['path_result'])
## print(t)
## print(q)
## print(t_e)
## print(t_pred)
## print(t_e_pred)
#
#n_day=int(data['n_day'])
#n_values=int(data['n_values'])

#pred=predict_Q(n_day,n_values)
## print(pred.q_s)
## input("Press Enter to continue...")
#for index in range(0,len(t)):
#    t_1day = int(t[index] + 24); index_1day = t_pred.index(t_1day)
#    t_2day = int(t[index] + 48); index_2day = t_pred.index(t_2day)
#    t_e_1day = t_e_pred[index_1day]
#    t_e_2day = t_e_pred[index_2day]
#    q_write, q_1day, q_2day, m_c, n_c = pred.run(t[index],q[index],t_e[index],t_e_1day,t_e_2day,0.01)
#    if (q_write):
#        write_q(data['path_result'],t[index],t_e_1day,q_1day,t_e_2day,q_2day, m_c, n_c)
#

