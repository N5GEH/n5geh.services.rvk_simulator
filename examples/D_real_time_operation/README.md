D_real_time_operation

Examples of configuration for gateway running in the real time as it 
might with real devices. It requires the platform to run either at 
localhost or at the TU-Dresden domain.

The examples are mirroring those of B_basic_platform and 
C_external_platform but use real time steps and internal clocks of both 
gateways and the platform. This results in changes in the initialization
 procedure of gateway at the platform. 
 
In this mode the platform and gateways will potentiall run indefinitely 
or until they crash on their own. The removal of redundant gateways from
 the platform has to be done either manually or by using some other 
 script. In other words, each gateway that is provisioned with the 
 platform will stay registered with it unless the provisioning is undone
 by some other actor.

Both examples refer to the normal use case without demonstrator 
operation as such a combination is deemed impracticable and therefore 
highly unlikely.

Only the example bsp04_1plat4gw_noAuth_noDemo has been successfully 
tested.