from datetime import datetime, timedelta
import math


class timestepmanager:
    """ manages the timestep of the simulation """
    def __init__(self, maximal_timestep_in_s, minimal_timestep_in_s, current_time):
        self.redo_timestep = False
        self.new_timestep = maximal_timestep_in_s
        self.max_timestep = maximal_timestep_in_s
        self.current_timestep = maximal_timestep_in_s
        self.end_of_tstep = current_time + timedelta(seconds = maximal_timestep_in_s)
        self.min_timestep = minimal_timestep_in_s
        self.dbg = 0
        if(self.dbg > 0):
            print('current timestep = {} s'.format(self.current_timestep))

    def get_redo(self):
        return self.redo_timestep

    def set_redo(self, new_redo):
        self.redo_timestep = new_redo

    def set_new_tstep(self, new_tstep):
        if(self.dbg > 1):
            print('old timestep = {}; new timestep = {}'.format(self.current_timestep, new_tstep))
        self.new_timestep =max(min(new_tstep, self.new_timestep), self.min_timestep)
        self.redo_timestep = True

    def update_timestep(self, current_time):
        nn = math.floor(self.get_dist_to_end(current_time) / self.new_timestep) + 1
        self.current_timestep = self.get_dist_to_end(current_time) / nn
        if(self.dbg > 1):
            print('set timestep = {} at time = {}'.format(self.current_timestep, current_time))
        self.redo_timestep = False

    def has_timestep_ended(self, current_time):
        if(current_time >= self.end_of_tstep):
            self.end_of_tstep = current_time + timedelta(seconds = self.max_timestep)
            if(self.dbg > 0):
                if(self.current_timestep != self.max_timestep):
                    print('reset to {} s at time {}'.format(self.max_timestep, current_time))
            self.current_timestep = self.max_timestep
            return True
        else:
            return False

    def get_timestep(self):
        return self.current_timestep

    def get_dist_to_end(self, current_time):
        return (self.end_of_tstep - current_time).total_seconds()

    def set_end_time(self, new_current_time):
        self.end_of_tstep = new_current_time + timedelta(seconds = self.max_timestep)

        
            
            
        