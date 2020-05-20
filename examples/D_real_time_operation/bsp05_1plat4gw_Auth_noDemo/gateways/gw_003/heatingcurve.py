#from datetime import datetime, timedelta

import utils


########################################################################

class HeatingSystem:
    # constructor method with instance variables
    def __init__(self, design_ambient_temp, design_indoor_temp, design_supply_temp, design_return_temp,
                 n_coefficient, m_coefficient, design_heat_load):
        self.p_atm = utils.get_pressure_in_MPa() # in MPa
        self.design_ambient_temp = design_ambient_temp
        self.design_indoor_temp = design_indoor_temp
        self.design_supply_temp = design_supply_temp
        self.supply_temp = design_supply_temp
        self.design_return_temp = design_return_temp
        self.return_temp = design_return_temp
        self.n_coefficient = n_coefficient
        self.m_coefficient = m_coefficient
        self.design_heat_load = design_heat_load    # in kW
        self.volume_flow = 0.0
        self.calc_volume_flow()
        self.status = 0

    def turn_on(self, ambient_temperature):
        self.status = 1
        self.calc_volume_flow()
        self.calc_supply_temperature(ambient_temperature)
        self.calc_return_temperature(ambient_temperature)

    def turn_off(self):
        self.status = 0
        self.volume_flow = 0.0
        self.supply_temp = self.design_indoor_temp
        self.return_temp = self.design_indoor_temp

    def get_status(self):
        return self.status

    def get_supply_temperature(self, ambient_temperature):
        self.calc_supply_temperature(ambient_temperature)
        return self.supply_temp

    def calc_supply_temperature(self, ambient_temperature):
        DeltaT = self.design_supply_temp - self.design_return_temp
        DTmn = 0.5 * (self.design_supply_temp + self.design_return_temp) - self.design_indoor_temp
        phi = (self.design_indoor_temp - ambient_temperature) / (self.design_indoor_temp - self.design_ambient_temp)
        if(phi<0.0):
            phi=0.0
        phi2 = phi ** (1.0 / (1.0 + self.n_coefficient))
        self.supply_temp = self.design_indoor_temp + 0.5 * phi * DeltaT + phi2 * DTmn
        #return wyn

    def get_return_temperature(self, ambient_temperature):
        self.calc_return_temperature(ambient_temperature)
        return self.return_temp

    def calc_return_temperature(self, ambient_temperature):
        delta_temp = self.design_supply_temp - self.design_return_temp
        delta_temp_mn = 0.5 * (self.design_supply_temp + self.design_return_temp) - self.design_indoor_temp
        phi = (self.design_indoor_temp - ambient_temperature) / (self.design_indoor_temp - self.design_ambient_temp)
        if(phi<0.0):
            phi=0.0
        phi2 = phi ** (1.0 / (1.0 + self.n_coefficient))
        self.return_temp = self.design_indoor_temp - 0.5 * phi * delta_temp + phi2 * delta_temp_mn
        #return wyn

    def get_avg_hk_temperature(self, ambient_temperature):
        delta_temp_mn = 0.5 * (self.design_supply_temp + self.design_return_temp) - self.design_indoor_temp
        phi = (self.design_indoor_temp - ambient_temperature) / (self.design_indoor_temp - self.design_ambient_temp)
        phi2 = phi ** (1.0 / (1.0 + self.n_coefficient))
        wyn = self.design_indoor_temp + phi2 * delta_temp_mn
        return wyn

    def get_volume_flow(self):
        return self.volume_flow

    def heat_load(self, ambient_temperature):
        phi = (self.design_indoor_temp - ambient_temperature) / (self.design_indoor_temp - self.design_ambient_temp)
        return phi * self.design_heat_load  # in kW

    def get_design_mass_flow(self):
        # in  kg/s = kW / (kJ/kg/K * K)
        #print('heat_load = {}'.format(self.heat_load(self.design_ambient_temp)))
        #print('cp = {}'.format(cp_fluid_water(self.get_avg_hk_temperature(self.design_ambient_temp), self.p_atm, 1)))
        #print('Dt = {}'.format(self.design_supply_temp - self.design_return_temp))
        # in kg/s = kW / (kJ/kg/K * K)
        return self.heat_load(self.design_ambient_temp) / (
                    utils.cp_fluid_water(self.get_avg_hk_temperature(self.design_ambient_temp), self.p_atm, 1) * (self.design_supply_temp - self.design_return_temp))  # kg/s = kW / (kJ/kg/K * K)

    def calc_volume_flow(self):
        self.volume_flow = self.get_design_mass_flow() / utils.rho_fluid_water(self.get_avg_hk_temperature(self.design_ambient_temp), self.p_atm, 1)    # m3/s = kg/s / kg/m3

 