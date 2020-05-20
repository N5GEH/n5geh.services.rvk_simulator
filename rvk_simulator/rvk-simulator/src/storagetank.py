import math
import utils
import fluidelem
import mysolver
from datetime import datetime, timedelta
from time import sleep

########################################################################

class HeatStorageTank():
    # constructor method with instance variables
    def __init__(self, effective_height, inner_radius, effective_pipe_surface, effective_pipe_volume,
                 initial_temperature, alpha_loss, actual_time, el_heat_power, el_heat_status, timestepmanager, solverschema, elemtype):
        #        self.effective_volume = effective_volume  # in dm3 = l = 0,001 m3
        #        self.upper_temp = upper_temp                                  # in °C
        #        self.lower_temp = lower_temp                                  # in °C
        self.effective_height = effective_height  # in m
        self.loaded_height = effective_height  # in m
        self.inner_radius = inner_radius  # in m
        self.nr_slices = 20  # discretization of the tank's volume - discretization that is seen from the outside
        self.nr_calc = 20   # discretization of the tank's volume - actual discretization may be >= nr_slices
        t1 = [initial_temperature]  # in °C
        self.temp = self.nr_calc * t1  # list of temperatures of heating water in the storage tank
        self.tout = self.nr_calc * t1  # list of temperatures of heating water in the storage tank
        self.temp_dhw = self.nr_calc * t1  # list of temperatures of domestic hot water in the helical pipe within the storage tank
        self.tout_dhw = self.nr_calc * t1  # list of temperatures of domestic hot water in the helical pipe within the storage tank
        self.idx_loaded_layer = self.nr_calc  # index of the discrete layer that contains the interface etween cold and hot water
        self.temp_avg_loaded = initial_temperature  # in °C
        self.effective_pipe_volume = effective_pipe_volume  # in m3 - water volume of the pipes of inner heat exchanger
        self.effective_volume = math.pi * self.inner_radius * self.inner_radius * self.effective_height - self.effective_pipe_volume # in m3
        self.slice_volume = self.effective_volume / self.nr_calc  # in m3
        self.cut_surface = math.pi * self.inner_radius * self.inner_radius  # in m2 - surface of the xy projection  - rzut poziomy
        self.slice_height = self.effective_height / self.nr_calc  # in m
        self.red_outside_surface = 2.0 * math.pi * (self.inner_radius + 0.004) * self.effective_height
        self.red_out_surf_slice = self.red_outside_surface / self.nr_calc
        self.effective_pipe_surface = effective_pipe_surface  # in m2 - surface of the pipes of the inner heat exchanger
        self.pipe_surf_slice = self.effective_pipe_surface / self.nr_calc  # in m2 - surface of the pipes of inner heat exchanger pro slice
        self.pipe_volume_slice = effective_pipe_volume / self.nr_calc  # in m3 - water volume of the pipes of inner heat exchanger
        self.lambda_water = 0.5  # in W/m/K
        self.p_atm = 0.1 * 1.01325  # in MPa
        self.t_outside = initial_temperature
        self.alpha_dhw = 1.0  # heat transfer rate at the inner side of pipes - flow or no flow possible in W/m2/K
        self.alpha_tank = 1.0  # heat transfer rate at the outer side of pipes - no flow assumed          in W/m2/K
        #self.k_coef = 0.005/50.0  # heat transfer coeficient across the pipe in W/m2/K
        self.k_coef = 50.0/0.005  # heat transfer coeficient across the pipe in W/m2/K
        self.alpha_loss = alpha_loss # heat transfer coefficient to the outside in W/m2/K
        self.acttime = actual_time
        self.tsm = timestepmanager
        self.mstr_hw = 0.0
        self.mstr_dhw = 0.0
        self.el_heat_power = el_heat_power
        self.el_heat_status = el_heat_status
        self.wechsel_zeit_in_h = 0.0
        self.solverschema = solverschema
        if(self.solverschema == 'implizit'):
            if(elemtype == 0):
                self.n_of_var = self.nr_calc * 2
            elif(elemtype == 1):
                self.n_of_var = self.nr_calc * 4
            else:
                print('ERROR storage tank solver elemtype')
            self.slv = mysolver.mysolver('gauss elimination',self.n_of_var)
        elif(self.solverschema == 'explizit'):
            self.slv = mysolver.mysolver('dummy', 0)
        self.t_hw = [fluidelem.fluidelem(ii, initial_temperature,initial_temperature,initial_temperature,0.0,0.0,-1.0,self.slice_volume , -1.0, elemtype, self.tsm, 'hw', self.slv, 0.8) for ii in range(self.nr_calc)]
        self.t_dhw = [fluidelem.fluidelem(ii, initial_temperature,initial_temperature,initial_temperature,0.0,0.0,-1.0, self.pipe_volume_slice, -1.0, elemtype, self.tsm, 'dhw', self.slv, 0.8) for ii in range(self.nr_calc)]
        self.max_k = 0.0  # W/K
        self.max_mstr_hw = 0.0  # kg/s
        self.max_mstr_dhw = 0.0  # kg/s
        self.dbg = 0

    # =======================================================================

    def calc_energy_left_to_tmax(self, tmax):
        # only values below tmax are integrated
        p_in_MPa = utils.get_pressure_in_MPa()
        calc_option = utils.get_calc_option()
        cpmax = utils.cp_fluid_water(tmax, p_in_MPa, calc_option)
        wyn = 0.0
        # Q in kWh = Dt * cp * V_i * rho_i  [ K * J/kg/K * m3 * kg/m3 * h/3600s * 1kW/1000W = kWh]
        for elem in self.t_hw:
            tx = elem.get_average_temp()
            cpx = utils.cp_fluid_water(tx, p_in_MPa, calc_option)
            rox = utils.rho_fluid_water(tx, p_in_MPa, calc_option)
            if(tmax >= tx):
                wyn = wyn + (tmax * cpmax - tx * cpx) * self.slice_volume * rox / (3600.0 * 1000.0)
        return wyn

    # =======================================================================

    def calc_energy_above_tmin(self, tmin):
        # only values above tmin are integrated
        p_in_MPa = utils.get_pressure_in_MPa()
        calc_option = utils.get_calc_option()
        cpmin = utils.cp_fluid_water(tmin, p_in_MPa, calc_option)
        wyn = 0.0
        # Q in kWh = Dt * cp * V_i * rho_i  [ K * J/kg/K * m3 * kg/m3 * h/3600s * 1kW/1000W = kWh]
        for elem in self.t_hw:
            tx = elem.get_average_temp()
            cpx = utils.cp_fluid_water(tx, p_in_MPa, calc_option)
            rox = utils.rho_fluid_water(tx, p_in_MPa, calc_option)
            if(tx >= tmin):
                wyn = wyn + (tx * cpx - tmin * cpmin) * self.slice_volume * rox / (3600.0 * 1000.0)
        return wyn

    # =======================================================================

    def get_max_th_tank_power(self, t_kw):
        temp = t_kw
        p_in_MPa = utils.get_pressure_in_MPa()
        calc_option = utils.get_calc_option()
        cp = utils.cp_fluid_water(temp, p_in_MPa, calc_option)
        pumped_power = self.max_mstr_hw * cp * temp * 0.001  # kW = kg/s * J/kg/K * K * 1kW/1000W
        
        conducted_power = 0.0
        for elem in self.t_hw:
            tx = elem.get_average_temp()
            conducted_power = conducted_power + self.max_k * (tx - t_kw) * 0.001
        
        return (pumped_power + conducted_power)    # in kW

    # =======================================================================

    def get_temp_dhw(self):
        return self.t_dhw[self.nr_calc - 1].get_average_temp()

    # =======================================================================

    def get_el_heater_consumption(self):
        return self.el_heat_status * self.el_heat_power

    # =======================================================================

    def get_max_thermal_rod_power(self):
        return self.el_heat_power  # in kW

    # =======================================================================

    def get_el_heater_status(self):
        return self.el_heat_status

    # =======================================================================

    def update_act_time(self,acttime):
        self.acttime = acttime

    # =======================================================================

    def output_temperatures(self):
        # returns the temperature profile across the storage tank
        te2 = []
        nn = int(self.nr_calc / self.nr_slices)
        for ii in range(self.nr_slices):
            suma = 0.0
            for jj in range(nn):
                suma = suma + self.temp[ii * nn +jj]
                #if(str(type(suma))!="<class 'float'>"):
                    #print('suma = {}; ii = {}; jj = {}; nn = {}, te2 = {}'.format(suma, ii, jj, nn, te2))
                    #print('temp[{}] = {}; mstr = {}; tavg = {}; tinp = {}, tout = {}'.format(ii*nn+jj, self.temp[ii * nn +jj], self.t_hw[ii * nn +jj].get_mstr(), self.t_hw[ii * nn +jj].get_average_temp(), self.t_hw[ii * nn +jj].get_input_temp(), self.t_hw[ii * nn +jj].get_output_temp()))
            te2.append(suma / nn)
        return te2

    # =======================================================================

    def dhw_profile_temperatures(self):
        # returns the temperature profile across the storage tank
        te2 = []
        nn = int(self.nr_calc / self.nr_slices)
        for ii in range(self.nr_slices):
            suma = 0.0
            for jj in range(nn):
                suma = suma + self.temp_dhw[ii * nn +jj]
                #if(str(type(suma))!="<class 'float'>"):
                    #print('suma = {}; ii = {}; jj = {}; nn = {}, te2 = {}'.format(suma, ii, jj, nn, te2))
                    #print('temp[{}] = {}; mstr = {}; tavg = {}; tinp = {}, tout = {}'.format(ii*nn+jj, self.temp[ii * nn +jj], self.t_hw[ii * nn +jj].get_mstr(), self.t_hw[ii * nn +jj].get_average_temp(), self.t_hw[ii * nn +jj].get_input_temp(), self.t_hw[ii * nn +jj].get_output_temp()))
            te2.append(suma / nn)
        return te2

    # =======================================================================

    def get_mstr_hw(self):
        return self.mstr_hw

    # =======================================================================

    def get_mstr_dhw(self):
        return self.mstr_dhw

    # =======================================================================

    def get_slice_wechsel_zeit_in_h(self):
        return self.wechsel_zeit_in_h

    # =======================================================================

    def calculate_storage_tank(self, Timestep, hk_inp_temp, hk_inp_volfl_m3s, hk_out_temp, chp_inp_temp, chp_out_temp,
                     chp_inp_volfl_m3s, gb_inp_temp, gp_out_temp, gb_inp_volfl_m3s, dhw_inp_temp, dhw_out_temp, dhw_inp_volfl_m3s):
        """ temperatures of the water of heating water and domestic hot water in the tank """
        # inp enters unit & leaves storage tank, out leaves unit & enters storage tank
        # hk - heating circuit, chp - chp unit, gb - gas boiler
        # temp - temperature; volfl - volume flow
        
        # heating circuit - output from the system - water taken out of the storage tank by the heating system
        hk_rho = utils.rho_fluid_water(hk_inp_temp, self.p_atm, 1)
        hk_cp = utils.cp_fluid_water(hk_inp_temp, self.p_atm, 1)
        hk_mstr = hk_rho * hk_inp_volfl_m3s                            # in kg/s = kg/m3 * m3/s 
        # combined power and heat unit - input to the storage tank
        chp_rho = utils.rho_fluid_water(chp_out_temp, self.p_atm, 1)
        chp_cp = utils.cp_fluid_water(chp_out_temp, self.p_atm, 1)
        chp_mstr = chp_rho * chp_inp_volfl_m3s                         # in kg/s = kg/m3 * m3/s 
        # gas boiler unit - input to the storage tank
        gb_rho = utils.rho_fluid_water(gb_inp_temp, self.p_atm, 1)
        gb_cp = utils.cp_fluid_water(gb_inp_temp, self.p_atm, 1)
        gb_mstr = gb_rho * gb_inp_volfl_m3s                            # in kg/s = kg/m3 * m3/s 
        # mixing of streams from chp and gas boiler units - input to the storage tank
        mix_up_mstr = chp_mstr + gb_mstr
        if(mix_up_mstr != 0.0):
            t_mix_up = (gb_mstr * gb_cp * gb_inp_temp + chp_mstr * chp_cp * chp_out_temp) / (mix_up_mstr * hk_cp)
            # iterate out the temperature of the mixed flow of hot water
            mix_cp = utils.cp_fluid_water(t_mix_up, self.p_atm, 1)
            t_1 = (gb_mstr * gb_cp * gb_inp_temp + chp_mstr * chp_cp * chp_out_temp) / (mix_up_mstr * mix_cp)
        else:
            t_mix_up = 0.5 * (gb_inp_temp + chp_out_temp)
        anz_iter = 0
        while ((abs(t_1 - t_mix_up) > 0.000001) and (anz_iter < 1000)):
            t_mix_up = t_1
            mix_cp = utils.cp_fluid_water(t_mix_up, self.p_atm, 1)
            t_1 = (gb_mstr * gb_cp * gb_inp_temp + chp_mstr * chp_cp * chp_out_temp) / (mix_up_mstr * mix_cp)
            anz_iter = anz_iter + 1
        if (anz_iter == 1000):
            print('actual time = {}'.format(self.acttime))
            print('error = {}'.format(t_mix_up - t_1))
            print('         | t in C |  mstr in kg/s ')
            print(' mixed   | {} |  {} '.format(t_mix_up,mix_up_mstr))
            print(' chp     | {} |  {} '.format(chp_out_temp,chp_mstr))
            print(' gas boi | {} |  {} '.format(gb_out_temp,gb_mstr))
            print('---------+----------+-----------------')
            
        # balance of the hot water in the upper part of the storage tank - plus means input of hot water, minus means more hot water being taken out from the tank
        netto_hot_mstr = mix_up_mstr - hk_mstr                         # in kg/s = kg/m3 * m3/s 
        # netto gain of hot mass in the upper part of storage
        hot_gain = netto_hot_mstr * Timestep  # in kg = kg/s * s
        hot_volume = hot_gain / utils.rho_fluid_water(t_mix_up, self.p_atm, 1)  # in m3 = kg / kg/m3
        # misc number of slices that are fully filled hot water being pumped in m3
        anz_slices = int(hot_volume / self.slice_volume)
        # height_slices  -->  self.effective_heigth
        # hot_volume     -->  self.effective_volume
        height_slices = hot_volume * self.effective_height / self.effective_volume
        #print('hot_gain = {}; hot_volume = {}; anz_slices = {}; height_slices = {}'.format(hot_gain,hot_volume,anz_slices,height_slices))
        # hk_out_temp = self.t24
        cold_cp = utils.cp_fluid_water(hk_out_temp, self.p_atm, 1)
        

        # heat flow from heating appliances to the storage tank - convective influx with t_1, in W
        Q_c_hot_inp = netto_hot_mstr * mix_cp * (t_mix_up - self.temp[0])
        # heat flow from storage tank to the heating appliances to the heating appliances balanced with the input from heating system - convective influx
        Q_c_cold_inp = netto_hot_mstr * cold_cp * (hk_out_temp - self.temp[self.nr_calc - 1])
        
        if (netto_hot_mstr >= 0.0):   # flow direction from above down
            tinp = t_mix_up
            downwards = True
        else:                         # flow direction from below up
            tinp = hk_out_temp
            downwards = False

        tinp_dhw = dhw_inp_temp

        t_new_dhw = []
        t_new = []
        # 
        # calculate output temperatures
        for ii in range(self.nr_calc - 2):
            self.tout_dhw[ii] = 0.5 * (self.temp_dhw[ii] + self.temp_dhw[ii + 1])
            self.tout[ii] = 0.5 * (self.temp[ii] + self.temp[ii + 1])
        self.tout_dhw[self.nr_calc - 1] = self.temp_dhw[self.nr_calc - 1]
        self.tout[self.nr_calc - 1] = self.temp[self.nr_calc - 1]
