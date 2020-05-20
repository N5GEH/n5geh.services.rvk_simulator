from datetime import datetime, timedelta

import utils


########################################################################

class GasBoiler():
    # constructor method with instance variables
    def __init__(self, thermal_eff, max_th_power, status, min_rest_time, input_temp, output_temp, ambient_temp, actual_time):
     # gasheater.GasBoiler(0.85   , 7.0         , 0     , 60.0         , 10.0      , 85.0       ,    20.0)
        self.thermal_eff = thermal_eff
        self.max_th_power = max_th_power
        self.status = status
        self.min_rest_time = min_rest_time
        self.next_safe_turn_on = actual_time
        self.design_input_temperature = input_temp  # 40.0  # in grad C
        self.design_output_temperature = output_temp  # 85.0  # in grad C
        self.p_atm = utils.get_pressure_in_MPa()
        self.design_mass_flow = self.calc_mass_flow()
        self.ambient_temp = ambient_temp
        if(status == 0):
            self.input_temperature = ambient_temp
            self.output_temperature = ambient_temp       # hot end - temperature of water flowing out of chp
            self.mass_flow = 0.0
        elif(status == 1):
            self.input_temperature = input_temp
            self.output_temperature = output_temp
            self.mass_flow = self.design_mass_flow
        #print('INIT mstr = {}'.format(self.mass_flow))
    #...................................................................
    def set_status(self, new_status):
        self.status = new_status

    def turn_on(self, actual_time):
        if actual_time >= self.next_safe_turn_on:
            self.status = 1
            self.set_inp_temp(self.design_input_temperature)
            self.set_out_temp(self.design_output_temperature)
            self.set_mass_flow(self.design_mass_flow)
        #print('KESSEL TURN ON '.format(self.status))
        return [self.status, self.input_temperature, self.output_temperature, self.mass_flow, self.next_safe_turn_on-actual_time]

    def turn_off(self, actual_time):
        #print('GAS BOILER OFF')
        self.status = 0
        self.next_safe_turn_on = actual_time + timedelta(seconds=self.min_rest_time)
        self.set_inp_temp(self.ambient_temp)
        self.set_out_temp(self.ambient_temp)
        self.set_mass_flow(0.0)
        #print('KESSEL TURN OFF '.format(self.status))
        return [self.status, self.input_temperature, self.output_temperature, self.mass_flow]

    def get_kessel(self):
        return [self.status, self.input_temperature, self.output_temperature, self.mass_flow]

    def get_status(self):
        return self.status
    #...................................................................
    def get_volume_flow_at_input(self):
        return self.mass_flow / utils.rho_fluid_water(self.get_inp_temp(), self.p_atm, 1)  # in m3/s

    def get_max_thermal_boiler_power(self):
        return self.max_th_power                                                           # in kW

    def get_volume_flow_at_output(self):
        return self.mass_flow / utils.rho_fluid_water(self.get_out_temp(), self.p_atm, 1)  # in m3/s

    def calc_mass_flow(self):
        return self.max_th_power / (utils.cp_fluid_water(self.design_avg_temp(), self.p_atm, 1) * (self.design_output_temperature - self.design_input_temperature))  # in kg/s = kW / (kJ/kg/K * K)  # in kg/s = kW / (kJ/kg/K * K)

    def set_mass_flow(self, new_mass_flow):
        self.mass_flow = new_mass_flow
        #print('KESSEL SET MSTR = {}'.format(self.mass_flow))
    #...................................................................
    def get_heat_output(self):
        # in kW = kg/s * kJ/kg/K * K
        return self.mass_flow * utils.cp_fluid_water(self.get_inp_temp(), self.p_atm, 1) * (
                self.get_out_temp() - self.get_inp_temp())
    #...................................................................
    def design_avg_temp(self):
        return (0.5 * (self.design_input_temperature + self.design_output_temperature))

    def get_inp_temp(self):
        return self.input_temperature  # in °C

    def set_inp_temp(self, new_input_temperature):
        self.input_temperature = new_input_temperature

    def get_out_temp(self):
        return self.output_temperature  # in °C

    def set_out_temp(self, new_output_temperature):
        self.output_temperature = new_output_temperature

    def get_gas_mstr(self, heizwert_in_MJ_per_kg):
        return (self.get_heat_output())/(heizwert_in_MJ_per_kg * self.thermal_eff)
#
    #...................................................................
    # end of class GasBoiler

