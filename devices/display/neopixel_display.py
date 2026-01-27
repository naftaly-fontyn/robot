"""
Interface for bpi_mbit-S2 board
"""

import neopixel
from utime import sleep_ms
from font_5x5 import FONTS_5x5, SYMBOLS, FONT_5x5_WIDTH, unpack_font_to_grid


# class for a neopixel display

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
RGBW_COLORS = {
    'black': (0, 0, 0, 0),
    'white': (255, 255, 255, 255),
    'red': (255, 0, 0, 0),
    'lime': (0, 255, 0, 0),
    'blue': (0, 0, 255, 0),
    'yellow': (255, 255, 0, 0),
    'cyan': (0, 255, 255, 0),
    'magenta': (255, 0, 255, 0),
    'silver': (192, 192, 192, 0),
    'gray': (128, 128, 12, 0),
    'maroon': (128, 0, 0, 0),
    'olive': (128, 128, 0, 0),
    'green': (0, 128, 0, 0),
    'purple': (128, 0, 128, 0),
    'teal': (0, 128, 128, 0),
    'navy': (0, 0, 128, 0)
}


class NeoPixelDisplay:
    """
    A neopixel high level class
    """
    def __init__(self, pin, bytes_per_pixel=3, columns=5, rows=5,
                 order='TTD_LTR'):
        self.pin = pin
        self.bytes_per_pixel = bytes_per_pixel
        self.columns = columns
        self.rows = rows
        self.order = order
        # self._buffer = bytearray(columns * rows * bytes_per_pixel)  # RGB565 format
        self._neopixel = neopixel.NeoPixel(pin, columns * rows,
                                           bpp=bytes_per_pixel)

    def _setitem__(self, index, value):
        self.set_pixel(*index, value)

    def __getitem__(self, index):
        return self.get_pixel(*index)

    def _to_index(self, x, y):
        if self.order == 'TTD_LTR':
            return self.columns*self.rows - y - x * self.rows - 1

    def _color_codes_to_rgb(self, color):
        if isinstance(color, (tuple,list)):
            return color
        elif self.bytes_per_pixel == 3 and color in RGB_COLORS:
            return RGB_COLORS[color]
        elif self.bytes_per_pixel == 4 and color in RGBW_COLORS:
            return RGBW_COLORS[color]
        else:
            raise ValueError()

    def set_pixel(self, x, y, color):
        """
        Set pixel color at x, y

        Args:
            x (_type_): _description_
            y (_type_): _description_
            color (_type_): _description_
        """
        if 0 <= x < self.columns and 0 <= y < self.rows:
            index = self._to_index(x, y)
            self._neopixel[index] = self._color_codes_to_rgb(color)

    def get_pixel(self, x, y):
        if 0 <= x < self.columns and 0 <= y < self.rows:
            index = self._to_index(x, y) * self.bytes_per_pixel
            return self._neopixel[index]
        return None

    def set_rect(self, rect_array, x=0, y=0):
        for i in range(x, min(self.columns, x + len(rect_array))):
            for j in range(y, min(self.rows, y + len(rect_array[0]))):
                self.set_pixel(i, j, rect_array[i - x][j - y])


    def clear(self, update=True):
        for i in range(self.columns * self.rows):
            self._neopixel[i] = self._color_codes_to_rgb('black')
        if update:
            self._neopixel.write()

    def _transpose(self, rect):
        ret = []
        c = len(rect)
        r = len(rect[0])
        for i in range(r):
            ret.append([])
            for j in range(c):
                ret[i].append(rect[j][i])
        return ret

    def scroll_text(self, text, delay=150, code='white'):
        black = self._color_codes_to_rgb('black')
        led_main = [[black for _ in range(self.columns)] for __ in range(self.rows)]
        led_buff = [[black for _ in range(self.columns)] for __ in range(self.rows)]
        scroll_time = 0
        code = self._color_codes_to_rgb(code)
        c = ''
        for l, t in enumerate(text):
            c = t if t in FONTS_5x5 else ' '
            led_buff = unpack_font_to_grid(FONTS_5x5[c], code, black)
            # for i in range(25):  # draw font in grid
            #     ledBuff[i % self.columns][self.rows - i // self.columns -1] = \
            #         code if _FONTS[c][i] != '*' else black
            scroll_time = self.columns * 2 if l == len(text) - 1 else FONT_5x5_WIDTH[c] + 1
            self.set_rect(led_buff)
            self._neopixel.write()
            for _ in range(scroll_time):
                tmp_col = led_buff.pop(0)
                led_buff.append([(0,0,0)]*self.rows)
                led_main.pop(0)
                led_main.append(tmp_col)
                self.set_rect((led_main))
                self._neopixel.write()
                sleep_ms(delay)

    def symbol(self, sym, color='white'):
        black = self._color_codes_to_rgb('black')
        color = self._color_codes_to_rgb(color)
        s = SYMBOLS[sym]
        led_buff = unpack_font_to_grid(s, color, black)
        for i in range(25):  # draw font in grid
            led_buff[i % self.columns][self.rows - i // self.columns -1] = \
                color if s[i] != ' ' else black
        self.set_rect(led_buff)
        self._neopixel.write()

    def show(self):
        self._neopixel.write()