#        for ii in range(self.nr_calc):
#            if (ii < (self.nr_calc - 1)):
#                self.tout_dhw[ii] = 0.5 * (self.temp_dhw[ii] + self.temp_dhw[ii + 1])
#            else:
#                self.tout_dhw[ii] = self.temp_dhw[ii]
#
#            if downwards:             # flow direction from above down
#                if (ii == 0):             # outflow temp - first element is the lowerst one
#                    self.tout[ii] = self.temp[ii]
#                else:
#                    self.tout[ii] = 0.5 * (self.temp[ii] + self.temp[ii - 1])
#            
#            else:                     # flow direction from below up
#                if (ii < (self.nr_calc - 1)):
#                    self.tout[ii] = 0.5 * (self.temp[ii] + self.temp[ii + 1])
#                else:
#                    self.tout[ii] = self.temp[ii]

        # dhw calculation
        for ii in range(self.nr_calc):
            # domestic hot water calculation
            if(ii == 0):
                Qdhw_from_below = utils.cp_fluid_water(tinp_dhw, self.p_atm, 1) * netto_hot_mstr * tinp_dhw    # kW = kJ/kg/K * kg/s * K
            else:
                Qdhw_from_below = utils.cp_fluid_water(self.tout_dhw[ii - 1], self.p_atm, 1) * netto_hot_mstr * self.tout_dhw[ii - 1]    # kW = kJ/kg/K * kg/s * K
            Qdhw_from_above = utils.cp_fluid_water(self.tout_dhw[ii], self.p_atm, 1) * netto_hot_mstr * self.tout_dhw[ii]    # kW = kJ/kg/K * kg/s * K
            # interface between domestic hot water and heating water 
            Rwall = (1.0 / self.alpha_dhw + 1.0 / self.k_coef + 1.0 / self.alpha_tank) / self.pipe_surf_slice    # K/W = m2*K/W / m2
            Q_wall = (self.temp[ii] - self.temp_dhw[ii]) / Rwall     # in W = K * W/K
            Q_netto_dhw = Q_wall - Qdhw_from_below + Qdhw_from_above
            
            # heating water calculation
            Q_loss = self.alpha_loss * self.red_out_surf_slice * (self.t_outside - self.temp[ii])
            if(downwards):              # flow direction from above down
                if(ii == self.nr_calc):
                    Qhk_from_above = utils.cp_fluid_water(tinp, self.p_atm, 1) * netto_hot_mstr * tinp    # kW = kJ/kg/K * kg/s * K
                else:
                    Qhk_from_above = utils.cp_fluid_water(self.tout[ii], self.p_atm, 1) * netto_hot_mstr * self.tout[ii]    # kW = kJ/kg/K * kg/s * K
                Qhk_from_below =  utils.cp_fluid_water(self.tout[ii - 1], self.p_atm, 1) * netto_hot_mstr * self.tout[ii - 1]    # kW = kJ/kg/K * kg/s * K
                # balance for domestic hot water
                
                Q_netto_heatWater = Q_loss + Qhk_from_above - Qhk_from_below - Q_wall
                twyn = self.temp[0]
                
            else:                       # flow direction from below up
                if(ii == 0):
                    Qhk_from_below = utils.cp_fluid_water(tinp, self.p_atm, 1) * netto_hot_mstr * tinp    # kW = kJ/kg/K * kg/s * K
                else:
                    Qhk_from_below = utils.cp_fluid_water(self.tout[ii - 1], self.p_atm, 1) * netto_hot_mstr * self.tout[ii - 1]    # kW = kJ/kg/K * kg/s * K
                Qhk_from_above =  utils.cp_fluid_water(self.tout[ii - 1], self.p_atm, 1) * netto_hot_mstr * self.tout[ii]    # kW = kJ/kg/K * kg/s * K
                # balance for domestic hot water
                Q_netto_heatWater = Q_loss + Qhk_from_above - Qhk_from_below - Q_wall
                twyn = self.temp[self.nr_calc - 1]
                    
                
                
            # balance for storage tank water
            Q_netto_heatWater = Q_loss + Qhk_from_above - Qhk_from_below - Q_wall
            

            t_new_dhw.append(self.temp_dhw[ii] + Timestep * Q_netto_dhw / (
                    self.pipe_volume_slice 
                  * utils.rho_fluid_water(self.temp_dhw[ii], self.p_atm, 1) 
                  * utils.cp_fluid_water(self.temp_dhw[ii], self.p_atm, 1)))
            t_new.append(self.temp[ii] - Timestep * Q_netto_heatWater / (
                    (self.slice_volume - self.pipe_volume_slice) 
                  * utils.rho_fluid_water(self.temp[ii], self.p_atm, 1)
                  * utils.cp_fluid_water(self.temp[ii],self.p_atm, 1)))
            
        self.temp = t_new
        self.temp_dhw = t_new_dhw
            
            
        #print('time = {}; ii = {}; Q_netto_dhw  ={}; Q_netto_heatWater = {}'.format(self.acttime, ii, Q_netto_dhw, Q_netto_heatWater))
        #print('time = {}; ii = {}; Q_wall  ={}; self.temp[99] = {}; self.temp_dhw[99] = {}'.format(self.acttime, ii, Q_wall, self.temp[99], self.temp_dhw[99]))
        #print('time = {}; ii = {}; Q_wall  ={}; Q_loss = {};'.format(self.acttime, ii, Q_wall, Q_loss))
        #print('time = {}; ii = {}; Q_c_hot_inp  ={}; Q_c_cold_inp = {}; netto_hot_mstr = {}'.format(self.acttime, ii, Q_c_hot_inp, Q_c_cold_inp, netto_hot_mstr))
        #print('time = {}; ii = {}; t_mix_up  ={}; hk_out_temp = {}; netto_hot_mstr = {}; self.temp[self.nr_calc - 1] = {}'.format(self.acttime, ii, t_mix_up, hk_out_temp, netto_hot_mstr,self.temp[self.nr_calc - 1]))
        #print('time = {}; ii = {}; self.temp[0]  ={}; self.temp[1] = {}; netto_hot_mstr = {}; self.temp_dhw[0] = {}'.format(self.acttime, ii, self.temp[0], self.temp[1], netto_hot_mstr,self.temp_dhw[0]))
        #print('time = {}; ii = {}; n[0]  ={}; self.temp[0] = {}; netto_hot_mstr = {}; self.temp_dhw[0] = {}'.format(self.acttime, ii, hot_volume/self.pipe_volume_slice, self.temp[0], netto_hot_mstr,self.temp_dhw[0]))
        #sleep(1)
    

    # =======================================================================

    def calculate_storage_tank_obj(self, tsm, hk_inp_temp, hk_inp_volfl_m3s, hk_out_temp, chp_inp_temp, chp_out_temp,
                     chp_inp_volfl_m3s, gb_inp_temp, gp_out_temp, gb_inp_volfl_m3s, dhw_inp_temp, dhw_out_temp, dhw_inp_volfl_m3s, 
                     el_heat_status, current_time, t_ambient):
        """ temperatures of the water of heating water and domestic hot water in the tank """
        # inp enters unit & leaves storage tank, out leaves unit & enters storage tank
        # hk - heating circuit, chp - chp unit, gb - gas boiler
        # temp - temperature; volfl - volume flow
        
        # heating circuit - output from the system - water taken out of the storage tank by the heating system
        hk_rho = utils.rho_fluid_water(hk_inp_temp, self.p_atm, 1)
        hk_cp = utils.cp_fluid_water(hk_inp_temp, self.p_atm, 1)
        hk_mstr = hk_rho * hk_inp_volfl_m3s                            # in kg/s = kg/m3 * m3/s 
        # combined power and heat unit - input to the storage tank
        chp_rho = utils.rho_fluid_water(chp_out_temp, self.p_atm, 1)
        chp_cp = utils.cp_fluid_water(chp_out_temp, self.p_atm, 1)
        chp_mstr = chp_rho * chp_inp_volfl_m3s                         # in kg/s = kg/m3 * m3/s 
        # gas boiler unit - input to the storage tank
        gb_rho = utils.rho_fluid_water(gp_out_temp, self.p_atm, 1)
        gb_cp = utils.cp_fluid_water(gp_out_temp, self.p_atm, 1)
        gb_mstr = gb_rho * gb_inp_volfl_m3s                            # in kg/s = kg/m3 * m3/s 

        # mixing of streams from chp and gas boiler units - input to the storage tank
        mix_up_mstr = chp_mstr + gb_mstr
        if(mix_up_mstr != 0.0):
            t_mix_up = (gb_mstr * gb_cp * gp_out_temp + chp_mstr * chp_cp * chp_out_temp) / (mix_up_mstr * hk_cp)
            # iterate out the temperature of the mixed flow of hot water
            mix_cp = utils.cp_fluid_water(t_mix_up, self.p_atm, 1)
            t_1 = (gb_mstr * gb_cp * gp_out_temp + chp_mstr * chp_cp * chp_out_temp) / (mix_up_mstr * mix_cp)
        else:
            t_mix_up = min(gp_out_temp, chp_out_temp)
            mix_cp = utils.cp_fluid_water(t_mix_up, self.p_atm, 1)
            t_1 = t_mix_up
        anz_iter = 0
        while ((abs(t_1 - t_mix_up) > 0.000001) and (anz_iter < 1000)):
            t_mix_up = t_1
            mix_cp = utils.cp_fluid_water(t_mix_up, self.p_atm, 1)
            t_1 = (gb_mstr * gb_cp * gp_out_temp + chp_mstr * chp_cp * chp_out_temp) / (mix_up_mstr * mix_cp)
            anz_iter = anz_iter + 1
        if (anz_iter == 1000):
            print('actual time = {}'.format(self.acttime))
            print('error = {}'.format(t_mix_up - t_1))
            print('         | t in C |  mstr in kg/s ')
            print(' mixed   | {} |  {} '.format(t_mix_up,mix_up_mstr))
            print(' chp     | {} |  {} '.format(chp_out_temp,chp_mstr))
            print(' gas boi | {} |  {} '.format(gp_out_temp,gb_mstr))
            print('---------+----------+-----------------')
            
        # balance of the hot water in the upper part of the storage tank - plus means input of hot water, minus means more hot water being taken out from the tank
        netto_hot_mstr = mix_up_mstr - hk_mstr                         # in kg/s = kg/m3 * m3/s 
        netto_cold_mstr = hk_mstr - mix_up_mstr                        # in kg/s = kg/m3 * m3/s 
        #print('mix_up_mstr = {}; hk_mstr = {}'.format(mix_up_mstr, hk_mstr))
        # netto gain of hot mass in the upper part of storage
        hot_gain = netto_hot_mstr * self.tsm.get_timestep()  # in kg = kg/s * s
        hot_volume = hot_gain / utils.rho_fluid_water(t_mix_up, self.p_atm, 1)  # in m3 = kg / kg/m3
        # misc number of slices that are fully filled hot water being pumped in m3
        #print('hot vol = {}; sliceVol = {}: mix_mstr = {}; hk_mstr = {};chp_mstr = {}; gb_mstr = {};hk_inp_volfl_m3s = {}, typ ={}'.format(hot_volume, self.slice_volume,mix_up_mstr , hk_mstr, chp_mstr, gb_mstr, hk_inp_volfl_m3s, type(hk_inp_volfl_m3s)))
        anz_slices = int(hot_volume / self.slice_volume)
        # height_slices  -->  self.effective_heigth
        # hot_volume     -->  self.effective_volume
        height_slices = hot_volume * self.effective_height / self.effective_volume
        #print('hot_gain = {}; hot_volume = {}; anz_slices = {}; height_slices = {}'.format(hot_gain,hot_volume,anz_slices,height_slices))
        # hk_inp_temp = self.t24
        cold_cp = utils.cp_fluid_water(hk_inp_temp, self.p_atm, 1)
        
        
        
        mix_down_mstr = hk_mstr + netto_hot_mstr  # = mix_up_mstr = chp_mstr + gb_mstr
        t_st = self.get_output_temperature()
        cptst = utils.cp_fluid_water(t_st, self.p_atm, 1)
        hk_cp_out = utils.cp_fluid_water(hk_out_temp, self.p_atm, 1)
        if(mix_down_mstr != 0.0):
            t_mix_down = (t_st * cptst * self.mstr_hw + hk_out_temp * hk_cp_out * hk_mstr) / (mix_down_mstr * cptst)
            mix_cp = utils.cp_fluid_water(t_mix_down, self.p_atm, 1)
            t_2 = (t_st * cptst * self.mstr_hw + hk_out_temp * hk_cp_out * hk_mstr) / (mix_down_mstr * mix_cp)
        else:
            # whole flow comes from from heating system - chp and boiler are most likely off
            t_mix_down = hk_out_temp
            mix_cp = utils.cp_fluid_water(t_mix_down, self.p_atm, 1)
            t_2 = t_mix_down
        anz_iter = 0
        while((abs(t_2 - t_mix_down) > 0.000001) and (anz_iter < 1000)):
            t_mix_down = t_2
            mix_cp = utils.cp_fluid_water(t_mix_down, self.p_atm, 1)
            t_2 = (t_st * cptst * self.mstr_hw + hk_out_temp * hk_cp_out * hk_mstr) / (mix_down_mstr * mix_cp)
            anz_iter = anz_iter + 1
        if (anz_iter == 1000):
            print('actual time = {}'.format(self.acttime))
            print('error = {}'.format(t_mix_down - t_2))
            print('         | t in C |  mstr in kg/s ')
            print(' mixed   | {} |  {} '.format(t_mix_down,mix_down_mstr))
            print(' st.tank | {} |  {} '.format(t_st,mix_down_mstr))
            print(' heating | {} |  {} '.format(hk_out_temp,hk_mstr))
            print('---------+----------+-----------------')
            
        

        #print('t_mix_up = {}; mstr = {}; wechsel = {}'.format(t_mix_up,netto_cold_mstr,self.slice_volume/(netto_cold_mstr*3.6),))

        # heat flow from heating appliances to the storage tank - convective influx with t_1, in W
        Q_c_hot_inp = netto_hot_mstr * mix_cp * (t_mix_up - self.temp[0])
        # heat flow from storage tank to the heating appliances to the heating appliances balanced with the input from heating system - convective influx
        Q_c_cold_inp = netto_hot_mstr * cold_cp * (hk_inp_temp - self.temp[self.nr_calc - 1])
