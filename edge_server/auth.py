from flask import request, jsonify
from Crypto.PublicKey import ECC
from Crypto.Signature import DSS
from Crypto.Hash import SHA256
import random
import string
from peers import known_peers, node_info

challenges = {}


def generate_challenge():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=16))


def register_routes(app):
    @app.route('/register', methods=['POST'])
    def register():
        data = request.json
        identifier = f"{data['ip']}:{data['port']}"
        print("\n=========== AUTH PHASE ===========")
        print(f"[AUTH] Registration request from {identifier}")

        peer_key = ECC.import_key(data["public_key"])
        challenge = generate_challenge()
        challenges[identifier] = peer_key, challenge

        print("[AUTH] Public Key received and challenge generated!")
        print(f"[AUTH] Challenge for {identifier}: {challenge}")

        return jsonify({"challenge": challenge})

    @app.route('/authenticate', methods=['POST'])
    def authenticate():
        data = request.json
        identifier = f"{data['ip']}:{data['port']}"
        peer_key, challenge = challenges.get(identifier, (None, None))

        if not peer_key:
            print("[ERROR] No challenge found for peer!")
            return {"error": "Peer not registered"}, 400

        h = SHA256.new(challenge.encode('utf-8'))
        verifier = DSS.new(peer_key, 'fips-186-3')

        try:
            verifier.verify(h, bytes.fromhex(data['signature']))
            known_peers[identifier] = {
                "ip": data['ip'],
                "port": data['port'],
                "promised_capacity": data['promised_capacity'],
                "current_load": 0
            }
            print(f"[VERIFY] Peer {identifier} authenticated successfully!")
            return {"status": "Authenticated"}
        except Exception as e:
            print(f"[ERROR] Signature invalid for {identifier}")
            return {"error": "Authentication Failed"}, 403