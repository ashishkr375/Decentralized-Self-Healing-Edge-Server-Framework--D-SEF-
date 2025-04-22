import hashlib
import threading
import time
import random
from peers import node_info, known_peers, get_signed_resource_offer, key_pair
import requests
from offer_manager import verify_resource_offer

# Chord configuration
CHORD_BITS = 160 
CHORD_SIZE = 2 ** CHORD_BITS
finger_table = []
successor = None
predecessor = None

# ---- DHT Data Store for Resource Offers ----
# Each node will store offers it is responsible for here
# Key: Chord ID, Value: List of signed offers
self_dht_data_store = {}

# Calculate consistent hash for node ID
def get_chord_id(ip, port):
    """Generate a consistent node ID in the Chord ring using SHA1"""
    key = f"{ip}:{port}"
    return int(hashlib.sha1(key.encode()).hexdigest(), 16)

# Initialize node's position in Chord ring
def initialize_chord():
    global successor, predecessor
    
   
    node_id = get_chord_id(node_info["ip"], node_info["port"])
    node_info["chord_id"] = node_id
    
    initialize_finger_table()
    
    # Set ourselves as our own successor initially
    successor = {
        "ip": node_info["ip"],
        "port": node_info["port"],
        "chord_id": node_id
    }
    
    # Start periodic stabilization
    threading.Thread(target=run_stabilize, daemon=True).start()
    
    print(f"[CHORD] Node initialized with ID: {node_id}")
    print(f"[CHORD] Node position in ring: {(node_id * 100) / CHORD_SIZE:.6f}%")

def initialize_finger_table():
    """Initialize the finger table with empty entries"""
    global finger_table
    
    finger_table = []
    node_id = node_info["chord_id"]
    
    for i in range(CHORD_BITS):
        # Start of finger i is (n + 2^i) mod 2^m
        start = (node_id + (2 ** i)) % CHORD_SIZE
        finger_table.append({
            "start": start, 
            "node": None 
        })
    
    # Schedule immediate finger table fixing
    threading.Thread(target=fix_all_fingers, daemon=True).start()

def fix_all_fingers():
    """Fix all fingers at once when joining the network"""
    time.sleep(2)  
    
  
    for i in range(min(20, CHORD_BITS)):
        try:
            
            finger_id = finger_table[i]["start"]
            successor_node = find_successor(finger_id)
            
            
            if successor_node and "chord_id" in successor_node:
               
                if successor_node["chord_id"] != node_info["chord_id"] or i == 0:
                    finger_table[i]["node"] = successor_node
                    print(f"[CHORD] Initialized finger {i} to point to {successor_node['ip']}:{successor_node['port']} (ID: {successor_node['chord_id'] % 10000})")
            
            time.sleep(0.2) 
        except Exception as e:
            print(f"[CHORD] Error fixing finger {i}: {e}")

def find_successor(id):
    """Find the successor node for a given ID"""
   
    if successor is None or successor["chord_id"] == node_info["chord_id"]:
        return node_info
    
    
    if is_between(node_info["chord_id"], id, successor["chord_id"]):
        return successor
    
    
    n_prime = closest_preceding_node(id)
    
    
    if n_prime["chord_id"] == node_info["chord_id"]:
        return successor
    
    
    try:
        url = f"https://{n_prime['ip']}:{n_prime['port']}/chord/find_successor"
        response = requests.get(url, params={"id": id}, timeout=3, verify=False)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"[CHORD] Forward query failed: {e}")
        
        return successor
    
    return successor

def closest_preceding_node(id):
    """Find the closest preceding node for a given ID"""
    node_id = node_info["chord_id"]
    
    
    for i in range(CHORD_BITS - 1, -1, -1):
        finger_node = finger_table[i]["node"]
        if finger_node and "chord_id" in finger_node and is_between(node_id, finger_node["chord_id"], id):
            return finger_node
    
    return node_info

