import time
import esp32
import gc
import usocket as socket

# Log Levels
DEBUG    = 10
INFO     = 20
WARNING  = 30
ERROR    = 40
CRITICAL = 50

LEVEL_NAMES = {
    10: "DEBUG",
    20: "INFO",
    30: "WARN",
    40: "ERROR",
    50: "CRIT"
}

_logger_instance = None

class Logger:
    def __init__(self, level=WARNING):
        self.level_console = level
        self.level_network = INFO
        self.sock = None
        self.multicast_ip = '224.0.1.187'
        self.multicast_port = 5683
        self.topic = "log"

    def set_level(self, console=None, network=None):
        """Change log levels at runtime."""
        if console is not None:
            self.level_console = int(console)
        if network is not None:
            self.level_network = int(network)
        _logger_instance.info(f'Change log level Console {self.level_console}, Network {self.level_network}')

    def start_broadcast(self, ip='224.0.1.187', port=5683):
        """Enable UDP multicast logging."""
        self.multicast_ip = ip
        self.multicast_port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        print(f"[Logger] UDP logging enabled to {ip}:{port}")

    def log(self, level, msg, *args, **kwargs):
        if level < self.level_console and level < self.level_network:
            return

        if args:
            try:
                msg = msg % args
            except:
                pass

        # Console Logging
        if level >= self.level_console:
            t = time.localtime()
            ts = "{:02d}:{:02d}:{:02d}".format(t[3], t[4], t[5])
            lname = LEVEL_NAMES.get(level, "LOG")
            print(f"[{ts}] [{lname}] {msg}")

        # Network Logging (CoAP Multicast)
        if level >= self.level_network and self.sock:
            try:
                lname = LEVEL_NAMES.get(level, "LOG")
                payload = f"[{lname}] {msg}"
                self.sock.sendto(payload.encode('utf-8'), (self.multicast_ip, self.multicast_port))
            except Exception as e:
                print(f"[Logger] Network Error: {e}")

    def debug(self, msg, *args, **kwargs):
        self.log(DEBUG, msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.log(INFO, msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.log(WARNING, msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.log(ERROR, msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self.log(CRITICAL, msg, *args, **kwargs)

def mem_info_str():
    used = gc.mem_alloc()
    free = gc.mem_free()
    total = used + free
    max_free = 0
    try:
        # idf_heap_info returns (total, free, largest_free, min_free)
        max_free = max([x[2] for x in esp32.idf_heap_info(esp32.HEAP_DATA)])
    except:
        pass
    return f"MEM: Used {used}, Free {free}, Total {total}, Max {max_free}"

def get_logger(filename="log.txt", level=WARNING, to_console=True,
               logger_name="",max_bytes=4096, backup_count=2):
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = Logger(level)
    return _logger_instance