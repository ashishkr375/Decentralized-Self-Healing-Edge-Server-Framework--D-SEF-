import threading
import random
import time
import requests
from flask import request, jsonify, Blueprint
from Crypto.PublicKey import ECC
from Crypto.Signature import DSS
from Crypto.Hash import SHA256

known_peers = {}
node_info = {}
key_pair = None
misbehavior_counts = {}
MISBEHAVIOR_THRESHOLD = 5
MISBEHAVIOR_QUARANTINE_TIME = 300  # seconds
quarantined_peers = {}

# --- TLS/HTTPS Support ---
HTTPS_PREFIX = "https://"
HTTP_PREFIX = "http://"
VERIFY_SSL = False  # Set to True in production with real certs

# --- Network protocol selection logic ---
import os
ssl_exists = os.path.exists('cert.pem') and os.path.exists('key.pem')
PROTOCOL = 'https' if ssl_exists else 'http'

# --- Helper to get peer URL with correct protocol ---
def get_peer_url(ip, port):
    return f"{PROTOCOL}://{ip}:{port}"

# --- Global safety check for key_pair ---
def ensure_key_pair():
    global key_pair
    if key_pair is None:
        print("[KEY_PAIR] Was None, generating new key!")
        key_pair = ECC.generate(curve='P-256')
    # Defensive: if still None, raise error
    if key_pair is None:
        raise RuntimeError("[KEY_PAIR] FATAL: ECC key_pair could not be initialized!")

def initialize_node(args):
    global key_pair
    ensure_key_pair()
    print("[DEBUG] initialize_node called. key_pair:", key_pair)
    from chord import get_chord_id
    node_info.update({
        "ip": args.ip,
        "port": args.port,
        "promised_capacity": int(get_actual_capacity() if 'get_actual_capacity' in globals() else args.promised_capacity or 0),
        "current_load": 0,
        "public_key": key_pair.public_key().export_key(format='PEM')
    })
    if "chord_id" not in node_info:
        node_info["chord_id"] = int(get_chord_id(node_info["ip"], node_info["port"]))
    else:
        node_info["chord_id"] = int(node_info["chord_id"] or 0)
    self_id = f"{node_info['ip']}:{node_info['port']}"
    known_peers[self_id] = node_info.copy()
    print(f"[DEBUG] Added self to known_peers: {self_id}")
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
        response = requests.post(get_peer_url(bootstrap_url.split('://')[-1].split(':')[0], bootstrap_url.split('://')[-1].split(':')[1]) + "/register", json=payload, timeout=5, verify=ssl_exists)
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
            requests.post(get_peer_url(bootstrap_url.split('://')[-1].split(':')[0], bootstrap_url.split('://')[-1].split(':')[1]) + "/authenticate", json=auth_payload, verify=ssl_exists)
            print(f"[SYNC] Joined network via {bootstrap_url}")
            fetch_peer_table(get_peer_url(bootstrap_url.split('://')[-1].split(':')[0], bootstrap_url.split('://')[-1].split(':')[1]))
            gossip_new_peer(get_peer_url(bootstrap_url.split('://')[-1].split(':')[0], bootstrap_url.split('://')[-1].split(':')[1]))
    except Exception as e:
        print(f"[ERROR] Could not join network: {e}")

def fetch_peer_table(peer_url):
    try:
        response = requests.get(peer_url + "/peer", timeout=5, verify=ssl_exists)
        if response.status_code == 200:
            updated = False
            for peer in response.json().get("peers", []):
                peer_id = f"{peer['ip']}:{peer['port']}"
                if peer_id != f"{node_info['ip']}:{node_info['port']}" and peer_id not in known_peers:
                    # Add Chord ID to peer if missing
                    if "chord_id" not in peer:
                        from chord import get_chord_id
                        peer["chord_id"] = get_chord_id(peer["ip"], peer["port"])
                    known_peers[peer_id] = peer
                    updated = True
            
            # Only print if we actually added new peers
            if updated:
                print_peer_table()
    except Exception as e:
        print(f"[FETCH_PEER_TABLE] Error: {e}")

def gossip_new_peer(peer_url):
    # Add Chord ID to our node_info if missing
    if "chord_id" not in node_info:
        from chord import get_chord_id
        node_info["chord_id"] = get_chord_id(node_info["ip"], node_info["port"])
        
    for peer_id, peer in known_peers.items():
        if not is_peer_quarantined(peer_id):
            try:
                requests.post(get_peer_url(peer['ip'], peer['port']) + "/update_peer", json=node_info, timeout=3, verify=ssl_exists)
            except:
                mark_peer_misbehavior(peer_id)

def start_auto_discovery():
    def discover_peers():
        while True:
            if known_peers:
                peer = random.choice(list(known_peers.values()))
                if not is_peer_quarantined(f"{peer['ip']}:{peer['port']}"):
                    fetch_peer_table(get_peer_url(peer['ip'], peer['port']))
                    health_check()
            time.sleep(random.randint(1, 5))

    threading.Thread(target=discover_peers, daemon=True).start()

