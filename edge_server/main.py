from flask import Flask
import argparse
from peers import initialize_node, register_routes as register_peer_routes
from esp_handler import register_routes as register_esp_routes
from auth import register_routes as register_auth_routes

app = Flask(__name__)

parser = argparse.ArgumentParser(description="Edge Server Node")
parser.add_argument("--ip", type=str, required=True)
parser.add_argument("--port", type=int, required=True)
parser.add_argument("--promised_capacity", type=int, required=True)
parser.add_argument("--bootstrap", type=str, required=False)
args = parser.parse_args()

initialize_node(args)
register_peer_routes(app)
register_auth_routes(app)
register_esp_routes(app)

@app.route('/status', methods=['GET'])
def status():
    from peers import node_info
    return {
        "ip": node_info["ip"],
        "port": node_info["port"],
        "promised_capacity": node_info["promised_capacity"],
        "current_load": node_info["current_load"],
        "esp_active": node_info.get("esp_active", False)
    }

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=args.port)
