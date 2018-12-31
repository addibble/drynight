from magicbluelib import MagicBlue
from bluepy.btle import BTLEException
import zmq
import time
from constants import ZMQAddrs, MACAddrs
from containers import *


c = zmq.Context()
s = c.socket(zmq.SUB)
s.bind(ZMQAddrs.LIGHT)
s.setsockopt(zmq.SUBSCRIBE, b"")

while True:
    try:
        o = s.recv_pyobj()
        print(o)
    except:
        raise
    try:
        if not mb.test_connection():
            raise BTLEException
    except (BTLEException, NameError):
        mb = MagicBlue(MACAddrs.light, version=10)
        mb.connect()

    if o.command == "warm":
        mb.set_warm_light(intensity=o.value)
    elif o.command == "color":
        mb.set_color(o.value)
    elif o.command == "on":
        mb.turn_on()
    elif o.command == "off":
        mb.turn_off()
