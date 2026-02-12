import math
import asyncio
from machine import Pin, I2C
from utime import sleep_ms, ticks_ms

from boards.matrixbit_on3 import MBIT_PIN_MAP
from mbit_ext.superbit_extension_board import Motor, Pca9685
from utils.messagebus import Subscriber, Publisher
from tasks.display_task import PRINT
from utils.calibration import calibration
import utils.t_logger as t_logger
log = t_logger.get_logger()


WHEEL_BASE = (115 + 75) /2  # mm
WHEEL_DIAMETER = 37  # mm

def calibrate_motor(calib_motor, break_motor):
    from tasks.ahrs_task import IMU, MAG
    buf = []
    gyro_bias = [0, 0, 0]
    calib = calibration.get('motors', {})
    # quick gyro offset calibration
    n = 100
    for _ in range(n):
        gyro = IMU.read_gyro_xyz()
        gyro_bias[0] += gyro[0]/n
        gyro_bias[1] += gyro[1]/n
        gyro_bias[2] += gyro[2]/n
        sleep_ms(20)
    # print(gyro_bias)
    _calib = []
    for pwm in (10, 20, 30, 40, 50, 60, 70,80, 90, 95):
        ret = _estimate_vss_and_tau(calib_motor, break_motor, buf, gyro_bias, _calib, pwm)
        _calib.append(ret)
        log.debug(ret['pwm'], ret['Vss'], ret['tau'])
    calib[f'M{calib_motor.motor_id}'] = _calib
    # print(calib)
    calibration.set('motors', calib)
    calibration.save_calibration()

def _estimate_vss_and_tau(calib_motor, break_motor, buf, gyro_bias, _calib, pwm):
    # tau about 0.21, pwm_0(stall) > 5 , pwm_1 < 95(saturated)
    from tasks.ahrs_task import IMU, MAG
    buf = []
    t0 = ticks_ms()
    sleep_ms(100)
    break_motor.set_throttle(0)
    calib_motor.set_throttle(pwm / 100)
    t = ticks_ms() - t0
    buf.append((t, IMU.read_gyro_xyz()))
    while t < 1_500 :
        sleep_ms(100)
        t = ticks_ms() - t0
        buf.append((t, IMU.read_gyro_xyz()))
    break_motor.set_throttle(0)
    calib_motor.set_throttle(0)
    omega_ss = 0
    n = 0
    for i in range(len(buf)-1, -1, -1):
            # dt = (buf[i+1][0] - buf[i][0]) / 1000
        omega = buf[i][1][2] - gyro_bias[2] # (buf[i+1][1][0] - buf[i][1][0]) / dt
        if buf[i][0] >= 1000:
            omega_ss += omega
            n += 1
        elif abs(omega) <= abs(omega_ss / n * 0.68):  # find tau
            break
    tau = buf[i][0] / 1000
    v_ss = math.radians(abs(omega_ss / n)) * WHEEL_BASE  # [mm/sec] steady state velocity
    l = v_ss * 1.5 * (1 - math.exp(-1.5/tau))            # [mm] distance traveled
    tau = buf[i][0] / 1000                               # [sec]  time constant
    # print(f'OMEGAss: {abs(omega_ss) / n}dps, Tau {tau} sec Dist: {l} mm')
        # print(buf)
    return {'pwm': pwm, 'Vss': v_ss, 'tau': tau}
    # _calib.append({'pwm': pwm, 'Vss': v_ss, 'tau': tau})



async def motors_task(pwm_controller, motor0_id, motor1_id, revers_motor1):
    """
    Task to control DC motors pair
    awaiting message:
        topic: 'motors_task'
        message: {'motor0_power': <float>,
                  'motor1_power': <float>,
                  /'time_ms': <int>,/
                  /'distance_mm': <int>,/
                  }
    publishing message:
        topic: 'motors_report'
        message: {'ack': 'ACK'|'NACK',
                  }

    Args:
        pwm_controller (Pca9685): Pca9685 object to use for communication.
        motor0_id (int): servo idy 1-4.
        motor1_id (int): servo idy 1-4.
        revers_motor1 (bool): revers the command to motor1.

    Returns:
        None

    Raises:
        None
    """
    motor_0 = Motor(motor_id=motor0_id, pwm_controller=pwm_controller)
    motor_1 = Motor(motor_id=motor1_id, pwm_controller=pwm_controller, revers=revers_motor1)

    sbr_us = Subscriber('motors_task', topics='motors_task')
    plsh = Publisher('motors_task')
    log.info('start motors_task')
    while True:
        topic, src, message = await sbr_us.get()
        if 'calibrate' in message:
            if message['calibrate'] == 'motor0' or message['calibrate'] == 'both':
                calibrate_motor(motor_0, motor_1)
            if message['calibrate'] == 'motor1' or message['calibrate'] == 'both':
                calibrate_motor(motor_1, motor_0)
            plsh.publish('motors_report', {'ack': 'ACK', 'calibrate': calibration.data})
            continue
        m0_pwr = message.get('motor0_power', 0)
        m1_pwr = message.get('motor1_power', 0)
        dist_mm = message.get('distance_mm', None)
        t_ms = message.get('time_ms', None)
        motor_0.set_throttle(m0_pwr / 100)
        motor_1.set_throttle(m1_pwr / 100)
        if t_ms:
            await asyncio.sleep_ms(t_ms)
            motor_0.set_throttle(0)
            motor_1.set_throttle(0)
        plsh.publish('motors_report', {'ack': 'ACK'})


if __name__ == "__main__":
    async def test():
        main_i2c = I2C(0, scl=Pin(MBIT_PIN_MAP['P19']),
                       sda=Pin(MBIT_PIN_MAP['P20']),
                       freq=400_000)
        pwm_controller = Pca9685(i2c_obj=main_i2c, pwm_freq=50)
        asyncio.create_task(motors_task(pwm_controller=pwm_controller, motor0_id=0, motor1_id=2, revers_motor1=True))
        await asyncio.sleep(1)
        plsh = Publisher('motors_test')
        for angle in range(0, 1):
            plsh.publish(topic='motors_task', message={'motor0_power': 50, 'motor1_power': -50, 'time_ms':1000})
            response = await Subscriber('motors_report', topics='servo_report').get()
            print(response)
            await asyncio.sleep(1)

    asyncio.run(test())
