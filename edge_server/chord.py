import hashlib
import threading
import time
import random
from peers import node_info, known_peers
import requests

# Chord configuration
CHORD_BITS = 160  # SHA1 hash produces 160 bits
CHORD_SIZE = 2 ** CHORD_BITS
finger_table = []  # List of (start, node) entries
successor = None
predecessor = None

# Calculate consistent hash for node ID
def get_chord_id(ip, port):
    """Generate a consistent node ID in the Chord ring using SHA1"""
    key = f"{ip}:{port}"
    return int(hashlib.sha1(key.encode()).hexdigest(), 16)

# Initialize node's position in Chord ring
def initialize_chord():
    global successor, predecessor
    
    # Set node's Chord ID
    node_id = get_chord_id(node_info["ip"], node_info["port"])
    node_info["chord_id"] = node_id
    
    # Initialize finger table
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
        
        # Important: Initially set each finger to point to our successor, not ourselves
        # This ensures we don't get stuck with self-references
        finger_node = successor if successor and successor["chord_id"] != node_info["chord_id"] else None
        
        finger_table.append({
            "start": start, 
            "node": finger_node
        })
    
    # Schedule immediate finger table fixing
    threading.Thread(target=fix_all_fingers, daemon=True).start()

def fix_all_fingers():
    """Fix all fingers at once when joining the network"""
    time.sleep(2)  # Give the system a moment to stabilize
    
    for i in range(min(20, CHORD_BITS)):  # Fix at least the first 20 fingers
        try:
            fix_finger(i)
            time.sleep(0.2)  # Small delay between fixes
        except Exception as e:
            print(f"[CHORD] Error fixing finger {i}: {e}")

def fix_finger(i):
    """Fix a specific finger table entry"""
    finger_id = finger_table[i]["start"]
    
    # Don't set fingers to point to ourselves - find a different node
    successor_node = find_successor(finger_id)
    
    if successor_node and successor_node.get("chord_id") != node_info["chord_id"]:
        finger_table[i]["node"] = successor_node
        print(f"[CHORD] Updated finger {i} to point to {successor_node['ip']}:{successor_node['port']} (ID: {successor_node['chord_id'] % 10000})")
        return True
    
    return False

def find_successor(id):
    """Find the successor node for a given ID"""
    # If we are alone in the network
    if successor is None or successor["chord_id"] == node_info["chord_id"]:
        return node_info
    
    # If id is between us and our successor
    if is_between(node_info["chord_id"], id, successor["chord_id"]):
        return successor
    
    # Otherwise, find the closest preceding node and ask it
    n_prime = closest_preceding_node(id)
    
    # If that's us, return our successor
    if n_prime["chord_id"] == node_info["chord_id"]:
        return successor
    
    # Otherwise, forward the query
    try:
        url = f"http://{n_prime['ip']}:{n_prime['port']}/chord/find_successor"
        response = requests.get(url, params={"id": id}, timeout=3)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"[CHORD] Forward query failed: {e}")
        # If we can't reach that node, return our best guess
        return successor
    
    return successor

def closest_preceding_node(id):
    """Find the closest preceding node for a given ID"""
    node_id = node_info["chord_id"]
    
    # Check finger table from largest to smallest distance
    for i in range(CHORD_BITS - 1, -1, -1):
        finger_node = finger_table[i]["node"]
        if finger_node and is_between(node_id, finger_node["chord_id"], id):
            return finger_node
    
    return node_info

def is_between(start, id, end):
    """Check if id is in the range (start, end] on the Chord ring"""
    # Handle wrapping around the ring
    if start < end:
        return start < id <= end
    else:  # end wrapped around 0
        return start < id or id <= end

def join_chord(bootstrap_node):
    """Join an existing Chord ring through a bootstrap node"""
    global successor, predecessor
    
    node_id = node_info["chord_id"]
    print(f"[CHORD] Joining ring with ID: {node_id} (mod 10000: {node_id % 10000})")
    
    try:
        # Ask bootstrap node for our successor
        url = f"{bootstrap_node}/chord/find_successor"
        response = requests.get(url, params={"id": node_id}, timeout=5)
        
        if response.status_code == 200:
            successor_data = response.json()
            
            # Ensure the successor has a chord_id
            if "chord_id" not in successor_data:
                successor_data["chord_id"] = get_chord_id(successor_data["ip"], successor_data["port"])
                
            # Don't set ourselves as our own successor
            if successor_data["chord_id"] == node_id:
                # Try getting the bootstrap node's successor instead
                try:
                    url = f"{bootstrap_node}/chord/successor"
                    resp = requests.get(url, timeout=5)
                    if resp.status_code == 200 and resp.json():
                        successor_data = resp.json()
                except:
                    pass
            
            successor = successor_data
            print(f"[CHORD] Joined ring with successor: {successor['ip']}:{successor['port']} (ID: {successor['chord_id'] % 10000})")
            
            # Notify our successor that we might be its predecessor
            notify_successor()
            
            # After setting successor, get the finger table of our successor
            try:
                url = f"http://{successor['ip']}:{successor['port']}/chord/finger_table"
                finger_resp = requests.get(url, timeout=5)
                if finger_resp.status_code == 200:
                    print("[CHORD] Retrieved finger table from successor to bootstrap our routing")
            except:
                print("[CHORD] Could not retrieve finger table from successor")
            
            # Schedule immediate finger table fixing
            threading.Thread(target=fix_all_fingers, daemon=True).start()
            
            return True
    except Exception as e:
        print(f"[CHORD] Failed to join ring: {e}")
    
    return False

