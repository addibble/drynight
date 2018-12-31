import struct
import time
import logging
from datetime import datetime
from Crypto.Cipher import AES
from bluepy.btle import Peripheral, DefaultDelegate, ADDR_TYPE_RANDOM, BTLEException
from constants import UUIDS, AUTH_STATES, ALERT_TYPES
from containers import HeartRateReading, AccelerometerReading
import zmq

last = {}
last['hrm'] = None
last['accel'] = None

class AuthenticationDelegate(DefaultDelegate):

    """This Class inherits DefaultDelegate to handle the authentication process."""

    def __init__(self, device, zsock, log=None):
        DefaultDelegate.__init__(self)
        self.device = device
        if log:
            self._log = log
        else:
            self._log = logging.getLogger(self.__class__.__name__)
        self.zsock = device.zsock
 
    def handleNotification(self, hnd, data):
        # Debug purposes
        if hnd == self.device._char_auth.getHandle():
            if data[:3] == b'\x10\x01\x01':
                self.device._req_rdn()
            elif data[:3] == b'\x10\x01\x04':
                self.device.auth_state = AUTH_STATES.KEY_SENDING_FAILED
            elif data[:3] == b'\x10\x02\x01':
                # 16 bytes
                random_nr = data[3:]
                self.device._send_enc_rdn(random_nr)
            elif data[:3] == b'\x10\x02\x04':
                self.device.auth_state = AUTH_STATES.REQUEST_RN_ERROR
            elif data[:3] == b'\x10\x03\x01':
                self.device.auth_state = AUTH_STATES.AUTH_OK
            elif data[:3] == b'\x10\x03\x04':
                self.device.auth_state = AUTH_STATES.ENCRIPTION_KEY_FAILED
                self.device._send_key()
            else:
                self.device.auth_state = AUTH_STATES.AUTH_FAILED
        else:
            sensor = struct.unpack('b', data[0])[0]
            seq = struct.unpack('B', data[1])[0]
            length = len(data)
            if hnd == 56 and sensor == 1 and len(data) == 8:
                res = struct.unpack('hhh', data[2:])
                self.zsock.send_pyobj(AccelerometerReading(time.time(), list(res), mac=self.device.mac_address))
                last['accel'] = time.time()
            elif hnd == 56:
                pass
                #self._log.debug("hnd {} sensor {} len {} seq {}".format(hnd, sensor, length, seq))

            elif hnd == 41:
                hr = struct.unpack('B', data[1])[0]
                self.zsock.send_pyobj(HeartRateReading(time.time(), hr, mac=self.device.mac_address))
                last['hrm'] = time.time()
            #if len(data) == 20: # raw accel data
            #    pass
                #print "Accel x: %s y: %s z: %s" % struct.unpack('hhh', data[2:8])
                #print "Accel x: %s y: %s z: %s" % struct.unpack('hhh', data[8:14])
                #print "Accel x: %s y: %s z: %s" % struct.unpack('hhh', data[14:])
            #elif sensor == 2 and len(data) == 10:
            #    res = struct.unpack('hhhh', data[2:])
            #    print("h56 sensor 2 len 10 {}".format(res))
            else:
                self._log.debug("hnd {} sensor {} len {} seq {}".format(hnd, sensor, length, seq))