#
#       ================================================================
        # DOMESTIC HOT WATER - always from 0 to nr_calc-1 - only one flow direction possible
        #tinp_dhw = dhw_inp_temp
        #in_idx_dhw = 0
        #out_idx_dhw = self.nr_calc - 1
        dhw_mstr = dhw_inp_volfl_m3s * utils.rho_fluid_water(dhw_inp_temp, self.p_atm, 1)
#
#       ----------------------------------------------------------------

        [tinp_hw, in_idx_hw, out_idx_hw] = self.calc_inputs_hw(netto_cold_mstr, hk_out_temp, t_mix_up)
#       ----------------------------------------------------------------
        self.calc_init_hydraulik(current_time, netto_cold_mstr, dhw_mstr, tinp_hw, dhw_inp_temp, in_idx_hw, out_idx_hw)
#       ----------------------------------------------------------------
        # domestic hot water
        t_new_dhw = []
        # heating water
        t_new_hw = []
        # 
        [t_new_hw, t_new_dhw] = self.solve_hydraulic(t_new_dhw, t_new_hw, tinp_hw, dhw_inp_temp, in_idx_hw, 0, out_idx_hw, self.nr_calc - 1, el_heat_status, t_ambient) 

#       ----------------------------------------------------------------
        # balances for all elements and heat exchange between them

        # 