def is_between(start, id, end):
    """Check if id is in the range (start, end] on the Chord ring"""
    
    if start < end:
        return start < id <= end
    else:  
        return start < id or id <= end

def join_chord(bootstrap_node):
    """Join an existing Chord ring through a bootstrap node"""
    global successor, predecessor
    
    node_id = node_info["chord_id"]
    print(f"[CHORD] Joining ring with ID: {node_id} (mod 10000: {node_id % 10000})")
    
    try:
        
        url = f"https://{bootstrap_node}/chord/find_successor"
        response = requests.get(url, params={"id": node_id}, timeout=5, verify=False)
        
        if response.status_code == 200:
            successor_data = response.json()
            
            
            if "chord_id" not in successor_data:
                successor_data["chord_id"] = get_chord_id(successor_data["ip"], successor_data["port"])
                
            
            if successor_data["chord_id"] == node_id:
                
                try:
                    url = f"https://{bootstrap_node}/chord/successor"
                    resp = requests.get(url, timeout=5, verify=False)
                    if resp.status_code == 200 and resp.json():
                        successor_data = resp.json()
                except:
                    
                    for peer_id, peer in known_peers.items():
                        if peer_id != f"{node_info['ip']}:{node_info['port']}" and peer_id != f"{successor_data['ip']}:{successor_data['port']}":
                            if "chord_id" not in peer:
                                peer["chord_id"] = get_chord_id(peer["ip"], peer["port"])
                            successor_data = peer
                            break
            
            successor = successor_data
            print(f"[CHORD] Joined ring with successor: {successor['ip']}:{successor['port']} (ID: {successor['chord_id'] % 10000})")
            
            
            notify_successor()
            
            
            if len(finger_table) > 0:
                finger_table[0]["node"] = successor
            
            
            threading.Thread(target=fix_all_fingers, daemon=True).start()
            
            return True
    except Exception as e:
        print(f"[CHORD] Failed to join ring: {e}")
    
    return False

def notify_successor():
    """Notify our successor that we might be its predecessor"""
    if successor and successor["chord_id"] != node_info["chord_id"]:
        try:
            url = f"https://{successor['ip']}:{successor['port']}/chord/notify"
            payload = {
                "ip": node_info["ip"],
                "port": node_info["port"],
                "chord_id": node_info["chord_id"]
            }
            requests.post(url, json=payload, timeout=3, verify=False)
        except Exception as e:
            print(f"[CHORD] Failed to notify successor: {e}")

def run_stabilize():
    """Periodically run the stabilize process"""
    while True:
        try:
            stabilize()
            fix_fingers()
            advertise_resource_offer_to_peers()
            time.sleep(5) 
        except Exception as e:
            print(f"[CHORD] Stabilization error: {e}")
            time.sleep(1)

