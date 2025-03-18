import threading
import random
import time
import requests
from flask import request, jsonify
from Crypto.PublicKey import ECC
from Crypto.Signature import DSS
from Crypto.Hash import SHA256

known_peers = {}
node_info = {}
key_pair = None

def initialize_node(args):
    global key_pair
    key_pair = ECC.generate(curve='P-256')
    node_info.update({
        "ip": args.ip,
        "port": args.port,
        "promised_capacity": args.promised_capacity,
        "current_load": 0
    })
    self_id = f"{node_info['ip']}:{node_info['port']}"
    known_peers[self_id] = node_info.copy()

    if args.bootstrap:
        join_network(args.bootstrap)
    start_auto_discovery()
    

def join_network(bootstrap_url):
    payload = {
        "ip": node_info["ip"],
        "port": node_info["port"],
        "promised_capacity": node_info["promised_capacity"],
        "public_key": key_pair.public_key().export_key(format='PEM')
    }
    try:
        response = requests.post(f"{bootstrap_url}/register", json=payload, timeout=5)
        if response.status_code == 200:
            challenge = response.json().get('challenge')
            h = SHA256.new(challenge.encode('utf-8'))
            signer = DSS.new(key_pair, 'fips-186-3')
            signature = signer.sign(h)
            auth_payload = {
                "ip": node_info["ip"],
                "port": node_info["port"],
                "promised_capacity": node_info["promised_capacity"],
                "signature": signature.hex()
            }
            requests.post(f"{bootstrap_url}/authenticate", json=auth_payload)
            print(f"[SYNC] Joined network via {bootstrap_url}")
            fetch_peer_table(bootstrap_url)
            gossip_new_peer(bootstrap_url)
    except Exception as e:
        print(f"[ERROR] Could not join network: {e}")

def fetch_peer_table(peer_url):
    try:
        response = requests.get(f"{peer_url}/peer", timeout=5)
        if response.status_code == 200:
            for peer in response.json().get("peers", []):
                peer_id = f"{peer['ip']}:{peer['port']}"
                if peer_id != f"{node_info['ip']}:{node_info['port']}":
                    known_peers[peer_id] = peer
            print_peer_table()
    except:
        pass

def gossip_new_peer(peer_url):
    for peer_id, peer in known_peers.items():
        try:
            requests.post(f"http://{peer['ip']}:{peer['port']}/update_peer", json=node_info, timeout=3)
        except:
            pass

def start_auto_discovery():
    def discover_peers():
        while True:
            if known_peers:
                peer = random.choice(list(known_peers.values()))
                fetch_peer_table(f"http://{peer['ip']}:{peer['port']}")
                health_check()
            time.sleep(random.randint(1, 5))

    threading.Thread(target=discover_peers, daemon=True).start()


def health_check():
    dead_peers = []
    for peer_id, peer in known_peers.items():
        try:
            requests.get(f"http://{peer['ip']}:{peer['port']}/peer", timeout=3)
        except:
            dead_peers.append(peer_id)
    for dead in dead_peers:
        print(f"[HEALTH] Removing dead peer {dead}")
        known_peers.pop(dead, None)


def print_peer_table():
    print("\n========== UPDATED PEER TABLE ==========")
    print("| IP                  | Port | Load | Capacity |")
    print("-----------------------------------------")
    for peer_id, peer in known_peers.items():
        print(f"| {peer['ip']:<18} | {peer['port']:<4} | {peer.get('current_load', 0):<4} | {peer.get('promised_capacity', 0):<8} |")
    print("-----------------------------------------\n")


def register_routes(app):
    @app.route('/peer', methods=['GET'])
    def get_peers():
        peer_list = []
        for peer_id, peer in known_peers.items():
            peer_copy = dict(peer)
            peer_copy.pop("key_pair", None)
            peer_list.append(peer_copy)
        return jsonify({"peers": peer_list})

    @app.route('/update_peer', methods=['POST'])
    def update_peer():
        data = request.json
        peer_id = f"{data['ip']}:{data['port']}"
        known_peers[peer_id] = data
        print(f"[GOSSIP] Peer table updated with {data['ip']}:{data['port']}")
        return {"status": "peer updated"}