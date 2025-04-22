import json
from datetime import datetime, timezone
import threading
import os

LOG_FILE = os.path.join(os.path.dirname(__file__), 'task_accounting.log')
log_lock = threading.Lock()

def get_utc_timestamp():
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

def sign_log_entry(log_entry, sign_func=None):
    # Placeholder for digital signature: sign_func(log_entry_json) returns signature
    # If sign_func is None, skip signing
    if sign_func:
        log_entry['signature'] = sign_func(json.dumps(log_entry, sort_keys=True))
    else:
        log_entry['signature'] = None
    return log_entry

def append_log_entry(event_type, task_id, node_id, details=None, sign_func=None):
    log_entry = {
        'timestamp_utc': get_utc_timestamp(),
        'task_id': task_id,
        'event_type': event_type,
        'node_id': node_id,
        'details': details or {},
    }
    log_entry = sign_log_entry(log_entry, sign_func)
    with log_lock:
        # Ensure log file exists
        if not os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'w') as f:
                pass
        with open(LOG_FILE, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    return log_entry

# Ensure log file is created at import time
with log_lock:
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w') as f:
            pass
