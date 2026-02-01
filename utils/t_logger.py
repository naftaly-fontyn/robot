import _thread
import time
import os
import sys
import uio

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

# Singleton instance holder
_logger_instance = None

class ThreadedLogger:
    def __init__(self, filename="log.txt", level=INFO, to_console=True,
                 logger_name="", max_bytes=4096, backup_count=2):
        self.filename = filename
        self.level = level
        self.to_console = to_console
        self.name = logger_name
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._ensure_path(filename)
        self.queue = []
        self.lock = _thread.allocate_lock()
        self.running = True

        # Start the background file writer
        _thread.start_new_thread(self._worker, ())

    def _ensure_path(self, path):
        """
        Checks if the directory for the log file exists.
        If not, creates it (supports nested paths like 'logs/2023/sys.log').
        """
        # If it's just 'log.txt', no directory needed
        if "/" not in path:
            return

        # Split path: "logs/current/sys.log" -> ["logs", "current"]
        parts = path.split("/")[:-1]

        # Reconstruct and check each level
        current_path = ""
        for part in parts:
            if current_path == "":
                current_path = part
            else:
                current_path += "/" + part

            try:
                # Check if dir exists
                os.stat(current_path)
            except OSError:
                # Doesn't exist, create it
                try:
                    os.mkdir(current_path)
                    print(f"[Logger] Created directory: {current_path}")
                except Exception as e:
                    print(f"[Logger] Failed to create dir {current_path}: {e}")

    def _format(self, level, msg, **kwargs):
        t = time.localtime()
        # [HH:MM:SS] [LEVEL] [file:line] Message
        ts = "{:02d}:{:02d}:{:02d}".format(t[3], t[4], t[5])
        level_name = LEVEL_NAMES.get(level, "LOG")
        f_path = kwargs.get('file_path', None)
        func = kwargs.get('function', None)
        l_num = kwargs.get('line_number', None)
        meta = ""
        if self.name:
            meta += f"[{self.name}] "
        if f_path:
            meta += f"[{f_path}"
            if l_num: meta += f":{l_num}"
            meta += "] "
        elif l_num:
            meta += f"[:{l_num}] " # Line number only
        if func:
            meta += f"[{func}] "

        full_msg = f"[{ts}] [{level_name}] {meta}{msg}\n"
        return full_msg

    def log(self, level, msg, *args, exc_info=None, **kwargs):
        if level >= self.level:
            if args:
                try:
                    msg = msg % args
                except Exception:
                    # Fallback if arguments don't match format string
                    msg = f"{msg} [Formatting Error: {args}]"

            full_msg = self._format(level, msg, **kwargs)

            # Handle Tracebacks
            if exc_info:
                buf = uio.StringIO()
                if isinstance(exc_info, BaseException):
                    sys.print_exception(exc_info, buf)
                else:
                    buf.write("(Traceback unavailable)\n")
                full_msg += buf.getvalue()

            # 1. Console Output (Main Thread - Immediate)
            if self.to_console:
                if level >= ERROR:
                    sys.stderr.write(full_msg)
                else:
                    sys.stdout.write(full_msg)

            # 2. File Output (Worker Thread - Queued)
            with self.lock:
                self.queue.append(full_msg)

    # Convenience wrappers
    def debug(self, msg, *args, exc_info=None):
        self.log(DEBUG, msg, *args, exc_info=exc_info)

    def info(self, msg, *args, exc_info=None):
        self.log(INFO, msg, *args, exc_info=exc_info)

    def warning(self, msg, *args, exc_info=None):
        self.log(WARNING, msg, *args, exc_info=exc_info)

    def error(self, msg, *args, exc_info=None):
        self.log(ERROR, msg, *args, exc_info=exc_info)

    def critical(self, msg, *args, exc_info=None):
        self.log(CRITICAL, msg, *args, exc_info=exc_info)

    def _rotate(self):
        try:
            if os.stat(self.filename)[6] < self.max_bytes: return
        except OSError: return
        try: os.remove(f"{self.filename}.{self.backup_count}")
        except OSError: pass
        for i in range(self.backup_count - 1, 0, -1):
            try: os.rename(f"{self.filename}.{i}", f"{self.filename}.{i+1}")
            except OSError: pass
        try: os.rename(self.filename, f"{self.filename}.1")
        except OSError: pass

    def _worker(self):
        while self.running:
            chunk = ""
            with self.lock:
                if self.queue:
                    chunk = "".join(self.queue)
                    self.queue = []

            if chunk:
                try:
                    self._rotate()
                    with open(self.filename, 'a') as f:
                        f.write(chunk)
                except Exception as e:
                    print(f"!! LOGGER ERROR: {e}")

            time.sleep(1)

# --- Singleton Accessor ---
def get_logger(filename="log.txt", level=INFO, to_console=True,
               logger_name="",max_bytes=4096, backup_count=2):
    """
    Returns the singleton logger instance.
    Initializes it on the first call using the provided arguments.
    Subsequent calls ignore arguments and return the existing instance.
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = ThreadedLogger(
            filename, level, to_console, logger_name, max_bytes, backup_count)
    return _logger_instance