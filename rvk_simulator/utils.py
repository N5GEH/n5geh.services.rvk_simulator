import os
import math
import json
from datetime import datetime, time # , timedelta, timezone
########################################################################

def rho_fluid_water(temp_in_C, p_in_MPa, calc_option):
    """ returns density of the fluid water in kg/m3 """
    #if((temp_in_C > -273.15) and (temp_in_C < 1000.0)):
    #    temp = temp_in_C
    #else:
    #    temp = 0.0
    temp = temp_in_C

    if calc_option == 0:
        """ ' Verfahren nach IAPWS R7-97(2012)
' The International Association for the Properties of Water and Steam
' Revised Release on the IAPWS Industrial Formulation 1997
' for the Thermodynamic  Properties of Water and Steam
        """
        wyn = 0.0


    elif calc_option == 1:
        """ ' Verfahren nach Glueck """
        wyn = 1002.045 - 0.1029905 * temp - 0.003698162 * (temp * temp) + 0.000003991053 * (temp * temp * temp)

    elif calc_option == 2:
        """ ' luftfreies Wasser nach PTB Mitteilungen 100/3-90 """
        C0 = 999.83952
        c1 = 16.952577
        C2 = -7.9905127 * 0.001
        C3 = -4.6241757 * 0.00001
        C4 = 1.0584601 * 0.0000001
        C5 = -2.8103006 * 0.0000000001
        b1 = 0.0168872
        wyn = (
                      C0 + c1 * temp + C2 * temp * temp + C3 * temp * temp * temp + C4 * temp * temp * temp * temp + C5 * temp * temp * temp * temp * temp) / (
                      1.0 + b1 * temp)

    elif calc_option == 3:
        """ ' luftgesaettigtes Wasser nach PTB Mitteilungen 100/3-90 """
        C0 = 999.83952
        c1 = 16.952577
        C2 = -7.9905127 * 0.001
        C3 = -4.6241757 * 0.00001
        C4 = 1.0584601 * 0.0000001
        C5 = -2.8103006 * 0.0000000001
        b1 = 0.0168872
        wyn = (
                      C0 + c1 * temp + C2 * temp * temp + C3 * temp * temp * temp + C4 * temp * temp * temp * temp + C5 * temp * temp * temp * temp * temp) / (
                      1.0 + b1 * temp) - 0.004612 + 0.000106 * temp

    elif calc_option == 4:
        """ ' regression of Joachim based on data of Glueck """
        wyn = -7.46649184008019E-08 * temp * temp * temp * temp + 2.94491388243001E-05 * temp * temp * temp - 6.66507624328283E-03 * temp * temp + 2.65068149440988E-02 * temp + 1000.58459596234

    return wyn
    # end of rho_fluid_water function


########################################################################

def check_and_open_file(path):
    """ returns list of strings """
    if os.path.isfile(path):
        try:
            with open(path, 'r') as myf:
                mywetter = []
                for line in myf:
                    mywetter.append(line)
                return (mywetter)
        except Exception as e:
            print('Problem reading file {}'.format(path))
            return 3
    else:
        print('File {} does not exist.'.format(path))
        return 3
    # end check_and_open_file

########################################################################

def check_and_open_json_file(path):
    """ returns dictionary """
    if os.path.isfile(path):
        try:
            with open(path, 'r') as myf:
                return (json.loads(myf.read()))
        except Exception as e:
            print('Problem reading file {}'.format(path))
            print('Problem reading file {}'.format(e))
            return 3
    else:
        print('File {} does not exist.'.format(path))
        return 3
    # end check_and_open_json_file

########################################################################

def get_pressure_in_MPa():
    return 0.101325

########################################################################

def get_calc_option():
    return 1

########################################################################


