from crate import client
from datetime import datetime, timedelta, timezone
import utils
import predict_thermal

## Here, replace <CA_CERT_FILE> with the path to the CA certificate file - server verification
#connection = client.connect('https://localhost:4200/', ca_cert="<CA_CERT_FILE>", verify_ssl_cert=True)

## client verification
#connection = client.connect('https://localhost:4200/', cert_file="<CERT_FILE>", key_file="<KEY_FILE>", timeout=5, error_trace=True, username="<USERNAME>", password="<PASSWORD>")
# If you have not configured a custom database user, you probably want to authenticate as the CrateDB superuser, which is crate. The superuser does not have a password, so you can omit the password argument.

def initialize_crate_db_connection():
    """ initializes connection and returns connection cursor """
    connection = client.connect('http://127.0.0.1:4200/', timeout=50, error_trace=True, username="crate")
    return connection.cursor()

def get_heat_consumption_from_crate(cursor, start_time, horizont_in_h, pred, time_step_in_s):
    """ 
    # gets data from crate db
    # calculates from it the heat flows needed by Martin's function 
    # and passes them as result 
    """
    # 
    q_th_dhw = 0.0
    q_th_hk = 0.0
    t_a_avg = 0.0
    n_avg = 0
    p_in_MPa = utils.get_pressure_in_MPa()
    calc_opt = utils.get_calc_option()
    # 
    cursor.execute("SELECT time_index,t30_ambientairtemperature,t21_domestichotwater,t22_domesticcoldwater,v01_colddrinkingwater,t25_supply_heatingcircuit,t24_return_heatingcircuit,v02_heatingcircuit FROM mtopeniot.etrvk")
    result = cursor.fetchone()
    while result != None:
        timestamp = datetime.utcfromtimestamp(float(result[0]*0.001))
        actual_time = start_time
        if((timestamp >= start_time) and (timestamp < (start_time + timedelta(hours=horizont_in_h)))):
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
            # aggregate the data in the needed resolution
            t_act = actual_time.hour                           # t_act - actual time in hours
            q_act = (q_dhw + q_hk)/time_step_in_s              # q_act - actual heat load of the system in W 
            t_e_act = t30_ambientairtemperature                # t_e_act - ambient air temperature in grad Celcius
            # add aggregated data to the data structure for predict_thermal.py
            pred.run_to_save_data(t_act,q_act,t_e_act)
            #if(timestamp >= (actual_time + timedelta(seconds=resolution_in_s))):
            #    # save the aggregated result and reset the sums
            #    # calculate the result
            #    t_act = actual_time.hour                               # t_act - actual time in hours
            #    q_act = (q_th_dhw + q_th_hk)/(time_step_in_s * n_avg)  # q_act - actual heat load of the system in W 
            #    t_e_act = t_a_avg / n_avg                              # t_e_act - ambient air temperature in grad Celcius
            #    # add aggregated data to the data structure for predict_thermal.py
            #    pred.run_to_save_data(t_act,q_act,t_e_act)
            #    # reset - and save values for the next step
            #    t_a_avg = t30_ambientairtemperature
            #    n_avg = 1
            #    q_th_dhw = q_dhw
            #    q_th_hk = q_hk
            #    actual_time = actual_time + timedelta(seconds=resolution_in_s)
            #elif((timestamp >= actual_time) and (timestamp < (actual_time + timedelta(seconds=resolution_in_s)))):
            #    # aggregate the heat
            #    t_a_avg = t_a_avg + t30_ambientairtemperature
            #    n_avg = n_avg + 1
            #    q_th_dhw = q_th_dhw + q_dhw
            #    q_th_hk = q_th_hk + q_hk
            
            
            
            
        
        
        
#start_time = datetime.now() - timedelta(hours=horizont_in_h)




    
#cursor = initialize_crate_db_connection()
#get_heat_consumption_from_crate(cursor, start_time, horizont_in_h, pred, time_step_in_s)

print('ready to connect to crate')
connection = client.connect('http://127.0.0.1:4200/', timeout=50, error_trace=True, username="crate")

print('connected to crate, ready to get cursor')
# executing a query
cursor = connection.cursor()
print(type(cursor))
print(cursor)


print(client.paramstyle)

H = open("./full_crate.dat","w")
H.write(' all data stored in the database - hier extracted by means of linktocrate.py\n')

print('got a cursor, ready to execute query SHOW TABLES')
#cursor.execute("SELECT time_index AS 'time', ((t21_domestichotwater-t22_domesticcoldwater)*4.2*1000.0*v01_colddrinkingwater) AS 'Q_el_tot_in_kW' FROM mtopeniot.etrvk", "ORDER BY 1")
#cursor.execute("""SELECT time_index AS ?, ((t21_domestichotwater-t22_domesticcoldwater)*4.2*1000.0*v01_colddrinkingwater) AS ? FROM mtopeniot.etrvk, ORDER BY 1""", ("time","Q_el_tot_in_kW",))
#cursor.execute("""SELECT time_index AS ?, ((t21_domestichotwater-t22_domesticcoldwater)*4.2*1000.0*v01_colddrinkingwater) AS ? FROM mtopeniot.etrvk""", ("time","Q_el_tot_in_kW"))
#cursor.execute("""SELECT time_index AS ?, (( -> SELECT time_index as time, ((t21_domestichotwater-t22_domesticcoldwater)*4.2*1000.0*v01_colddrinkingwater) AS ? FROM mtopeniot.etrvk""", ("time","Q_el_tot_in_kW"))))
#cursor.execute("SELECT time_index AS time, ((t21_domestichotwater-t22_domesticcoldwater)*4.2*1000.0*v01_colddrinkingwater) AS Q_el_tot_in_kW FROM mtopeniot.etrvk", "ORDER BY 1")
cursor.execute("SHOW TABLES")

# fetching results
print('executed the first query, ready to fetch the results')
result = cursor.fetchone()
while result != None:
    print('result = {}'.format(result))
    result = cursor.fetchone()

act_time = datetime.now()
ii = 0

print('sending the second query')
myquery = "SELECT iteration,t30_ambientairtemperature,t21_domestichotwater,t22_domesticcoldwater,v01_colddrinkingwater,t25_supply_heatingcircuit,t24_return_heatingcircuit,v02_heatingcircuit,mass_flow_dhw,mass_flow_heating_water,elctric_heater_status,turnover_time_of_one_seg_in_h FROM mtopeniot.etrvk ORDER BY turnover_time_of_one_seg_in_h"
cursor.execute(myquery)
print('executed the second query, ready to fetch the results')
result = cursor.fetchone()

while result != None:
    #print(type(result),type(result[0]),result[0],float(result[0]))
    ii = ii + 1
    x1 = result[8]
    x2 = result[9]
    x3 = result[10]
    xutc = x1 * 1000000.0 + x2 + x3
    mytstamp = datetime.utcfromtimestamp(float(xutc))
    timestamp = datetime.utcfromtimestamp(float(result[0]*0.001))
    if(timestamp>(act_time - timedelta(seconds=3700))):
        print('ii = {} ; type = {} ; result = {} ; time stamp = {}'.format(ii,type(result[0]),result,timestamp))
    
    H.write('{}  {}  {}  {}\n'.format(ii, mytstamp, xutc, result))
    
    
    result = cursor.fetchone()
H.close()

print('end of data from crate DB')

