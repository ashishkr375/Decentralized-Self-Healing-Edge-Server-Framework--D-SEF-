import json
from Crypto.Hash import SHA256
from Crypto.Signature import DSS
from Crypto.PublicKey import ECC
from datetime import datetime
import uuid

def create_resource_offer(node_info, resource_stats, private_key):
    """
    Create and sign a resource offer JSON object.
    Args:
        node_info (dict): Basic node info (ip, port, promised_capacity, etc)
        resource_stats (dict): Output from get_current_system_stats()
        private_key (ECC key): Node's ECC private key
    Returns:
        offer (dict): Resource offer with signature
    """
    offer = {
        'ip': node_info['ip'],
        'port': node_info['port'],
        'promised_capacity': node_info.get('promised_capacity'),
        'current_load': node_info.get('current_load', 0),
        'resource_stats': resource_stats,
        'timestamp_utc': datetime.utcnow().isoformat()
    }
    offer_json = json.dumps(offer, sort_keys=True)
    h = SHA256.new(offer_json.encode('utf-8'))
    signer = DSS.new(private_key, 'fips-186-3')
    signature = signer.sign(h)
    offer['signature'] = signature.hex()
    return offer

def verify_resource_offer(offer, public_key):
    """
    Verify a resource offer's signature.
    Args:
        offer (dict): Resource offer (must include 'signature')
        public_key (ECC key): Node's ECC public key
    Returns:
        bool: True if valid, False otherwise
    """
    signature = bytes.fromhex(offer['signature'])
    offer_copy = dict(offer)
    del offer_copy['signature']
    offer_json = json.dumps(offer_copy, sort_keys=True)
    h = SHA256.new(offer_json.encode('utf-8'))
    verifier = DSS.new(public_key, 'fips-186-3')
    try:
        verifier.verify(h, signature)
        return True
    except Exception:
        return False

def create_signed_resource_offer(node_info, system_stats, pricing_parameters, private_key):
    """
    Construct and sign a Resource Offer JSON object with all required fields.
    """
    from datetime import datetime
    from Crypto.Hash import SHA256
    from Crypto.Signature import DSS
    import json

    offer = {
        'node_id': node_info.get('chord_id'),
        'node_address': f"{node_info.get('ip')}:{node_info.get('port')}",
        'system_stats': system_stats,
        'pricing_parameters': pricing_parameters,
        'offer_timestamp_utc': datetime.utcnow().isoformat(),
        'offer_id': str(uuid.uuid4()),
    }
    # Prepare for signing
    offer_json = json.dumps(offer, sort_keys=True)
    h = SHA256.new(offer_json.encode('utf-8'))
    signer = DSS.new(private_key, 'fips-186-3')
    signature = signer.sign(h)
    offer['signature'] = signature.hex()
    return offer