def cp_fluid_water(temp_in_C, p_in_MPa, calc_option):
    """ returns specific heat capacity of fluid water in kJ / kg / K """
    #if((temp_in_C > -273.15) and (temp_in_C < 1000.0)):
    #    temp = temp_in_C
    #else:
    #    temp = 0.0
    temp = temp_in_C

    if calc_option == 0:
        """ ' Verfahren nach IAPWS R7-97(2012)
' The International Association for the Properties of Water and Steam
' Revised Release on the IAPWS Industrial Formulation 1997
' for the Thermodynamic  Properties of Water and Steam
        """
        wyn = 0.0


    elif calc_option == 1:
        """ ' function c_H2O_von_t  in stoffdat.for """
        wyn = 4.206328 + (-0.001131471 + 0.00001224984 * temp) * temp

    elif calc_option == 2:
        """ ' function ALLG_stoffwerte_wa_cp  in 00_t000_modul_inoutpar.for
  '>    \brief   Berechnung der spezifischen Waermekapazitaet cp von Wasser bei konstantem Druck  \n
  '     Einheit             : J/kgK                                                    \n
  '     Quell               : GLUECK Zustands- und Stoffwerte 1991                     \n
  '     Geltungsbereich     : 10 < t < 200oC / 30 < t < 200oC                          \n
  '     Maximaler Fehler    : ca. 0.45%      / ca. 0.03% bei p = 1 MPa
        """
        wyn = 4.173666 + 4.691707 * 0.00001 * temp - 6.695665 * 0.0000001 * temp * temp + 4.217099 * 0.00000001 * temp * temp * temp

    return wyn
    # end cp_fluid_water

########################################################################




def alpha(t_wall_in_C, t_fluid_in_C, pipe_length_in_m, equiv_diam_in_m, Prandtl_nr, Reynolds_nr, lambda_fluid_in_W_m_K):
    #print('Re = {}; Pr = {}; d = {}; lam = {}; L = {}; t_wall = {}; t_fluid = {}'.format(Reynolds_nr, Prandtl_nr, equiv_diam_in_m, lambda_fluid_in_W_m_K, pipe_length_in_m, t_wall_in_C, t_fluid_in_C))
    # returns alpha in W/m2/K - nach der zweiten Methode von Glück
    if(Reynolds_nr==0.0):
        return lambda_fluid_in_W_m_K/(0.5*equiv_diam_in_m*(1.0-(0.5**0.5)))
    elif(Reynolds_nr>0.0):
        RePrDl = Reynolds_nr * Prandtl_nr * equiv_diam_in_m / pipe_length_in_m
        dum1 = (RePrDl**0.333) * 1.615 - 0.7
        dum2 = (RePrDl**0.5) * ((2.0/(1.0 + 22.0 * Prandtl_nr))**0.167)
        Nu_lam = (3.66**3 + 0.7**3 + dum1**3 + dum2**3)**(1.0/3.0)
        
        BB = 1.0/((5.09*(math.log(Reynolds_nr)/math.log(10.0))-4.24)**2.0)
        dum1 = 1.0 + ((equiv_diam_in_m/pipe_length_in_m)**(2.0/3.0))
        dum2 = 1.0 + 12.7 * (BB**0.5) * ((Prandtl_nr**(2.0/3.0)) - 1.0)
        Nu_turb = BB * Reynolds_nr * Prandtl_nr * dum1 / dum2

        if(Reynolds_nr<=2300.0):
            Nu = Nu_lam
        elif(Reynolds_nr>=10000.0):
            Nu = Nu_turb
        else:
            RePrDl = 2300.0 * Prandtl_nr * equiv_diam_in_m / pipe_length_in_m
            dum1 = (RePrDl**0.333) * 1.615 - 0.7
            dum2 = (RePrDl**0.5) * ((2.0/(1.0 + 22.0 * Prandtl_nr))**0.167)
            Nu_lam = (3.66**3 + 0.7**3 + dum1**3 + dum2**3)**(1.0/3.0)
            BB = 1.0/((5.09*(math.log(10000.0)/math.log(10.0))-4.24)**2.0)
            dum1 = 1.0 + ((equiv_diam_in_m/pipe_length_in_m)**(2.0/3.0))
            dum2 = 1.0 + 12.7 * (BB**0.5) * ((Prandtl_nr**(2.0/3.0)) - 1.0)
            Nu_turb = BB * 10000.0 * Prandtl_nr * dum1 / dum2
            gamma = (Reynolds_nr - 2300.0) / (10000.0 - 2300.0)
            Nu = (1.0-gamma) * Nu_lam + gamma * Nu_turb
            #print('RePrDl = {}; d = {} ; L = {}'.format(RePrDl, equiv_diam_in_m, pipe_length_in_m))
            #print('\n Nu = {}; gamma = {} ; dum2 = {}\n'.format(Nu, gamma, dum2))
    else:
        Nu = 0.0
    # W/(m2.K) = W/m/K / m
    return Nu * lambda_fluid_in_W_m_K / equiv_diam_in_m
    # end alpha


