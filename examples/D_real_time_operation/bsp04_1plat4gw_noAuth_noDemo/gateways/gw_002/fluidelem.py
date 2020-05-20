from time import sleep

import utils
import timestep
import mysolver




class fluidelem():
    """ fluid element for the calculation of temperature profile in pipe or stratified tank """
    def __init__(self, myid, tinp, tout, tavg, mstr, qext, flcp, volume, density, option, timestepmanager, tag, solver, tstep_anteil):
        self.myid = myid    # id
        self.tavg = tavg    # average temperature in °C
        self.t1   = tinp    # input temperature when mstr>0 in °C
        self.t2   = tout    # output temperature when mstr>0 in °C
        self.mstr = mstr    # mass flow in kg/s
        self.qext = qext    # external heat in W
        self.flcp = flcp    # specific heat capacity in J/kg/K - if it is equal to zero or negative calculate cp from external function
        self.vol = volume   # volume of the element in m3
        #self.qconv = 0.0    # convective heat balance in kW
        self.qcond = 0.0    # conductive heat balance in kW
        self.qtot = 0.0     # total heat balance in kW
        self.option = option # 0 - ideal mixing, expicit, 1 - linear profile explicit, 10 - ideal mixing implicit, 11 - linear profile implicit
        self.tsm = timestepmanager
        self.tag = tag       # name of the system the element is in
        self.solver = solver
        self.sign = +1
        # flag for the external cp
        if(flcp<=0.0):
            self.extcp = True
        else:
            self.extcp = False
        # flag for the external rho
        if(density<=0.0):
            self.extro = True
        else:
            self.extro = False
        if(tstep_anteil<0.1):
            tstep_anteil = 0.1
        if(tstep_anteil>0.9):
            tstep_anteil = 0.9
        self.tstep_anteil = tstep_anteil
        self.rho = self.rhocalc(tavg)  # density of the element in kg/m3
        self.mass = volume * density # mass of the element in kg

#
    def get_tag(self):
        return self.tag
#
    def get_id(self):
        return self.myid
#
    def get_tstep_anteil(self):
        return self.tstep_anteil
#
    def set_tstep_anteil(self,new_tstep_anteil):
        self.tstep_anteil = new_tstep_anteil
#
    def cpcalc(self, temp):
        """ returns the specific heat capacity in J/kg/K """
        if(self.extcp):
            patm = 0.1 * 1.01325  # in MPa
            return utils.cp_fluid_water(temp, patm, 1) * 1000.0
        else:
            return self.flcp
#
    def rhocalc(self, temp):
        """ returns the density in kg/m3 """
        if(self.extro):
            patm = 0.1 * 1.01325  # in MPa
            return utils.rho_fluid_water(temp, patm, 1)
        else:
            return self.rho
#
    def get_mstr(self):
        return self.mstr   # in kg/s
#
    def set_mstr(self, massestrom):
        self.mstr = massestrom
        self.update_mass()
        if (((massestrom * self.tsm.get_timestep()) / (self.mass))>=self.tstep_anteil):
            self.tsm.set_new_tstep((self.tstep_anteil * self.mass) / massestrom)
            #print('mass = {}; mstr = {}; ratio = {}; rho = {}; vol = {}; temp = {}'.format(self.mass, massestrom, (0.1 * self.mass) / massestrom, self.rho, self.vol,self.get_average_temp()))
        if(self.mstr >= 0.0):
            self.sign = +1
        else:
            self.sign = -1
#
    def get_sign(self):
        return self.sign
#
    def get_average_temp(self):
        return self.tavg
#
    def set_average_temp(self, new_t_avg):
        #if(str(type(new_t_avg))!="<class 'float'>"):
            #print('self.tavg = {}; new_t_avg = {}'.format(self.tavg, new_t_avg))
        self.tavg = new_t_avg
#
    def get_input_temp(self):
        if (self.mstr>=0.0):
            return self.t1
        else:
            return self.t2
#
    def get_output_temp(self):
        if(self.option == 0):
            return self.tavg  
        elif(self.option == 1):
            if(self.mstr >= 0.0):
                return self.t2  
            else:
                return self.t1  
