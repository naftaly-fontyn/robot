import uasyncio as asyncio
import sys


def supervised(restart_delay=5, log_file='error.log'):
    """
    A decorator that wraps an async function in a supervisor loop.
    If the function crashes, it logs the error and restarts after `restart_delay`.
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # The "Supervisor Loop"
            while True:
                try:
                    # Run the actual task
                    return await func(*args, **kwargs)

                except asyncio.CancelledError:
                    # IMPORTANT: Allow the task to be cancelled cleanly
                    print(f"[{func.__name__}] Task cancelled.")
                    raise

                except Exception as e:
                    print(f"[{func.__name__}] CRASHED: ", exc_info=e)

                    print(f"[{func.__name__}] Restarting in {restart_delay}s...")
                    await asyncio.sleep(restart_delay)
        return wrapper
    return decorator

"""
# Apply the decorator
@supervised(restart_delay=2)
async def sensor_loop(sensor_id):
    print(f"Reading {sensor_id}...")

    # Simulate work
    await asyncio.sleep(1)

    # Simulate a crash
    if True:
        raise ValueError("Sensor disconnected!")

@supervised(restart_delay=10, log_file='wifi_errors.log')
async def wifi_checker():
    print("Checking WiFi...")
    await asyncio.sleep(5)
    # This simulates a task that runs once and finishes naturally.
    # If it finishes without error, the supervisor exits too.
    print("WiFi is OK.")

# Main Application
async def main():
    # You start them normally. The decorator handles the rest.
    asyncio.create_task(sensor_loop("Temp_1"))
    asyncio.create_task(wifi_checker())

    while True:
        await asyncio.sleep(1)

asyncio.run(main())
"""