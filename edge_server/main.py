from flask import Flask, jsonify
import argparse
import threading
import time
from peers import initialize_node, register_routes as register_peer_routes, get_signed_resource_offer
from esp_handler import register_routes as register_esp_routes
from auth import register_routes as register_auth_routes
from chord import initialize_chord, register_routes as register_chord_routes, join_chord, print_finger_table, publish_offer
from resource_manager import start_resource_monitor, get_latest_stats
from scheduler import scheduler_bp
from executor import executor_bp
import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import psutil

app = Flask(__name__)

def get_actual_capacity():
    # Use available CPU and RAM to estimate capacity
    cpu_count = psutil.cpu_count(logical=False) or 1
    cpu_freq = psutil.cpu_freq()
    cpu_ghz = cpu_freq.max/1000.0 if cpu_freq else 2.0
    ram_gb = psutil.virtual_memory().total / (1024**3)
    # Example: weighted sum (customize as needed)
    return int((cpu_count * cpu_ghz * 1000) + (ram_gb * 100))

parser = argparse.ArgumentParser(description="Edge Server Node")
parser.add_argument("--ip", type=str, required=True)
parser.add_argument("--port", type=int, required=True)
parser.add_argument("--promised_capacity", type=int, required=False, help="(Deprecated) Simulated capacity. Actual system resources will be used.")
parser.add_argument("--bootstrap", type=str, required=False)
parser.add_argument("--debug", action='store_true')
args = parser.parse_args()

node_info = {
    "ip": args.ip,
    "port": args.port,
    "promised_capacity": get_actual_capacity(),
    "current_load": 0
}

initialize_node(args)

register_peer_routes(app)
register_auth_routes(app)
register_esp_routes(app)
register_chord_routes(app)
app.register_blueprint(scheduler_bp)
app.register_blueprint(executor_bp)

initialize_chord()

# --- Resource Monitoring Integration ---
start_resource_monitor()

def update_node_resource_stats():
    def updater():
        from peers import node_info
        import time
        while True:
            node_info['resource_stats'] = get_latest_stats()
            time.sleep(30)  # Update every 30 seconds
    threading.Thread(target=updater, daemon=True).start()

update_node_resource_stats()

def periodic_offer_advertisement():
    while True:
        try:
            offer = get_signed_resource_offer()
            resp = publish_offer(offer)
            print(f"[ADVERTISEMENT] Published offer to DHT: {resp}")
        except Exception as e:
            print(f"[ADVERTISEMENT] Error publishing offer: {e}")
        time.sleep(60)  # Advertise every 60 seconds

threading.Thread(target=periodic_offer_advertisement, daemon=True).start()

if args.bootstrap:
    def delayed_join():
        time.sleep(2)  
        
        bootstrap_url = args.bootstrap
        from peers import fetch_peer_table
        fetch_peer_table(bootstrap_url)
        
        print("[CHORD] Attempting to join ring via bootstrap node...")
        success = join_chord(bootstrap_url)
        
        if success:
            print("[CHORD] Successfully joined the Chord ring")
        else:
            print("[CHORD] Failed to join Chord ring, operating as standalone node")
        
        print_finger_table()
    
    threading.Thread(target=delayed_join).start()

# --- Flask-Limiter Rate Limiting ---
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["50 per minute"]  # Adjust as needed
)

@app.route('/status', methods=['GET'])
@limiter.limit("50 per minute")
def status():
    from peers import node_info
    from chord import get_chord_id
    
    if "chord_id" not in node_info:
        node_info["chord_id"] = get_chord_id(node_info["ip"], node_info["port"])
    
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

def print_tables():
    time.sleep(5)
    from peers import print_peer_table
    print_peer_table()
    
    while True:
        time.sleep(300)
        from peers import print_peer_table
        print_peer_table()
        print_finger_table()

threading.Thread(target=print_tables, daemon=True).start()

if __name__ == "__main__":
    cert_path = os.path.join(os.path.dirname(__file__), '..', 'cert.pem')
    key_path = os.path.join(os.path.dirname(__file__), '..', 'key.pem')
    ssl_context = (cert_path, key_path) if os.path.exists(cert_path) and os.path.exists(key_path) else None
    app.run(host="0.0.0.0", port=args.port, debug=args.debug, ssl_context=ssl_context)