#
    def calc_input_temp(self, up_neighbour_avg_temp, down_neighbour_avg_temp):
        if(self.mstr >= 0.0):
            self.t1 = 0.5 * (self.get_average_temp() + up_neighbour_avg_temp)
        else:
            self.t2 = 0.5 * (self.get_average_temp() + down_neighbour_avg_temp)
        #if((str(type(self.t1  ))!="<class 'float'>") or (str(type(self.t2))!="<class 'float'>")):
            #print('calc_input_temp: id = {}; t1 = {}; t2 = {}'.format(self.get_id(), self.t1, self.t2))
#
    def calc_output_temp(self, up_neighbour_avg_temp, down_neighbour_avg_temp):
        if(self.option == 0):
            if(self.mstr >= 0.0):
                self.t2 = self.get_average_temp()
            else:
                self.t1 = self.get_average_temp()
        elif(self.option == 1):
            if(self.mstr >= 0.0):
                self.t2 = 0.5 * (self.get_average_temp() + down_neighbour_avg_temp)
            else:
                self.t1 = 0.5 * (self.get_average_temp() + up_neighbour_avg_temp)
        #if((str(type(self.t1  ))!="<class 'float'>") or (str(type(self.t2))!="<class 'float'>")):
            #print('calc_output_temp: id = {}; t1 = {}; t2 = {}'.format(self.get_id(), self.t1, self.t2))
#
    def set_input_temp(self, temp):
        if(self.mstr >= 0.0):
            self.t1 = temp
        else:
            self.t2 = temp
        #if(str(type(temp))!="<class 'float'>"):
            #print('set_input_temp: id = {}; temp = {}; t1 = {}; t2 = {}'.format(self.get_id(), temp, self.t1, self.t2))
#
    def set_output_temp(self, temp):
        if(self.mstr >= 0.0):
            self.t2 = temp
        else:
            self.t1 = temp
        #if(str(type(temp))!="<class 'float'>"):
            #print('set_input_temp: id = {}; temp = {}; t1 = {}; t2 = {}'.format(self.get_id(), temp, self.t1, self.t2))
#
    def update_mass(self):
        self.mass = self.vol * self.rhocalc(self.get_average_temp())   # in kg = m3 * kg/m3
        #if(self.myid==0):
            #print('m = {}; V = {}; rho = {}; t  {} '.format(self.mass, self.vol, self.rhocalc(self.get_average_temp()), self.get_average_temp()))
#
    def calc_q_conv(self):
        cpinp = 0.001 * self.cpcalc(self.get_input_temp())
        cpout = 0.001 * self.cpcalc(self.get_output_temp())
        return abs(self.mstr) * (cpinp * self.get_input_temp() - cpout * self.get_output_temp())  # kW = kg/s* kJ/kg/K * K
        #cpinp = 0.001 * self.cpcalc(self.t1)
        #cpout = 0.001 * self.cpcalc(self.t2)
        #if(str(type(self.mstr * (cpinp * self.t1 - cpout * self.t2)))!="<class 'float'>"):
            #print('calc_q_conv: id = {}; mstr = {}; cpinp = {}; t1 = {}; cpout = {}; t2 = {}'.format(self.get_id(), self.mstr, cpinp, self.t1, cpout, self.t2))
        #return self.mstr * (cpinp * self.t1 - cpout * self.t2)  # kW = kg/s* kJ/kg/K * K
#
    def calc_q_total(self, qconductive):
        return (self.calc_q_conv() + qconductive)   # in kW
#
    def calc_delta_t(self, qconductive):
        cpavg = 0.001 * self.cpcalc(self.get_average_temp())   # in kJ/kg/K
        #if(str(type(self.tsm.get_timestep() * self.calc_q_total(qconductive) / (self.mass * cpavg)))!="<class 'float'>"):
            #print('calc_delta_t: timstep = {}; q_tot = {}; mass = {}; pcavg = {}'.format(self.tsm.get_timestep(), self.calc_q_total(qconductive), self.mass, cpavg))
        return self.tsm.get_timestep() * self.calc_q_total(qconductive) / (self.mass * cpavg)  #  K = kJ / kJ/K = s * kW / (kg * kJ/kg/K)
