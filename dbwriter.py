import zmq
import sqlite3
from containers import *

def main():
    dbfile = "data.db"
    db = sqlite3.connect(dbfile)
    zctx = zmq.Context()
    zsock = zctx.socket(zmq.SUB)
    zsock.connect("tcp://127.0.0.1:6001")
    c = db.cursor()
    c.execute("PRAGMA journal_mode=WAL")
    try:
        c.execute("create table hrm_raw (time real, hr integer)")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("create table accel_raw (time real, x integer, y integer, z integer)")
    except sqlite3.OperationalError:
        pass
    db.commit()
    zsock.setsockopt(zmq.SUBSCRIBE, b"")
    while True:
        try:
            obj = zsock.recv_pyobj()
            if obj.__class__.__name__ == 'AccelerometerReading':
                print(obj.xyz)
            else:
                print("unknown type {}".format(obj.__class__.__name__))
        except zmq.ZMQError:
            if e.errno == zmq.ETERM:
                break
            else:
                raise


if __name__ == "__main__":
    main()