def stabilize():
    """Verify node's immediate successor and update if needed"""
    global successor
    
    if not successor:
        
        for peer_id, peer in known_peers.items():
            if peer_id != f"{node_info['ip']}:{node_info['port']}":
                if "chord_id" not in peer:
                    peer["chord_id"] = get_chord_id(peer["ip"], peer["port"])
                successor = peer
                print(f"[CHORD] Found successor from peer table: {successor['ip']}:{successor['port']}")
                break
        return
    
    if successor["chord_id"] == node_info["chord_id"]:
        
        for peer_id, peer in known_peers.items():
            if peer_id != f"{node_info['ip']}:{node_info['port']}":
                if "chord_id" not in peer:
                    peer["chord_id"] = get_chord_id(peer["ip"], peer["port"])
                
                
                if is_between(node_info["chord_id"], peer["chord_id"], successor["chord_id"]) or successor["chord_id"] == node_info["chord_id"]:
                    successor = peer
                    print(f"[CHORD] Found better successor: {successor['ip']}:{successor['port']}")
                    
                    
                    if len(finger_table) > 0:
                        finger_table[0]["node"] = successor
        return
    
    try:
       
        url = f"https://{successor['ip']}:{successor['port']}/chord/predecessor"
        response = requests.get(url, timeout=3, verify=False)
        
        if response.status_code == 200 and response.json():
            x = response.json()
            
            
            if "chord_id" not in x:
                x["chord_id"] = get_chord_id(x["ip"], x["port"])
            
            
            if is_between(node_info["chord_id"], x["chord_id"], successor["chord_id"]):
                successor = x
                print(f"[CHORD] Updated successor to {successor['ip']}:{successor['port']}")
                
                
                if len(finger_table) > 0:
                    finger_table[0]["node"] = successor
        
        
        notify_successor()
    except Exception as e:
        print(f"[CHORD] Error checking successor's predecessor: {e}")
        
        backup_successor = None
        for peer_id, peer in known_peers.items():
            if peer_id != f"{node_info['ip']}:{node_info['port']}":
                if "chord_id" not in peer:
                    peer["chord_id"] = get_chord_id(peer["ip"], peer["port"])
                
                if not backup_successor or is_between(node_info["chord_id"], peer["chord_id"], backup_successor["chord_id"]):
                    backup_successor = peer
        
        if backup_successor:
            successor = backup_successor
            print(f"[CHORD] Successor failed, updating to: {successor['ip']}:{successor['port']}")
            
            
            if len(finger_table) > 0:
                finger_table[0]["node"] = successor

def fix_fingers():
    """Periodically fix a random finger table entry"""
    
    i = int(random.random() * random.random() * CHORD_BITS)
    
    try:
        
        finger_id = finger_table[i]["start"]
        
       
        successor_node = find_successor(finger_id)
        
        
        if successor_node and "chord_id" in successor_node:
            current = finger_table[i]["node"]
            
            if not current or current["chord_id"] != successor_node["chord_id"]:
                finger_table[i]["node"] = successor_node
                print(f"[CHORD] Updated finger {i} (start={finger_id % 10000}) to point to {successor_node['ip']}:{successor_node['port']} (ID: {successor_node['chord_id'] % 10000})")
    except Exception as e:
        print(f"[CHORD] Error fixing finger {i}: {e}")

def advertise_resource_offer_to_peers():
    """Send our current resource offer to all known peers (could be called during stabilization/gossip)."""
    import requests
    from peers import known_peers, node_info
    offer = get_signed_resource_offer()
    for peer_id, peer in known_peers.items():
        if peer_id != f"{node_info['ip']}:{node_info['port']}":
            try:
                url = f"https://{peer['ip']}:{peer['port']}/resource_offer"
                # Optionally POST or PUT if you want to push, or just GET if you want to fetch
                # Here, just an example of fetching peer's offer (for demonstration)
                requests.get(url, timeout=3, verify=False)  # Set verify=True in production
            except Exception as e:
                print(f"[RESOURCE OFFER] Failed to reach {peer['ip']}:{peer['port']}: {e}")

def print_finger_table():
    """Display the current finger table"""
    print("\n========== CHORD FINGER TABLE ==========")
    print("| Index | Start ID (mod 10000) | Successor IP:Port  | Succ ID (mod 10000) |")
    print("--------------------------------------------------------------------------")
    
    samples = [0, 1, 2, 3, 4, 5, 10, 20, 40, 80, 159]
    
    for i in samples:
        if i < len(finger_table):
            finger = finger_table[i]
            node = finger["node"]
            start_id_short = finger["start"] % 10000
            
            if node:
                node_id_short = node["chord_id"] % 10000
                print(f"| {i:<5} | {start_id_short:<18} | {node['ip']}:{node['port']:<15} | {node_id_short:<18} |")
            else:
                print(f"| {i:<5} | {start_id_short:<18} | None              | None               |")
    
    if successor:
        succ_id = successor["chord_id"] % 10000
        print(f"\nCurrent successor: {successor['ip']}:{successor['port']} (ID: {succ_id})")
    else:
        print("\nNo successor set")
        
    if predecessor:
        pred_id = predecessor["chord_id"] % 10000
        print(f"Current predecessor: {predecessor['ip']}:{predecessor['port']} (ID: {pred_id})")
    else:
        print("No predecessor set")
    
    print("--------------------------------------------------------------------------\n")