########################################################################

def mu_water_in_m2_s(tFluid):
    return 1.0 / (556272.7 + 19703.39 * tFluid + 124.4091 * (tFluid ** 2) - 0.3770952 * (tFluid ** 3))
    # end mu_water_in_m2_s

########################################################################

def Prandtl_number_water(tFluid):
    return max(1.0 / (0.07547718 + 0.00276297 * tFluid + 0.00003210257 * tFluid * tFluid - 0.0000001015768 * tFluid * tFluid * tFluid), 0.00000001)
    # end Prandtl_number_water

########################################################################

def lambda_water_W_m_K(tFluid_in_gradC):
    temp_in_K = tFluid_in_gradC + 273.15
    AA = -2.4149
    BB = 2.45165 * (10.0)**(-2.0)
    CC = -0.73121 * (10.0)**(-4.0)
    DD = 0.99492 * (10.0)**(-7.0)
    EE = -0.5373 * (10.0)**(-10.0)
    return (AA + BB*temp_in_K) + CC*(temp_in_K**2) + DD*(temp_in_K**3) + EE*(temp_in_K**4)
    # end lambda_water_W_m_K

########################################################################

def interpolate_value_from_list_of_dicts(value1, tag_of_val1, list_of_dicts, tag_of_result):
    """ returns the linear interpolation of y-value for x-value of 'value1'
        
        assumptions are:
        - x-values are saved with the tag 'tag_of_val1'
        - y-values are saved with the tag 'tag_of_result'
        - x- values are monoton and growing with index"""
    if(len(list_of_dicts) == 0):
        return 0  # list is empty
    elif(len(list_of_dicts) == 1):
        return list_of_dicts[0][tag_of_result]   # list contains only one dict element
    else:
        ii=0
        while(list_of_dicts[ii][tag_of_val1] == list_of_dicts[ii+1][tag_of_val1]):
            ii += 1   # x-values of neighbouring elements are identical
        if(ii < len(list_of_dicts)):
            if(list_of_dicts[ii][tag_of_val1] < list_of_dicts[ii+1][tag_of_val1]):
                # growing
                while((ii < len(list_of_dicts)) and (list_of_dicts[ii][tag_of_val1] < value1)):
                    ii += 1
            elif():
                # falling
                while((ii < len(list_of_dicts)) and (list_of_dicts[ii][tag_of_val1] > value1)):
                    ii += 1
            if(ii > 0):
                if(ii >= len(list_of_dicts)):
                    ii = len(list_of_dicts) - 1
                # interpolation or extrapolation upwards when ii == len(list_of_dicts)
                # a = (y2 - y1) / (x2 - x1)
                AA = (list_of_dicts[ii][tag_of_result] - list_of_dicts[ii - 1][tag_of_result]) / (list_of_dicts[ii][tag_of_val1] - list_of_dicts[ii - 1][tag_of_val1])
                # b = (x2 * y1 - x1 * y2) / (x2 - x1)
                BB = (list_of_dicts[ii][tag_of_val1] * list_of_dicts[ii - 1][tag_of_result] - list_of_dicts[ii - 1][tag_of_val1] * list_of_dicts[ii][tag_of_result]) / (list_of_dicts[ii][tag_of_val1] - list_of_dicts[ii - 1][tag_of_val1])
            else:
                # ii == 0 (idx == 1) - extrapolation downwards
                # a = (y2 - y1) / (x2 - x1)
                AA = (list_of_dicts[ii + 1][tag_of_result] - list_of_dicts[ii][tag_of_result]) / (list_of_dicts[ii + 1][tag_of_val1] - list_of_dicts[ii][tag_of_val1])
                # b = (x2 * y1 - x1 * y2) / (x2 - x1)
                BB = (list_of_dicts[ii + 1][tag_of_val1] * list_of_dicts[ii][tag_of_result] - list_of_dicts[ii][tag_of_val1] * list_of_dicts[ii + 1][tag_of_result]) / (list_of_dicts[ii + 1][tag_of_val1] - list_of_dicts[ii][tag_of_val1])
            return (AA * value1 + BB)
        else:
            return list_of_dicts[len(list_of_dicts)][tag_of_result]
    # end interpolate_value_from_list_of_dicts

