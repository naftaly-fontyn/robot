"""
Main app of the robot operational program. It sets up the main asynio
event loop and routes for the REST server used to control the robot.
Software models controlling the robot device communicate using a
messagebus that enable to decimate messages. module may subscribe to
topics and post messages/events to topics
"""
import sys
import time
import asyncio
import gc
import machine
import micropython

import utils.t_logger
from utils.init_wifi import init_wifi
from utils.async_restful_server import AsyncRestfulServer
from tasks.display_task import display_task, PRINT
from utils.messagebus import MessageBus, Subscriber, Publisher
import boards.matrixbit_on3 as mbit
from mbit_ext.superbit_extension_board import Pca9685
from tasks.display_task import display_task, PRINT
from tasks.us_task import us_task
from tasks.system_task import us_scan
from tasks.servo_task import servo_task
from tasks.leds_task import led_task
from tasks.ahrs_task import ahrs_task
from tasks.motors_task import motors_task


log = utils.t_logger.get_logger()

def i2c_bus_recovery(scl, sda):
    """
    Manually toggle SCL to clear any stuck slaves (Bus Recovery).
    This fixes issues where sensors hold SDA low after a soft reboot.
    """
    # TODO-1: Check if needed
    # scl = machine.Pin(scl_pin, machine.Pin.OUT)
    # sda = machine.Pin(sda_pin, machine.Pin.IN)
    # Cycle SCL 9 times to force slaves to release SDA
    for _ in range(9):
        scl.value(0)
        time.sleep_us(5)
        scl.value(1)
        time.sleep_us(5)
    # Generate a Stop condition
    scl.value(0)
    time.sleep_us(5)
    # sda = machine.Pin(sda_pin, machine.Pin.OUT)
    sda.init(machine.Pin.OUT, machine.Pin.PULL_UP)
    sda.value(0)
    time.sleep_us(5)
    scl.value(1)
    time.sleep_us(5)
    sda.value(1)


def main():
    log.info('=== APP Main ===')
    asyncio.run(async_main())

def global_exception_handler(loop, context):
    """Catch anything not covered by decorators"""
    exception = context.get('exception')
    msg = context.get('message')
    log.warning("!! GLOBAL HANDLER CAUGHT UNHANDLED ERROR !!", exc_info=exception)

async def async_main():
    print('APP')
    init_wifi()
    # setup messagebus
    publisher = Publisher('app_main')
    subscribe = Subscriber('main', topics='quit')  # stop event loop
    # setup the I2C
    scl = machine.Pin(mbit.MBIT_PIN_MAP['P19'], machine.Pin.OUT)
    sda = machine.Pin(mbit.MBIT_PIN_MAP['P20'], machine.Pin.IN)
    i2c_bus_recovery(scl, sda)
    main_i2c = machine.I2C(0, scl=machine.Pin(mbit.MBIT_PIN_MAP['P19']),
                           sda=machine.Pin(mbit.MBIT_PIN_MAP['P20']),
                           freq=400_000)
    PRINT('I2C bus')
    PRINT("I2C Scan:", main_i2c.scan())
    # setup devices
    asyncio.create_task(display_task(main_i2c))
    PRINT('Display ssd1306')

    pwm_controller = Pca9685(i2c_obj=main_i2c, pwm_freq=50)
    PRINT('PCA9685 PWM')

    loop = asyncio.get_event_loop()
    loop.set_exception_handler(global_exception_handler)

    # Setup Tasks
    asyncio.create_task(led_task())
    asyncio.create_task(servo_task(pwm_controller=pwm_controller, servo_id=4))
    asyncio.create_task(us_task())
    asyncio.create_task(us_scan(0, 180, 0))
    asyncio.create_task(ahrs_task(main_i2c))
    await asyncio.sleep(0.1)  # calib
    asyncio.create_task(motors_task(pwm_controller, 0, 2, True))
    await asyncio.sleep(5)    # calib
    # RESTFUL server
    app_server = AsyncRestfulServer()

    # Setup routes fro the REST server
    @app_server.route('/app/ping', ('GET',))
    async def ping_handler(server, writer, query, request):
        await app_server.send_json(writer, {'ping': 'OK'})


    @app_server.route('/app/quit', ('POST',))
    async def quit_handler(server, writer, query, request):
        publisher.publish('quit', {})
        await app_server._send_response(writer, 200, "Shutting down")


    @app_server.route("/ota/enter", methods=("POST",))
    async def ota_enter_handler(server, writer, query, request):
        print('=== OTA ===')
        try:
            with open("mode.ota", "w") as f:
                f.write("enter")
            await app_server._send_response(writer, 200, "OK")
            asyncio.sleep(1)
            machine.soft_reset()
        except Exception as e:
            print(e)
            await app_server._send_response(writer, 500, str(e))

    @app_server.route("/app/messagebus", methods=("POST",))
    async def messagebus_handler(server, writer, query, request):
        data = await request.json()
        if not data:
            await app_server._send_response(writer, 400, "Bad Request missing body")
            return
        publisher.publish(data['topic'], data['payload'])
        if data.get('wait_reply', 'No').upper() == 'YES' or data.get('reply_topic', None):
            topic, sender_id, message = await Subscriber(
                subscriber_id='messagebus_handler', topics=data['reply_topic']).get(
                    timeout=float(data.get('reply_timeout', 2)))
            await app_server.send_json(
                writer, {'topic': topic, 'sender_id': sender_id, 'message': message})
        else:
            await app_server._send_response(writer, 200, "OK")
    asyncio.create_task(app_server.run())
    gc.collect()
    micropython.mem_info()

    # print(await us_scan(0, 180, 5))

    # Keep main alive
    while True:
        if subscribe.get_nowait():
            break
        await asyncio.sleep(1)


if __name__ == '__main__':
    main()