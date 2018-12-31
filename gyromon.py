import sys
from base import MiBand2
import zmq

def main():
    MAC = sys.argv[1]
    zctx = zmq.Context()
    zsock = zctx.socket(zmq.PUB)
    zsock.bind("tcp://127.0.0.1:6001")
    band = MiBand2(MAC, zsock, debug=True)
    band.setSecurityLevel(level="medium")

    if len(sys.argv) > 2:
        if band.initialize():
            print("Init OK")

    band.authenticate()
    band.set_heart_monitor_sleep_support(enabled=False)
    
    #print 'getting data'
    #print 'Soft revision:',band.get_revision()
    #print 'Hardware revision:',band.get_hrdw_revision()
    #print 'Serial:',band.get_serial()
    #print 'Battery:', band.get_battery_info()
    #print 'Time:', band.get_current_time()
    #print 'Steps:', band.get_steps()
    #band.enumerate()
    band.record_data()

if __name__ == "__main__":
    main()