#
        self.temp_dhw = t_new_dhw
        for elem in self.t_dhw:
            elem.set_average_temp(t_new_dhw[elem.get_id()])
        self.temp = t_new_hw

        for elem in self.t_hw:
            elem.set_average_temp(t_new_hw[elem.get_id()])
        #print(' {:8.3f} {} {}; hk_inp_volfl_m3s = {}; gb_inp_volfl_m3s = {}; chp_inp_volfl_m3s = {}; dhw_inp_volfl_m3s = {}'.format(self.acttime, t_new_hw[6], self.t_hw[6].get_mstr(), hk_inp_volfl_m3s, gb_inp_volfl_m3s, chp_inp_volfl_m3s, dhw_inp_volfl_m3s))
        #print(' {:8.3f} {} {} {} {} {}'.format(self.acttime, t_new_dhw[0], self.t_dhw[0].get_mstr(), self.t_dhw[0].get_mstr(), self.t_dhw[0].get_input_temp(), self.t_dhw[0].get_average_temp(), self.t_dhw[0].get_output_temp()))
#
#       ----------------------------------------------------------------
        # OUTPUTS
        self.mstr_hw = netto_cold_mstr
        self.mstr_dhw = dhw_mstr
        self.out_idx_hw = out_idx_hw
        if(self.mstr_hw !=0.0):
            self.wechsel_zeit_in_h = self.slice_volume * utils.rho_fluid_water(tinp_hw, self.p_atm, 1) / (self.mstr_hw * 3600.0)  # h = kg / kg/h = m3 * kg/m3 / (kg/s * 3600 s/h)
        else:
            self.wechsel_zeit_in_h = 0.0
