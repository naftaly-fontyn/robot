# Buzzer pin P0 (note the jumper )
# 4 X RGB LED's using NeoPixel on P12 2x2 (same GPIO are used by the Matrix:Bit on board 3 LED's)
# All 17 pins accessible
# PCA9685 for 4X motors pwm (in pairs) and 8 x Servo (total 16 PWM outputs) address 0x40
# Motors
#   M1 channel A LED_8,  channel B LED_9
#   M2 channel A LED_10, channel B LED_11
#   M1 channel A LED_12, channel B LED_13
#   M1 channel A LED_14, channel B LED_15
# Servos
#   S1 LED_0
#   S2 LED_1
#   S3 LED_2
#   S4 LED_3
#   S5 LED_4
#   S6 LED_5
#   S7 LED_6
#   S8 LED_7
#
# Pin connectors
#  --------------------------------------------------------------------------------------
# |                                    Microbit slot                                     |
#  --------------------------------------------------------------------------------------
#                     [P13][P12][P11][P10]  ---  [P09][P08][P07][P06]
# [   ][   ][GND][GND][SDA][SCL][+3V][P14] |   | [P05][P04][P03][P02][P01][P01][P00][BUZ]
#                                          |   |
# P12 X    +5V X                           |   |                           X GND    X GND
# P13 X    GND X                           |   |                           X P06    X P09
# P14 X    P01 X Tx                        | B |                           X P04    X P10
# GND X    P02 X Rx                        | A |                           X +3V    X +3V
#                                          | T |
# +3V X    +3V X                           | T |                           X GND    X GND
# SCL X    SCL X                           | E |                           X P02    X P08
# SDA X    SDA X                           | R |                           X P01    X P07
# GND X    GND X                           | Y |                           X +3V    X +3V
#                                          |   |
# +3V X    +3V X                           |   |                           X GND    X GND
# SCL X    SCL X                           |   |                           X P03    X P11
# SDA X    SDA X                           |   |                           X P00    X P05
# GND X    GND X                           |   |                           X +3V    X +3V
#                                          |   |
#                y r b                     |   |                     b r y
# [M1  X  X]  S5 X X X                     |   |                     X X X S1  [X  X  M3]
#             S6 X X X                     |   |                     X X X S2
#             S7 X X X                     |   |                     X X X S3
# [M2  X  X]  S8 X X X                     |   |                     X X X S4  [X  X  M4]
#                                           ---
#

import config

import machine
import utime
import ustruct

if config.MCU_BOARD == 'BPI_Bit_S2':
    import boards.bpi_mbit_s2 as mbit
if config.MCU_BOARD == 'MatrixBit_on3_v2':
    import boards.matrixbit_on3 as mbit

I2C_SCL_PIN = mbit.MBIT_PIN_MAP['P19']
I2C_SDA_PIN = mbit.MBIT_PIN_MAP['P20']
I2C_PCA9685_ADDRESS = 0x40


_I3C_OBJ = None


def set_bit_to(value, bit_value, bit_position, bits=1):
    mask = (1 << bits) - 1
    if bit_value is None:
        return value
    bit_value = bit_value & mask
    value = value & ~(mask << bit_position)
    value |= (bit_value << bit_position)
    return value


def get_bit(value, bit_position, bits=1):
    mask = (1 << bits) - 1
    if isinstance(value, (bytes, bytearray)):
        value = [i for i in value][0]
    return (value >> bit_position) & mask


