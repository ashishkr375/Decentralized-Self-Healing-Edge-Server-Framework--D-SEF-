import requests
import argparse
import random
import time
import csv
import os
import math
from datetime import datetime

parser = argparse.ArgumentParser(description="ESP Simulator")
parser.add_argument("--bootstrap", type=str, required=True, help="Bootstrap Edge Node URL")
parser.add_argument("--interval", type=int, default=5, help="Load packet interval")
args = parser.parse_args()

current_edge_server = None

RESULTS_FILE = os.environ.get('ESP_RESULTS_FILE', 'esp_sim_results.csv')

if not os.path.exists(RESULTS_FILE):
    with open(RESULTS_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'edge_ip', 'edge_port', 'load', 'result', 'response_time_ms', 'redirected'])

print("------------ ESP SIMULATOR STARTED ------------")

def fetch_peers():
    try:
        response = requests.get(f"{args.bootstrap}/peer", timeout=5)
        peers = response.json().get("peers", [])
        print("[ESP DEBUG] Peers fetched:", peers)  # <--- Add this line
        return peers
    except Exception as e:
        print("[ESP DEBUG] Exception fetching peers:", e)
        return []

def do_computation_task(task_type, load):
    # Example: CPU-bound task (prime check), memory, or math
    if task_type == 'prime':
        n = max(2, load)
        is_prime = True
        for i in range(2, int(math.sqrt(n)) + 1):
            if n % i == 0:
                is_prime = False
                break
        return is_prime
    elif task_type == 'matrix':
        # Matrix multiplication
        size = min(100, max(2, int(load/10)))
        a = [[i+j for j in range(size)] for i in range(size)]
        b = [[i*j for j in range(size)] for i in range(size)]
        c = [[sum(a[i][k]*b[k][j] for k in range(size)) for j in range(size)] for i in range(size)]
        return c[0][0]
    else:
        # Fallback: busy-wait
        t0 = time.time()
        while time.time() - t0 < load/1000.0:
            pass
        return True

def send_load():
    global current_edge_server
    peers = fetch_peers()

    if not peers:
        print("[ESP] No peers found! Retrying in next interval.")
        return

    if current_edge_server not in peers:
        current_edge_server = random.choice(peers)
        print(f"[ESP] Selected edge server {current_edge_server['ip']}:{current_edge_server['port']}")

    load = random.randint(100, 1000)
    task_type = random.choice(['prime', 'matrix'])
    url = f"http://{current_edge_server['ip']}:{current_edge_server['port']}/handle_request"
    start = time.time()
    redirected = ''
    result = 'success'
    try:
        # Actually do the computation locally as well for demo/validation
        local_result = do_computation_task(task_type, load)
        response = requests.post(url, json={"processing_load": load, "task_type": task_type}, timeout=10)
        data = response.json()
        elapsed = int((time.time() - start) * 1000)
        if 'redirected' in data:
            redirected_ip, redirected_port = data['redirected'].split(":")
            current_edge_server = {'ip': redirected_ip, 'port': int(redirected_port)}
            redirected = f"{redirected_ip}:{redirected_port}"
            print(f"[ESP] Redirected to {redirected_ip}:{redirected_port}")
        else:
            print(f"[ESP] Sent {task_type} task (load={load}) -> {current_edge_server['ip']}:{current_edge_server['port']}")
        with open(RESULTS_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                current_edge_server['ip'],
                current_edge_server['port'],
                f"{task_type}:{load}",
                result,
                elapsed,
                redirected
            ])
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        result = 'fail'
        print(f"[ESP] Connection failed! {str(e)} Trying next best peer next round.")
        with open(RESULTS_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                current_edge_server['ip'] if current_edge_server else '',
                current_edge_server['port'] if current_edge_server else '',
                f"{task_type}:{load}",
                result,
                elapsed,
                redirected
            ])
        current_edge_server = None

while True:
    send_load()
    time.sleep(args.interval)