#       ----------------------------------------------------------------
        #print('LAST CALL')
        #print('actual time = {}'.format(self.acttime))
        #print('myid = {}; tt1 = {}; tt3 = {}'.format(myid, tt1, tt3))
        #print('time = {}; ii = {}; Q_netto_dhw  ={}; Q_netto_heatWater = {}'.format(self.acttime, ii, Q_netto_dhw, Q_netto_heatWater))
        #print('time = {}; ii = {}; Q_wall  ={}; self.temp[99] = {}; self.temp_dhw[99] = {}'.format(self.acttime, ii, Q_wall, self.temp[99], self.temp_dhw[99]))
        #print('time = {}; ii = {}; Q_wall  ={}; Q_loss = {};'.format(self.acttime, ii, Q_wall, Q_loss))
        #print('time = {}; ii = {}; Q_c_hot_inp  ={}; Q_c_cold_inp = {}; netto_hot_mstr = {}'.format(self.acttime, ii, Q_c_hot_inp, Q_c_cold_inp, netto_hot_mstr))
        #print('time = {}; ii = {}; t_mix_up  ={}; hk_out_temp = {}; netto_hot_mstr = {}; self.temp[self.nr_calc - 1] = {}'.format(self.acttime, ii, t_mix_up, hk_out_temp, netto_hot_mstr,self.temp[self.nr_calc - 1]))
        #print('time = {}; ii = {}; self.temp[0]  ={}; self.temp[1] = {}; netto_hot_mstr = {}; self.temp_dhw[0] = {}'.format(self.acttime, ii, self.temp[0], self.temp[1], netto_hot_mstr,self.temp_dhw[0]))
        #print('time = {}; ii = {}; n[0]  ={}; self.temp[0] = {}; netto_hot_mstr = {}; self.temp_dhw[0] = {}'.format(self.acttime, ii, hot_volume/self.pipe_volume_slice, self.temp[0], netto_hot_mstr,self.temp_dhw[0]))
        #sleep(1)
    

    # =======================================================================

    def calc_Reynolds_number(self, equiv_rad_in_m, mstr_in_kg_s, pipe_surf_in_m2, temp_fluid_in_gradC):
        velocity = mstr_in_kg_s / (pipe_surf_in_m2 * utils.rho_fluid_water(temp_fluid_in_gradC, utils.get_pressure_in_MPa(), 1))
        return velocity * 2.0 * equiv_rad_in_m / utils.mu_water_in_m2_s(temp_fluid_in_gradC)

    # =======================================================================

    def solve_hydraulic(self, t_new_dhw, t_new_hw, tinp_hw, tinp_dhw, in_idx_hw, in_idx_dhw, out_idx_hw, out_idx_dhw, el_heat_status, t_ambient):
        #print('solverschema = {}'.format(self.solverschema))
        if(self.solverschema == 'implizit'):
            #self.slv.
            

            t_wall_in_C = 0.0
            # L * pi*rr2 = V_r = self.effective_pipe_volume  \ ==>  L = self.effective_pipe_surface*self.effective_pipe_surface/(4*pi*self.effective_pipe_volume)
            # 2*pi*rr * L = self.effective_pipe_surface      / ==>  rr = 2*pi*self.effective_pipe_volume / self.effective_pipe_surface
            pipe_length_in_m = self.effective_pipe_surface * self.effective_pipe_surface / (4.0 * math.pi * self.effective_pipe_volume)
            equiv_rad_in_m = 2.0 * self.effective_pipe_volume / self.effective_pipe_surface
            for elem in self.t_dhw:
                ii = elem.get_id()
                elem.update_mass()
                lambda_fluid_in_W_m_K = utils.lambda_water_W_m_K(elem.get_average_temp())
                self.max_mstr_dhw = max(self.max_mstr_dhw, elem.get_mstr())
                Reynolds_nr = self.calc_Reynolds_number(equiv_rad_in_m, abs(elem.get_mstr()), math.pi*equiv_rad_in_m*equiv_rad_in_m, elem.get_average_temp())
                Prandtl_nr = utils.Prandtl_number_water(elem.get_average_temp())
                self.alpha_dhw= utils.alpha(t_wall_in_C, elem.get_average_temp(), pipe_length_in_m, 2.0*equiv_rad_in_m, Prandtl_nr, Reynolds_nr, lambda_fluid_in_W_m_K)
                self.alpha_tank = self.alpha_dhw
                Rwall = (1.0 / self.alpha_dhw + 1.0 / self.k_coef + 1.0 / self.alpha_tank) / self.pipe_surf_slice    # K/W = m2*K/W / m2
                self.max_k = max(self.max_k, 1.0/Rwall)
                Q_wall = (self.temp[ii] - self.temp_dhw[ii]) / Rwall     # in W = K * W/K - plus for dhw, minus for hw
                t_wall = []
                t_wall.append(self.temp[ii])
                r_es = []
                r_es.append(Rwall)
                elem.create_part_mtx_1(r_es, tinp_dhw, in_idx_dhw, out_idx_dhw, t_wall, 'dhw')

                
            
            for elem in self.t_hw:
                ii = elem.get_id()
                elem.update_mass()
                lambda_fluid_in_W_m_K = utils.lambda_water_W_m_K(elem.get_average_temp())
                self.max_mstr_hw = max(self.max_mstr_hw, elem.get_mstr())
                Reynolds_nr = self.calc_Reynolds_number(equiv_rad_in_m, abs(elem.get_mstr()), math.pi*equiv_rad_in_m*equiv_rad_in_m, elem.get_average_temp())
                Prandtl_nr = utils.Prandtl_number_water(elem.get_average_temp())
                #print('t_wall = {}; t_fl = {}; L = {}; d = {}; Pr = {}; Re = {}; lam = {}'.format(t_wall_in_C, elem.get_average_temp(), pipe_length_in_m, 2.0*equiv_rad_in_m, Prandtl_nr, Reynolds_nr, lambda_fluid_in_W_m_K))
                self.alpha_dhw= utils.alpha(t_wall_in_C, elem.get_average_temp(), pipe_length_in_m, 2.0*equiv_rad_in_m, Prandtl_nr, Reynolds_nr, lambda_fluid_in_W_m_K)
                self.alpha_tank = self.alpha_dhw
                #print('a1 = {}; k = {}; a2 = {}; A = {}'.format(self.alpha_dhw , self.k_coef , self.alpha_tank, self.pipe_surf_slice))    # K/W = m2*K/W / m2
                Rwall = (1.0 / self.alpha_dhw + 1.0 / self.k_coef + 1.0 / self.alpha_tank) / self.pipe_surf_slice    # K/W = m2*K/W / m2
                self.max_k = max(self.max_k, 1.0/Rwall)
                Q_wall = 0.001 * (self.temp[ii] - self.temp_dhw[ii]) / Rwall     # in W = K * W/K - plus for dhw, minus for hw
                Q_loss = 0.001 * self.alpha_loss * self.red_out_surf_slice * (t_ambient - self.temp[ii])  # plus for hw in W/m2/K * 
                t_wall = []
                r_es = []
                # 0-th heat flow
                t_wall.append(self.temp_dhw[ii])
                r_es.append(Rwall)
                # 1-st heat flow
                t_wall.append(t_ambient)
                r_es.append(1.0 / (self.alpha_loss * self.red_out_surf_slice))
                elem.create_part_mtx_1(r_es, tinp_hw, in_idx_hw, out_idx_hw, t_wall, 'hw')
            
            wyn = self.slv.solve_gauss_elimination()
            
            t_new_dhw = [wyn[ii] for ii in range(0, 2*self.nr_calc, 2)]
            t_new_hw = [wyn[ii] for ii in range(1, 2*self.nr_calc, 2)]
            
        elif(self.solverschema == 'explizit'):
            # DHW calculation
            for elem in self.t_dhw:
                ii = elem.get_id()
                elem.update_mass()
                Rwall = (1.0 / self.alpha_dhw + 1.0 / self.k_coef + 1.0 / self.alpha_tank) / self.pipe_surf_slice    # K/W = m2*K/W / m2
                Q_wall = (self.temp[ii] - self.temp_dhw[ii]) / Rwall     # in W = K * W/K - plus for dhw, minus for hw
                #print
                # new temperature of domestic hot water
                t_new_dhw.append(elem.calc_avg_temp(Q_wall))
                #if(ii==(self.nr_calc-1)):
                #if(ii==(0)):
                    #print('time = {}; ii = {};Dt = {} ; Q_conv = {}; Q_tot = {}; t_old = {}; t_new = {}; mstr = {}; t_out = {}; t_inp = {}, mass = {}'.format(self.acttime,ii,elem.calc_delta_t(Q_wall),elem.calc_q_conv(),elem.calc_q_total(Q_wall),self.temp[ii],t_new_dhw[ii],elem.get_mstr(),elem.get_output_temp(), elem.get_input_temp(), elem.print_sth()))
        # 
            #print('\n SOLVE HYDRAULIC \n')
            # heating water calculation
            for elem in self.t_hw:
                ii = elem.get_id()
                elem.update_mass()
                Rwall = (1.0 / self.alpha_dhw + 1.0 / self.k_coef + 1.0 / self.alpha_tank) / self.pipe_surf_slice    # K/W = m2*K/W / m2
                Q_wall = 0.001 * (self.temp[ii] - self.temp_dhw[ii]) / Rwall     # in W = K * W/K - plus for dhw, minus for hw
                Q_loss = 0.001 * self.alpha_loss * self.red_out_surf_slice * (t_ambient - self.temp[ii])  # plus for hw in W/m2/K * 
                # new temperature of heating water
                if (((ii == 5) or (ii == 6)) and (el_heat_status > 0.0)):
                    t_new_hw.append(elem.calc_avg_temp(Q_loss - Q_wall + el_heat_status * 0.5 * self.el_heat_power))
                    self.el_heat_status = el_heat_status
                else:
                    t_new_hw.append(elem.calc_avg_temp(Q_loss - Q_wall))
                #if((elem.get_id() == (self.nr_calc - 1))and(elem.get_average_temp()>=tinp_hw)):
                    #print('tinp_hw = {:6.2f}; hk_out_temp = {:6.2f}; t_mix_up = {:6.2f}; tavg = {:6.2f}; tt1 = {:6.2f}; tt3 = {:6.2f}; tinp = {:6.2f}; tout = {:6.2f}; q_conv = {:6.2f}, Dtinp = {:6.4f}; Dtout = {:6.4f}; Dtconv = {:6.4f}, Qwall = {:8.2f}; Qloss = {:8.2f}'.format(tinp_hw, hk_out_temp, t_mix_up,elem.get_average_temp(), tt1, tt3, elem.get_input_temp(),elem.get_output_temp(),elem.calc_q_conv(), elem.get_input_temp()-elem.get_average_temp(),elem.get_output_temp()-elem.get_average_temp(),elem.get_input_temp()-elem.get_output_temp(),Q_wall,Q_loss))
                #if(elem.get_id() == (self.nr_calc - 1)):
                    #print('mstr = {:6.2f}; Cinp = {:6.2f}; Cout = {:6.2f}; Qconv = {:6.2f}; Qctest = {:6.2f}'.format(elem.get_mstr(),abs(elem.get_mstr())*4.2*elem.get_input_temp(),abs(elem.get_mstr())*4.2*elem.get_output_temp(),elem.calc_q_conv(),elem.get_mstr()*4.2*(elem.get_input_temp()-elem.get_output_temp())))
                    #print('mstr = {:6.2f}; Cinp = {:6.2f}; Cout = {:6.2f}; Qconv = {:6.2f}'.format(elem.get_mstr(),elem.get_mstr()*4.2*elem.get_input_temp(),abs(elem.get_mstr())*4.2*elem.get_output_temp(),elem.calc_q_conv()))
                #if(ii==(self.nr_calc-1)):
                #if(ii==(0)):
                    #print('time = {}; ii = {};Dt = {} ; Q_conv = {}; Q_tot = {}; t_old = {}; t_new = {}; mstr = {}; t_out = {}; t_inp = {}, mass = {}'.format(self.acttime,ii,elem.calc_delta_t(Timestep, Q_loss - Q_wall),elem.calc_q_conv(),elem.calc_q_total(Q_loss - Q_wall),self.temp[ii],t_new_hw[ii],elem.get_mstr(),elem.get_output_temp(), elem.get_input_temp(), elem.print_sth()))
        else:
            print('ERR - unknown solver schema {}'.format(self.solverschema))
        return [t_new_hw, t_new_dhw]

    # =======================================================================

    def calc_init_hydraulik(self, current_time, netto_cold_mstr, dhw_mstr, tinp_hw, dhw_inp_temp, in_idx_hw, out_idx_hw):
