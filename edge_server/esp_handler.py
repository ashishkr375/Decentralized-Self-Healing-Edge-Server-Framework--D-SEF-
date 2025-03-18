from flask import request, jsonify
import requests
from peers import known_peers, node_info

def register_routes(app):
    @app.route('/handle_request', methods=['POST'])
    def handle_request():
        data = request.json
        processing_load = data.get('processing_load', 10)

        print("------------ ESP REQUEST RECEIVED ------------")
        print(f"[LOAD] Incoming ESP load packet: {processing_load} units")

        node_info["current_load"] += processing_load
        print(f"[STATUS] Current Load: {node_info['current_load']} / {node_info['promised_capacity']}")

        if node_info["current_load"] > node_info["promised_capacity"]:
            print("[WARNING] Capacity exceeded. Trying to forward...")
            best_peer = None
            for peer_id, peer in known_peers.items():
                if peer["current_load"] < peer["promised_capacity"]:
                    best_peer = peer
                    break

            if best_peer:
                try:
                    print(f"[FORWARD] Redirecting load to {best_peer['ip']}:{best_peer['port']}")
                    requests.post(f"http://{best_peer['ip']}:{best_peer['port']}/handle_request", json={"processing_load": processing_load})
                    return jsonify({"redirected": f"{best_peer['ip']}:{best_peer['port']}"})
                except:
                    print("[ERROR] Failed to forward. Accepting locally.")
        return jsonify({"status": "Accepted locally"})
