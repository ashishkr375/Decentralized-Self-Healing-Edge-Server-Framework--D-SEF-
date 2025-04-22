import subprocess
import time
import sys
import signal
import os

# Configuration
IP = "10.1.3.199"
BOOTSTRAP_PORT = 5000
PORTS = list(range(5000, 5035))  # From 5000 to 5034
BOOTSTRAP_URL = f"http://{IP}:{BOOTSTRAP_PORT}"

# Store all processes
processes = []

def signal_handler(sig, frame):
    print("\nShutting down all servers...")
    for p in processes:
        try:
            p.terminate()
        except:
            pass
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def start_server(port, is_bootstrap=False):
    """Start a single edge server"""
    capacity = 450 + (port % 10) * 100  # Vary capacity between 450-1350

    # Use uv run python ... for proper env isolation
    cmd = [
        sys.executable, "-m", "uv", "run", "python", "edge_server/main.py",
        "--ip", IP,
        "--port", str(port),
        "--promised_capacity", str(capacity)
    ]
    if not is_bootstrap:
        cmd.extend(["--bootstrap", BOOTSTRAP_URL])

    print(f"Starting{'bootstrap' if is_bootstrap else ''} server on port {port}...")
    if sys.platform == 'win32':
        process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        with open(os.devnull, 'w') as devnull:
            process = subprocess.Popen(cmd, stdout=devnull, stderr=devnull)

    processes.append(process)
    return process

def start_visualizer():
    """Start the visualization server"""
    cmd = [sys.executable, "-m", "uv", "run", "python", "edge_server/visualizer.py"]

    print("Starting visualization server on port 8080...")
    if sys.platform == 'win32':
        process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        process = subprocess.Popen(cmd)

    processes.append(process)
    return process

def generate_ssl_certs():
    """Generate self-signed SSL certs if not present (key.pem, cert.pem)."""
    cert_path = os.path.join(os.path.dirname(__file__), 'cert.pem')
    key_path = os.path.join(os.path.dirname(__file__), 'key.pem')
    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        print("Generating self-signed SSL certificates for HTTPS...")
        # Use openssl to generate certs (cross-platform)
        cmd = [
            'openssl', 'req', '-x509', '-newkey', 'rsa:4096',
            '-keyout', key_path, '-out', cert_path, '-days', '365', '-nodes', '-subj', '/CN=localhost'
        ]
        try:
            subprocess.run(cmd, check=True)
            print("SSL certificates generated.")
        except Exception as e:
            print(f"[ERROR] Could not generate SSL certificates: {e}")
            print("You must have openssl installed and in your PATH.")
            sys.exit(1)

def main():
    # First, ensure SSL certs exist
    generate_ssl_certs()
    # First, start the bootstrap node
    bootstrap_process = start_server(BOOTSTRAP_PORT, is_bootstrap=True)
    
    # Wait for bootstrap node to initialize
    print("Waiting for bootstrap node to initialize...")
    time.sleep(5)
    
    # Then start other nodes
    for port in PORTS:
        if port != BOOTSTRAP_PORT:
            start_server(port)
            # Short delay between starting servers to avoid race conditions
            time.sleep(1)
    
    # Finally, start the visualizer
    start_visualizer()
    
    print("\nAll servers are running!")
    print(f"Visualization available at: http://{IP}:8080")
    print("Press Ctrl+C to shut down all servers")
    
    # Keep the script running to manage the processes
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    main() 