#       ----------------------------------------------------------------
        # DHW calculation
        for elem in self.t_dhw:
            elem.set_mstr(dhw_mstr)
            myid = elem.get_id()
            if((myid - 1) >= 0):
                tt1 = self.t_dhw[myid - 1].get_average_temp()
            else:
                tt1 = elem.get_average_temp()
                #print('elem id = {}; tt1 = {}'.format(myid, tt1))
#
            if((myid + 1) <= (self.nr_calc - 1)):
                tt3 = self.t_dhw[myid + 1].get_average_temp()
            else:
                tt3 = elem.get_average_temp()
                #print('elem id = {}; tt3 = {}'.format(myid, tt3))
#
            if (elem.get_id() == 0):
                #if(str(type(dhw_inp_temp))!="<class 'float'>"):
                    #print('dhw: id = {}; dhw_inp_temp = {}'.format(elem.get_id(), dhw_inp_temp))
                elem.set_input_temp(dhw_inp_temp)
                elem.calc_output_temp(tt1, tt3)
            elif (elem.get_id() == (self.nr_calc - 1)):
                elem.calc_input_temp(tt1, tt3)
            else:
                elem.calc_input_temp(tt1, tt3)
                elem.calc_output_temp(tt1, tt3)
            #print('elem id = {}; tt1 = {}; tt3 = {}'.format(myid,tt1,tt3))