def notify_successor():
    """Notify our successor that we might be its predecessor"""
    if successor and successor["chord_id"] != node_info["chord_id"]:
        try:
            url = f"http://{successor['ip']}:{successor['port']}/chord/notify"
            payload = {
                "ip": node_info["ip"],
                "port": node_info["port"],
                "chord_id": node_info["chord_id"]
            }
            requests.post(url, json=payload, timeout=3)
        except Exception as e:
            print(f"[CHORD] Failed to notify successor: {e}")

def run_stabilize():
    """Periodically run the stabilize process"""
    while True:
        try:
            stabilize()
            fix_fingers()
            time.sleep(5)  # Run every 5 seconds
        except Exception as e:
            print(f"[CHORD] Stabilization error: {e}")
            time.sleep(1)

def stabilize():
    """Verify node's immediate successor and update if needed"""
    global successor
    
    if not successor:
        # If we don't have a successor, try to find one from our peer table
        for peer_id, peer in known_peers.items():
            if peer_id != f"{node_info['ip']}:{node_info['port']}":
                if "chord_id" not in peer:
                    peer["chord_id"] = get_chord_id(peer["ip"], peer["port"])
                successor = peer
                print(f"[CHORD] Found successor from peer table: {successor['ip']}:{successor['port']}")
                break
        return
    
    if successor["chord_id"] == node_info["chord_id"]:
        # We're our own successor (ring of one node)
        # Check if we can find another node in the peer table
        for peer_id, peer in known_peers.items():
            if peer_id != f"{node_info['ip']}:{node_info['port']}":
                if "chord_id" not in peer:
                    peer["chord_id"] = get_chord_id(peer["ip"], peer["port"])
                
                # Only update successor if the peer's ID is the next one after ours
                if is_between(node_info["chord_id"], peer["chord_id"], successor["chord_id"]) or successor["chord_id"] == node_info["chord_id"]:
                    successor = peer
                    print(f"[CHORD] Found better successor: {successor['ip']}:{successor['port']}")
        return
    
    try:
        # Get our successor's predecessor
        url = f"http://{successor['ip']}:{successor['port']}/chord/predecessor"
        response = requests.get(url, timeout=3)
        
        if response.status_code == 200 and response.json():
            x = response.json()
            
            # Ensure x has a chord_id
            if "chord_id" not in x:
                x["chord_id"] = get_chord_id(x["ip"], x["port"])
            
            # If their predecessor is between us and our successor, it becomes our new successor
            if is_between(node_info["chord_id"], x["chord_id"], successor["chord_id"]):
                successor = x
                print(f"[CHORD] Updated successor to {successor['ip']}:{successor['port']}")
        
        # Notify our successor that we might be its predecessor
        notify_successor()
    except Exception as e:
        print(f"[CHORD] Error checking successor's predecessor: {e}")
        # If we can't reach our successor, check if we have a suitable node in our peer table
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

def fix_fingers():
    """Periodically fix finger table entries"""
    # Choose a random finger to fix
    i = random.randint(0, CHORD_BITS - 1)
    
    try:
        # Only log successful updates
        if fix_finger(i):
            print(f"[CHORD] Fixed finger {i}, now points to {finger_table[i]['node']['ip']}:{finger_table[i]['node']['port']}")
    except Exception as e:
        print(f"[CHORD] Error fixing finger {i}: {e}")

def print_finger_table():
    """Display the current finger table"""
    print("\n========== CHORD FINGER TABLE ==========")
    print("| Index | Start ID (mod 10000) | Successor IP:Port  | Succ ID (mod 10000) |")
    print("--------------------------------------------------------------------------")
    
    # Only print a sample of fingers to avoid cluttering the output
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
        
        # Ensure the node has a chord_id
        if "chord_id" not in node:
            node["chord_id"] = get_chord_id(node["ip"], node["port"])
        
        # Update predecessor if we don't have one or if this node is closer than our current predecessor
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
        # Return just the first 20 entries for efficiency
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