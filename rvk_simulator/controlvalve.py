

########################################################################

class ThreeWayControlValve:
    # constructor method with instance variables
    def __init__(self, hub_position):
        self.hub_position = hub_position

    def set_hub(self, new_position):
        self.hub_position = new_position

    def get_hub(self):
        return self.hub_position
