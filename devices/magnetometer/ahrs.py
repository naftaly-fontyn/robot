import math

def compute_pitch_roll(ax, ay, az):
    """
    Computes Pitch and Roll from Accelerometer G-forces.
    Returns angles in Radians.
    """
    # Roll (Rotation around X-axis)
    # atan2(Y, Z)
    roll = math.atan2(ay, az)
    
    # Pitch (Rotation around Y-axis)
    # atan2(-X, sqrt(Y*Y + Z*Z))
    # We use sqrt to handle the Z-component correctly when tilted
    pitch = math.atan2(-ax, math.sqrt(ay*ay + az*az))
    
    return (pitch, roll)

def compute_tilt_compensated_heading(mx, my, mz, pitch, roll):
    """
    Calculates Heading relative to Magnetic North, compensating for board tilt.
    Arguments:
      mx, my, mz: Raw Magnetometer readings
      pitch, roll: Board Attitude in Radians (from Accelerometer)
    """
    
    # Pre-compute sines and cosines
    cos_p = math.cos(pitch)
    sin_p = math.sin(pitch)
    cos_r = math.cos(roll)
    sin_r = math.sin(roll)
    
    # 1. Tilt Compensation Math (Standard Transformation)
    # Rotate the magnetic vector into the horizontal plane
    
    # X_horizontal
    Xh = mx * cos_p + my * sin_r * sin_p + mz * cos_r * sin_p
    
    # Y_horizontal
    Yh = my * cos_r - mz * sin_r
    
    # 2. Calculate Heading
    heading_rad = math.atan2(Yh, Xh)
    
    # 3. Convert to Degrees
    heading_deg = math.degrees(heading_rad)
    
    # 4. Normalize to 0-360
    if heading_deg < 0:
        heading_deg += 360
        
    return heading_deg