########################################################################

def get_significant_parts(line):
    """ line is list of strings
        function returns list of nonempty elements"""
    wyn = []
    for element in line:
        if element != '':
            wyn.append(element)
    return wyn
    # end get_significant_parts

########################################################################

def get_ith_column(ii, line):
    """ returns ii-th element of the list 'line' """
    return get_significant_parts(line)[ii - 1]
    # end get_ith_column

########################################################################

def get_tab_from_list_of_dicts(tab_to_find, val_to_find, tab_to_return, list_of_dics, precision, growing, first_idx):
    # return value of key tab_to_return from a dict in a list of dicts
    # that fulfills val_to_find <= list_of_dicts[tab_to_find]
    # where 
    if(first_idx >= len(list_of_dics)):
        first_idx = 0
    if(growing and(val_to_find<=list_of_dics[first_idx][tab_to_find])and(val_to_find>(list_of_dics[first_idx][tab_to_find]-precision))):
        return list_of_dics[first_idx][tab_to_return]
    elif((not growing) and(val_to_find>=list_of_dics[first_idx][tab_to_find])and(val_to_find<(list_of_dics[first_idx][tab_to_find]+precision))):
        return list_of_dics[first_idx][tab_to_return]
    else:
        for elem in list_of_dics:
            if(growing and(val_to_find<=elem[tab_to_find])and(val_to_find>(elem[tab_to_find]-precision))):
                return elem[tab_to_return]
            elif((not growing) and(val_to_find>=elem[tab_to_find])and(val_to_find<(elem[tab_to_find]+precision))):
                return elem[tab_to_return]

########################################################################

def min_val_in_list_of_dicts(tab_to_find, list_of_dicts):
    if(len(list_of_dicts)>0):
        wyn = list_of_dicts[0][tab_to_find]
        for elem in list_of_dicts[1:]:
            wyn = min(elem[tab_to_find], wyn)
        return wyn
    else:
        print('ERROR in utils.min_val_in_list_of_dicts :: List is empty')

########################################################################
    # ==================================================================

def convert_time_to_hours(dtime):
    # returns the number of hours since the 1.1.2000
    return (hours_of_year_month(dtime) + dtime.day * 24.0 + dtime.hour + dtime.minute/60.0 + dtime.second/3600.0 + dtime.microsecond/3600000000)

#end convert_time_to_hours

########################################################################
    # ==================================================================

def hours_of_year_month(dtime):
    # returns number of hours in months and years since 1.1.2000
    yrs = dtime.year - 2000
    mth = dtime.month
    months = {1:31,2:28,3:31,4:30,5:31,6:30,7:31,8:31,9:30,10:31,11:30,12:31}
    mysum = 0
    for ii in range(mth-1):
        mysum = mysum + months[ii+1]
    return (yrs * 8760.0 + mysum * 24.0)

#end hours_of_year_month

########################################################################
    # ==================================================================

def get_time_in_hour(line):
    return float(get_ith_column(1, line))

#end get_time_in_hour

########################################################################
    # ==================================================================

def linear_interpolation(xx, x1, x2, y1, y2):
    if xx == x1:
        return y1
    elif xx == y2:
        return y2
    else:
        aa = (y2 - y1) / (x2 - x1)
        bb = (x2 * y1 - x1 * y2) / (x2 - x1)
        return (aa * xx + bb)

#end linear_interpolation

########################################################################

