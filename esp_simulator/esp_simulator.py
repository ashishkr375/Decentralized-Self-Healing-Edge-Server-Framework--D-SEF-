import requests
import argparse
import random
import time

parser = argparse.ArgumentParser(description="ESP Simulator")
parser.add_argument("--bootstrap", type=str, required=True, help="Bootstrap Edge Node URL")
parser.add_argument("--interval", type=int, default=5, help="Load packet interval")
args = parser.parse_args()

current_edge_server = None

print("------------ ESP SIMULATOR STARTED ------------")

def fetch_peers():
    try:
        response = requests.get(f"{args.bootstrap}/peer", timeout=5)
        peers = response.json().get("peers", [])
        return peers
    except:
        return []

def send_load():
    global current_edge_server
    peers = fetch_peers()

    if not peers:
        print("[ESP] No peers found! Retrying in next interval.")
        return

    if current_edge_server not in peers:
        current_edge_server = random.choice(peers)
        print(f"[ESP] Selected edge server {current_edge_server['ip']}:{current_edge_server['port']}")

    try:
        load = random.randint(10, 500)
        url = f"http://{current_edge_server['ip']}:{current_edge_server['port']}/handle_request"
        response = requests.post(url, json={"processing_load": load}, timeout=5)
        data = response.json()

        if 'redirected' in data:
            redirected_ip, redirected_port = data['redirected'].split(":")
            current_edge_server = {'ip': redirected_ip, 'port': int(redirected_port)}
            print(f"[ESP] Redirected to {redirected_ip}:{redirected_port}")
        else:
            print(f"[ESP] Sent load: {load} units -> {current_edge_server['ip']}:{current_edge_server['port']}")

    except:
        print("[ESP] Connection failed! Trying next best peer next round.")
        current_edge_server = None

while True:
    send_load()
    time.sleep(args.interval)
