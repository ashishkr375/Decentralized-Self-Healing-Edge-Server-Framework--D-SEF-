from flask import Blueprint, request, jsonify
from peers import known_peers
from chord import discover_offers_by_chord_id
from task_manager import TaskDescriptor
from accounting import append_log_entry
import time
import requests

scheduler_bp = Blueprint('scheduler', __name__)

@scheduler_bp.route('/submit_task', methods=['POST'])
def submit_task():
    data = request.json
    try:
        task = TaskDescriptor.from_dict(data)
    except Exception as e:
        return jsonify({'error': f'Invalid task descriptor: {e}'}), 400
    result = schedule_task(task)
    return jsonify(result)

def schedule_task(task_descriptor, redundant_k=1):
    """
    Basic scheduling: discover resource offers, filter by requirements, select best-fit, dispatch task.
    """
    offers = []
    now = time.time()
    # 1. Resource Discovery: iterate known peers, query their DHT offer
    for peer_id, peer in known_peers.items():
        chord_id = peer.get('chord_id')
        if not chord_id:
            continue
        peer_offers = discover_offers_by_chord_id(chord_id)
        # Only keep offers from the last 5 minutes
        for offer in peer_offers:
            offer_time = offer.get('offer_timestamp_utc')
            if offer_time:
                try:
                    offer_ts = time.mktime(time.strptime(offer_time[:19], "%Y-%m-%dT%H:%M:%S"))
                    if now - offer_ts > 300:
                        continue
                except Exception:
                    pass
            offers.append(offer)
    # 2. Node Filtering: check resource requirements
    eligible = []
    reqs = task_descriptor.resource_requirements
    max_price = task_descriptor.max_price_usd
    for offer in offers:
        stats = offer.get('system_stats', {})
        pricing = offer.get('pricing_parameters', {})
        price_ok = True
        if max_price is not None and 'cpu_per_hour_usd' in pricing and 'ram_gb_per_hour_usd' in pricing:
            # Estimate total price for this task's requirements
            cpu_price = pricing['cpu_per_hour_usd'] * reqs.get('cpu_cores', 0)
            ram_price = pricing['ram_gb_per_hour_usd'] * reqs.get('ram_gb', 0)
            total_price = cpu_price + ram_price
            price_ok = total_price <= max_price
        if stats.get('cpu_cores_logical', 0) >= reqs.get('cpu_cores', 0) and \
           stats.get('memory_available_gb', 0) >= reqs.get('ram_gb', 0) and price_ok:
            eligible.append((offer, total_price if price_ok and max_price is not None else None))
    # 3. Node Selection & 4. Task Dispatch: Auction - pick lowest price
    if max_price is not None and eligible:
        eligible.sort(key=lambda x: x[1] if x[1] is not None else float('inf'))
    # Redundant execution: send to multiple nodes if redundant_k > 1
    results = []
    for idx, offer_tuple in enumerate(eligible):
        if redundant_k > 0 and idx >= redundant_k:
            break
        offer = offer_tuple[0]
        try:
            url = f"http://{offer['node_address']}/execute_task"
            append_log_entry(
                event_type="TASK_SCHEDULED_TO_NODE_X",
                task_id=task_descriptor.task_id,
                node_id=offer['node_id'],
                details={'executor': offer['node_address'], 'agreed_price': offer_tuple[1]}
            )
            resp = requests.post(url, json=task_descriptor.to_dict(), timeout=10)
            if resp.status_code == 200:
                result = resp.json()
                expected_checksum = task_descriptor.payload.get('expected_output_checksum')
                actual_checksum = result.get('output_checksum')
                checksum_valid = None
                if expected_checksum:
                    checksum_valid = (expected_checksum == actual_checksum)
                    append_log_entry(
                        event_type="TASK_RESULT_CHECKSUM_VERIFIED",
                        task_id=task_descriptor.task_id,
                        node_id=offer['node_id'],
                        details={
                            'expected_checksum': expected_checksum,
                            'actual_checksum': actual_checksum,
                            'checksum_valid': checksum_valid
                        }
                    )
                append_log_entry(
                    event_type="TASK_ACCEPTED_BY_NODE_X",
                    task_id=task_descriptor.task_id,
                    node_id=offer['node_id'],
                    details={'executor': offer['node_address'], 'agreed_price': offer_tuple[1], 'checksum_valid': checksum_valid}
                )
                results.append({'task_id': task_descriptor.task_id, 'executor': offer['node_address'], 'agreed_price': offer_tuple[1], 'result': result, 'checksum_valid': checksum_valid})
            else:
                results.append({'error': f'Executor {offer["node_address"]} returned status {resp.status_code}', 'details': resp.text})
        except Exception as e:
            results.append({'error': f'Failed to dispatch task to {offer["node_address"]}: {e}'})
    # Majority/consensus validation for redundant execution
    if redundant_k > 1:
        # Count matching checksums
        checksum_counts = {}
        for r in results:
            if 'result' in r and 'output_checksum' in r['result']:
                cksum = r['result']['output_checksum']
                checksum_counts[cksum] = checksum_counts.get(cksum, 0) + 1
        # Find the most common checksum
        if checksum_counts:
            best_cksum = max(checksum_counts, key=checksum_counts.get)
            majority_count = checksum_counts[best_cksum]
            consensus = majority_count >= ((redundant_k // 2) + 1)
            return {'redundant_results': results, 'consensus_checksum': best_cksum, 'consensus_count': majority_count, 'consensus_valid': consensus}
        else:
            return {'redundant_results': results, 'consensus_valid': False}
    # Non-redundant: return first successful or last error
    for r in results:
        if 'result' in r:
            return r
    return results[-1] if results else {'error': 'No eligible nodes found for task requirements.'}
