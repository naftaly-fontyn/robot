# Matrix:bit on3 v2


MBIT_PIN_MAP = {
    'P0': 33,   # touch8
    'P1': 32,    # touch9
    'P2': 35,    # Analog
    'P3': 34,    # Analog
    'P4': 39,    # Analog, Light sensor
    'P5': 0,     # Button A
    'P6': 16,    # Buzzer U2RXD
    'P7': 17,    # NeoPixels RGB LED 3x1
    'P8': 26,    #
    'P9': 25,    #
    'P10': 36,   # Sound/Analog (PWM?) MIC
    'P11': 2,    # Button B (boot2) ADC2_2, Touch2 (LED?) [Not ADC]
    'P12': 17,   # Duplicate !!
    'P13': 18,   # SPI sck
    'P14': 19,   # SPI miso
    'P15': 21,   # SPI mosi  [Not ADC] (23)
    'P16': 5,    # (? High during boot?)
    'P17': 'V3.3',
    'P18': 'V3.3',
    'P19': 22,   # I2C scl U0RTS
    'P20': 23,   # I2C sda
    'P21': 'GND',
    'P22': 'GND',
    'P': 27,
    'Y': 14,     #
    'T': 12,     #
    'H': 13,     #
    'O': 15,     #
    'N': 4,
}
# Integrated Flasg(6, 7, 8, 9, 10, 11), No_ADAC(13, 14, 15), Flash_Voltage(12),
# In_Only(34, 35, 36, 39) Boot_Message(15), Boot_Mode(0), 4(T0), 21,
# USB_PORT(1, 3)
# best to use and [4], 16, 17, 18, 19, [21], 22, 23, 25?, 26?, 27?, 5,
# ADC 32, 33, 34*, 35*, 36*
# PWM 2, 4, 12-19, 21-23, 25-27, 32-22
# DAC1 25, DAC2 26
# Touch [4], 15, 13, 12, 14, 27, 33, 32
OLED_096_ADDRESS = 0x3C    # SSD1306
GYRO_ACCEL_ADDRESS = 0x6B  # QMI8658
COMPASS = 0x30             # MMC5983
LIGHT_SENSOR = 39          # readonly
MICROPHONE = 36            # readonly
SPEAKER = 16
NEOPIXEL = 17              # RGB 3X1 NeoPixels
BUTTON_A = 0               # boot2
BUTTON_B = 2               # boot!

BOOT = 0
LIGHT_SENSOR_R = 39        # light sensor
# TEMPERATURE_SENSOR = 14
# RGB_LED = 18  # WS2812 5x5 RGB