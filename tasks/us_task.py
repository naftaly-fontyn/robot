import asyncio
from machine import Pin
from boards.matrixbit_on3 import MBIT_PIN_MAP
from devices.ultrasonic.hcsr04 import HCSR04
from utils.messagebus import Subscriber, Publisher
from utils.async_task_supervisor import supervised
from utils.t_logger import get_logger
from tasks.display_task import PRINT

TRIGGER_PIN = 1
ECHO_PIN = 2

log = get_logger()

@supervised(restart_delay=2)
async def us_task():
    """
    Task to control ultrasonic sensor
    awaiting message:
        topic: 'us_task'
        message: {'measure': 'DO' | 'DONT',
                  }
    publishing message:
        topic: 'us_report'
        message: {'distance': <float>,
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
    ultrasonic = HCSR04(trigger_pin=MBIT_PIN_MAP[f'P{TRIGGER_PIN}'],
                        echo_pin=MBIT_PIN_MAP[f'P{ECHO_PIN}'])
    sbr_us = Subscriber('us_task', topics='us_task')
    plsh = Publisher('us_task')
    PRINT('USound task')
    while True:
        topic, src, message = await sbr_us.get()
        if message.get('measure', 'DONT') == 'DO':
            distance = ultrasonic.distance_cm()
            plsh.publish('us_report', {'distance': distance})


if __name__ == "__main__":
    async def test():
        asyncio.create_task(us_task())
        await asyncio.sleep(1)

        plsh = Publisher('us_test')
        plsh.publish(topic='us_task', message={'measure': 'DO'})
        response = await Subscriber('us_report', topics='us_response').get()
        print(response)

    asyncio.run(test())
