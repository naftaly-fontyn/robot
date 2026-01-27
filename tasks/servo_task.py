import asyncio
from machine import Pin, I2C

from boards.matrixbit_on3 import MBIT_PIN_MAP
from mbit_ext.superbit_extension_board import Servo, Pca9685
from utils.messagebus import Subscriber, Publisher
from tasks.display_task import PRINT


async def servo_task(pwm_controller, servo_id):
    """
    Task to control servo
    awaiting message:
        topic: 'servo_task'
        message: {'set_angle': <float>,
                  }
    publishing message:
        topic: 'servo_report'
        message: {'ack': 'ACK'|'NACK',
                  }

    Args:
        servo_id (int): servo idy 1-8.
        pwm_controller (Pca9685): Pca9685 object to use for communication.
        max_angel (int): max servo angel. default: 225
        max_pulse_ms (float): max pulse width in ms. default: 2.6666
        min_angel (int): min servo angel. default: -45
        min_pulse_ms (float): min pulse width in ms. default: 0.6689

    Returns:
        None

    Raises:
        None
    """
    servo = Servo(servo_id=servo_id, pwm_controller=pwm_controller,
                  max_angle=225, max_pulse_ms=2.6666,
                  min_angle=-45, min_pulse_ms=0.6689)
    sbr_us = Subscriber('servo_task', topics='servo_task')
    plsh = Publisher('servo_task')
    PRINT('Servo_task')
    while True:
        topic, src, message = await sbr_us.get()
        if isinstance(message.get('set_angle', None), (int, float)):
            servo.set_angle(message['set_angle'])
            plsh.publish('servo_report', {'ack': 'ACK'})


if __name__ == "__main__":
    async def test():
        main_i2c = I2C(0, scl=Pin(MBIT_PIN_MAP['P19']),
                       sda=Pin(MBIT_PIN_MAP['P20']),
                       freq=400_000)
        pwm_controller = Pca9685(i2c_obj=main_i2c, pwm_freq=50)
        asyncio.create_task(servo_task(pwm_controller=pwm_controller, servo_id=4))
        await asyncio.sleep(1)
        plsh = Publisher('servo_test')
        for angle in range(0, 181, 5):
            plsh.publish(topic='servo_task', message={'set_angle': angle})
            response = await Subscriber('servo_test', topics='servo_report').get()
            print(response)
            await asyncio.sleep(0.2)

    asyncio.run(test())
