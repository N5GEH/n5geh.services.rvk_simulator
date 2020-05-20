# -*- coding: utf-8 -*-
"""
Created: 21.05.2019

@author: Martin Knorr

thermal demand prediction
"""

import time
import json
from datetime import datetime, timedelta
import utils

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
    def __init__(self, n_day, n_values, eps, predef_loads_file_path, use_predef_loads, output_horizont_in_h, output_resolution_in_s, conf_powr, rvk):

        self.n_day = n_day          # number of past days considered
        self.n_values = n_values    # number of values per day
        self.dt=24//n_values        # time step
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
        self.output_horizont_in_h = output_horizont_in_h
        self.output_resolution_in_s = output_resolution_in_s
        # conf_powr - configuration of electricity demand prediction
        self.type_of_prediction = conf_powr['type_of_prediction']
        if(self.type_of_prediction == 'SLP'):
            self.el_data = conf_powr['SLP']
            self.slp_resolution_in_s = conf_powr['resolution_in_s']
        self.rvk = rvk
        # debug modus
        self.dbg = 1
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
            print('Prove whether the times in file and in simulation are consistent.')
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

#=======================================================================

    def run_to_predict_thermal_loads(self, weather_pred, output_horizont_in_h, output_resolution_in_s, t_act, actual_time, start_datetime, start_sim_inh, end_sim_inh):
        """ calculates the list of predicted thermal loads of the system in W"""
        t_a_min = 200.0
        thermal_load_1 = []
        thermal_load_prediction = []
        horizont_time = actual_time + timedelta(hours=output_horizont_in_h)
        act_time_1 = actual_time
        act_time_2 = actual_time
        #while(actual_time <= horizont_time):
        n_steps = int(output_horizont_in_h // self.dt)
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
        
        #n_steps = int(output_horizont_in_h * 3600.0 // output_resolution_in_s)
        #n_day = int(output_horizont_in_h // self.n_values)
        #n_steps = self.n_values * n_day
        n_steps = int((output_horizont_in_h * 3600.0) // output_resolution_in_s)
        for step in range(n_steps):
            act_time_2 = act_time_2 + timedelta(seconds=output_resolution_in_s)
            simtime_in_h = ((act_time_2 - start_datetime).total_seconds() / 3600.0) + start_sim_inh  # simulationstime in h
            q_pred = utils.interpolate_value_from_list_of_dicts(simtime_in_h, 'time_in_h', thermal_load_1, 'q_in_W')
            thermal_load_prediction.append({'date':act_time_2, 'time_in_h': simtime_in_h, 'q_in_W': q_pred})
            #thermal_load_prediction.append({act_time_2: q_pred})
            #print('actual_time = {}; simtime in h = {}; q_pred = {}'.format(act_time_2, simtime_in_h, q_pred))
        if(self.dbg > 0):
            H = open("./thermal_pred.dat","w")
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

    def it_is_winter(self,actual_time):
       if(actual_time.month in range(11, 12)):
           return True
       elif(actual_time.month in range(1, 2)):
           return True
       elif((actual_time.month == 11) and (actual_time.day >= 1)):
           return True
       elif((actual_time.month == 3) and (actual_time.day <= 20)):
           return True
       else:
           return False

#=======================================================================

    def it_is_summer(self,actual_time):
       if(actual_time.month in range(6, 8)):
           return True
       elif((actual_time.month == 5) and (actual_time.day >= 15)):
           return True
       elif((actual_time.month == 9) and (actual_time.day <= 14)):
           return True
       else:
           return False

#=======================================================================

    def run_to_predict_electric_loads(self, actual_time, output_horizont_in_h, start_datetime, start_sim_inh):
        # returns predicted electrical load in W
        if(self.it_is_summer(actual_time)):
            # summer time from 15.05 to 14.09
            season = self.el_data['summer time']
        elif(self.it_is_winter(actual_time)):
            # winter time from 1.11 to 20.03
            season = self.el_data['winter time']
        else:
            # transition period from 21.03 to 14.05 and from 15.09 to 31.10
            season = self.el_data['transition period']
        if(actual_time.isoweekday() in range(1, 5)):
            data_set = season['workday']
        elif(actual_time.isoweekday() == 6):
            data_set = season['Saturday']
        else:
            data_set = season['Sunday']
        #print('data_set = {}'.format(data_set))

        act_time_1 = actual_time
        act_time_2 = actual_time

        el_load_pred1 = []
        #print('self.slp_resolution_in_s = {}'.format(self.slp_resolution_in_s))
        for index, elem in enumerate(data_set):
            act_time_1 = act_time_1 + timedelta(seconds=self.slp_resolution_in_s)
            simtime_in_h = ((act_time_1 - start_datetime).total_seconds() / 3600.0) + start_sim_inh  # simulationstime in h
            el_load_pred1.append({'date': act_time_1, 'time_in_h': simtime_in_h, 'q_in_W': 1000.0*elem})     # load in W
            
        #print('actual time = {}'.format(actual_time))
        #print(el_load_pred1)
        # interpolationof the electrical load onto the required resolution of the energy vector
        electric_load_prediction = []
        
        n_steps = int(self.output_horizont_in_h * 3600.0 // self.output_resolution_in_s)
        #print('self.slp_resolution_in_s = {}'.format(self.output_resolution_in_s))
        for step in range(n_steps):
            act_time_2 = act_time_2 + timedelta(seconds=self.output_resolution_in_s)
            simtime_in_h = ((act_time_2 - start_datetime).total_seconds() / 3600.0) + start_sim_inh  # simulationstime in h
            q_pred = utils.interpolate_value_from_list_of_dicts(simtime_in_h, 'time_in_h', el_load_pred1, 'q_in_W')
            electric_load_prediction.append({'date': act_time_2, 'time_in_h': simtime_in_h, 'q_in_W': q_pred})
            #electric_load_prediction.append({act_time_2: q_pred})
        
        
        if(self.dbg > 0):
            H = open("./electrc_pred.dat","w")
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
        return self.rvk.max_pred_temp_supply_heating_sys(t_a_min)

    # ==================================================================

    def get_max_temp_of_chp(self):
        return self.rvk.get_max_temp_of_chp()

    # ==================================================================

    def thermal_energy_that_can_be_put_in_storage(self, tmax):
        # returns thermal energy in kWh that can be still put into storage tank
        # tmax - maximal temperature of the storage tank in °C
        #tank = self.rvk.get_storage_tank()
        return self.rvk.get_energy_left_to_tmax(tmax)

    # ==================================================================

    def thermal_energy_that_can_be_got_from_storage(self, tmin):
        # returns thermal energy in kWh that can be still put into storage tank
        # tmax - maximal temperature of the storage tank in °C
        #tank = self.rvk.get_storage_tank()
        return self.rvk.thermal_energy_that_can_be_got_from_storage(tmin)
        # end thermal_energy_that_can_be_got_from_storage

    # ==================================================================

    def calc_min_el_production(self, minp_thrm_can_be_put_in, minp_thrm_left_in_tank, pred_el_kWh, pred_th_kWh):
        # min production = - rod.el(tank) - pred.el
        # chp = off; kessel as nedded - max consumption el.
        # get kWh that can be still put into storage tank - this will be max possible rod Leistung = minp_thrm_can_be_put_in in kWh
        # calc. how much heat has to be produced - check whether it can be covered by rod and boiler - if not chp has to be turned on and produce electricity
        # get the appropriate electricity consumption from prediction
        # return negative sum of the both
        #
        # heat that is to be produced by heating rod in one timestep cannot exceed the intake capacity of the storage tank + predicted heat consumption
        rod_therm = self.rvk.get_max_thermal_rod_power() * self.output_resolution_in_s / 3600.0  # in kWh
        if(rod_therm > (minp_thrm_can_be_put_in + pred_th_kWh)):
            # control signal to be sent to the heating rod
            el_heat_status = (minp_thrm_can_be_put_in + pred_th_kWh) / rod_therm
            # heat to be produced by the heating rod 
            rod_therm = minp_thrm_can_be_put_in + pred_th_kWh
        else:
            el_heat_status = 1.0 
        # calculate electrical consuption taking the efficiency into account (here = 1,0)
        rod_el_tank = rod_therm / 1.0
        # update tank status - the energy that can be put in is reduced by the rod production minus consumption
        #
        # chp production 
        # chp has to be turned on if the system is not able to provide enough heat with boiler, heating rod and output from the storage tank
        chp_th_prod = 0.0
        chp_el_prod = 0
        max_prod_of_boiler = self.rvk.get_max_thermal_boiler_power() * self.output_resolution_in_s / 3600.0  # in kWh
        # max heat output of storage tank with running boiler - get max thermal power based upon max heating water flow and max temp difference
        max_out_tank = self.rvk.get_max_th_tank_power() * self.output_resolution_in_s / 3600.0  # in kWh
        if(pred_th_kWh > (rod_therm + max_prod_of_boiler + max_out_tank)):
            chp_th_prod = pred_th_kWh - (rod_therm + max_prod_of_boiler + max_out_tank)
            chp_el_prod = self.rvk.get_el_prod_kWh(chp_th_prod)
            
            
        # update tank status - 
        minp_thrm_can_be_put_in = minp_thrm_can_be_put_in - (rod_therm + chp_th_prod - pred_th_kWh)
        minp_thrm_left_in_tank = minp_thrm_left_in_tank + rod_therm + chp_th_prod - pred_th_kWh
        
        return ((- pred_el_kWh - rod_el_tank + chp_el_prod), minp_thrm_can_be_put_in, minp_thrm_left_in_tank)
        # end calc_min_el_production

    # ==================================================================

    def calc_max_el_production(self, maxp_thrm_can_be_put_in, maxp_thrm_left_in_tank, pred_el_kWh, pred_th_kWh):
        # max production = chp.el(tank) - pred.el
        # heating rod off; kessel as neded - max. production el.
        # get kWh that can be still put into storage tank
        # calculate how long can you produce with chp not to overdo it
        # get the appropriate electricity consumption from prediction
        # return the difference
        rod_el_tank = 0.0
        rod_therm = 0.0
        # chp can produce only as much as fits in into the storage tank minus predicted usage
        chp_th_prod = self.rvk.chp.get_design_heat_output() * self.output_resolution_in_s / 3600.0  # in kWh
        if (chp_th_prod > (maxp_thrm_can_be_put_in + pred_th_kWh)):
            chp_th_prod = maxp_thrm_can_be_put_in + pred_th_kWh
        chp_el_prod = self.rvk.get_el_prod_kWh(chp_th_prod)
        # update status of the storage tank
        maxp_thrm_can_be_put_in = maxp_thrm_can_be_put_in - chp_th_prod
        maxp_thrm_left_in_tank = maxp_thrm_left_in_tank + chp_th_prod
        return ((chp_el_prod - pred_el_kWh), maxp_thrm_can_be_put_in, maxp_thrm_left_in_tank)
        # end calc_max_el_production

    # ==================================================================

    def predict_energy_vector(self, weather_pred, t_act, actual_time, start_datetime, start_sim_inh, end_sim_inh, output_horizont_in_h, output_resolution_in_s):
        thermal_load_prediction = self.run_to_predict_thermal_loads(weather_pred, output_horizont_in_h, output_resolution_in_s, t_act, actual_time, start_datetime, start_sim_inh, end_sim_inh)
        electric_load_prediction = self.run_to_predict_electric_loads(actual_time, output_horizont_in_h, start_datetime, start_sim_inh)
        min_electric_prod = []
        max_electric_prod = []
        # calc storage space left in tank
        minp_thrm_can_be_put_in = self.thermal_energy_that_can_be_put_in_storage(self.get_max_temp_of_chp())  # in kWh
        maxp_thrm_can_be_put_in = minp_thrm_can_be_put_in                           # in kWh
        # calc heating energy left in tank
        t_a_min = utils.min_val_in_list_of_dicts('temp_in_C', weather_pred)  # minimal predicted ambient temperature in °C
        tv_max = self.max_pred_temp_supply_heating_sys(t_a_min)                # maximal expected supply temperature in °C
        minp_thrm_left_in_tank = self.thermal_energy_that_can_be_got_from_storage(tv_max)
        maxp_thrm_left_in_tank = minp_thrm_left_in_tank
        # time management
        time_stamp = actual_time + timedelta(hours=self.output_horizont_in_h)
        # for each timestep until the time horizont do
        ii = 0
        print('\n\nGE GE GE\n\n')
        if(self.dbg > 0):
            G = open("./debug.dat","w")
            G.write(' original \n')
            G.write(' index ; minp_thrm_can_be_put_in, maxp_thrm_can_be_put_in, minp_thrm_left_in_tank, maxp_thrm_left_in_tank\n')
            #G.close()
        energy_vector = []
        while (actual_time < time_stamp):
            if(self.dbg > 0):
                G.write('{}  {:9.3f}  {:9.3f}  {:11.3f}  {:11.3f}\n'.format(ii,minp_thrm_can_be_put_in, maxp_thrm_can_be_put_in, minp_thrm_left_in_tank, maxp_thrm_left_in_tank))
            
            # time management
            actual_time = actual_time + timedelta(seconds=self.output_resolution_in_s)
            pred_el_kWh = utils.get_tab_from_list_of_dicts('date', actual_time, 'q_in_W', electric_load_prediction, timedelta(seconds=self.output_resolution_in_s), True, ii) * self.output_resolution_in_s / (3600.0 * 1000.0) # in kWh
            pred_th_kWh = utils.get_tab_from_list_of_dicts('date', actual_time, 'q_in_W', thermal_load_prediction, timedelta(seconds=self.output_resolution_in_s), True, ii) * self.output_resolution_in_s / (3600.0 * 1000.0)   # in kWh
            # calc energy vector
            (minp_ev, minp_thrm_can_be_put_in, minp_thrm_left_in_tank) = self.calc_min_el_production(minp_thrm_can_be_put_in, minp_thrm_left_in_tank, pred_el_kWh, pred_th_kWh)
            (maxp_ev, maxp_thrm_can_be_put_in, maxp_thrm_left_in_tank) = self.calc_max_el_production(maxp_thrm_can_be_put_in, maxp_thrm_left_in_tank, pred_el_kWh, pred_th_kWh)
            min_electric_prod.append({'time stamp' : actual_time, 'P_avg_el_in_kW' : minp_ev})
            max_electric_prod.append({'time stamp' : actual_time, 'P_avg_el_in_kW' : maxp_ev})
            ii = ii + 1
            min_W = minp_ev * self.output_resolution_in_s *3600.0 * 1000.0   # W = kWh * 1000W/kW * 3600s/h * s
            max_W = maxp_ev * self.output_resolution_in_s *3600.0 * 1000.0   # W = kWh * 1000W/kW * 3600s/h * s
            simtime_in_h = ((actual_time - start_datetime).total_seconds() / 3600.0) + start_sim_inh  # simulationstime in h
            energy_vector.append({'time stamp': actual_time, 'time_in_h' : simtime_in_h, 'P_el_min_in_W': min_W , 'P_el_max_in_W': max_W})
            #print('finished {}'.format(ii))
        #energy_vector = {'time stamp': actual_time, 'P_el_min_in_W': min_electric_prod, 'P_el_max_in_W': max_electric_prod}
        if(self.dbg > 0):
            G.close()
        if(self.dbg > 0):
            H = open("./energy_vec.dat","w")
            H.write(' original \n')
            H.write(' index ; "time stamp" ; "time in h" ; "min production W" ; "max production W"\n')
            for idx,elem in enumerate(energy_vector):
                H.write('{}  {}  {:9.3f}  {:11.3f}  {:11.3f}\n'.format(idx,elem['time stamp'], elem['time_in_h'],elem['P_el_min_in_W'],elem['P_el_max_in_W']))
            H.close()
        print('X')
        sleep(15)
        return energy_vector
        # end predict_energy_vector

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

