
import asyncio

import machine
import neopixel

from boards.matrixbit_on3 import NEOPIXEL
from utils.messagebus import Subscriber, Publisher
from tasks.display_task import PRINT


RGB_COLORS = {
    'black': (0, 0, 0),
    'white': (255, 255, 255),
    'red': (255, 0, 0),
    'lime': (0, 255, 0),
    'blue': (0, 0, 255),
    'yellow': (255, 255, 0),
    'cyan': (0, 255, 255),
    'magenta': (255, 0, 255),
    'silver': (192, 192, 192),
    'gray': (128, 128, 128),
    'maroon': (128, 0, 0),
    'olive': (128, 128, 0),
    'green': (0, 128, 0),
    'purple': (128, 0, 128),
    'teal': (0, 128, 128),
    'navy': (0, 0, 128)
}


async def led_task():
    """
    Task to control onboard LEDS
    awaiting message:
        topic: 'leds_task'
        message: {'leds_commands': [{'led_id': <int>, 'color': <int> | <str>}, ...],
                  }
    publishing message:
        topic: 'leds_report'
        message: {'ack': 'ACK'|'NACK',
                  }

    Args:

    Returns:
        None

    Raises:
        None
    """
    leds = neopixel.NeoPixel(machine.Pin(NEOPIXEL), 3)
    sbr_led =Subscriber('leds_task', topics='led_task')
    plsh = Publisher('leds_task')
    PRINT('LEDS task')
    while True:
        topic, src, message = await sbr_led.get()
        for rec in message['led_list']:
            color = rec.get('color', (0,0,0))
            if isinstance(color, str):
                color = RGB_COLORS.get(color, (0,0,0))
            elif  isinstance(color, int):
                color = (color & 0xFF0000) >> 16, (color & 0xFF00) >> 8, (color & 0xFF)
            leds[int(rec['led_id'])] = color
        leds.write()
        plsh.publish('leds_report', {'ack': 'ACK'})


if __name__ == "__main__":

    async def test():
        asyncio.create_task(led_task())
        await asyncio.sleep(1)

        plsh = Publisher('led_test')
        plsh.publish(
            topic='leds_task',
            message={'leds_commands': [{'led_id': 0, 'color': 'red'}, {'led_id': 1, 'color': 'green'}]})
        print('send')
        await asyncio.sleep(5)
        plsh.publish(
            topic='leds_task',
            message={'leds_commands': [{'led_id': 0, 'color': (0,0,0)}, {'led_id': 1, 'color': 0x000000}]})

        await asyncio.sleep(10)



    asyncio.run(test())