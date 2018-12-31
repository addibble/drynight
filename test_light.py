import zmq
from containers import LightControl
from constants import ZMQAddrs
import time

def test_light():
    c = zmq.Context()
    c.setsockopt(zmq.IMMEDIATE, 0)
    c.setsockopt(zmq.DELAY_ATTACH_ON_CONNECT, 1)
    c.setsockopt(zmq.LINGER, 5)
    s = c.socket(zmq.PUB)
    s.connect(ZMQAddrs.LIGHT)
    print(dir(s))
    time.sleep(1)
    print(s)
    s.send_pyobj(LightControl("color", (255,0,0)))
    s.send_pyobj(LightControl("color", (0,255,0)))
    s.send_pyobj(LightControl("color", (0,0,255)))
    time.sleep(1)
    s.send_pyobj(LightControl("off", (0,0,0)))
    s.close()

test_light()
