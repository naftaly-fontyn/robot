# AHRS: Attitude Heading Reference System
import math
import asyncio
import time
from machine import Pin, I2C

from boards.matrixbit_on3 import MBIT_PIN_MAP
from devices.imu import qmi8658
from utils.messagebus import Subscriber, Publisher, QueueEmpty
from devices.magnetometer.mmc5983 import MMC5983
from tasks.display_task import PRINT


# [1,0,0] = A * [a,b,c]

BOARD_PLACEMENT = [
    [0, 0, -1],
    [0, 1, 0],
    [1, 0, 0]
]

# def determinant(matrix):
#     return matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1]) - \
#            matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0]) + \
#            matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])


def dot(u, v): return u[0]*v[0] + u[1]*v[1] + u[2]*v[2]
def sub(u, v): return [u[i]-v[i] for i in range(3)]
def vec_scale(v, s): return [v[i]*s for i in range(3)]
def vec_norm(v): return math.sqrt(dot(v, v))
def normalize(v): return vec_scale(v, 1/vec_norm(v))
def cross(u, v):
    return [
        u[1]*v[2] - u[2]*v[1],
        u[2]*v[0] - u[0]*v[2],
        u[0]*v[1] - u[1]*v[0]
    ]

def orthonormal_basis(v):
    # pick something not parallel
    if abs(v[0]) < 0.9:
        w = [1,0,0]
    else:
        w = [0,1,0]

    u2 = sub(w, vec_scale(v, dot(v, w)))  # remove projection
    u2 = normalize(u2)
    u3 = cross(v, u2)
    u3 = normalize(u3)
    return [v, u2, u3]  # Returns a matrix with the orthonormal basis vectors as rows

def mat_mul(A, B):
    # 3x3 * 3x3
    M = [[0]*3 for _ in range(3)]
    for i in range(3):
        for j in range(3):
            M[i][j] = (A[i][0]*B[0][j] +
                       A[i][1]*B[1][j] +
                       A[i][2]*B[2][j])
    return M

def transpose(M):
    return [
        [M[0][0], M[1][0], M[2][0]],
        [M[0][1], M[1][1], M[2][1]],
        [M[0][2], M[1][2], M[2][2]],
    ]

def mat_vec_mul(A, v):
    r = [0, 0, 0]
    for i in range(3):
        for j in range(3):
            r[i] += A[i][j] * v[j]
    return r


def build_rotation(v, t):
    v = normalize(v)
    t = normalize(t)
    # both must be unit vectors!
    # Bv and Bt are matrices whose ROWS are the basis vectors {v, u2, u3} and {t, w2, w3}
    Bv = orthonormal_basis(v)
    Bt = orthonormal_basis(t)
    # The rotation matrix A that maps vector v to t is A = M_t * (M_v)^-1,
    # where M_v and M_t are matrices with the basis vectors as COLUMNS.
    # In our row-major representation, this is equivalent to A = (Bt^T) * Bv.
    A = mat_mul(transpose(Bt), Bv)
    return A


async def _read_sensor_with_retry(sensor_func):
    """
    Continuously tries to read from a sensor function until it returns a non-None value.
    This is necessary because the sensor may not have data ready on every poll.
    """
    value = sensor_func()
    while value is None:
        await asyncio.sleep_ms(1) # Small delay to not overwhelm the I2C bus
        value = sensor_func()
    return value


async def _calibrate_gyro(imu, num_samples=200):
    """
    Calculates the gyroscope bias by averaging a number of readings at startup.
    Assumes the robot is stationary. The driver now handles axis remapping.
    """
    PRINT("Calib keep still")
    bias_x, bias_y, bias_z = 0.0, 0.0, 0.0
    for _ in range(num_samples):
        gyro_reading = await _read_sensor_with_retry(imu.read_gyro_xyz)
        bias_x += gyro_reading[0]
        bias_y += gyro_reading[1]
        bias_z += gyro_reading[2]
        await asyncio.sleep_ms(5)

    bias = (bias_x / num_samples, bias_y / num_samples, bias_z / num_samples)
    # print(f"Gyroscope bias calculated: {bias}")
    PRINT('Done Calib')
    return bias

def calculate_heading(mag_reading, accel_reading):
    """
    Calculates a tilt-compensated heading from magnetometer and accelerometer data.
    This is a standard algorithm to get a compass heading that is not affected
    by the pitch or roll of the sensor.
    """
    # 1. Get Pitch and Roll from the accelerometer (gravity vector)
    ax, ay, az = accel_reading
    # Roll (Rotation around X-axis)
    roll_rad = math.atan2(ay, az)
    # Pitch (Rotation around Y-axis)
    pitch_rad = math.atan2(-ax, math.sqrt(ay * ay + az * az))

    # 2. De-rotate the magnetometer readings to the horizontal plane
    mx, my, mz = mag_reading
    cos_pitch = math.cos(pitch_rad)
    sin_pitch = math.sin(pitch_rad)
    cos_roll = math.cos(roll_rad)
    sin_roll = math.sin(roll_rad)

    # Tilt-compensated magnetic field vector (Xh, Yh)
    mag_x_comp = mx * cos_pitch + my * sin_roll * sin_pitch + mz * cos_roll * sin_pitch
    mag_y_comp = my * cos_roll - mz * sin_roll

    # 3. Calculate the heading from the compensated components
    heading_rad = math.atan2(mag_y_comp, mag_x_comp)
    heading_deg = math.degrees(heading_rad)

    # Convert from mathematical (CCW) to navigational (CW)
    heading_deg = -heading_deg

    # Normalize to 0-360 degrees
    if heading_deg < 0:
        heading_deg += 360

    return heading_deg

