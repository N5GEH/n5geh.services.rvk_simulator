from datetime import datetime, timedelta
import utils
########################################################################
def cloud_schedule_gen(actual_time, energy_vector, start_datetime, config_file):
    #config_file = utils.check_and_open_json_file('./config.json')
    output_horizon_in_h = config_file['prediction']['output_horizon_in_h']
    output_resolution_in_s = config_file['prediction']['output_resolution_in_s']
    precision_out_res = timedelta(seconds=output_resolution_in_s)
    wetter_file = utils.check_and_open_file(config_file['calculation']['simulation_mode']['weather_file_path'])        # list of strings
    start_sim_inh = config_file['calculation']['simulation_mode']['start_sim_in_hours']
    end_sim_inh = config_file['calculation']['simulation_mode']['end_sim_in_hours']
    
    lower_thresold = 100.0  # in W/m2
    upper_thresold = 350.0  # in W/m2
    
    ii = 0
    result_array = []
    for elem in energy_vector:
        out_time = elem['time stamp']
        #time_in_h = utils.convert_time_to_hours()
        dir_rad = get_direct_sun_radiation(True, wetter_file, actual_time, start_datetime, start_sim_inh, end_sim_inh)
        if(dir_rad <= lower_thresold):
            # low insolation ==> high energy prices - produce as much as possible in order to sell
            active_flag = True
            value = utils.get_tab_from_list_of_dicts('time stamp', out_time, 'P_el_max_in_W', energy_vector, precision_out_res, True, ii)
        elif(dir_rad >= upper_thresold):
            # high insolation ==> low energy prices - consume as much as possible in order to save energy or get premium for buying
            active_flag = True
            value = utils.get_tab_from_list_of_dicts('time stamp', out_time, 'P_el_min_in_W', energy_vector, precision_out_res, True, ii)
        else:
            # moderate insolation ==> run in optimal operation mode to make the most efficient use of the fuel
            active_flag = False
            value = 0.0
        
        newx = {'time_stamp' : out_time, 'activation' : active_flag , 'energy_production_in_W' : value}
        result_array.append(newx)
        ii = ii + 1
        #print(newx)
    return {'timestep_in_s' : output_resolution_in_s, 'active schedule' : True, 'values' : result_array}
    # end cloud_schedule_gen

########################################################################

def get_direct_sun_radiation(simulation, wetter_file, actual_time, start_datetime, start_sim_inh, end_sim_inh):
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
    #end get_direct_sun_radiation

########################################################################

def send_schedule_to_rvk(current_schedule, platform_mqtt_client, apiKey, sensor_name, attributes, fnr):
    #apiKey = 'QKAAbMxLbv5TfhFxjTv4lhw92m'
    #sensor_name = 'urn:ngsi-ld:rvk:001'
    #attributes = 'cmd'   # HERE TO DO YET ASK STEPHAN what it was fiware tutorial mqtt
    topic = "/{}/{}/{}".format(apiKey, sensor_name, attributes)
    print('\n\n\n\n\nsuscribed to topic {}'.format(topic))
    (columns, data_to_send) = generate_payload_from_platform(current_schedule)
    payloads = ['{}|{}'.format(c,d) for c, d in zip(columns, data_to_send)]
    print('created payload:\n{}'.format(payloads))
    platform_mqtt_client.publish(topic,'|'.join(payloads))
    print('published payloads')
    H = open("./sent_payload_"+str(fnr)+".dat","a+")
    H.write(' schedule in ul format sent from platform  \n')
    H.write(' {}  \n'.format(payloads))
    H.close()
    # end send_schedule_to_rvk

########################################################################

def generate_payload_from_platform(current_schedule):
    columns = []
    data_to_send = []
    
    columns.append('timestep_in_s')
    data_to_send.append(current_schedule['timestep_in_s'])
    
    columns.append('active schedule')
    data_to_send.append(current_schedule['active schedule'])
    
    result_array = current_schedule['values']
    
    for idx,elem in enumerate(result_array):
        columns.append('ts '+str(idx))
        data_to_send.append(elem['time_stamp'])
    
        columns.append('act '+str(idx))
        data_to_send.append(elem['activation'])
    
        columns.append('e_in_W '+str(idx))
        data_to_send.append(elem['energy_production_in_W'])

    return (columns, data_to_send)
    # end generate_payload_from_platform

########################################################################