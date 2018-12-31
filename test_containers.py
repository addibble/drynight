import zmq
from containers import AccelerometerReading, HeartRateReading
import time

def test_containers():
    c = zmq.Context()
    s = c.socket(zmq.PUB)
    s.bind("tcp://127.0.0.1:6001")
    s.send_pyobj(AccelerometerReading(time.time(), (1.1,2.2,3.3), mac="AA:BB:CC:DD:EE:FF"))
    time.sleep(1)
    s.send_pyobj(AccelerometerReading(time.time(), (1.1,2.2,3.3), mac="AA:BB:CC:DD:EE:FF"))