def register_routes(app):
    """Register Chord protocol API endpoints"""
    from flask import request, jsonify
    
    @app.route('/chord/find_successor', methods=['GET'])
    def route_find_successor():
        id = int(request.args.get('id'))
        result = find_successor(id)
        return jsonify(result)
    
    @app.route('/chord/predecessor', methods=['GET'])
    def route_predecessor():
        return jsonify(predecessor)
    
    @app.route('/chord/notify', methods=['POST'])
    def route_notify():
        global predecessor
        node = request.json
        
        if "chord_id" not in node:
            node["chord_id"] = get_chord_id(node["ip"], node["port"])
        
        if not predecessor or is_between(predecessor["chord_id"], node["chord_id"], node_info["chord_id"]):
            predecessor = node
            print(f"[CHORD] Updated predecessor to {node['ip']}:{node['port']} (ID: {node['chord_id'] % 10000})")
        
        return jsonify({"status": "ok"})
    
    @app.route('/chord/successor', methods=['GET'])
    def route_successor():
        """Return this node's successor"""
        return jsonify(successor)
    
    @app.route('/chord/finger_table', methods=['GET'])
    def route_get_finger_table():
        """Return this node's finger table"""
        sample_fingers = [finger_table[i] for i in range(min(20, len(finger_table)))]
        return jsonify({
            "node_id": node_info["chord_id"],
            "fingers": sample_fingers
        })

    @app.route('/chord/debug', methods=['GET'])
    def route_debug():
        """Return debug information about this node and its view of the ring"""
        peers_with_ids = {}
        for peer_id, peer in known_peers.items():
            peer_copy = dict(peer)
            if "chord_id" not in peer_copy:
                peer_copy["chord_id"] = get_chord_id(peer_copy["ip"], peer_copy["port"])
            peer_copy["chord_id_mod_10000"] = peer_copy["chord_id"] % 10000
            peers_with_ids[peer_id] = peer_copy
            
        return jsonify({
            "node_info": {
                "ip": node_info["ip"],
                "port": node_info["port"],
                "chord_id": node_info["chord_id"],
                "chord_id_mod_10000": node_info["chord_id"] % 10000
            },
            "successor": successor,
            "predecessor": predecessor,
            "known_peers": peers_with_ids,
            "finger_table_sample": [finger_table[i] for i in [0, 1, 2, 3, 4] if i < len(finger_table)]
        })

    @app.route('/chord/fix_fingers', methods=['POST'])
    def route_fix_fingers():
        """Trigger immediate finger table fixing"""
        threading.Thread(target=fix_all_fingers, daemon=True).start()
        return jsonify({"status": "Finger table fix initiated"})

    @app.route('/chord/analyze', methods=['GET'])
    def route_analyze():
        """Return analysis of the finger table health"""
        analysis = {
            "self_references": 0,
            "null_entries": 0,
            "total_entries": len(finger_table),
            "unique_successors": set(),
            "coverage_percent": 0
        }
        
        for finger in finger_table:
            if finger["node"] is None:
                analysis["null_entries"] += 1
            elif finger["node"]["chord_id"] == node_info["chord_id"]:
                analysis["self_references"] += 1
            else:
                finger_id = f"{finger['node']['ip']}:{finger['node']['port']}"
                analysis["unique_successors"].add(finger_id)
        
        analysis["unique_successors"] = list(analysis["unique_successors"])
        analysis["coverage_percent"] = (len(analysis["unique_successors"]) / max(1, (len(finger_table) - analysis["null_entries"]))) * 100
        
        return jsonify(analysis) 

    @app.route('/chord/store_metadata', methods=['POST'])
    def store_metadata():
        data = request.json
        key = int(data['key'])
        offer = data['value']
        signature = data.get('signature')
        node_address = offer['node_address']
        from peers import known_peers
        peer = known_peers.get(node_address)
        if not peer or 'public_key' not in peer:
            return jsonify({'error': 'Unknown peer or missing public key'}), 400
        from Crypto.PublicKey import ECC
        public_key = ECC.import_key(peer['public_key'])
        # FIX: Pass the full data dict (including 'signature') to verify_dht_update
        if not signature or not verify_dht_update(data, public_key):
            return jsonify({'error': 'Invalid DHT update signature'}), 400
        if not verify_resource_offer(offer, public_key):
            return jsonify({'error': 'Invalid offer signature'}), 400
        if key not in self_dht_data_store:
            self_dht_data_store[key] = []
        self_dht_data_store[key] = [o for o in self_dht_data_store[key] if o['node_address'] != node_address]
        self_dht_data_store[key].append(offer)
        return jsonify({'status': 'Offer stored'})

    @app.route('/chord/lookup_metadata', methods=['GET'])
    def lookup_metadata():
        key = int(request.args.get('key'))
        if not is_successor_for_key(key):
            return jsonify({'error': 'Not responsible for this key'}), 400
        return jsonify({'offers': self_dht_data_store.get(key, [])})

