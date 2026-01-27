# from left to right
#  /--------------------------------------------------------------\
#  | X S0 (0x10)  X S1 (0x12) X S2 (0x14) X S3 (0x16) X S4 (0x18) |
#  \-------------\                                   /------------/
#                |                                   |
#                | O                               O |
#                |          GND +3V SDA SCL          |
#                |           X   X   X   X           |
#                \-----------------------------------/
#
# I2C Address 0x50
#  Is read only LE regs [0x10, 0x11] [0x12, 0x13] [0x14, 0x15] [0x16 0x17] [0x18, 0x19]

from machine import I2C, Pin
import time

# i2c = I2C(0, scl=Pin(22), sda=Pin(23), freq=100000)
_LINE_FOLLOWER_ADDRESS = 0x50

_=[[1.6233765, -618.3441], [2.348796, -1365.0027], [2.2811532, -1306.2456], [2.7481956, -1773.2044], [2.5665708, -1598.9094]]

class LineFollower:
    def __init__(self, i2c, addr=_LINE_FOLLOWER_ADDRESS, num_sensors=5, threshold=512):
        self.i2c = i2c
        self.addr = addr
        self.num_sensors = num_sensors
        self.threshold = threshold
        self._whight0 = [0, 0, 0, 0, 0]
        self._black0 = [1023, 1023, 1023, 1023, 1023]
        self._ab = [[2.101392, -1104.9644], [2.3830804, -1390.2297], [2.235886, -1237.6746], [2.8591852, -1878.05568], [2.9390154, -1961.93968]]
        
    def read_sensor(self, sensor_id):
        if not(0 <= sensor_id < self.num_sensors):
            raise ValueError(f"Sensor {sensor_id} not found")
        reg_l = 0x10 + sensor_id * 2
        try:
            data = self.i2c.readfrom_mem(self.addr, reg_l, 2)
            value = int.from_bytes(data, 'little')
            return value
        except OSError as e:
            print(f"Error reading sensor {sensor_id} at register {hex(reg_l)}: {e}")
            return None

    def read_all_sensors(self):
        sensor_values = []
        for sensor_id in range(self.num_sensors):
            value = self.read_sensor(sensor_id)
            sensor_values.append(value)
        return sensor_values

    def read_all_normlized(self):
        ret = []
        for i, v in enumerate(self.read_all_sensors()):
            ret.append(v * self._ab[i][0] + self._ab[i][1])
        return ret

    def read_bw_sensors(self):
        ret = 0
        for i, v in self.read_all_sensors():
            ret |= (1 << i) if v < self.threshold else 0
        return ret

    def cg_line(self):
        m0 = 0
        m1 = 0
#         for i, v in enumerate(self.read_all_sensors()):
        for i, v in enumerate(self.read_all_normlized()):
            m0 += v
            m1 += v * (i - 2)
        return m1 / m0
    
    def calibrate_white(self):
        n = 10
        self._whight0 = [0 for _ in range(5)]
        print("CAL")
        for i in range(n):
            v = self.read_all_sensors()
            for i, w in enumerate(v):
                self._whight0[i] += (w / n)
        for i, b, w  in zip(range(5), self._black0, self._whight0):
            a = (1000 - 200) / ( b - w)
            c = 1000 - b * a
            print(a, c)
            self._ab[i] = [a, c]
        print(self._whight0)
        
    def calibrate_black(self):
        n = 10
        self._black0 = [0 for _ in range(5)]
        print("CAL")
        for i in range(n):
            v = self.read_all_sensors()
            for i, w in enumerate(v):
                self._black0[i] += (w / n)
        for i, b, w  in zip(range(5), self._black0, self._whight0):
            a = (1000 - 200) / ( b - w)
            c = 1000 - b * a
            print(a, c)
            self._ab[i] = [a, c]
        print(self._whight0)
        print(self._ab)


if __name__ == "__main__":
    print("\n--- Line Follower Test ---")
    i2c = I2C(0, scl=Pin(22), sda=Pin(23), freq=100000)
    lf = LineFollower(i2c, _LINE_FOLLOWER_ADDRESS)
    print(i2c.scan())
    if input('Do Clibrate [Yy]').lower() == 'y':
        _ = input("White Calibrate")
        lf.calibrate_white()
        _ = input("Black Calibrate")
        lf.calibrate_black()
#         raise Exception
    for _ in range(10):
#         sensor_data = lf.read_all_sensors()
        sensor_data = lf.read_all_normlized()
        print(sensor_data)
        poss = lf.cg_line()
        output = []
#         for sensor_name, value in enumerate(sensor_data):
#             output.append(f"{sensor_name}: {value if value is not None else 'ERR'}")
        print(" | ".join([str(i) for i in sensor_data]), poss)
        time.sleep(0.5)
