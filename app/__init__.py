"""
Main Robot Application
Architecture:
- Delayed Initialization (inside async_main)
- CoAP Server (Control & Telemetry)
- Hardware Tasks (Motors, AHRS, Display)
"""
import sys
import time
import asyncio
import gc
import machine
import micropython
import ujson

# --- Utils ---
# import utils.t_logger
from utils.init_wifi import init_wifi
from utils.messagebus import MessageBus, Subscriber, Publisher
from utils.coap_server import (
    AsyncCoAPServer, CoAPRequest,
    METHOD_GET, METHOD_POST,
    RESP_CONTENT, RESP_CHANGED, RESP_BAD_REQ, RESP_INTERNAL_ERR,
)

# --- Hardware & Tasks ---
import boards.matrixbit_on3 as mbit
from mbit_ext.superbit_extension_board import Pca9685
from tasks.display_task import display_task, PRINT
from tasks.us_task import us_task
from tasks.system_task import us_scan
from tasks.servo_task import servo_task
from tasks.leds_task import led_task
from tasks.ahrs_task import ahrs_task
from tasks.motors_task import motors_task

# log = utils.t_logger.get_logger()

# Global reference (useful for debugging in REPL)
coap = None

def i2c_bus_recovery(scl, sda):
    """Clear stuck I2C bus"""
    for _ in range(9):
        scl.value(0); time.sleep_us(5)
        scl.value(1); time.sleep_us(5)
    scl.value(0); time.sleep_us(5)
    sda.init(machine.Pin.OUT, machine.Pin.PULL_UP)
    sda.value(0); time.sleep_us(5)
    scl.value(1); time.sleep_us(5)
    sda.value(1)

async def async_main():
    global coap
    print('=== APP START (CoAP Native) ===')
    gc.collect()

    # 1. Initialize WiFi First
    init_wifi()
    gc.collect()
    publisher = Publisher('app_main')
    subscribe = Subscriber('main', topics='quit')  # stop event loop
    gc.collect()


    # 2. Hardware Setup
    scl_pin = machine.Pin(mbit.MBIT_PIN_MAP['P19'], machine.Pin.OUT)
    sda_pin = machine.Pin(mbit.MBIT_PIN_MAP['P20'], machine.Pin.IN)
    i2c_bus_recovery(scl_pin, sda_pin)
    print('[Init] I2C Bus Recovery')
    main_i2c = machine.I2C(0, scl=machine.Pin(mbit.MBIT_PIN_MAP['P19']),
                           sda=machine.Pin(mbit.MBIT_PIN_MAP['P20']),
                           freq=400_000)
    print('[Init] I2C Scanned:', main_i2c.scan())
    gc.collect()

    pwm_controller = Pca9685(i2c_obj=main_i2c, pwm_freq=50)
    print('[Init] PCA9685 Ready')
    gc.collect()


    # 3. Initialize CoAP Server & Publisher
    # We do this HERE so sockets are created only after WiFi is up
    coap = AsyncCoAPServer()
    print('[Init] CoAP Server Ready')
    gc.collect()

    coap_pub = Publisher('coap_in')

    # --- DEFINE ROUTES (Inside async_main scope) ---

    @coap.route('/app/ping', ('GET',))
    async def ping_handler(req: CoAPRequest):
        return RESP_CONTENT, {'text': 'OK'}

    @coap.route('/app/quit', ('POST',))
    async def quit_handler(req: CoAPRequest):
        publisher.publish('quit', {})
        return RESP_CHANGED, {"text": "Shutting down"}

    @coap.route("/ota/enter", methods=("POST",))
    async def ota_enter_handler(req: CoAPRequest):
        print('=== OTA ===')
        try:
            with open("mode.ota", "w") as f:
                f.write("enter")
            req.server._send_response_packet(req.address, req.token, req.msg_id, RESP_CHANGED, {"text": "OK"})
            asyncio.sleep(1)
            machine.soft_reset()
        except Exception as e:
            print(e)
            return RESP_INTERNAL_ERR, {"text": str(e)}

    @coap.route("/app/messagebus", methods=("POST",))
    async def messagebus_handler(req: CoAPRequest):
        print('=== MessaheBus ===')
        data = req.json
        if not data:
            # await app_server._send_response(writer, 400, "Bad Request missing body")
            return RESP_BAD_REQ, {'text': "Bad Request missing body"}
        publisher.publish(data['topic'], data['payload'])
        if data.get('wait_reply', 'No').upper() == 'YES' or data.get('reply_topic', None):
            req.send_ack()
            topic, sender_id, message = await Subscriber(
                subscriber_id='messagebus_handler', topics=data['reply_topic']).get(
                    timeout=float(data.get('reply_timeout', 2)))
            # await app_server.send_json(
            #     writer, {'topic': topic, 'sender_id': sender_id, 'message': message})
            return RESP_CONTENT, {'topic': topic, 'sender_id': sender_id, 'message': message}
        else:
            # await app_server._send_response(writer, 200, "OK")
            return RESP_CHANGED, {"text": "OK"}
    print('Done routs')
    gc.collect()

    # --- START TASKS ---
    # 4. Start Server Task
    asyncio.create_task(coap.run())
    print('[Init] CoAP Server Started')
    # gc.collect()

    # 5. Start Hardware Tasks
    asyncio.create_task(display_task(main_i2c))
    asyncio.create_task(led_task())
    asyncio.create_task(servo_task(pwm_controller=pwm_controller, servo_id=4))
    asyncio.create_task(us_task())
    # Scan logic (0 to 180 degrees)
    asyncio.create_task(us_scan(0, 180, 0))
    asyncio.create_task(ahrs_task(main_i2c))
    print('[Init] Hardware Tasks Started')
    gc.collect()
    await asyncio.sleep(0.5)
    asyncio.create_task(motors_task(pwm_controller, 0, 2, True))
    gc.collect()
    # mem_profile('Hardware Tasks started')
    print('[Init] Hardware Tasks Started')
    gc.collect()

    # 6. Discovery Loop
    # Broadcasts "I am here" every 5s for the Host PC
    # async def discovery_loop():
    #     while True:
    #         # coap.broadcast_presence()
    #         await asyncio.sleep(5)
    # asyncio.create_task(discovery_loop())

    # gc.collect()
    micropython.mem_info()
    print("=== System Ready ===")

    while True:
        if subscribe.get_nowait():
            break
        await asyncio.sleep(1)

def main():
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("Stopped by User")
    except Exception as e:
        print("Critical Error:")
        sys.print_exception(e)
        time.sleep(1)
        # machine.reset()

if __name__ == '__main__':
    main()