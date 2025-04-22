from flask import request, jsonify
import requests
from peers import known_peers, node_info
from accounting import append_log_entry, LOG_FILE
import os
import json

def register_routes(app):
    @app.route('/handle_request', methods=['POST'])
    def handle_request():
        data = request.json
        processing_load = data.get('processing_load', 10)
        task_type = data.get('task_type', None)

        print("------------ ESP REQUEST RECEIVED ------------")
        print(f"[LOAD] Incoming ESP load packet: {processing_load} units")
        if task_type:
            print(f"[TASK] Task type requested: {task_type}")

        # Generate a single task_id for both RECEIVED and COMPLETED logs
        task_id = f"esp_{os.urandom(4).hex()}"

        # Log receipt of ESP request
        append_log_entry(
            event_type="ESP_REQUEST_RECEIVED",
            task_id=task_id,
            node_id=f"{node_info.get('ip','unknown')}:{node_info.get('port','unknown')}",
            details={
                'processing_load': processing_load,
                'task_type': task_type
            }
        )

        result = None
        if task_type == 'prime':
            n = max(2, processing_load)
            is_prime = True
            for i in range(2, int(n**0.5) + 1):
                if n % i == 0:
                    is_prime = False
                    break
            result = is_prime
        elif task_type == 'matrix':
            size = min(100, max(2, int(processing_load/10)))
            a = [[i+j for j in range(size)] for i in range(size)]
            b = [[i*j for j in range(size)] for i in range(size)]
            c = [[sum(a[i][k]*b[k][j] for k in range(size)) for j in range(size)] for i in range(size)]
            result = c[0][0]
        else:
            # Fallback: busy-wait
            import time
            t0 = time.time()
            while time.time() - t0 < processing_load/1000.0:
                pass
            result = True

        # Earnings calculation
        earned = processing_load * 0.01

        # Check if we need to forward (simulate capacity exceeded)
        best_peer = None
        if node_info.get('promised_capacity', 0) and node_info.get('current_load', 0) + processing_load > node_info.get('promised_capacity', 0):
            for peer in known_peers.values():
                if peer['ip'] == node_info['ip'] and peer['port'] == node_info['port']:
                    continue
                if peer.get('current_load', 0) + processing_load <= peer.get('promised_capacity', 0):
                    best_peer = peer
                    break

            if best_peer:
                try:
                    print(f"[FORWARD] Redirecting load to {best_peer['ip']}:{best_peer['port']}")
                    append_log_entry(
                        event_type="ESP_REQUEST_FORWARDED",
                        task_id=task_id,
                        node_id=f"{node_info.get('ip','unknown')}:{node_info.get('port','unknown')}",
                        details={'forwarded_to': f"{best_peer['ip']}:{best_peer['port']}", 'processing_load': processing_load, 'task_type': task_type}
                    )
                    requests.post(f"http://{best_peer['ip']}:{best_peer['port']}/handle_request", json={"processing_load": processing_load, "task_type": task_type}, timeout=5)
                    return jsonify({"redirected": f"{best_peer['ip']}:{best_peer['port']}"})
                except Exception as e:
                    print("[ERROR] Failed to forward. Accepting locally.")
        # Log completion
        append_log_entry(
            event_type="ESP_REQUEST_COMPLETED",
            task_id=task_id,
            node_id=f"{node_info.get('ip','unknown')}:{node_info.get('port','unknown')}",
            details={
                'processing_load': processing_load,
                'task_type': task_type,
                'result': result,
                'earned': earned
            }
        )
        return jsonify({'status': 'done', 'result': result, 'earned': earned})

    @app.route('/logs', methods=['GET'])
    def get_logs():
        """Return all log entries as a JSON array."""
        logs = []
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r') as f:
                for line in f:
                    try:
                        logs.append(json.loads(line))
                    except Exception:
                        continue  # skip malformed lines
        return jsonify(logs)