class Pca9685:
# address 0x40, scl=22, sda=23
    def __init__(self, i2c_obj=None, scl=None, sda=None, clock=25_000_000,
                 pwm_freq=50, i2c_clock=100_000):
        global _I3C_OBJ
        if all(i is None for i in [_I3C_OBJ, i2c_obj, scl, sda]):
            raise ValueError('Missing i2c object')
        if i2c_obj and _I3C_OBJ:
            print('Warning i2c already set using prevues i2c interface')
        elif i2c_obj:
            _I3C_OBJ = i2c_obj
        elif isinstance(scl, int) and isinstance(sda, int):
            _I3C_OBJ = machine.I2C(scl=machine.Pin(scl), sda=machine.Pin(sda), freq=i2c_clock)
        elif isinstance(scl, str) and isinstance(sda, str):
            _I3C_OBJ = machine.I2C(scl=machine.Pin(mbit.MBIT_PIN_MAP[scl]),
                                   sda=machine.Pin(mbit.MBIT_PIN_MAP[sda]), freq=i2c_clock)
        elif isinstance(scl, machine.Pin) and isinstance(sda, machine.Pin):
            _I3C_OBJ = machine.I2C(scl=scl, sda=sda, freq=i2c_clock)
        else:
            raise ValueError('Missing i2c object or bad pin')
        self._i2c_obj = _I3C_OBJ
        self.clock = clock  # the PCA9685 clock
        self._pwm_freq = pwm_freq
        self.address = I2C_PCA9685_ADDRESS
        self._mode1 = None  # restart, extclk, ai, sleep, sub1, sub2, sub3, allcall 0x01
        self._mode2 = None  # 7-5, inver, och, outdrv, outne[1:0] 0x04
        self._subadr1 = None
        self._subadr2 = None
        self._subadr3 = None
        self._allcalladdr = None
        self._prescale = None
        self.reset()

    def _sw_reset(self):
        self._i2c_obj.writeto(0, bytes([0x06]))
        utime.sleep_us(800)

    def reset(self):
        self._sw_reset()
        # print(self.get_mode1())
        self.set_mode1(0)
        utime.sleep_us(500)
        self.pwm_freq()

    def pwm_freq(self, freq=None):
        freq = self._pwm_freq if freq is None else freq
        self._prescale = self.prescale(freq)
        self.set_mode1(sleep=1)
        utime.sleep_us(500)
        self._write_regs(254,bytes([self._prescale]))
        self.set_mode1(sleep=0, restart=0)
        self._pwm_freq = freq

    def prescale(self, freq):
        prescale = self.clock // (4096 * freq) - 1
        if 3 <= prescale <= 255:
            return prescale
        prescale = max(min(prescale, 255), 3)
        f0 = self.clock / (((3 + 1) * 4096))
        f1 = self.clock / (((255 + 1) * 4096))
        f = self.clock / ((prescale + 1) * 4096)
        print(f'Warning PWM clock should be between {f0} and {f1} is is set to {f}')
        return prescale

    def set_mode1(self, raw_val=None,restart=None, ext_clock=None, ai=None, sleep=None,
                  sub1=None, sub2=None, sub3=None, allcall=None):
        mode1 = self._mode1
        if mode1 is None:
            mode1 = 0x00
        if raw_val is None:
            mode1 = set_bit_to(mode1, restart, 7)
            mode1 = set_bit_to(mode1, ext_clock, 6)
            mode1 = set_bit_to(mode1, ai, 5)
            mode1 = set_bit_to(mode1, sleep, 4)
            mode1 = set_bit_to(mode1, sub1, 3)
            mode1 = set_bit_to(mode1, sub2, 2)
            mode1 = set_bit_to(mode1, sub3, 1)  # reserved
            mode1 = set_bit_to(mode1, allcall, 0)
        else:
            mode1 = raw_val
            sleep = get_bit(mode1, 4)
        # print('mode1 set ', hex(mode1))
        self._write_regs(0x00, bytes([mode1]))
        if sleep is not None and sleep == 0:
            utime.sleep_us(500)
        self._mode1 = mode1

    def set_mode2(self, invert=0, och=0, outdrv=1, outne=0):
        mode2 = self._mode2
        if mode2 is None:
            mode2 = 0x04
        mode2 = set_bit_to(mode2, invert, 4)
        mode2 = set_bit_to(mode2, och, 3)
        mode2 = set_bit_to(mode2, outdrv, 2)
        mode2 = set_bit_to(mode2, outne, 0, 2)
        self._write_regs(0x01, bytes([mode2]))
        self._mode2 = mode2

    def get_mode1(self):
        self._mode1 = self._read_regs(0x00, 1)[0]
        return {
            'restart': get_bit(self._mode1, 7),
            'ext_clock': get_bit(self._mode1, 6),
            'ai': get_bit(self._mode1, 5),
            'sleep': get_bit(self._mode1, 4),
            'sub1': get_bit(self._mode1, 3),
            'sub2': get_bit(self._mode1, 2),
            'sub3': get_bit(self._mode1, 1),
            'allcall': get_bit(self._mode1, 0)}

    def get_mode2(self):
        self._mode2 = self._read_regs(0x01, 1)[0]
        return {'invert': get_bit(self._mode2, 4),
                'och': get_bit(self._mode2, 3),
                'outdrv': get_bit(self._mode2, 2),
                'outne': get_bit(self._mode2, 0, 2)}


    def set_led_pwm(self, led_id, on_tick, off_tick):
        on_tick = round(on_tick)
        off_tick = round(off_tick)
        # print(led_id, on_tick, off_tick)
        if on_tick + off_tick > 4095:
            raise ValueError
        # self._write_regs(led_id * 4 + 6,
        #                  bytes([on_tick & 0xFF, on_tick >> 8,
        #                         off_tick & 0xFF, off_tick >> 8]))
        self._write_regs(led_id * 4 + 6, bytes([on_tick & 0xFF]))
        self._write_regs(led_id * 4 + 6 + 1, bytes([on_tick >> 8]))
        self._write_regs(led_id * 4 + 6 + 2, bytes([off_tick & 0xFF]))
        self._write_regs(led_id * 4 + 6 + 3, bytes([off_tick >> 8]))

    def get_led_pwm(self, led_id):
        ...

    def _write_regs(self, start_address, value_list):
        self._i2c_obj.writeto_mem(self.address, start_address, value_list)
        utime.sleep_us(10)

    def _read_regs(self, start_address, length):
        ret = b''
        for i in range(length):
            ret += self._i2c_obj.readfrom_mem(self.address, start_address + i, 1)
            utime.sleep_us(5             )
        return ret


