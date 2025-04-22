import psutil
import threading
import time
import json
from datetime import datetime, timezone

# This will hold the latest system stats
latest_stats = {}

STATS_UPDATE_INTERVAL = 60  # seconds


def get_current_system_stats(partition=None):
    """
    Returns a JSON-serializable dictionary of current system stats.
    """
    if partition is None:
        # Default to root partition on Unix, C: on Windows
        partition = 'C:/' if psutil.WINDOWS else '/'
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_cores_physical = psutil.cpu_count(logical=False)
    cpu_cores_logical = psutil.cpu_count(logical=True)
    mem = psutil.virtual_memory()
    memory_total_gb = round(mem.total / (1024 ** 3), 2)
    memory_available_gb = round(mem.available / (1024 ** 3), 2)
    memory_used_percent = mem.percent
    disk = psutil.disk_usage(partition)
    disk_total_gb = round(disk.total / (1024 ** 3), 2)
    disk_free_gb = round(disk.free / (1024 ** 3), 2)
    disk_used_percent = disk.percent
    timestamp_utc = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
    return {
        'cpu_percent': cpu_percent,
        'cpu_cores_physical': cpu_cores_physical,
        'cpu_cores_logical': cpu_cores_logical,
        'memory_total_gb': memory_total_gb,
        'memory_available_gb': memory_available_gb,
        'memory_used_percent': memory_used_percent,
        'disk_total_gb': disk_total_gb,
        'disk_free_gb': disk_free_gb,
        'disk_used_percent': disk_used_percent,
        'timestamp_utc': timestamp_utc
    }

def update_stats_periodically(interval=STATS_UPDATE_INTERVAL, partition=None):
    global latest_stats
    while True:
        try:
            latest_stats = get_current_system_stats(partition=partition)
        except Exception as e:
            latest_stats = {'error': str(e)}
        time.sleep(interval)

def start_resource_monitor(interval=STATS_UPDATE_INTERVAL, partition=None):
    t = threading.Thread(target=update_stats_periodically, args=(interval, partition), daemon=True)
    t.start()
    return t

# Optionally, add a function to get the latest cached stats
def get_latest_stats():
    return latest_stats
