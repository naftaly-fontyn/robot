from machine import SoftI2C, Pin
from mmc5983 import MMC5983
import time

# I2C Setup
i2c = SoftI2C(scl=Pin(22), sda=Pin(23), freq=400000)
mag = MMC5983(i2c)

print("--- COMPASS CALIBRATION ---")
print("Rotate the board in all directions (Figure-8 motion)")
print("Start in 3...")
time.sleep(1)
print("2...")
time.sleep(1)
print("1...")
time.sleep(1)
print("GO!")

min_x, max_x = 100, -100
min_y, max_y = 100, -100
min_z, max_z = 100, -100

OFFSET_X = 2.2045
OFFSET_Y = -5.2486
OFFSET_Z = 6.9641

OFFSET_X = 1.9062
OFFSET_Y = -5.1964
OFFSET_Z = 7.0099

start_time = time.ticks_ms()

while time.ticks_diff(time.ticks_ms(), start_time) < 20000: # 20 seconds
    data = mag.read_mag_xyz()
    if data:
        x, y, z = data
        
        # Update Min/Max
        min_x = min(min_x, x)
        max_x = max(max_x, x)
        min_y = min(min_y, y)
        max_y = max(max_y, y)
        min_z = min(min_z, z)
        max_z = max(max_z, z)
        
        print(f"Sampling... X[{min_x:.1f}:{max_x:.1f}] Y[{min_y:.1f}:{max_y:.1f}]")
        
    time.sleep(0.05)

# Calculate Offsets (Midpoint)
offset_x = (max_x + min_x) / 2
offset_y = (max_y + min_y) / 2
offset_z = (max_z + min_z) / 2

scale_x = (max_x - min_x)
scale_y = (max_y - min_y)
scale_z = (max_z - min_z)

print("\n--- CALIBRATION COMPLETE ---")
print("Copy these values into main.py:")
print(f"OFFSET_X = {offset_x:.4f}  # {scale_x}")
print(f"OFFSET_Y = {offset_y:.4f}  # {scale_y}")
print(f"OFFSET_Z = {offset_z:.4f}  # {scale_z}")