def extract_time_stamp_from_string(mystr):
    # 
    mydate, mytime = mystr.split("T")
    myyear, mymonth, myday = mydate.split("-")
    myhour, myminute, mysecond = mytime.split(":")
    mysecond,mymicrosecond = mysecond.split(".")
    return datetime(year=int(myyear), month=int(mymonth), day=int(myday), hour=int(myhour), minute=int(myminute), second=int(mysecond), microsecond=int(mymicrosecond))
    # end extract_time_stamp_from_string

########################################################################

def extract_hms_time_from_string(mystr):
    # 
    if(':' in mystr):
        myhour, myminute, mysecond = mystr.split(":")
    else:
        myhour = '0'
        myminute = '0'
        mysecond = mystr
    if('.' in mysecond):
        mysecond,mymicrosecond = mysecond.split(".")
    else:
        mymicrosecond = '0'
    return time(hour=int(myhour), minute=int(myminute), second=int(mysecond), microsecond=int(mymicrosecond))
    # end extract_time_stamp_from_string

########################################################################

def get_factor_rounding():
    return 100000000.0
    # end get_factor_rounding

########################################################################

def build_full_utc_time_from_elements(x1, x2, x3):
    # returns a datetime.datetime object = time stamp
    # all inputs are doubles
    myshft = get_factor_rounding()
    xutc = x1 * myshft + x2 + x3
    return datetime.utcfromtimestamp(float(xutc))
    # end build_full_utc_time_from_elements

########################################################################

def build_small_utc_time_from_full_one(xtime):
    myshft = get_factor_rounding()
    x1 = float(int(xtime/myshft))
    x2 = float(int(xtime-x1*myshft))
    x3 = xtime - int(xtime)
    return x2
    # end build_small_utc_time_from_full_one

########################################################################

def decompose_utc_time_to_floats(xtime):
    myshft = get_factor_rounding()
    x1 = float(int(xtime/myshft))
    x2 = float(int(xtime-x1*myshft))
    x3 = xtime - int(xtime)
    return (x1, x2, x3)
    # end decompose_utc_time_to_floats

########################################################################

def my_thread_kill():
    thread.interrupt.main()
    print('thread exit')
    sys.exit()
    print('sys exit')
    # end my_thread_kill

########################################################################

# ==================================================================

def get_ambient_temperature(simulation, wetter_file, actual_time, start_datetime, start_sim_inh, end_sim_inh):
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
        #print('UTILS: actual_time ={}; start_datetime = {}; simtime = {}; start_sim_inh = {}'.format(actual_time, start_datetime, simtime, start_sim_inh))
        ii = 0
        while condition:
            line1 = get_significant_parts(wetter_file[ii].rstrip().split(" "))
            hour = get_time_in_hour(line1)
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
        line2 = get_significant_parts(wetter_file[jj].rstrip().split(" "))
        x1 = hour
        x2 = get_time_in_hour(line2)
        y1 = float(get_ith_column(8, line1))
        y2 = float(get_ith_column(8, line2))
        #print('UTILS: ii = {}, jj = {}, simtime = {}, x1 = {}, x2 = {}, y1 = {}, y2 = {}, wyn = {}'.format(ii, jj, simtime, x1,x2,y1,y2,linear_interpolation(simtime, x1, x2, y1, y2)))
        # time since the beginning of the start of the simulation in hours 
        return linear_interpolation(simtime, x1, x2, y1, y2)
    else:
        # real time calculation - values are received via MQTT? - dead for now
        return 10.0

#end get_ambient_temperature


# ==================================================================