IMU = None
MAG = None

async def ahrs_task(i2c_obj):
    """
    Task to get gyro, accelerometer, and magnetometer data.
    awaiting message:
        topic: 'ahrs_task'
        message: {'command': 'single' | 'continuous' | 'stop' | 'calibrate',
                  /'cycle_time_ms': <int>/,
                  /'calibrate_time_s': <int>/,}
    publishing message:
        topic: 'ahrs_report'
        message: {/'time_tick_ms': <int>,
                  'accel_xyz': [<float>, <float>, <float>],
                  'gyro_xyz': [<float>, <float>, <float>],
                  'heading': <float>,
                  'temperature': <float>/,
                  /'ack': 'ACK'|'NACK'/,
                  }

    default cycle_time_ms: 100ms
    default calibrate_time_s: 20s
    Args:
        i2c_obj (machine.I2C): I2C object to use for communication.

    Returns:
        None

    Raises:
        None
    """
    global IMU, MAG
    if IMU is None:
        IMU = qmi8658.QMI8658(i2c_obj)
    if MAG is None:
        MAG = MMC5983(i2c_obj)
    # print(IMU)
    imu = IMU
    mag = MAG
    await asyncio.sleep(0.5)

    # Calibrate Gyroscope to find the zero-rate offset
    PRINT('AHRS task')
    gyro_bias = await _calibrate_gyro(imu)
    if False:
        await asyncio.sleep(2)
        mag.calibrate()
        input('Continue')
    # Get initial orientation from accelerometer. The driver now handles axis remapping.
    accel_reading = await _read_sensor_with_retry(imu.read_accel_xyz)
    rot_matrix = build_rotation(normalize(accel_reading), [0,0,-1])
    sbr_ahrs = Subscriber('ahrs_task', topics='ahrs_task')
    plsh = Publisher('ahrs_task')
    timeout = None
    last_command = None
    while True:
        try:
            topic, src, message = await sbr_ahrs.get(timeout=timeout)
            if message and message.get('command', None):
                if message['command'] == 'single':
                    timeout = None
                    last_command = 'single'
                elif message['command'] == 'continuous':
                    timeout = message.get('cycle_time_ms', 100)
                    last_command = 'continuous'
                elif message['command'] == 'calibrate':
                    timeout = message.get('calibrate_time_s', 20)
                    last_command = 'calibrate'
                elif message['command'] == 'stop':
                    timeout = None
                    last_command = 'stop'
        except QueueEmpty:
            pass
            # The driver now handles axis remapping.
        if last_command in ('single', 'continuous'):
            accel_reading = await _read_sensor_with_retry(imu.read_accel_xyz)
            accel_xyz = mat_vec_mul(rot_matrix, accel_reading)
            gyro_reading = await _read_sensor_with_retry(imu.read_gyro_xyz)
            gyro_calibrated = sub(gyro_reading, gyro_bias)
            gyro_xyz = mat_vec_mul(rot_matrix, gyro_calibrated)
            mag_reading = mag.read_mag_xyz()
            heading = calculate_heading(mag_reading, accel_reading) if mag_reading else None
            temperature = imu.read_temperature()
            # print sensor values for debugging
            # print(f"ACCEL: {accel_reading[0]:.2f}, {accel_reading[1]:.2f}, {accel_reading[2]:.2f} | MAG: {mag_reading[0]:.2f}, {mag_reading[1]:.2f}, {mag_reading[2]:.2f}")
            # print("MAG: Failed to get reading")
            plsh.publish('ahrs_report', {
                'time_tick_ms': time.ticks_ms(),
                'accel_xyz': accel_xyz,
                'gyro_xyz': gyro_xyz,
                'heading': heading,
                'temperature': temperature})
        elif last_command == 'calibrate':
            plsh.publish('ahrs_report', {'ack': 'ACK' if mag.calibrate(calib_time=20) else 'NACK'})


if __name__ == "__main__":
    async def test():
        main_i2c = I2C(0, scl=Pin(MBIT_PIN_MAP['P19']),
                       sda=Pin(MBIT_PIN_MAP['P20']),
                       freq=400_000)
        asyncio.create_task(ahrs_task(i2c_obj=main_i2c))
        await asyncio.sleep(5)
        plsh = Publisher('ahrs_test')
        for angle in range(50):
            plsh.publish(topic='ahrs_task', message={'command': 'single'})
            response = await Subscriber('ahrs_test', topics='ahrs_report').get()
            print(response)
            await asyncio.sleep(0.2)

    asyncio.run(test())