class Motor:
# (8,9)-(14,15)
    def __init__(self, motor_id, revers=False, pwm_controller=None):
        self.motor_id = motor_id
        channels = [8,9,10,11,12,13,14,15][motor_id*2:motor_id*2+2]
        self.channel_a = channels[1] if revers else channels[0]
        self.channel_b = channels[0] if revers else channels[1]
        self.pwm_controller = pwm_controller
        self.revers = revers
        if self.pwm_controller is None and _I3C_OBJ is None:
            raise ValueError('Missing i2c object')
        elif self.pwm_controller is None:
            self.pwm_controller = _I3C_OBJ
        pass

    def set_throttle(self, throttle):
        """
        Convert throttle value to PWM and direction signals.

        throttle (float): value between -1.0 and 1.0
            0 is stop, negative is revers
        """
        on = 0
        off = min(max(throttle * 4095, -4095), 4095)
        # print('set_throttle', throttle, on, off)
        if throttle in (None, 'break'):
            self.pwm_controller.set_led_pwm(led_id=self.channel_a, on_tick=0, off_tick=1024)
            self.pwm_controller.set_led_pwm(led_id=self.channel_b, on_tick=0, off_tick=1024)
        elif throttle < 0:
            off = -off
            self.pwm_controller.set_led_pwm(led_id=self.channel_a, on_tick=0, off_tick=0)
            self.pwm_controller.set_led_pwm(led_id=self.channel_b, on_tick=on, off_tick=off)
        elif throttle > 0:
            self.pwm_controller.set_led_pwm(led_id=self.channel_a, on_tick=on, off_tick=off)
            self.pwm_controller.set_led_pwm(led_id=self.channel_b, on_tick=0, off_tick=0)
        else:
            self.pwm_controller.set_led_pwm(led_id=self.channel_a, on_tick=0, off_tick=0)
            self.pwm_controller.set_led_pwm(led_id=self.channel_b, on_tick=0, off_tick=0)

class Servo:
    def __init__(self, servo_id, min_angle=0, max_angle=180, min_pulse_ms=1,
                 max_pulse_ms=2, pwm_controller=None):
        channels = [0,1,2,3,4,5,6,7][servo_id]
        self.channel = channels
        self.min_angle = min_angle
        self.max_angle = max_angle
        self.min_pulse = min_pulse_ms
        self.max_pulse = max_pulse_ms
        self._diff_angle = max_angle - min_angle
        self._diff_pulse = max_pulse_ms - min_pulse_ms
        self.angle = None
        self.pwm_controller = pwm_controller
        if self.pwm_controller is None and _I3C_OBJ is None:
            raise ValueError('Missing i2c object')
        elif self.pwm_controller is None:
            self.pwm_controller = _I3C_OBJ
        pass

    def set_angle(self, angle_deg):
        t_cycle = 1000 / self.pwm_controller._pwm_freq
        tick = t_cycle / 4096
        on = 0
        a = (((angle_deg - self.min_angle) / self._diff_angle) *
              self._diff_pulse + self.min_pulse)
        off = round(a / tick)
        # print(t_cycle, tick, off, off * tick)
        self.pwm_controller.set_led_pwm(self.channel, on, off)

class Buzzer:
# pin0
    ...

if __name__ == '__main__':
    pass
    pwm_cntl = Pca9685(pwm_freq=50, scl=I2C_SCL_PIN, sda=I2C_SDA_PIN)
    m0 = Motor(0, pwm_controller=pwm_cntl)
    m0.set_throttle(-0.75 * 0)
    utime.sleep(2)
    m0.set_throttle(0)
    # -45->0.6 225->2.4
    s0 = Servo(4, pwm_controller=pwm_cntl,
               max_angle=225, max_pulse_ms=2.6666,
               min_angle=-45, min_pulse_ms=0.6689)
    #  -50 -- 280
    s0.set_angle(0)  #115 - 100)
    utime.sleep(2)
    s0.set_angle(90)  #115)   # 90
    utime.sleep(2)
    s0.set_angle(180)  #115+100)   # 90