def get_jth_column_val(simulation, wetter_file, actual_time, start_datetime, start_sim_inh, end_sim_inh, max_counter, time_col_nr, val_col_nr):
    # returns ambient air temperature as read from the wetter_file in the TRY04 format
    # simulation     - flag for real time or file based 
    # wetter_file    - file with weather parameters in TRY04 format
    # actual_time    - the current time or current simulation time in the datetime format
    # start_datetime - start of the calculations in datetime format
    # start_sim_inh  - only in simulation mode - the starting point of the simulation in hours - will be found in the wetter_file
    # end_sim_inh    - only in simulation mode - the end point of the simulation in hours - arbitrarily stated
    if simulation:
        #max_counter = 8760
        #val_col_nr = 8
        # file based simulation - values are read from the file
        #            hour_of_year = 1
        condition = True
        simtime = ((actual_time - start_datetime).total_seconds() / 3600.0) + start_sim_inh  # simulationstime in h
        #print('   UTILS: simtime = {}'.format(simtime))
        #print('   UTILS: actual_time ={}; start_datetime = {}; simtime = {}; start_sim_inh = {}'.format(actual_time, start_datetime, simtime, start_sim_inh))
        ii = 0
        kk = 0
        while condition:
            #print('______________ ii = {}'.format(ii))
            #print('______________ wfile = {}'.format(wetter_file[ii]))
            line1 = get_significant_parts(wetter_file[ii].rstrip().split(" "))
            #print('    UTILS: time_col_nr = {}; line = {}'.format(time_col_nr, line1))
            hour = float(get_ith_column(time_col_nr, line1)) + kk * max_counter
            #print('    UTILS: ii = {}; kk = {}; hour = {}; simtime = {}'.format(ii, kk, hour, simtime))
            condition = (hour < simtime)
            ii = ii + 1
            if (ii >= max_counter):
                ii = 0
                kk = kk + 1
        #print('    UTILS: ii = {}'.format(ii))
        if (ii == 0):
            ii = max_counter  # ==> jj after this if will become jj:=max_counter - 1
        else:
            ii = ii - 1
        jj = ii - 1
        if jj<0:              # should never take place thanks to the previous if
            jj = max_counter - 1
        line2 = get_significant_parts(wetter_file[jj].rstrip().split(" "))
        x1 = hour
        x2 = float(get_ith_column(time_col_nr, line2))
        y1 = float(get_ith_column(val_col_nr, line1))
        y2 = float(get_ith_column(val_col_nr, line2))
        #print('    UTILS: ii = {}, jj = {}, simtime = {}, x1 = {}, x2 = {}, y1 = {}, y2 = {}, wyn = {}'.format(ii, jj, simtime, x1,x2,y1,y2,linear_interpolation(simtime, x1, x2, y1, y2)))
        # time since the beginning of the start of the simulation in hours 
        return linear_interpolation(simtime, x1, x2, y1, y2)
    else:
        # real time calculation - values are received via MQTT? - dead for now
        return 10.0

#end get_ambient_temperature


#=======================================================================

def it_is_winter(actual_time):
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

def it_is_summer(actual_time):
   if(actual_time.month in range(6, 8)):
       return True
   elif((actual_time.month == 5) and (actual_time.day >= 15)):
       return True
   elif((actual_time.month == 9) and (actual_time.day <= 14)):
       return True
   else:
       return False

#=======================================================================

def get_slp_data_set(actual_time, el_data, time_slot_in_s):
    # returns data set with predicted electrical loads in kW 
    # for one day divided into slots of time_slot_in_s seconds
    # starting with the value representative for the actual_time
    # data come from el_data i.e. json data structure as defined in config.json prediction->power->SLP

    # determine the season of the year: summer, winter of the transition period between them
    if(it_is_summer(actual_time)):
        # summer time from 15.05 to 14.09
        season = el_data['summer time']
    elif(it_is_winter(actual_time)):
        # winter time from 1.11 to 20.03
        season = el_data['winter time']
    else:
        # transition period from 21.03 to 14.05 and from 15.09 to 31.10
        season = el_data['transition period']

    # determine the type of the day and get the respective data set
    if(actual_time.isoweekday() in range(1, 5)):
        data_set = season['workday']
    elif(actual_time.isoweekday() == 6):
        data_set = season['Saturday']
    else:
        data_set = season['Sunday']

    # find the position of actual_time in the data set
    # determine actual_time in seconds
    act_time_in_s = actual_time.hour*3600.0 + actual_time.minute*60.0 + actual_time.second + actual_time.microsecond / 1000000.0
    # find number of the time slot that it is in
    idx = int(act_time_in_s // time_slot_in_s)
    #print('UTILS: idx = {}'.format(idx))
    # create new data set that starts with the record of the actual time
    wyn = data_set[idx:] + data_set[:idx]

    # return the resulting new data set
    return wyn
    # end get_slp_data_set

#=======================================================================


#=======================================================================
