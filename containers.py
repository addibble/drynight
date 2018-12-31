class HeartRateReading(object):
    def __init__(self, ts, hr, mac=None):
        self.timestamp = ts
        self.xyz = (x,y,z)
        self.mac = mac
        pass

class AccelerometerReading(object):
    def __init__(self, ts, xyz, mac=None):
        self.timestamp = ts
        self.xyz = xyz
        self.mac = mac
        pass

class LightControl(object):
    def __init__(self, command, value):
        self.command = command
        self.value = value
