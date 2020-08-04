# examples - general directory

There are four groups of example configurations that are presented here:

**A_basic_simulation**: Example of configuration for a stand alone 
calculation of the gateway. It has no prerequisites, i.e. there is no 
need for the platform to run in the background for this example to work.

**B_basic_platform**: Examples of configuration for gateway running in 
artificial time and communicating with the platform over localhost 
(127.0.0.1). It requires the platform and especially the mqtt broker to 
run on the same machine.

**C_external_platform**: Examples of configuration for gateway running in 
artificial time and communicating with the platform of TU-Dresden along 
with authentication mechanism.
It requires the platform to run on the domain http://fiware.n5geh.de 

**D_real_time_operation**: Examples of configuration for gateway running in 
the real time as it might with real devices. 
It requires the platform to run either at localhost or at the TU-Dresden
 domain.

**REMARK on operation of gateways**:
Except for the standalone configuration A, it is highly advisable to 
start the fiware platform first, then proceed with running the platform 
script (py plat1.py) and then the gateways in any arbitrary order 
(py rvk1.py). 
When a gateway is started it starts its provisioning procedure with the 
platform. In some earlier versions of the fiware platform, the 
provisioning for the first gateway (with id: urn:ngsi-ld:rvk:001) has 
been already incorporated into the initializating scrpits of the fiware 
platform. In such a case, when the real_time_mode is off, the gateway 
will wait in vain for its time data that it needs to start in a 
synchronized manner with the platform. After around 15 seconds the 
gateway will undo its provisioning (as can be seen in the list of 
active gateways on the platform) and quit.
It should be simply restarted and then the whole provisioning and 
initialization procedure should execute flawlessly.