#
    def calc_avg_temp(self, qconductive):
        #if(self.get_id() == 19):
            #print('q = {}; t = {}; Dt = {}'.format(self.calc_q_total(qconductive), self.calc_delta_t(self.tsm.get_timestep(), qconductive), self.get_average_temp()))
        #if(str(type(self.calc_delta_t(self.tsm.get_timestep(), qconductive)))!="<class 'float'>"):
            #print('elem_id = {}; self.calc_delta_t(self.tsm.get_timestep(), qconductive) = {}; qconductive = {}'.format(self.get_id(), self.calc_delta_t(self.tsm.get_timestep(), qconductive), qconductive))
        #if(((self.get_average_temp() + self.calc_delta_t(qconductive))>85.0)):
        #if(((self.tavg<self.t1)and(self.tavg<self.t2)) or ((self.tavg>self.t1)and(self.tavg>self.t2))):
            #print('{} elem_id = {}; delta_t = {}; qcond = {}, q_conv = {}, t1 = {}, t2 = {}, tavg = {} = mstr = {}'.format(self.get_tag(), self.get_id(), self.calc_delta_t(qconductive), qconductive, self.calc_q_conv(), self.t1, self.t2, self.get_average_temp(), self.mstr))
            #print('        ELEM: q_conv = {}; mstr = {}; mass = {}; volume = {}; t1 = {}; t2 = {}, tavg = {}; '.format(self.calc_q_conv, self.mstr, self.mass, self.vol, self.t1,self.t2, self.tavg))
        if(self.mass > (abs(self.mstr) * self.tsm.get_timestep())):
            return (self.get_average_temp() + self.calc_delta_t(qconductive))
        else:
            #sleep(30)
            return self.get_input_temp()
#
    def create_part_mtx_0(self, r_es, tinp_hw, in_idx_hw, out_idx_hw, t_wall):
        bb = self.tsm.get_timestep() * abs(self.mstr) / self.mass
        cpavg = self.cpcalc(self.tavg)
        cc = self.tsm.get_timestep() / (abs(self.mstr) * cpavg * r_es)
        nn = self.solver.get_system_size()
        
        if((self.option == 1) or (self.option == 11)):
            self.solver.set_amtx_elem(self.myid, self.myid, 1.0 + cc)      # diag 1
            self.solver.set_amtx_elem(self.myid, self.myid + nn, bb)       # diag 2
            self.solver.set_amtx_elem(self.myid + nn, self.myid + nn, 1.0) # diag 4
            self.solver.set_bvec_elem(self.myid, self.tavg)                # b
            self.solver.add_bvec_elem(self.myid, cc * t_wall)              # b
            if(self.myid == in_idx_hw):
                #self.solver.set_amtx_elem(self.myid, self.myid + nn - 1, -bb)
                self.solver.set_amtx_elem(self.myid + nn, self.myid, -0.5) # diag 3
                self.solver.set_amtx_elem(self.myid + nn, self.myid + 1, -0.5) # nbd 3
                self.solver.add_bvec_elem(self.myid, bb * tinp_hw)         # b
            elif(self.myid == out_idx_hw):
                self.solver.set_amtx_elem(self.myid, self.myid + nn - 1, -bb) # ndb 2
                self.solver.set_amtx_elem(self.myid + nn, self.myid, -1.0) # diag 3
            else:
                self.solver.set_amtx_elem(self.myid, self.myid + nn - 1, -bb) # nbd 2
                self.solver.set_amtx_elem(self.myid + nn, self.myid, -0.5) # diag 3
                self.solver.set_amtx_elem(self.myid + nn, self.myid + 1, -0.5) # nbd 3
        elif((self.option == 0) or (self.option == 10)):
            self.solver.set_amtx_elem(self.myid, self.myid, 1.0 + bb + cc)      # diag 1
            self.solver.set_bvec_elem(self.myid, self.tavg)                # b
            self.solver.add_bvec_elem(self.myid, cc * t_wall)              # b
            if(self.myid == in_idx_hw):
                #self.solver.set_amtx_elem(self.myid, self.myid + nn - 1, -bb)
                self.solver.add_bvec_elem(self.myid, bb * tinp_hw)         # b
            elif(self.myid == out_idx_hw):
                self.solver.set_amtx_elem(self.myid, self.myid - 1, -bb) # ndb 2
            else:
                self.solver.set_amtx_elem(self.myid, self.myid - 1, -bb) # nbd 2
        else:
            print('ERROR in element {} - option {} not available'.format(self.myid, self.option))
            