class MiBand2(Peripheral):
    _KEY = b'\xf5\xd2\x29\x87\x65\x0a\x1d\x82\x05\xab\x82\xbe\xb9\x38\x59\xcf'
    _send_key_cmd = struct.pack('<18s', b'\x01\x00' + _KEY)
    _send_rnd_cmd = struct.pack('<2s', b'\x02\x00')
    _send_enc_key = struct.pack('<2s', b'\x03\x00')

    def __init__(self, mac_address, zsock, timeout=0.5, debug=False):
        FORMAT = '%(asctime)-15s %(name)s (%(levelname)s) > %(message)s'
        logging.basicConfig(format=FORMAT)
        log_level = logging.WARNING if not debug else logging.DEBUG
        self._log = logging.getLogger(self.__class__.__name__)
        self._log.setLevel(log_level)
        self.zsock = zsock

        self._log.info('Connecting to ' + mac_address)
        Peripheral.__init__(self, mac_address, addrType=ADDR_TYPE_RANDOM)
        self._log.info('Connected')

        self.timeout = timeout
        self.mac_address = mac_address
        self.auth_state = None

        # TODO clean this up
        self.svc_1 = self.getServiceByUUID(UUIDS.svc['MIBAND1'])
        self.svc_2 = self.getServiceByUUID(UUIDS.svc['MIBAND2'])
        self.svc_heart = self.getServiceByUUID(UUIDS.svc['HEART_RATE'])

        self._char_auth = self.svc_2.getCharacteristics(UUIDS.char['AUTH'])[0]
        self._desc_auth = self._char_auth.getDescriptors(forUUID=UUIDS.notif['DESCRIPTOR'])[0]

        self._char_heart_ctrl = self.svc_heart.getCharacteristics(UUIDS.char['HEART_RATE_CONTROL'])[0]
        self._char_heart_measure = self.svc_heart.getCharacteristics(UUIDS.char['HEART_RATE_MEASURE'])[0]

        # Enable auth service notifications on startup
        self._auth_notif(True)
        # Let MiBand2 to settle
        self.waitForNotifications(0.1)

    # Auth helpers ######################################################################

    def _auth_notif(self, enabled):
        if enabled:
            self._log.info("Enabling Auth Service notifications status...")
            self._desc_auth.write(b"\x01\x00", True)
        elif not enabled:
            self._log.info("Disabling Auth Service notifications status...")
            self._desc_auth.write(b"\x00\x00", True)
        else:
            self._log.error("Something went wrong while changing the Auth Service notifications status...")

    def _encrypt(self, message):
        aes = AES.new(self._KEY, AES.MODE_ECB)
        return aes.encrypt(message)

    def _send_key(self):
        self._log.info("Sending Key...")
        self._char_auth.write(self._send_key_cmd)
        self.waitForNotifications(self.timeout)

    def _req_rdn(self):
        self._log.info("Requesting random number...")
        self._char_auth.write(self._send_rnd_cmd)
        self.waitForNotifications(self.timeout)

    def _send_enc_rdn(self, data):
        self._log.info("Sending encrypted random number")
        cmd = self._send_enc_key + self._encrypt(data)
        send_cmd = struct.pack('<18s', cmd)
        self._char_auth.write(send_cmd)
        self.waitForNotifications(self.timeout)

    # Parse helpers ###################################################################

    def _parse_date(self, bytes):
        year = struct.unpack('h', bytes[0:2])[0] if len(bytes) >= 2 else None
        month = struct.unpack('b', bytes[2])[0] if len(bytes) >= 3 else None
        day = struct.unpack('b', bytes[3])[0] if len(bytes) >= 4 else None
        hours = struct.unpack('b', bytes[4])[0] if len(bytes) >= 5 else None
        minutes = struct.unpack('b', bytes[5])[0] if len(bytes) >= 6 else None
        seconds = struct.unpack('b', bytes[6])[0] if len(bytes) >= 7 else None
        day_of_week = struct.unpack('b', bytes[7])[0] if len(bytes) >= 8 else None
        fractions256 = struct.unpack('b', bytes[8])[0] if len(bytes) >= 9 else None

        return {"date": datetime(*(year, month, day, hours, minutes, seconds)), "day_of_week": day_of_week, "fractions256": fractions256}

    def _parse_battery_response(self, bytes):
        level = struct.unpack('b', bytes[1])[0] if len(bytes) >= 2 else None
        last_level = struct.unpack('b', bytes[19])[0] if len(bytes) >= 20 else None
        status = 'normal' if struct.unpack('b', bytes[2])[0] == 0 else "charging"
        datetime_last_charge = self._parse_date(bytes[11:18])
        datetime_last_off = self._parse_date(bytes[3:10])

        # WTF?
        # struct.unpack('b', bytes[10])
        # struct.unpack('b', bytes[18])
        # print struct.unpack('b', bytes[10]), struct.unpack('b', bytes[18])

        res = {
            "status": status,
            "level": level,
            "last_level": last_level,
            "last_level": last_level,
            "last_charge": datetime_last_charge,
            "last_off": datetime_last_off
        }
        return res

    def initialize(self):
        self.setDelegate(AuthenticationDelegate(self, self.zsock, log=self._log))
        self._send_key()

        while True:
            self.waitForNotifications(0.1)
            if self.auth_state == AUTH_STATES.AUTH_OK:
                self._log.info('Initialized')
                self._auth_notif(False)
                return True
            elif self.auth_state is None:
                continue

            self._log.error(self.auth_state)
            return False

    def authenticate(self):
        self.setDelegate(AuthenticationDelegate(self, self.zsock, log=self._log))
        self._req_rdn()

        while True:
            self.waitForNotifications(0.1)
            if self.auth_state == AUTH_STATES.AUTH_OK:
                self._log.info('Authenticated')
                return True
            elif self.auth_state is None:
                continue

            self._log.error(self.auth_state)
            return False

    def get_battery_info(self):
        char = self.svc_1.getCharacteristics(UUIDS.char['BATTERY'])[0]
        return self._parse_battery_response(char.read())

    def get_current_time(self):
        char = self.svc_1.getCharacteristics(UUIDS.char['CURRENT_TIME'])[0]
        return self._parse_date(char.read()[0:9])

    def get_revision(self):
        svc = self.getServiceByUUID(UUIDS.svc['DEVICE_INFO'])
        char = svc.getCharacteristics(UUIDS.char['REVISION'])[0]
        data = char.read()
        revision = struct.unpack('9s', data[-9:])[0] if len(data) == 9 else None
        return revision

    def get_hrdw_revision(self):
        svc = self.getServiceByUUID(UUIDS.svc['DEVICE_INFO'])
        char = svc.getCharacteristics(UUIDS.char['HRDW_REVISION'])[0]
        data = char.read()
        revision = struct.unpack('8s', data[-8:])[0] if len(data) == 8 else None
        return revision

    def set_encoding(self, encoding="en_US"):
        char = self.svc_1.getCharacteristics(UUIDS.char['CONFIGURATION'])[0]
        packet = struct.pack('5s', encoding)
        packet = b'\x06\x17\x00' + packet
        return char.write(packet)

    def set_heart_monitor_sleep_support(self, enabled=True, measure_minute_interval=1):
        char_m = self.svc_heart.getCharacteristics(UUIDS.char['HEART_RATE_MEASURE'])[0]
        char_d = char_m.getDescriptors(forUUID=UUIDS.notif['DESCRIPTOR'])[0]
        char_d.write(b'\x01\x00', True)
        self._char_heart_ctrl.write(b'\x15\x00\x00', True)
        # measure interval set to off
        self._char_heart_ctrl.write(b'\x14\x00', True)
        if enabled:
            self._char_heart_ctrl.write(b'\x15\x00\x01', True)
            # measure interval set
            self._char_heart_ctrl.write(b'\x14' + str(measure_minute_interval).encode(), True)
        char_d.write(b'\x00\x00', True)

    def get_serial(self):
        svc = self.getServiceByUUID(UUIDS.svc['DEVICE_INFO'])
        char = svc.getCharacteristics(UUIDS.char['SERIAL'])[0]
        data = char.read()
        serial = struct.unpack('12s', data[-12:])[0] if len(data) == 12 else None
        return serial

    def get_steps(self):
        char = self.svc_1.getCharacteristics(UUIDS.char['STEPS'])[0]
        a = char.read()
        steps = struct.unpack('h', a[1:3])[0] if len(a) >= 3 else None
        meters = struct.unpack('h', a[5:7])[0] if len(a) >= 7 else None
        fat_gramms = struct.unpack('h', a[2:4])[0] if len(a) >= 4 else None
        # why only 1 byte??
        callories = struct.unpack('b', a[9])[0] if len(a) >= 10 else None
        return {
            "steps": steps,
            "meters": meters,
            "fat_gramms": fat_gramms,
            "callories": callories

        }

    def send_alert(self, _type):
        svc = self.getServiceByUUID(UUIDS.svc['ALERT'])
        char = svc.getCharacteristics(UUIDS.char['ALERT'])[0]
        char.write(_type)

    def enumerate(self):
        for service in self.getServices():
            print(service)
            for characteristic in service.getCharacteristics():
                if str(characteristic.uuid) in UUIDS.char_by_uuid:
                    uuid_name = UUIDS.char_by_uuid[str(characteristic.uuid)]
                else:
                    uuid_name = characteristic.uuid.getCommonName()
                print(uuid_name, characteristic.getHandle(), characteristic.propertiesToString())

    def record_data(self, accel_reset_time=60, ping_time=10, hrm_timeout=6, accel_timeout=3):
        char_m = self.svc_heart.getCharacteristics(UUIDS.char['HEART_RATE_MEASURE'])[0]
        notif_descriptor = char_m.getDescriptors(forUUID=UUIDS.notif['DESCRIPTOR'])[0]
        char_ctrl = self.svc_heart.getCharacteristics(UUIDS.char['HEART_RATE_CONTROL'])[0]
        char_sensor = self.svc_1.getCharacteristics(UUIDS.char['SENSOR'])[0]

        notif_descriptor.write(b'\x01\x00', True)
        char_ctrl.write(b'\x15\x01\x01', True)
        char_sensor.write(b'\x01\x03\x19')
        char_sensor.write(b'\x02')

        last_ping = time.time()
        accel_start = time.time()
        while True:
            try:
                self.waitForNotifications(1)
                t = time.time()
                if (t - last_ping) >= ping_time:
                    char_ctrl.write(b'\x16', True)
                    last_ping = t
                if (t - accel_start) > accel_reset_time:
                    self._log.error("resetting accel {}".format(t-accel_start))
                    notif_descriptor.write(b'\x01\x00', True)
                    char_sensor.write(b'\x01\x03\x19')
                    char_sensor.write(b'\x02')
                    accel_start = t
                if last['hrm'] and (t - last['hrm']) > hrm_timeout:
                    self._log.error("timeout for hrm {}".format(t-last['hrm']))
                    notif_descriptor.write(b'\x01\x00', True)
                    char_ctrl.write(b'\x15\x01\x01', True)
                    last['hrm'] = t
                if last['accel'] and (time.time() - last['accel']) > accel_timeout:
                    self._log.error("timeout for accel {}".format(t-last['accel']))
                    notif_descriptor.write(b'\x01\x00', True)
                    char_sensor.write(b'\x01\x03\x19')
                    char_sensor.write(b'\x02')
                    last['accel'] = t

            except Exception as e:
                self._log.error("exception: {}".format(e))
                self.stop_realtime()
                # TODO figure out how to reinit when BLE disconnects
                raise
            except KeyboardInterrupt:
                self._log.error("interrupt")
                self.stop_realtime()
                raise
            except IOError:
                self._log.error("ioerror")
                self.stop_realtime()
                raise

    def stop_realtime(self):
        char_m = self.svc_heart.getCharacteristics(UUIDS.char['HEART_RATE_MEASURE'])[0]
        char_d = char_m.getDescriptors(forUUID=UUIDS.notif['DESCRIPTOR'])[0]
        char_ctrl = self.svc_heart.getCharacteristics(UUIDS.char['HEART_RATE_CONTROL'])[0]

        char_sensor1 = self.svc_1.getCharacteristics(UUIDS.char['HZ'])[0]
        char_sens_d1 = char_sensor1.getDescriptors(forUUID=UUIDS.notif['DESCRIPTOR'])[0]

        char_sensor2 = self.svc_1.getCharacteristics(UUIDS.char['SENSOR'])[0]

        # stop heart monitor continues
        char_ctrl.write(b'\x15\x01\x00', True)
        char_ctrl.write(b'\x15\x01\x00', True)
        # IMO: stop heart monitor notifications
        char_d.write(b'\x00\x00', True)
        # WTF
        char_sensor2.write(b'\x03')
        # IMO: stop notifications from sensors
        char_sens_d1.write(b'\x00\x00', True)

        self.heart_measure_callback = None
        self.heart_raw_callback = None
        self.accel_raw_callback = None
