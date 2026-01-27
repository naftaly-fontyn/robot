
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

