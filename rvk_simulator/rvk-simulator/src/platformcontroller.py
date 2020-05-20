from datetime import datetime, timedelta
import utils
########################################################################
def cloud_schedule_gen(actual_time, energy_vector, start_datetime):
        config_file = utils.check_and_open_json_file('./config.json')
        output_horizont_in_h = config_file['prediction']['output_horizont_in_h']
        output_resolution_in_s = config_file['prediction']['output_resolution_in_s']
        wetter_file = utils.check_and_open_file(config_file['calculation']['simulation_mode']['weather_file_path'])        # list of strings
        start_sim_inh = config_file['calculation']['simulation_mode']['start_sim_in_hours']
        end_sim_inh = config_file['calculation']['simulation_mode']['end_sim_in_hours']
        
        lower_thresold = 100.0
        upper_thresold = 350.0
        
        
        ii = 0
        result_array = []
        for elem in energy_vector:
            out_time = elem['time stamp']
            time_in_h = convert_time_to_hours()
            dir_rad = get_direct_sun_radiation(True, wetter_file, actual_time, start_datetime, start_sim_inh, end_sim_inh)
            if(dir_rad <= lower_thresold):
                # low insolation ==> high energy prices - produce as much as possible in order to sell
                active_flag = True
                value = get_tab_from_list_of_dicts('time stamp', out_time, 'P_el_max_in_W', energy_vector, output_resolution_in_s, True, ii)
            elif(dir_rad >= upper_thresold):
                # high insolation ==> low energy prices - consume as much as possible in order to save energy or get premium for buying
                active_flag = True
                value = get_tab_from_list_of_dicts('time stamp', out_time, 'P_el_min_in_W', energy_vector, output_resolution_in_s, True, ii)
            else:
                # moderate insolation ==> run in optimal operation mode to make the most efficient use of the fuel
                active_flag = False
                value = 0.0
            
            newx = {'time_stamp' : out_time, 'activation' : active_flag , 'energy_production_in_W' : value}
            result_array.append(newx)
            ii = ii + 1
            #print(newx)
        return {'timestep_in_s' : output_resolution_in_s, 'active schedule' : True, 'values' : result_array}

########################################################################

def get_direct_sun_radiation(self, simulation, wetter_file, actual_time, start_datetime, start_sim_inh, end_sim_inh):
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
        y1 = float(utils.get_ith_column(12, line1))  # direkte Sonnenstrahlung bezogen auf die horizontale Ebene in W/m2
        y2 = float(utils.get_ith_column(12, line2))
        # time since the beginning of the start of the simulation in hours 
        return utils.linear_interpolation(simtime, x1, x2, y1, y2)
    else:
        # real time calculation - values are received via MQTT? - dead for now
        return 10.0

    #end get_ambient_temperature
########################################################################