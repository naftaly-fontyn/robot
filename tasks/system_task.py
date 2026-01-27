import asyncio

from utils.messagebus import Publisher, Subscriber
from tasks.display_task import PRINT


# distance ultrasonic scan 0-280 deg
# drive forward/backward
# turn right/left deg
# turn to heading


async def us_scan(start_angle, stop_angle, step):
    PRINT('US scan')
    publisher = Publisher('us_scan_task')
    us_scan_sub = Subscriber('us_scan', topics='us_scan')
    servo_sub = Subscriber('servo_test', topics='servo_report')
    us_sub = Subscriber('us_report', topics='us_report')
    while True:
        src, tpc, msg = await us_scan_sub.get()
        ret = []
        _step = msg['step'] if 'step' in msg else step
        _stop_angle = msg['stop_angle'] if 'stop_angle' in msg else stop_angle
        angle = msg['start_angle'] if 'start_angle' in msg else start_angle
        while angle <= _stop_angle:
            try:
                publisher.publish(topic='servo_task', message={'set_angle': angle})
                response = await servo_sub.get()
                await asyncio.sleep(1)
                publisher.publish(topic='us_task', message={'measure': 'DO'})
                _, _, response = await us_sub.get(timeout=3)
                ret.append({'angle': angle, 'distance': response['distance']})
            except Exception as e:
                print(e)
            angle += _step
        publisher.publish('us_scan_report', {'scan_distances': ret})


if __name__ == '__main__':
    from machine import I2C, Pin
    from boards.matrixbit_on3 import MBIT_PIN_MAP
    from mbit_ext.superbit_extension_board import Pca9685
    from tasks.us_task import us_task
    from tasks.servo_task import servo_task
    async def test():
        main_i2c = I2C(0, scl=Pin(MBIT_PIN_MAP['P19']),
                        sda=Pin(MBIT_PIN_MAP['P20']),
                        freq=400_000)
        pwm_controller = Pca9685(i2c_obj=main_i2c, pwm_freq=50)
        asyncio.create_task(servo_task(pwm_controller=pwm_controller, servo_id=4))
        asyncio.create_task(us_task())
        asyncio.create_task(us_scan(0, 180, 5))
        await asyncio.sleep(1)
        Publisher('test_scan').publish(topic='us_scan',message={})
        print(await Subscriber('xxx', 'us_scan_report').get())
#         print(await us_scan(0, 180, 5))

    asyncio.run(test())
