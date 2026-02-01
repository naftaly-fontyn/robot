# main.py - This is the file that runs on boot. Keep it small.
import os
import sys
import gc
import utils.t_logger

# create the logger
log = utils.t_logger.get_logger(
    filename='logs/log.txt', level=utils.t_logger.DEBUG, to_console=True,
    max_bytes=16384, backup_count=4)

try:
    # 1. THE TRIGGER
    os.remove('mode.ota')

    # --- IF WE ARE HERE, OTA IS REQUIRED ---
    log.info('=== Starting OTA ===')

    # 2. THE INTERNAL SAFETY NET
    # We must catch errors here so they don't jump to the 'except OSError' below
    try:
        from ota import main
        gc.collect()
        main()
    except Exception as e:
        log.error("OTA Critical Failure:", exc_info=e)
        sys.print_exception(e)

    # 3. STOP.
    # Never let execution fall through to the App logic after an OTA attempt
    sys.exit()

except OSError:
    # --- IF WE ARE HERE, FILE DID NOT EXIST ---
    # This is the only path to the App
    pass

# --- APP MODE ---
log.info('=== Starting App ===')
try:
    from app import main
    gc.collect()
    main()
except Exception as e:
    log.error('\nApp Crash:\n', exc_info=e)
    sys.print_exception(e)

log.info("Exit")
# import time
# time.sleep(5)
# sys.exit(0)
"""
import uasyncio as asyncio
import gc

# Explicitly run garbage collection to clean up memory
# after the boot process and before importing our large app.
gc.collect()

# Now, import the main application logic from the other file.
# This is where your routes and functions are defined.
from app_main import main

try:
    # Run the main async function from your app.
    asyncio.run(main())
finally:
    # Clean up the event loop on exit.
    asyncio.new_event_loop()
"""