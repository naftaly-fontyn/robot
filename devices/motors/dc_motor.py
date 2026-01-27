
class Motor:
# (8,9)-(14,15)
    def __init__(self, motor_id, revers=False, pwm_controller=None):
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
        if throttle < 0:
            off = -off
            self.pwm_controller.set_led_pwm(led_id=self.channel_a, on_tick=0, off_tick=0)
            self.pwm_controller.set_led_pwm(led_id=self.channel_b, on_tick=on, off_tick=off)
        elif throttle > 0:
            self.pwm_controller.set_led_pwm(led_id=self.channel_a, on_tick=on, off_tick=off)
            self.pwm_controller.set_led_pwm(led_id=self.channel_b, on_tick=0, off_tick=0)
        else:
            self.pwm_controller.set_led_pwm(led_id=self.channel_a, on_tick=0, off_tick=0)
            self.pwm_controller.set_led_pwm(led_id=self.channel_b, on_tick=0, off_tick=0)

class TwoMotors:
    ...
