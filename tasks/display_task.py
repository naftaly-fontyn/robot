
import asyncio
import machine
import devices.display.nano_gui.drivers.ssd1306.ssd1306 as ssd1306
import boards.matrixbit_on3 as mbit
from utils.messagebus import Subscriber, Publisher
import utils.t_logger as t_logger
log = t_logger.get_logger()


# display
#       clear rect xy xy/wh
#       print_at_xy text, warp , indent
#       draw_line xy, xy
#       draw ellipse major, minor fill
#       draw polygon [xy, xy,...] fill
#       plot_line xywh [x] [y] grid
#       plot_polar xywh [r] [theta] grid

def window_to_screen(window, x0, y0):
    x0 = min(window[0] + x0, window[4])
    y0 = min(window[1] + y0, window[5])
    return x0, y0, window[4], window[5]

class _Print:
    def __init__(self, dsp = None, w=ssd1306.SCREEN_WIDTH, h=ssd1306.SCREEN_HEIGHT, cw=8, ch=8):
        self.dsp = dsp
        self.sw = w
        self.sh = h
        self.cw = cw
        self.ch = ch
        self.x = 0
        self.y = 56

    def set_display(self, dsp):
        self.dsp = dsp

    def __call__(self, *a, **k):
        s = ' '.join([str(i) for i in a])
        log.info(s)
        if not self.dsp:
            return
        while s:
            self.dsp.scroll(0,-8)
            self.dsp.fill_rect(0, self.sh - 8, self.sw, 8, 0)
            self.dsp.text(s[:16], self.x, self.y)
            s = s[16:]
            self.dsp.show()

PRINT = _Print()


def display_task(i2c_obj, width=128, height=64):
    """
    for display_task
    Note: axies (0,0) top,left
    awaiting message:
        topic: 'display_task'
        message: {'set_window': {'x': <int>, 'y': <int>, 'w': <int>, 'h,: <int>},
                  'clear_rect': {'x': <int>, 'y': <int>, 'w': <int>, 'h': <int>},
                  'print_at_xy': {'x': <int>, 'y': <int>, 'text': <str>, 'warp': <bool>, 'indent': <int>},
                  'draw_line': {'x1': <int>, 'y1': <int>, 'x2': <int>, 'y2': <int>},
                  'draw_ellipse': {'x0': <int>, 'y0': <int>, major': <int>, 'minor': <int>, 'fill': <bool>},
                  'draw_polygon': {'points': [[<int>, <int>], ...], 'fill': <bool>},
                  'plot_line': { 'x': <list[int]>, 'y': <list[int]>, 'grid': <bool>},
                  'plot_polar': {'r': <list[int]>, 'theta': <list[int]>, 'grid': <bool>},
                  'print': {'text': <str>, 'wrap': <bool>
                  }
    publishing message:
        topic: 'display_report'
        message: {'ack': 'ACK'|'NACK',
                  }

    Args:
        i2c_obj (machine.I2C): I2C object to use for communication.
        width (int): width of display.
        height (int): height of display.

    """
    global PRINT
    display = ssd1306.SSD1306_I2C(i2c_obj, width, height, addr=0x3C)
    display.fill(0)
    display.show()
    PRINT.set_display(display)
    # PRINT = _Print(display)
    subscription = Subscriber('display_task', topics='display_task')
    publisher = Publisher('display_task')
    PRINT('Display up')
    window = [0, 0, width, height, width, height]
    while True:
        topic, src, message = await subscription.get()
        log.debug(message)
        if 'set_window' in message:
            if message['set_window'] == 'reset':
                window = [0, 0, width, height]
            else:
                window[0] = max(message['set_window'].get('x', 0), 0)
                window[1] = max(message['set_window'].get('y', 0), 0)
                window[2] = message['set_window'].get('w', width)
                window[3] = message['set_window'].get('h', height)
                window[4] = min(window[0] + window[2], width)
                window[5] = min(window[1] + window[3], height)

        if 'clear_rect' in message:
            display.fill_rect(message['clear_rect']['x'], message['clear_rect']['y'],
                              message['clear_rect']['w'], message['clear_rect']['h'], 0)
        elif 'print_at_xy' in message:
            if not (0<=message['print_at_xy']['x']<window[2] and
                    0<=message['print_at_xy']['y']<window[3]):
                publisher.publish('display_report', {'ack': 'NACK'})
                continue
            text = message['print_at_xy']['text']
            warp = message['print_at_xy']['warp']
            indent = message['print_at_xy']['x']
            x0 , y0, x1, y1 = window_to_screen(window, message['print_at_xy']['x'], message['print_at_xy']['y'])
            while text:
                chr_per_line = (x1 - x0) // 8
                if chr_per_line < 1 or (y1 - y0) < 8:
                    break
                display.text(text[:chr_per_line], x0, y0)
                if warp:
                    text = text[chr_per_line:]
                    x0 += indent
                    y0 += 8
                else:
                    break
        elif 'draw_line' in message:
            display.line(message['draw_line']['x1'], message['draw_line']['y1'],
                         message['draw_line']['x2'], message['draw_line']['y2'], 1)
        elif 'draw_ellipse' in message:
            display.ellipse(
                message['draw_ellipse']['x0'], message['draw_ellipse']['y0'],
                message['draw_ellipse']['major'], message['draw_ellipse']['minor'], True,
                message['draw_ellipse']['fill'])
        elif 'print' in message:
            ...
        display.show()
        publisher.publish('display_report', {'ack': 'ACK'})


if __name__ == "__main__":
    async def test():
        main_i2c = machine.I2C(0, scl=machine.Pin(mbit.MBIT_PIN_MAP['P19']),
                               sda=machine.Pin(mbit.MBIT_PIN_MAP['P20']),
                               freq=400_000)
        asyncio.create_task(display_task(main_i2c))
        await asyncio.sleep(1)
        await asyncio.sleep(1)
        publisher = Publisher('display_test')
        publisher.publish(topic='display_task', message={'clear_rect': {'x': 0, 'y': 0, 'w': 128, 'h': 64}})
        print(await Subscriber('display_test', topics='display_report').get())
        publisher.publish(topic='display_task', message={'print_at_xy': {'x': 0, 'y': 0, 'text': 'Hello World!', 'warp': True, 'indent': 0}})
        print(await Subscriber('display_test', topics='display_report').get())
        publisher.publish(topic='display_task', message={'draw_line': {'x1': 8, 'y1': 8, 'x2': 128, 'y2': 64}})
        print(await Subscriber('display_test', topics='display_report').get())
        publisher.publish(topic='display_task', message={'draw_ellipse': {'x0': 30, 'y0': 30, 'major': 7, 'minor': 13, 'fill': True}})
        print(await Subscriber('display_test', topics='display_report').get())




    asyncio.run(test())