def health_check():
    dead_peers = []
    for peer_id, peer in known_peers.items():
        # Never remove self!
        if peer_id == f"{node_info['ip']}:{node_info['port']}":
            continue
        if not is_peer_quarantined(peer_id):
            try:
                requests.get(get_peer_url(peer['ip'], peer['port']) + "/peer", timeout=3, verify=ssl_exists)
            except:
                dead_peers.append(peer_id)
                mark_peer_misbehavior(peer_id)
    for dead in dead_peers:
        print(f"[HEALTH] Removing dead peer {dead}")
        known_peers.pop(dead, None)

def print_peer_table():
    print("\n========== UPDATED PEER TABLE ==========")
    print("| IP               | Port | Load | Capacity | Chord ID       |")
    print("---------------------------------------------------------------")
    for peer_id, peer in known_peers.items():
        ip = peer.get("ip", "N/A") or "N/A"
        port = peer.get("port", "N/A") or "N/A"
        load = peer.get("current_load", 0) or 0
        cap = peer.get("promised_capacity", 0) or 0
        chord_id = peer.get("chord_id", "N/A")
        chord_id_short = f"{chord_id % 10000}" if isinstance(chord_id, int) else "N/A"
        print(f"| {ip:<15} | {port:<4} | {load:<4} | {cap:<8} | {chord_id_short:<14} |")
    print("---------------------------------------------------------------\n")

# --- PATCH /peer endpoint to always include self and all required fields ---
def get_all_peers():
    # Always include self with up-to-date info
    self_id = f"{node_info['ip']}:{node_info['port']}"
    all_peers = dict(known_peers)  # shallow copy
    all_peers[self_id] = node_info.copy()
    return list(all_peers.values())

# Register the /peer endpoint
peer_bp = Blueprint('peer_bp', __name__)

@peer_bp.route('/peer', methods=['GET'])
def peer_endpoint():
    # Return all known peers including self, with all required fields
    return jsonify({"peers": get_all_peers()})

# --- Add /status endpoint ---
@peer_bp.route('/status', methods=['GET'])
def status_endpoint():
    tasks = []
    if 'get_current_tasks' in globals():
        tasks = get_current_tasks()
    status_info = {
        "ip": node_info.get("ip"),
        "port": node_info.get("port"),
        "chord_id": int(node_info.get("chord_id", 0) or 0),  # Ensure integer
        "current_load": int(node_info.get("current_load", 0) or 0),
        "promised_capacity": int(node_info.get("promised_capacity", 0) or 0),
        "tasks": tasks
    }
    return jsonify(status_info)

def register_routes(app):
    app.register_blueprint(peer_bp)
    @app.route('/update_peer', methods=['POST'])
    def update_peer():
        data = request.json
        peer_id = f"{data['ip']}:{data['port']}"
        # Add Chord ID if missing
        if "chord_id" not in data:
            from chord import get_chord_id
            data["chord_id"] = get_chord_id(data["ip"], data["port"])
        known_peers[peer_id] = data
        print(f"[GOSSIP] Peer table updated with {data['ip']}:{data['port']}")
        return {"status": "peer updated"}

    # --- Resource Offer Endpoint ---
    @app.route('/resource_offer', methods=['GET'])
    def resource_offer():
        try:
            offer = get_signed_resource_offer()
            return jsonify(offer)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

# --- Resource Offer Integration ---
from offer_manager import create_signed_resource_offer
from resource_manager import get_latest_stats

DEFAULT_PRICING = {"cpu_per_hour_usd": 0.01, "ram_gb_per_hour_usd": 0.005}

def get_signed_resource_offer():
    ensure_key_pair()  # Always ensure key_pair is valid
    global key_pair, node_info
    if key_pair is None:
        raise RuntimeError("[OFFER] key_pair is None! Cannot sign resource offer.")
    print("[DEBUG] get_signed_resource_offer called. key_pair:", key_pair)
    offer = create_signed_resource_offer(
        node_info,
        get_latest_stats(),
        DEFAULT_PRICING,
        key_pair
    )
    return offer

# Optionally: expose offer via a Flask endpoint or use in DHT advertisement logic

def mark_peer_misbehavior(peer_id):
    now = time.time()
    misbehavior_counts[peer_id] = misbehavior_counts.get(peer_id, 0) + 1
    if misbehavior_counts[peer_id] >= MISBEHAVIOR_THRESHOLD:
        quarantined_peers[peer_id] = now + MISBEHAVIOR_QUARANTINE_TIME
        print(f"[SECURITY] Peer {peer_id} quarantined for misbehavior.")

def is_peer_quarantined(peer_id):
    now = time.time()
    until = quarantined_peers.get(peer_id)
    if until and now < until:
        return True
    if until and now >= until:
        del quarantined_peers[peer_id]
    return False