# debuglog.py — Tiny ring-buffer flash logger for ESP32 crash diagnostics
#
# Writes timestamped, memory-annotated log lines to /debug.log on flash.
# Designed to survive crashes (flushes every write) and never fill up
# flash (truncates the oldest half when the file exceeds MAX_SIZE).
#
# Usage:
#   from debuglog import log, dump
#   log("boot sequence started")
#   log("free mem: {} bytes".format(gc.mem_free()))
#   dump()  # prints the whole log to serial console
#
# The log file can also be pulled from the board:
#   mpremote connect <port> cat :debug.log

import gc
import time

# --- Configuration ---
LOG_FILE = "debug.log"
MAX_SIZE = 16384  # 16 KB cap — safe for ESP32-C3 flash

# --- Internal state ---
_boot_ticks = time.ticks_ms()


def _filesize(path):
    """Return file size in bytes, or 0 if the file does not exist."""
    try:
        import os
        return os.stat(path)[6]
    except Exception:
        return 0


def _truncate_if_needed():
    """If the log file exceeds MAX_SIZE, keep only the newest half."""
    size = _filesize(LOG_FILE)
    if size <= MAX_SIZE:
        return
    try:
        with open(LOG_FILE, "r") as f:
            # Skip the first half of the file
            f.read(size // 2)
            # Read the remaining (newest) half
            keep = f.read()
        # Find the first complete line boundary in the kept portion
        nl = keep.find("\n")
        if nl >= 0:
            keep = keep[nl + 1:]
        with open(LOG_FILE, "w") as f:
            f.write("--- log truncated (was {} bytes) ---\n".format(size))
            f.write(keep)
    except Exception as e:
        # If truncation itself fails, nuke the log and note it
        try:
            with open(LOG_FILE, "w") as f:
                f.write("--- log reset (truncation failed: {}) ---\n".format(e))
        except Exception:
            pass


def log(msg, also_print=True):
    """Append a single timestamped log line to flash.

    Each line contains:
      <ms_since_boot> | <free_heap_bytes> | <message>

    Flushes and closes the file handle immediately so the line
    survives even if the board crashes right after this call.
    """
    # Collect timing and memory info *before* any allocation
    elapsed = time.ticks_diff(time.ticks_ms(), _boot_ticks)
    try:
        free = gc.mem_free()
    except Exception:
        free = -1

    line = "{:>10d} | {:>7d} | {}\n".format(elapsed, free, msg)

    if also_print:
        # Also echo to serial console (without the trailing newline,
        # because print() adds its own)
        print("LOG: {}".format(msg))

    try:
        _truncate_if_needed()
        with open(LOG_FILE, "a") as f:
            f.write(line)
    except Exception as e:
        # Last-resort: if flash write fails, at least print
        print("debuglog WRITE FAILED: {}".format(e))


def section(heading):
    """Write a visual separator to make the log easier to scan."""
    log("---------- {} ----------".format(heading))


def log_exception(context, exc):
    """Log an exception with context string and type information."""
    try:
        import sys
        log("EXCEPTION in {}: {} — {}".format(context, type(exc).__name__, exc))
        # Try to capture a mini traceback (MicroPython supports this)
        try:
            import io
            buf = io.StringIO()
            sys.print_exception(exc, buf)
            tb = buf.getvalue()
            buf.close()
            for tb_line in tb.strip().split("\n"):
                log("  TB: {}".format(tb_line), also_print=False)
        except Exception:
            pass
    except Exception:
        log("EXCEPTION in {}: (could not format)".format(context))


def dump():
    """Print the entire log file to the serial console."""
    print("===== DEBUG LOG DUMP =====")
    try:
        with open(LOG_FILE, "r") as f:
            while True:
                line = f.readline()
                if not line:
                    break
                print(line, end="")
    except OSError:
        print("(no log file found)")
    print("===== END OF LOG =====")


def clear():
    """Delete the log file."""
    try:
        import os
        os.remove(LOG_FILE)
        print("debuglog: cleared")
    except Exception:
        pass


def mem(label=""):
    """Convenience: log current free memory with optional label."""
    gc.collect()
    free = gc.mem_free()
    if label:
        log("MEM [{}]: {} bytes free ({} KB)".format(label, free, free // 1024))
    else:
        log("MEM: {} bytes free ({} KB)".format(free, free // 1024))
    return free
