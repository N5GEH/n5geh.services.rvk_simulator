from datetime import datetime, timedelta

import utils



########################################################################

class ChpUnit:
    """  """
    # constructor method with instance variables
#chpunit.ChpUnit(        0.3         , 0.65       ,   4.0       , 0     , 5.0 * 60.0   , 10.0      , 75.0       ,     20.0 )
    def __init__(self, electrical_eff, thermal_eff, max_el_power, status, min_rest_time, input_temp, output_temp, ambient_temp, actual_time):
        self.status = status
        self.design_input_temperature = input_temp
        self.design_output_temperature = output_temp
        self.p_atm = utils.get_pressure_in_MPa()
        self.ambient_temp = ambient_temp
        self.electrical_eff = electrical_eff
        self.thermal_eff = thermal_eff
        self.max_el_power = max_el_power  # in kW
        self.status = status  # on/off
        self.min_rest_time = min_rest_time  # in seconds
        self.next_safe_turn_on = actual_time
        self.design_mass_flow = self.set_design_mass_flow()
        if(status == 0):
            self.input_temperature = ambient_temp         # cold end - temperature of water flowing into chp
            self.output_temperature = ambient_temp       # hot end - temperature of water flowing out of chp
            self.mass_flow = 0.0
        elif(status == 1):
            self.input_temperature = input_temp         # cold end - temperature of water flowing into chp
            self.output_temperature = output_temp       # hot end - temperature of water flowing out of chp
            self.mass_flow = self.design_mass_flow
        self.max_temp = output_temp

    #...................................................................
    def turn_on(self, actual_time, input_temp):
        if actual_time >= self.next_safe_turn_on:
            self.status = 1
            self.set_inp_temp(input_temp)
            self.set_out_temp(self.design_output_temperature)
            self.set_mass_flow(self.design_mass_flow)
            #print('status = {}; tinp = {}; tout = {}; mstr = {}'.format(self.status,self.get_inp_temp(), self.get_out_temp(),self.get_mass_flow()))
        return [self.status,self.get_inp_temp(), self.get_out_temp(),self.get_mass_flow(),(self.next_safe_turn_on-actual_time)]

    def turn_off(self, actual_time):
        #print('CHP OFF')
        self.status = 0
        self.next_safe_turn_on = actual_time + timedelta(seconds=self.min_rest_time)
        self.set_inp_temp(self.ambient_temp)
        self.set_out_temp(self.ambient_temp)
        self.set_mass_flow(0.0)
        #volstr = self.mass_flow / utils.rho_fluid_water(self.input_temperature, self.p_atm, 1)    # m3/s = kg/s / kg/m3
        return [self.status,self.get_inp_temp(), self.get_out_temp(), self.get_mass_flow()]

    #...................................................................

    def get_next_safe_turn_on_time(self):
        return self.next_safe_turn_on

    def reset_next_safe_turn_on(self, actual_time):
        self.next_safe_turn_on = actual_time + timedelta(seconds=self.min_rest_time)

    def get_status(self):
        #volstr = self.mass_flow / utils.rho_fluid_water(self.input_temperature, self.p_atm, 1)    # m3/s = kg/s / kg/m3
        #return [self.status,self.get_inp_temp(), self.get_out_temp(), self.get_mass_flow()]
        return self.status

    def get_chp(self):
        #volstr = self.mass_flow / utils.rho_fluid_water(self.input_temperature, self.p_atm, 1)    # m3/s = kg/s / kg/m3
        #return [self.status,self.get_inp_temp(), self.get_out_temp(), self.get_mass_flow()]
        return [self.status,self.get_inp_temp(), self.get_out_temp(), self.get_mass_flow()]
    #...................................................................
    def get_volume_flow_at_input(self):
        return self.get_mass_flow() / utils.rho_fluid_water(self.input_temperature, self.p_atm, 1)  # in m3/s = kg/s / kg/m3

    def get_volume_flow_at_output(self):
        return self.get_mass_flow() / utils.rho_fluid_water(self.output_temperature, self.p_atm, 1)  # in m3/s

    def set_mass_flow(self, new_mass_flow):
        self.mass_flow = new_mass_flow

    def get_mass_flow(self):
        # in  kg/s = kW / (kJ/kg/K * K)
        if((self.output_temperature - self.input_temperature) != 0.0):
            self.mass_flow = self.get_heat_output() / (
                utils.cp_fluid_water(self.input_temperature, self.p_atm, 1) * (self.output_temperature - self.input_temperature))
        else:
            self.mass_flow = 0.0
        return self.mass_flow

    def set_design_mass_flow(self):
        #        return self.get_volumen_flow() * utils.rho_fluid_water(self.get_inp_temp(), p_atm, 1)  #
        #        m1 = self.get_heat_output() / (0.001 * cp_fluid_water(self.get_inp_temp(), p_atm, 1) * (self.get_out_temp() - self.get_inp_temp()))  # in kg/s
        return self.get_design_heat_output() / (
                utils.cp_fluid_water(0.5 * (self.design_output_temperature + self.design_input_temperature), self.p_atm, 1) * (self.design_output_temperature - self.design_input_temperature))  # in kg/s = kW / (kJ/kg/K * K)
        #print(self.design_mass_flow)
        #return self.design_mass_flow

    def get_design_mass_flow(self):
        return self.design_mass_flow

    #...................................................................
    def get_heat_output(self):
        if (self.status == 1):
            return self.design_mass_flow * utils.cp_fluid_water(self.input_temperature, self.p_atm, 1) * (
                    self.output_temperature - self.input_temperature)  # in kW
        else:
            return 0.0  # in kW

    def get_design_heat_output(self):
        return self.thermal_eff * self.max_el_power / self.electrical_eff  # in kW
    #        return self.get_mass_flow * cp_fluid_water(self.get_inp_temp(), p_atm, 1) * (self.get_out_temp() - self.get_inp_temp()) * 0.001  # in kW

    def get_design_electric_output(self):
        return self.max_el_power  # in kW
    #
    #...................................................................
    def set_inp_temp(self, new_input_temperature):
        self.input_temperature = new_input_temperature

    def get_inp_temp(self):
        return self.input_temperature
    #...................................................................
    def set_out_temp(self, new_output_temperature):
        self.output_temperature = new_output_temperature

    def get_out_temp(self):
        return self.output_temperature

    def get_gas_mstr(self, heizwert_in_MJ_per_kg):
        return (self.get_heat_output())/(heizwert_in_MJ_per_kg * self.thermal_eff)

    def get_el_prod(self):
        # returns electrical production in kW
        if (self.status == 1):
            return self.get_heat_output() * self.electrical_eff / self.thermal_eff
        else:
            return 0.0

    def set_ambient_temp(self, new_ambient_temp):
        self.ambient_temp = new_ambient_temp

    def get_ambient_temp(self):
        return self.ambient_temp

    def get_max_temp_of_chp(self):
        print('CHP: max_temp = {}'.format(self.max_temp))
        return self.max_temp

    def get_el_prod_kWh(self, therm_prod_kWh):
        return (therm_prod_kWh * self.electrical_eff / self.thermal_eff)

    #...................................................................
    # end of class ChpUnit