def is_successor_for_key(key_chord_id):
    global node_info, predecessor
    my_id = node_info["chord_id"]
    pred_id = predecessor["chord_id"] if predecessor else None
    if pred_id is None or pred_id == my_id:
        return True
    if pred_id < my_id:
        return pred_id < key_chord_id <= my_id
    else:
        return key_chord_id > pred_id or key_chord_id <= my_id

def publish_offer(offer):
    from peers import get_peer_url
    key = offer['node_id']
    successor_node = find_successor(key)
    import requests
    dht_update = {'key': key, 'value': offer}
    dht_update['signature'] = sign_dht_update(dht_update)
    url = get_peer_url(successor_node['ip'], successor_node['port']) + "/chord/store_metadata"
    resp = requests.post(url, json=dht_update, timeout=5, verify=False)
    return resp.json()

def discover_offers_by_chord_id(chord_id):
    from peers import get_peer_url
    responsible_node = find_successor(chord_id)
    import requests
    url = get_peer_url(responsible_node['ip'], responsible_node['port']) + f"/chord/lookup_metadata?key={chord_id}"
    try:
        resp = requests.get(url, timeout=5, verify=False)
        if resp.status_code == 200:
            return resp.json().get('offers', [])
        else:
            return []
    except Exception as e:
        print(f"[DHT DISCOVERY] Error discovering offers for {chord_id}: {e}")
        return []

def sign_dht_update(update_dict):
    from Crypto.Hash import SHA256
    from Crypto.Signature import DSS
    import json
    from peers import ensure_key_pair, key_pair
    ensure_key_pair()  # Ensure key_pair is valid before signing
    if key_pair is None:
        raise RuntimeError("[DHT SIGN] key_pair is None! Cannot sign DHT update.")
    update = dict(update_dict)
    update.pop('signature', None)
    serialized = json.dumps(update, sort_keys=True).encode()
    h = SHA256.new(serialized)
    signer = DSS.new(key_pair, 'fips-186-3')
    signature = signer.sign(h)
    return signature.hex()

def verify_dht_update(update_dict, public_key):
    from Crypto.Hash import SHA256
    from Crypto.Signature import DSS
    import json
    update = dict(update_dict)
    sig = bytes.fromhex(update.pop('signature'))
    serialized = json.dumps(update, sort_keys=True).encode()
    h = SHA256.new(serialized)
    verifier = DSS.new(public_key, 'fips-186-3')
    try:
        verifier.verify(h, sig)
        return True
    except Exception:
        return False