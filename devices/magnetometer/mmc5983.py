from machine import SoftI2C
from sys import maxsize
import time
import ustruct

from utils.calibration import calibration

DEFAULT_CALIBRATION = [
    [1.0, 131072.0],
    [1.0, 131072.0],
    [1.0, 131072.0],
]

DEFAULT_CALIBRATION = [[0.007823502, 140235.0], [0.0077513372, -124671.5], [0.008930166, -133331.0]]

class MMC5983:
    def __init__(self, i2c, addr=0x30, board_orientation=None, calib=None):
        self.i2c = i2c
        self.addr = addr
        if board_orientation is None:
             self._board_orientation = ((2, 1), (1, -1), (0, -1))
        else:
            self._board_orientation = board_orientation
        self._calib = calib if calib else calibration.get('MMC5983', DEFAULT_CALIBRATION)

        # Registers
        self.REG_DATA = 0x00
        self.REG_CTRL0 = 0x09
        self.REG_CTRL1 = 0x0A
        self.REG_CTRL2 = 0x0B
        self.REG_ID    = 0x2F

        # Constants
        self.BW_100HZ = 0x00
        self.CM_100HZ = 0x05
        self.CONTINUOUS_MODE = 0x08

        # Check ID
        pid = self._read_reg(self.REG_ID, 1)
        if pid:
            print(f"MMC5983: Found ID {hex(pid[0])}")

        # Initialize
        self.reset()
        self.enable_continuous()

    def _write_reg(self, reg, val):
        try:
            self.i2c.writeto_mem(self.addr, reg, bytes([val]))
        except Exception as e:
            print(f"Write Error: {e}")

    def _read_reg(self, reg, length):
        try:
            return self.i2c.readfrom_mem(self.addr, reg, length)
        except: return None

    def reset(self):
        """Enable Auto Set/Reset feature"""
        self._write_reg(self.REG_CTRL0, 0x08)
        time.sleep(0.01)

    def enable_continuous(self):
        """Configure for 100Hz Continuous Read"""
        self._write_reg(self.REG_CTRL1, self.BW_100HZ)
        val = self.CONTINUOUS_MODE | self.CM_100HZ
        self._write_reg(self.REG_CTRL2, val)
        self._write_reg(self.REG_CTRL0, 0x08)
        time.sleep(0.1)
        print("MMC5983: Continuous 100Hz Enabled")

    def read_mag_xyz_raw(self):
        """Returns a tuple of raw, re-oriented 18-bit sensor values (x, y, z)."""
        try:
            raw_sensor = [0, 0, 0]
            data = self._read_reg(self.REG_DATA, 7)
            if not data: return None
            # Manual MSB/LSB assembly to ensure correct Endianness
            raw_sensor[0] = (data[0] << 8 | data[1]) << 2 | ((data[6] >> 6) & 0x03)
            raw_sensor[1] = (data[2] << 8 | data[3]) << 2 | ((data[6] >> 4) & 0x03)
            raw_sensor[2] = (data[4] << 8 | data[5]) << 2 | ((data[6] >> 2) & 0x03)

            # Re-orient axes and apply sign
            x_out = raw_sensor[self._board_orientation[0][0]] * self._board_orientation[0][1]
            y_out = raw_sensor[self._board_orientation[1][0]] * self._board_orientation[1][1]
            z_out = raw_sensor[self._board_orientation[2][0]] * self._board_orientation[2][1]

            return (x_out, y_out, z_out)

        except Exception as e:
            print(f"Error reading mag raw: {e}")
            return None
    def read_mag_xyz(self):
        """Returns a calibrated and normalized tuple (x, y, z)."""
        raw = self.read_mag_xyz_raw()
        if raw:
            # Apply calibration: (Raw - Offset) * Scale
            x_cal = (raw[0] - self._calib[0][1]) * self._calib[0][0]
            y_cal = (raw[1] - self._calib[1][1]) * self._calib[1][0]
            z_cal = (raw[2] - self._calib[2][1]) * self._calib[2][0]
            return (x_cal, y_cal, z_cal)
        else:
            return None

    def calibrate(self, calib_time=20):
        start_time = time.ticks_ms()
        min_x, max_x = maxsize, -maxsize
        min_y, max_y = maxsize, -maxsize
        min_z, max_z = maxsize, -maxsize
        x, y, z = 0, 0, 0

        while time.ticks_diff(time.ticks_ms(), start_time) < calib_time * 1000: # 20 seconds
            data = self.read_mag_xyz_raw()
            if data:
                x, y, z = data
                # Update Min/Max
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)
                min_z = min(min_z, z)
                max_z = max(max_z, z)
                # print(f"Sampling... X[{min_x:.1f}:{max_x:.1f}] Y[{min_y:.1f}:{max_y:.1f}] Z[{min_z:.1f}:{max_z:.1f}]")
            time.sleep(0.05)

        # Calculate Offsets (Midpoint)
        # Avoid division by zero if sensor didn't move or wasn't read
        if max_x > min_x and max_y > min_y and max_z > min_z:
            self._calib[0] = [100/(max_x - min_x), (max_x + min_x)/2]
            self._calib[1] = [100/(max_y - min_y), (max_y + min_y)/2]
            self._calib[2] = [100/(max_z - min_z), (max_z + min_z)/2]
            print(f"Calibration Complete: {self._calib}")
            calibration.set('MMC5983', self._calib)
            calibration.save_calibration()
            return True
        print("Calibration Failed")
        return False