#       ----------------------------------------------------------------
        # heating water calculation
        for elem in self.t_hw:
            elem.set_mstr(netto_cold_mstr)
            myid = elem.get_id()
            if((myid - 1) >= 0):
                tt1 = self.t_hw[myid - 1].get_average_temp()
            else:
                tt1 = elem.get_average_temp()
            #if(elem.get_id() == (self.nr_calc - 1)):
#
            if((myid + 1) <= (self.nr_calc - 1)):
                tt3 = self.t_hw[myid + 1].get_average_temp()
            else:
                tt3 = elem.get_average_temp()
#
            if (elem.get_id() == in_idx_hw):
                #if(str(type(tinp_hw))!="<class 'float'>"):
                    #print('dhw: id = {}; tinp_hw = {}'.format(elem.get_id(), tinp_hw))
                elem.set_input_temp(tinp_hw)
                elem.calc_output_temp(tt1, tt3)
            elif (elem.get_id() == out_idx_hw):
                elem.calc_input_temp(tt1, tt3)
                #elem.calc_output_temp(tt1, tt3)
                elem.set_output_temp(elem.get_average_temp())
            else:
                elem.calc_input_temp(tt1, tt3)
                elem.calc_output_temp(tt1, tt3)
            #if(((elem.get_average_temp()<elem.get_input_temp())and(elem.get_average_temp()<elem.get_output_temp()))or((elem.get_average_temp()>elem.get_input_temp())and(elem.get_average_temp()>elem.get_output_temp()))):
                #print('{} id = {}; tt1 = {}; tt3 = {}, tavg = {}, tinp = {}, tout = {}'.format(elem.get_tag(),elem.get_id(), tt1, tt3,elem.get_average_temp(), elem.get_input_temp(), elem.get_output_temp()))
            #print('time = {}; in_idx_hw = {}; tinp_hw = {}; tinp = {}; tout = {}; tt1 = {}; tt3 = {}'.format(self.acttime,in_idx_hw,tinp_hw,elem.tinp,elem.tout,tt1,tt3))
            #print('id = {}; tinp = {}; tavg = {}; tout = {}'.format(elem.get_id(),elem.get_input_temp(),elem.get_average_temp(),elem.get_output_temp()))
            #if((myid + 1) <= (self.nr_calc - 1)):
                
#       ----------------------------------------------------------------
        # correction of the timestep when needed
        #print(current_time)
        self.tsm.set_end_time(current_time)
        if(self.tsm.get_redo()):
            self.tsm.update_timestep(current_time)
