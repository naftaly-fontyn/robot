from machine import SoftI2C
import ustruct
import time
import utils.t_logger as t_logger

log = t_logger.get_logger()

class QMI8658:
    def __init__(self, i2c, addr=0x6B, board_orientation=None):
        self.i2c = i2c
        self.addr = addr
        self._init_sensor()
        # Default mapping based on your comments: X=Z, Y=-Y, Z=-X
        # Format: ((source_axis_idx, sign), ...)
        if board_orientation is None:
            self._board_orientation = ((2, 1), (1, -1), (0, -1))
        else:
            self._board_orientation = board_orientation

    def _write_reg(self, reg, val):
        self.i2c.writeto_mem(self.addr, reg, bytes([val]))

    def _read_reg(self, reg, length):
        return self.i2c.readfrom_mem(self.addr, reg, length)

    def _init_sensor(self):
        # 1. Enable Sensors (Accel + Gyro)
        self._write_reg(0x08, 0x03) # CTRL7
        time.sleep_ms(1) # Allow sensors to power up

        # 2. Enable Auto-Increment (Critical for multi-byte read)
        self._write_reg(0x02, 0x40) # CTRL1

        # 3. Accel Config: ±2g, 235Hz
        self._write_reg(0x03, 0x05) # CTRL2

        # 4. Gyro Config: ±2048dps, 235Hz
        self._write_reg(0x04, 0x75) # CTRL3

        # 5. Low Pass Filter (Smooth noise)
        self._write_reg(0x06, 0x11) # CTRL5

        # Wait for sensors to be ready
        time.sleep_ms(20)

        log.info("QMI8658: Initialized")

    def read_temperature(self):
        """Returns temperature in degrees Celsius"""
        try:
            data = self._read_reg(0x33, 2)
            raw = ustruct.unpack("<h", data)[0]
            return raw / 256.0
        except Exception as e:
            log.error(f"Error reading temp: {e}")
            return None

    def read_accel_xyz(self):
        """Returns tuple (x, y, z) in g-force"""
        try:
            # Status check (Bit 0 = Accel Data Ready)
            # status = self._read_reg(0x2D, 1)[0]
            status = self._read_reg(0x2E, 1)[0]
            if not (status & 0x01):
                return None

            data = self._read_reg(0x35, 6)
            raw = ustruct.unpack("<hhh", data)
            # Scale for ±2g (16384 LSB/g)
            # 2^15 / 2
            x = (raw[self._board_orientation[0][0]] * self._board_orientation[0][1]) / 16384.0
            y = (raw[self._board_orientation[1][0]] * self._board_orientation[1][1]) / 16384.0
            z = (raw[self._board_orientation[2][0]] * self._board_orientation[2][1]) / 16384.0
            return (x, y, z)
        except Exception as e:
            log.error(f"Error reading accel: {e}")
            return None

    def read_gyro_xyz(self):
        """Returns tuple (x, y, z) in degrees per second"""
        try:
            # Status check (Bit 1 = Gyro Data Ready)
            status = self._read_reg(0x2E, 1)[0]
            if not (status & 0x02):
                return None

            data = self._read_reg(0x3B, 6)
            raw = ustruct.unpack("<hhh", data)
            # Scale for ±2048dps (16 LSB/dps)
            # 2^15 / 2048
            x = (raw[self._board_orientation[0][0]] * self._board_orientation[0][1]) / 16.0
            y = (raw[self._board_orientation[1][0]] * self._board_orientation[1][1]) / 16.0
            z = (raw[self._board_orientation[2][0]] * self._board_orientation[2][1]) / 16.0
            return (x, y, z)
        except Exception as e:
            log.error(f"Error reading gyro: {e}")
            return None