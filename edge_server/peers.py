import hashlib
import threading
import random
import time
import requests
from flask import request, jsonify

FINGER_TABLE_SIZE = 5  # Use 5-bit space for testing (can increase for larger networks)

known_peers = {}  # Stores all nodes in the network
node_info = {}  # Stores this node's details
finger_table = []  # Chord finger table


### 1️⃣ UTILITY FUNCTIONS ###

def hash_node(ip, port):
    """ Generate a unique identifier for a node using SHA-1 hashing """
    node_id = hashlib.sha1(f"{ip}:{port}".encode()).hexdigest()
    return int(node_id, 16) % (2 ** FINGER_TABLE_SIZE)  # Limit to 2^m space


### 2️⃣ INITIALIZATION & JOINING NETWORK ###

def initialize_node(args):
    """ Initialize this node and join the network if bootstrap is provided """
    global node_info, finger_table
    node_info.update({
        "ip": args.ip,
        "port": args.port,
        "id": hash_node(args.ip, args.port),
        "promised_capacity": args.promised_capacity,
        "current_load": 0
    })

    known_peers[node_info['id']] = node_info.copy()
    print(f"Node initialized: {node_info}")

    # Initialize finger table
    finger_table = [None] * FINGER_TABLE_SIZE
    update_finger_table()

    if args.bootstrap:
        join_network(args.bootstrap)
    
    # Start stabilization process
    threading.Thread(target=stabilize, daemon=True).start()


def join_network(bootstrap_url):
    """ Join an existing Chord network using a bootstrap node """
    try:
        response = requests.post(f"{bootstrap_url}/register", json=node_info, timeout=5)
        if response.status_code == 200:
            print(f"[JOIN] Joined network via {bootstrap_url}")
            fetch_peer_table(bootstrap_url)
            update_finger_table()
    except Exception as e:
        print(f"[ERROR] Failed to join network: {e}")


def fetch_peer_table(peer_url):
    """ Fetch the peer table from another node """
    try:
        response = requests.get(f"{peer_url}/peer", timeout=5)
        if response.status_code == 200:
            for peer in response.json().get("peers", []):
                known_peers[peer['id']] = peer
    except:
        pass


### 3️⃣ CHORD LOOKUP FUNCTIONS ###

def update_finger_table():
    """ Populate the finger table with successors at distances of 2^i """
    global finger_table
    for i in range(FINGER_TABLE_SIZE):
        finger_id = (node_info["id"] + (2 ** i)) % (2 ** FINGER_TABLE_SIZE)
        finger_table[i] = find_successor(finger_id)
    print("\nUpdated Finger Table:", finger_table)


def find_successor(key):
    """ Find the successor node responsible for the given key """
    successor = get_successor()
    if node_info["id"] < key <= successor["id"]:
        return successor

    closest = closest_preceding_node(key)
    if closest:
        try:
            response = requests.get(f"http://{closest['ip']}:{closest['port']}/find_successor?key={key}")
            return response.json()
        except:
            pass

    return node_info  # Fallback if no valid lookup


def closest_preceding_node(key):
    """ Find the closest finger preceding the given key """
    for i in range(FINGER_TABLE_SIZE - 1, -1, -1):
        if finger_table[i] and node_info["id"] < finger_table[i]["id"] < key:
            return finger_table[i]
    return None


def get_successor():
    """ Get the immediate successor of this node """
    return finger_table[0] if finger_table[0] else node_info


### 4️⃣ STABILIZATION ###

def stabilize():
    """ Periodically update the finger table to maintain correctness """
    while True:
        try:
            update_finger_table()
        except:
            pass
        time.sleep(10)  # Update every 10 seconds


### 5️⃣ FLASK API ROUTES ###

def register_routes(app):
    @app.route('/peer', methods=['GET'])
    def get_peers():
        """ Return the list of known peers """
        return jsonify({"peers": list(known_peers.values())})

    @app.route('/find_successor', methods=['GET'])
    def api_find_successor():
        """ API endpoint for finding the successor of a given key """
        key = int(request.args.get("key"))
        successor = find_successor(key)
        return jsonify(successor)