#
        # end of function calc_init_hydraulik

    # =======================================================================
    def calc_inputs_hw(self, netto_cold_mstr, hk_out_temp, t_mix_up):
        # HEATING WATER - can flow both ways
        if(netto_cold_mstr >= 0.0):
            tinp_hw = hk_out_temp
            in_idx_hw = 0
            out_idx_hw = self.nr_calc - 1
        else:
            tinp_hw = t_mix_up
            in_idx_hw = self.nr_calc - 1
            out_idx_hw = 0
        return [tinp_hw, in_idx_hw, out_idx_hw]
        
        

    # =======================================================================

    def calc_pumping(self, Timestep, hk_inp_temp, hk_inp_volfl_m3s, hk_out_temp, chp_inp_temp, chp_out_temp,
                     chp_inp_volfl_m3s, gb_inp_temp, gp_out_temp, gb_inp_volfl_m3s):

        """calculates temperature changes in heat storage due to the excessive amount of water getting pumped through it"""

        # inp enters unit & leaves storage tank, out leaves unit & enters storage tank
        # hk - heating circuit, chp - chp unit, gb - gas boiler
        # temp - temperature; volfl - volume flow
        
        # heating circuit
        hk_rho = utils.rho_fluid_water(hk_out_temp, self.p_atm, 1)
        hk_cp = utils.cp_fluid_water(hk_out_temp, self.p_atm, 1)
        hk_mstr = hk_rho * hk_inp_volfl_m3s
        # combined power and heat unit
        chp_rho = utils.rho_fluid_water(chp_inp_temp, self.p_atm, 1)
        chp_cp = utils.cp_fluid_water(chp_inp_temp, self.p_atm, 1)
        chp_mstr = chp_rho * chp_inp_volfl_m3s
        # gas boiler unit
        gb_rho = utils.rho_fluid_water(gb_inp_temp, self.p_atm, 1)
        gb_cp = utils.cp_fluid_water(gb_inp_temp, self.p_atm, 1)
        gb_mstr = gb_rho * gb_inp_volfl_m3s
        # mixing of streams from chp and gas boiler units
        mix_up_mstr = chp_mstr + gb_mstr
        t_mix_up = (gb_mstr * gb_cp * gb_inp_temp + chp_mstr * chp_cp * chp_inp_temp) / (mix_up_mstr * hk_cp)

        #print('hk_rho = {}; hk_cp = {}; hk_mstr = {}'.format(hk_rho,hk_cp,hk_mstr*3600.0))
        #print('chp_rho = {}; chp_cp = {}; chp_mstr = {}'.format(chp_rho,chp_cp,chp_mstr*3600.0))
        #print('gb_rho = {}; gb_cp = {}; gb_mstr = {}'.format(gb_rho,gb_cp,gb_mstr*3600.0))
        #print('mix_up_mstr = {}; t_mix_up = {}'.format(mix_up_mstr*3600.0,t_mix_up))
        #print('mix_up_mstr - hk_mstr = {}'.format((mix_up_mstr-hk_mstr)*3600.0))
        #sleep(20)


        mix_cp = utils.cp_fluid_water(t_mix_up, self.p_atm, 1)
        t_1 = (gb_mstr * gb_cp * gb_inp_temp + chp_mstr * chp_cp * chp_inp_temp) / (mix_up_mstr * mix_cp)

        while abs(t_1 - t_mix_up) > 0.000001:
            t_mix_up = t_1
            mix_cp = utils.cp_fluid_water(t_mix_up, self.p_atm, 1)
            t_1 = (gb_mstr * gb_cp * gb_inp_temp + chp_mstr * chp_cp * chp_inp_temp) / (mix_up_mstr * mix_cp)

        # netto gain of hot mass in the upper part of storage
        hot_gain = (mix_up_mstr - hk_mstr) * Timestep  # in kg = kg/s * s
        hot_volume = hot_gain / utils.rho_fluid_water(t_mix_up, self.p_atm, 1)  # in m3 = kg / kg/m3
        # misc number of slices that are fully filled hot water being pumped in m3
        anz_slices = int(hot_volume / self.slice_volume)  
        # height_slices  -->  self.effective_heigth
        # hot_volume     -->  self.effective_volume
        height_slices = hot_volume * self.effective_height / self.effective_volume
        #print('hot_gain = {}; hot_volume = {}; anz_slices = {}; height_slices = {}'.format(hot_gain,hot_volume,anz_slices,height_slices))

        if anz_slices == 0:  # small changes of the loading of the storage tank
            # nothing really happens
            if hot_gain > 0:
                self.loaded_height = self.loaded_height - height_slices
            else:  # hot_gain < 0 -
                self.loaded_height = self.loaded_height - height_slices
        elif anz_slices > 0:  # hot water flows into the heat storage tank
            for ii in range(self.nr_calc - anz_slices):
                self.temp[ii] = self.temp[ii + anz_slices]
            for ii in range(anz_slices):
                self.temp[self.nr_calc - (ii + 1)] = t_mix_up  # hot water temperature entering above
            self.loaded_height = self.loaded_height - height_slices
        else:  # anz_slices < 0              # cold water flows into tank
            for ii in range(self.nr_calc - anz_slices):
                self.temp[self.nr_calc - (ii + 1)] = self.temp[self.nr_calc - (ii + 1 + anz_slices)]
            for ii in range(anz_slices):
                self.temp[ii] = hk_out_temp  # cold water entering below
            self.loaded_height = self.loaded_height - height_slices

        #print(any_slices)

        self.idx_loaded_layer = int(self.loaded_height / self.effective_height)
        #print('self.loaded_height = {}; self.idx_loaded_layer = {}'.format(self.loaded_height,self.idx_loaded_layer))

    # =======================================================================

    def calc_heat_exchange(self, Timestep):
        """calculates the temperature change of the water in the domestic hot water installation within the tank under pumping conditions"""
        #print('number of slices = {}'.format(self.nr_calc))
        #print('\n before:')
        #for t in self.temp:
        #print(t)
        # based upon myHydraulik.xls
        t_new = []
        for ii in range(self.nr_calc):
            Q_from_above = 0.0  # heat gains from layer above
            Q_from_below = 0.0  # heat gains from layer below
            #        Q   = k *  F  *  Delta t = W/m/K * 1/m * m2 * K
            if ii != 0:
                Q_from_above = self.lambda_water / self.slice_height * self.cut_surface * (
                        self.temp[ii - 1] - self.temp[ii])  # incoming heat
            if ii != self.nr_calc - 1:
                Q_from_below = self.lambda_water / self.slice_height * self.cut_surface * (
                        self.temp[ii + 1] - self.temp[ii])  # incoming heat
            # K + s * kW / (m3 * kJ/kg/K * kg/m3) = K + kJ / (kJ/K) = K + K = K
            t_new.append(self.temp[ii] + Timestep * (Q_from_above + Q_from_below) / (
                    self.slice_volume * utils.cp_fluid_water(self.temp[ii], self.p_atm, 1) * utils.rho_fluid_water(self.temp[ii],
                                                                                                          self.p_atm, 1)))
            #print('working: temp[{}] = {}; new = {}'.format(ii,self.temp[ii],t_new[ii]))
            #print('working: Q_from_above[{}] = {}; Q_from_below = {}'.format(ii,Q_from_above,Q_from_below))
        self.temp = t_new
        #print('\n after:')
        #for t in self.temp:
        #print(t)

    # =======================================================================
    def calc_dhw_heat_exchange(self, Timestep, t_in_dw, t_out_dw, mstr_dhw):
        t_new_dhw = []
        t_new = []
        for ii in range(self.nr_calc):
            alpha_dhw = 1.0  # heat transfer rate at the inner side of pipes - flow or no flow possible in W/m2/K
            alpha_tank = 1.0  # heat transfer rate at the outer side of pipes - no flow assumed          in W/m2/K
            k_coef = 1.0  # heat transfer coeficient across the pipe in W/m2/K
            Q_dhw = k_coef * self.pipe_surf_slice * (self.temp[ii] - self.temp_dhw[ii])
            t_new_dhw.append(self.temp_dhw[ii] + Timestep * Q_dhw / (
                    self.pipe_volume_slice * utils.rho_fluid_water(self.temp_dhw[ii], self.p_atm, 1) * utils.cp_fluid_water(
                self.temp_dhw[ii], self.p_atm, 1)))
            t_new.append(self.temp[ii] - Timestep * Q_dhw / (
                    self.pipe_volume_slice * utils.rho_fluid_water(self.temp[ii], self.p_atm, 1) * utils.cp_fluid_water(self.temp[ii],
                                                                                                       self.p_atm, 1)))

        self.temp = t_new
        self.temp_dhw = t_new_dhw
        #print('\n after:')
        #for ii in range(self.nr_calc):
            #print('temp[{}] = {}; tdhw[{}] = {}'.format(ii,self.temp[ii],ii,self.temp_dhw[ii]))

    # ==================================================================

    def get_output_temperature(self):
        if (self.mstr_hw >= 0.0 ):
            # flow from below up - storage tank is getting unloaded and filled with colder water
            return self.t_hw[self.nr_calc - 1].get_average_temp()
        else:
            # flow from abowe down - storage tank is getting loaded with hot water
            return self.t_hw[0].get_average_temp()
        return t20