#
    def create_part_mtx_1(self, r_es, tinp_hw, in_idx_hw, out_idx_hw, t_wall, mytype):
        """ coupled equation system - dhw coupled with heating water """
        # upper line is dhw, lower line is heating water == hw
        # r_es - list of the resistances; t_wall - list of the wall temperatures - negihbour temperature comes first
        bb = self.tsm.get_timestep() * abs(self.mstr) / self.mass
        bb = self.tsm.get_timestep() * self.mstr / self.mass
        cc = []
        sumcc = 0.0
        sumtc = 0.0
        # determine position in the equation system
        # mytype should be the same as self.tag
        if(mytype == 'dhw'):   # 0,2,4 - even numbers
            myn = self.myid * 2
        elif(mytype == 'hw'):  # 1,3,5 - uneven numbers
            myn = self.myid * 2 + 1
        # calculate components of global resistance
        for resistance in r_es:
            cpavg = self.cpcalc(self.tavg)
            cc.append(self.tsm.get_timestep() / (self.mass * cpavg * resistance))
            sumcc = sumcc + self.tsm.get_timestep() / (self.mass * cpavg * resistance)
            #print('id = {}; R = {}; m_S = {}; c_p={}; Delta tau = {}'.format(self.get_id(),resistance, self.mass, cpavg, self.tsm.get_timestep()))
        sumtc0 = self.tsm.get_timestep() * t_wall[0] / (self.mass * cpavg * r_es[0])
        for ii in range(len(r_es))[1:]:
            cpavg = self.cpcalc(self.tavg)
            sumtc = sumtc + self.tsm.get_timestep() * t_wall[ii] / (self.mass * cpavg * r_es[ii])
            
        # 
        nn = self.solver.get_system_size()  # ??
        n2 = int(nn/2)
        # stiffnesss matrix and load vector assembly
        if((self.option == 1) or (self.option == 11)):   # linear profile
            #print('id = {}; Dtau = {}; b = {}; c = {}, Sc  ={}, tinp = {}; inidx = {}; outidx = {}; n = {}; typ = {}; mstr = {}, m = {}, sign = {}'.format(self.get_id(),self.tsm.get_timestep(), bb, cc, sumcc, tinp_hw, in_idx_hw, out_idx_hw, myn, mytype,self.mstr,self.mass,self.sign))
            # mtx
            self.solver.set_amtx_elem(myn, myn, 1.0 + sumcc)      # diag 
            self.solver.set_amtx_elem(myn, myn + n2, self.sign*bb)
            self.solver.set_amtx_elem(myn + n2, myn, -0.5)
            self.solver.set_amtx_elem(myn + n2, myn + n2, 1.0)
            # create_part_mtx_1
            self.solver.set_bvec_elem(myn, self.tavg)
            self.solver.add_bvec_elem(myn, sumtc)
            #self.solver.add_bvec_elem(myn, sumtc0)
            # C_0
            if(mytype == 'dhw'):
                self.solver.set_amtx_elem(myn, myn + 1, -cc[0])
                #if(self.myid == 0):
                    #print('DHW: m_dhw = {}; C = {} ; V = {}'.format(self.mass,cc[0], self.vol))
            elif(mytype == 'hw'):
                self.solver.set_amtx_elem(myn, myn - 1, -cc[0])
                #if(self.myid == 0):
                    #print('HW: m_hw = {}; C = {} ; V = {}'.format(self.mass,cc[0], self.vol))
            else:
                print('error in create_part_mtx_1')
            # vec
            # stiffness matrix  - create_part_mtx_1
            if(self.myid == in_idx_hw):     # input
                # mtx
                self.solver.set_amtx_elem(myn + n2, myn + self.sign * 2, -0.5)
                #vec
                self.solver.add_bvec_elem(myn, tinp_hw * self.sign*bb)
                
            elif(self.myid == out_idx_hw):  # output
                # mtx
                self.solver.set_amtx_elem(myn, myn + n2 - 2*self.sign, -self.sign*bb)

                self.solver.set_amtx_elem(myn + n2, myn, -1.0)
                # vec
                
                
            else:                           # inside
                # mtx
                self.solver.add_amtx_elem(myn, myn + n2 - 2*self.sign, -self.sign*bb)
                
                self.solver.set_amtx_elem(myn + n2, myn + self.sign * 2, -0.5)
                # vec
                
                
            
            
        
        
    def create_part_mtx_2(self, r_es, t_wall, tinp_hw, in_idx_hw, out_idx_hw, mytype):
        """ coupled equation system -  """
        # upper line is dhw, lower line is heating water == hw
        # r_es - list of the resistances; t_wall - list of the wall temperatures - negihbour temperature comes first
        bb = self.tsm.get_timestep() * abs(self.mstr) / self.mass
        bb = self.tsm.get_timestep() * self.mstr / self.mass
        cc = []
        sumcc = 0.0
        sumtc = 0.0
        # determine position in the equation system
        # mytype should be the same as self.tag
        #if(mytype == 'dhw'):   # 0,2,4 - even numbers
        #    myn = self.myid * 2
        #elif(mytype == 'hw'):  # 1,3,5 - uneven numbers
        #    myn = self.myid * 2 + 1
        myn = self.myid
        # calculate components of global resistance
        for resistance in r_es:
            cpavg = self.cpcalc(self.tavg)
            cc.append(self.tsm.get_timestep() / (self.mass * cpavg * resistance))
            sumcc = sumcc + self.tsm.get_timestep() / (self.mass * cpavg * resistance)
            #print('id = {}; R = {}; m_S = {}; c_p={}; Delta tau = {}; sumcc = {}'.format(self.get_id(),resistance, self.mass, cpavg, self.tsm.get_timestep(), sumcc))
        #print('r_es = {}; t_wall = {}; mass = {}; cpavg = {}'.format(type(r_es),type(t_wall),type(self.mass),type(cpavg)))
        #print('r_es = {}; t_wall = {}; mass = {}; cpavg = {}'.format(r_es,t_wall,self.mass,cpavg))
        sumtc0 = self.tsm.get_timestep() * t_wall[0] / (self.mass * cpavg * r_es[0])
        for ii in range(len(r_es))[1:]:
            cpavg = self.cpcalc(self.tavg)
            sumtc = sumtc + self.tsm.get_timestep() * t_wall[ii] / (self.mass * cpavg * r_es[ii])
            #print('ii = {}; cp = {}; t_wall = {}; r_es = {}; sumtC = {}'.format(ii, cpavg, t_wall[ii], r_es[ii], sumtc))
        # 
        nn = self.solver.get_system_size()  # ??
        n2 = int(nn/2)
        # stiffnesss matrix and load vector assembly
        if((self.option == 1) or (self.option == 11)):   # linear profile
            #print('id = {}; Dtau = {}; b = {}; c = {}, Sc  ={}, tinp = {}; inidx = {}; outidx = {}; n = {}; typ = {}; mstr = {}, m = {}, sign = {}'.format(self.get_id(),self.tsm.get_timestep(), bb, cc, sumcc, tinp_hw, in_idx_hw, out_idx_hw, myn, mytype,self.mstr,self.mass,self.sign))
            # mtx
            self.solver.set_amtx_elem(myn, myn, 1.0 + sumcc)      # diag 
            self.solver.set_amtx_elem(myn, myn + n2, self.sign*bb)
            self.solver.set_amtx_elem(myn + n2, myn, -0.5)
            self.solver.set_amtx_elem(myn + n2, myn + n2, 1.0)

            self.solver.set_bvec_elem(myn, self.tavg)
            self.solver.add_bvec_elem(myn, sumtc)
            self.solver.add_bvec_elem(myn, sumtc0)
            # stiffness matrix - create_part_mtx_2
            if(self.myid == in_idx_hw):     # input
                # mtx
                self.solver.set_amtx_elem(myn + n2, myn + self.sign * 1, -0.5)
                #vec
                self.solver.add_bvec_elem(myn, tinp_hw * self.sign*bb)
                #print('tinp = {}; bb = {}'.format(tinp_hw,bb))
            elif(self.myid == out_idx_hw):  # output
                # mtx
                self.solver.set_amtx_elem(myn, myn + n2 - 1*self.sign, -self.sign*bb)
                # upstream - self.solver.set_amtx_elem(myn, myn - 2, -0.5*bb)
                self.solver.set_amtx_elem(myn + n2, myn, -1.0)
                # vec
                
                
            else:                           # inside
                # mtx
                self.solver.add_amtx_elem(myn, myn + n2 - 1*self.sign, -self.sign*bb)
                self.solver.set_amtx_elem(myn + n2, myn + self.sign * 1, -0.5)
                # vec
                
    
    def create_part_mtx_3(self, r_es, t_wall, tinp_hw, in_idx_hw, out_idx_hw, mytype):
        """ coupled equation system -  """
        # upper line is dhw, lower line is heating water == hw
        # r_es - list of the resistances; t_wall - list of the wall temperatures - negihbour temperature comes first
        bb = self.tsm.get_timestep() * abs(self.mstr) / self.mass
        bb = self.tsm.get_timestep() * self.mstr / self.mass
        #if(self.myid==0):
            #print('\n Dtau = {}; mstr = {}; mass = {}; sign = {}\n'.format(self.tsm.get_timestep(),self.mstr,self.mass,self.sign))
        cc = []
        sumcc = 0.0
        sumtc = 0.0
        # determine position in the equation system
        # mytype should be the same as self.tag
        #if(mytype == 'dhw'):   # 0,2,4 - even numbers
        #    myn = self.myid * 2
        #elif(mytype == 'hw'):  # 1,3,5 - uneven numbers
        #    myn = self.myid * 2 + 1
        myn = self.myid
        # calculate components of global resistance
        for resistance in r_es:
            cpavg = self.cpcalc(self.tavg)
            cc.append(self.tsm.get_timestep() / (self.mass * cpavg * resistance))
            sumcc = sumcc + self.tsm.get_timestep() / (self.mass * cpavg * resistance)
            #print('id = {}; R = {}; m_S = {}; c_p={}; Delta tau = {}; sumcc = {}'.format(self.get_id(),resistance, self.mass, cpavg, self.tsm.get_timestep(), sumcc))
        sumtc0 = self.tsm.get_timestep() * t_wall[0] / (self.mass * cpavg * r_es[0])
        for ii in range(len(r_es))[1:]:
            cpavg = self.cpcalc(self.tavg)
            sumtc = sumtc + self.tsm.get_timestep() * t_wall[ii] / (self.mass * cpavg * r_es[ii])
            #print('ii = {}; cp = {}; t_wall = {}; r_es = {}; sumtC = {}'.format(ii, cpavg, t_wall[ii], r_es[ii], sumtc))
        # 
        nn = self.solver.get_system_size()
        n2 = int(nn/2)
        # stiffnesss matrix and load vector assembly
        if((self.option == 1) or (self.option == 11)):   # linear profile
            #print('id = {}; Dtau = {}; b = {}; c = {}, Sc  ={}, tinp = {}; inidx = {}; outidx = {}; n = {}; typ = {}; mstr = {}, m = {}, sign = {}'.format(self.get_id(),self.tsm.get_timestep(), bb, cc, sumcc, tinp_hw, in_idx_hw, out_idx_hw, myn, mytype,self.mstr,self.mass,self.sign))
            # mtx
            self.solver.set_amtx_elem(myn, myn, 1.0 + sumcc)      # diag 
            self.solver.set_amtx_elem(myn, myn + n2, self.sign*bb)
            self.solver.set_amtx_elem(myn + n2, myn, -0.5)
            self.solver.set_amtx_elem(myn + n2, myn + n2, 1.0)
            # create_part_mtx_3
            self.solver.set_bvec_elem(myn, self.tavg)
            self.solver.add_bvec_elem(myn, sumtc)
            self.solver.add_bvec_elem(myn, sumtc0)
            # stiffness matrix - create_part_mtx_3
            if(self.myid == in_idx_hw):     # input
                # mtx
                self.solver.set_amtx_elem(myn + n2, myn + self.sign * 1, -0.5)
                #vec
                self.solver.add_bvec_elem(myn, tinp_hw * self.sign*bb)
                #print('myid = {}; tinp = {}; bb = {}'.format(self.myid, tinp_hw,bb))
            elif(self.myid == out_idx_hw):  # output
                # mtx
                self.solver.set_amtx_elem(myn, myn + n2 - 1*self.sign, -self.sign*bb)
                
                self.solver.set_amtx_elem(myn + n2, myn, -1.0)
                # vec
                
                
            else:                           # inside
                # mtx
                self.solver.add_amtx_elem(myn, myn + n2 - 1*self.sign, -self.sign*bb)
                
                self.solver.set_amtx_elem(myn + n2, myn + self.sign * 1, -0.5)
                # vec
                
    
