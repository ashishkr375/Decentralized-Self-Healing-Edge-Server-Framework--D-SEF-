from flask import Blueprint, request, jsonify
from resource_manager import get_latest_stats
from task_manager import TaskDescriptor
from accounting import append_log_entry
import docker
import os
import tempfile
import requests
import threading
import hashlib

# In-memory resource allocation tracker
allocated_resources = {}
total_earnings = 0.0

executor_bp = Blueprint('executor', __name__)

@executor_bp.route('/execute_task', methods=['POST'])
def execute_task_endpoint():
    data = request.json
    try:
        task = TaskDescriptor.from_dict(data)
    except Exception as e:
        return jsonify({'error': f'Invalid task descriptor: {e}'}), 400
    append_log_entry(
        event_type="TASK_ACCEPTED_BY_NODE_X",
        task_id=task.task_id,
        node_id=os.getenv('NODE_ID', 'executor'),
        details={}
    )
    # Run the task in a background thread
    thread = threading.Thread(target=execute_containerized_task, args=(task,))
    thread.start()
    return jsonify({'task_id': task.task_id, 'status': 'accepted/running'})

def allocate_resources(task_id, reqs):
    """Mark resources as allocated for a task."""
    allocated_resources[task_id] = reqs
    append_log_entry(
        event_type="RESOURCE_ALLOCATED",
        task_id=task_id,
        node_id=os.getenv('NODE_ID', 'executor'),
        details={'allocated': reqs}
    )

def deallocate_resources(task_id):
    """Free resources allocated for a task."""
    reqs = allocated_resources.pop(task_id, None)
    append_log_entry(
        event_type="RESOURCE_DEALLOCATED",
        task_id=task_id,
        node_id=os.getenv('NODE_ID', 'executor'),
        details={'deallocated': reqs}
    )

def add_earnings(task_id, amount):
    global total_earnings
    total_earnings += amount
    append_log_entry(
        event_type="PAYMENT_EARNED_BY_NODE_X",
        task_id=task_id,
        node_id=os.getenv('NODE_ID', 'executor'),
        details={'amount': amount, 'total_earnings': total_earnings}
    )

def execute_containerized_task(task_descriptor):
    stats = get_latest_stats()
    reqs = task_descriptor.resource_requirements
    if stats.get('cpu_cores_logical', 0) < reqs.get('cpu_cores', 0) or \
       stats.get('memory_available_gb', 0) < reqs.get('ram_gb', 0):
        append_log_entry(
            event_type="TASK_FAILED_ON_NODE_X",
            task_id=task_descriptor.task_id,
            node_id=os.getenv('NODE_ID', 'executor'),
            details={'reason': 'insufficient resources'}
        )
        print(f"[EXECUTOR] Task {task_descriptor.task_id} rejected: insufficient resources.")
        return
    allocate_resources(task_descriptor.task_id, reqs)
    append_log_entry(
        event_type="TASK_STARTED_ON_NODE_X",
        task_id=task_descriptor.task_id,
        node_id=os.getenv('NODE_ID', 'executor'),
        details={}
    )
    # 2. Resource Allocation (conceptual)
    # 3. Execution (docker_image)
    if task_descriptor.task_type == 'docker_image':
        payload = task_descriptor.payload
        image_name = payload.get('image_name')
        input_data_url = payload.get('input_data_url')
        env_vars = payload.get('environment_vars', {})
        max_duration = payload.get('max_duration_seconds', 3600)
        client = docker.from_env()
        input_file_path = None
        try:
            client.images.pull(image_name)
            if input_data_url:
                resp = requests.get(input_data_url)
                tmp_dir = tempfile.mkdtemp()
                input_file_path = os.path.join(tmp_dir, 'input.data')
                with open(input_file_path, 'wb') as f:
                    f.write(resp.content)
            volumes = {input_file_path: {'bind': '/input/input.data', 'mode': 'ro'}} if input_file_path else {}
            container = client.containers.run(
                image_name,
                environment=env_vars,
                volumes=volumes,
                detach=True,
                mem_limit=f"{reqs.get('ram_gb', 1)}g",
                nano_cpus=int(reqs.get('cpu_cores', 1) * 1e9),
                stdout=True,
                stderr=True
            )
            try:
                result = container.wait(timeout=max_duration)
            except Exception as e:
                container.kill()
                result = {'StatusCode': -1, 'Error': str(e)}
            logs = container.logs(stdout=True, stderr=True).decode()
            exit_code = result.get('StatusCode', -2)
            output_checksum = None
            task_result = {
                'task_id': task_descriptor.task_id,
                'exit_code': exit_code,
                'stdout_stderr': logs,
                'error': result.get('Error'),
            }
            if logs:
                output_checksum = hashlib.sha256(logs.encode()).hexdigest()
                task_result['output_checksum'] = output_checksum
            if task_descriptor.submission_url:
                try:
                    requests.post(task_descriptor.submission_url, json=task_result)
                except Exception as e:
                    print(f"[EXECUTOR] Error reporting result: {e}")
            append_log_entry(
                event_type="TASK_COMPLETED_ON_NODE_X",
                task_id=task_descriptor.task_id,
                node_id=os.getenv('NODE_ID', 'executor'),
                details={'exit_code': exit_code, 'output_checksum': output_checksum}
            )
            # Earnings logic: for demo, $1 per successful task
            if exit_code == 0:
                add_earnings(task_descriptor.task_id, 1.0)
            print(f"[EXECUTOR] Task {task_descriptor.task_id} completed. Exit: {exit_code}")
        except Exception as e:
            append_log_entry(
                event_type="TASK_FAILED_ON_NODE_X",
                task_id=task_descriptor.task_id,
                node_id=os.getenv('NODE_ID', 'executor'),
                details={'error': str(e)}
            )
            print(f"[EXECUTOR] Task {task_descriptor.task_id} failed: {e}")
        finally:
            if input_file_path and os.path.exists(input_file_path):
                os.remove(input_file_path)
            deallocate_resources(task_descriptor.task_id)
    # 5. Resource De-allocation (now implemented)
