from flask import Flask, jsonify
import argparse
import threading
import time
from peers import initialize_node, register_routes as register_peer_routes
from esp_handler import register_routes as register_esp_routes
from auth import register_routes as register_auth_routes
from chord import initialize_chord, register_routes as register_chord_routes, join_chord, print_finger_table

app = Flask(__name__)

parser = argparse.ArgumentParser(description="Edge Server Node")
parser.add_argument("--ip", type=str, required=True)
parser.add_argument("--port", type=int, required=True)
parser.add_argument("--promised_capacity", type=int, required=True)
parser.add_argument("--bootstrap", type=str, required=False)
args = parser.parse_args()

# Initialize peer table
initialize_node(args)

# Register all routes
register_peer_routes(app)
register_auth_routes(app)
register_esp_routes(app)
register_chord_routes(app)

# Initialize Chord DHT
initialize_chord()

# Join Chord ring through bootstrap if provided
if args.bootstrap:
    # Start Chord join in a separate thread to not block server startup
    def delayed_join():
        time.sleep(2)  # Wait for server to start and for peers to be discovered
        
        # First update peer table from bootstrap
        bootstrap_url = args.bootstrap
        from peers import fetch_peer_table
        fetch_peer_table(bootstrap_url)
        
        # Then join Chord ring
        print("[CHORD] Attempting to join ring via bootstrap node...")
        success = join_chord(bootstrap_url)
        
        if success:
            print("[CHORD] Successfully joined the Chord ring")
        else:
            print("[CHORD] Failed to join Chord ring, operating as standalone node")
        
        print_finger_table()
    
    threading.Thread(target=delayed_join).start()

@app.route('/status', methods=['GET'])
def status():
    from peers import node_info
    from chord import get_chord_id
    
    # Make sure we have a chord_id
    if "chord_id" not in node_info:
        node_info["chord_id"] = get_chord_id(node_info["ip"], node_info["port"])
    
    # Format Chord ID to be more readable
    chord_id_display = node_info["chord_id"] % 10000
    
    return {
        "ip": node_info["ip"],
        "port": node_info["port"],
        "promised_capacity": node_info["promised_capacity"],
        "current_load": node_info["current_load"],
        "esp_active": node_info.get("esp_active", False),
        "chord_id": node_info["chord_id"],
        "chord_id_short": chord_id_display
    }

# Display tables only occasionally to avoid cluttering the console
def print_tables():
    # Print once at startup
    time.sleep(5)
    from peers import print_peer_table
    print_peer_table()
    
    # Then print only every 5 minutes
    while True:
        time.sleep(300)  # Every 5 minutes instead of 30 seconds
        from peers import print_peer_table
        print_peer_table()
        print_finger_table()

threading.Thread(target=print_tables, daemon=True).start()

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=args.port)
