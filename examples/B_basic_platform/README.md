# B_basic_platform

Examples of configuration for gateway running in artificial time and 
communicating with the platform over localhost (127.0.0.1). It requires 
the platform and especially the mqtt broker to run on the same machine.

Both examples allow simulation of communication between the platform and
 simulator of gateway. Together they form the virtual power plant that 
 is controlled by the platform.

**Example bsp01_1plat4gw_noAuth_noDemo** is the base solution with 
simulation of data dispatch every in intervalls of 10 seconds.

Example bsp03_1plat4gw_noAuth_Demo is a proposal for the configuration 
that will send to the platform data of one day within the time intervall
 of around 3 minutes. The interdependencies between the variables and 
 estimation of required inputs are given in the Excel file 
 bsp03_1plat4gw_noAuth_Demo/time_management.xlsx

The directory bsp03_1plat4gw_noAuth_Demo/demonstrator contains software 
which emulates physical device connected to the gateway software. 
It receives data from the potentiometer (between 0 and 255) and adapts 
the daily profile of thermal load by adjusting its maximum between 5 and
 10 kW in the file lastgang.dat. The demonstrator also receives data 
from the gateway, derives the day time from it and sends back to the 
gateway the momentaneous thermal load depending on the time of the day 
based upon the file lastgang.dat. 

Integration of the demo1.py with the real simulator would mean that the 
demonstrator is being eliminated and the physical device directly 
communicates with the gateway emulator by sending it its momentaneous 
heat production that can be calculated from the temperatures and assumed
 constant mass flow in the hydraulic circuit. The device, in its turn, 
would receive signals from potentiometer.

In the current stage, the potentiometer is also emulated by the script 
bsp03_1plat4gw_noAuth_Demo/demonstrator/potentiometer/pott1.py.
