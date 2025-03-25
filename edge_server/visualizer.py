from flask import Flask, render_template, jsonify
import requests
import json
import time
import threading
import os
import math

app = Flask(__name__, static_folder='static', template_folder='templates')

# Store for node data
nodes_data = {}
chord_ring_data = {}
last_update = 0

# Create necessary directories
os.makedirs('edge_server/templates', exist_ok=True)
os.makedirs('edge_server/static', exist_ok=True)

def update_node_data():
    """Periodically fetch data from all nodes"""
    global nodes_data, chord_ring_data, last_update
    
    while True:
        try:
            # Scan ports to find active nodes
            active_ports = []
            base_url = "http://10.1.3.199"
            
            # Scan more ports - increase range to include all your servers
            for port in range(5000, 5035):  # Scan from 5000 to 5034
                try:
                    response = requests.get(f"{base_url}:{port}/status", timeout=1)
                    if response.status_code == 200:
                        active_ports.append(port)
                        print(f"Found active node at port {port}")
                except Exception as e:
                    pass
            
            print(f"Found {len(active_ports)} active nodes")
            
            # Fetch node data with increased timeout
            updated_nodes = {}
            for port in active_ports:
                try:
                    # Get basic status
                    status_response = requests.get(f"{base_url}:{port}/status", timeout=3)
                    if status_response.status_code == 200:
                        node_status = status_response.json()
                        
                        # Get Chord debug data
                        debug_response = requests.get(f"{base_url}:{port}/chord/debug", timeout=3)
                        if debug_response.status_code == 200:
                            chord_data = debug_response.json()
                            
                            # Combine data
                            node_id = f"{node_status['ip']}:{node_status['port']}"
                            updated_nodes[node_id] = {
                                "ip": node_status['ip'],
                                "port": node_status['port'],
                                "chord_id": node_status.get('chord_id', 0),
                                "chord_id_short": node_status.get('chord_id_short', 0),
                                "promised_capacity": node_status['promised_capacity'],
                                "current_load": node_status['current_load'],
                                "finger_table": chord_data.get('finger_table_sample', []),
                                "successor": chord_data.get('successor', {}),
                                "predecessor": chord_data.get('predecessor', {}),
                                "known_peers": list(chord_data.get('known_peers', {}).values())
                            }
                except Exception as e:
                    print(f"Error fetching data from port {port}: {str(e)}")
            
            # Update global data
            if updated_nodes:
                nodes_data = updated_nodes
                
                # Calculate positions on the ring for visualization
                chord_ring = []
                max_id = 2**160
                for node_id, node in nodes_data.items():
                    # Calculate position on a circle
                    angle = (node['chord_id'] / max_id) * 2 * math.pi
                    x = 250 + 200 * math.cos(angle)
                    y = 250 + 200 * math.sin(angle)
                    
                    # Add connections based on successor and finger table
                    connections = []
                    
                    # Add successor connection
                    if node.get('successor') and 'chord_id' in node['successor']:
                        succ_id = node['successor']['chord_id']
                        succ_angle = (succ_id / max_id) * 2 * math.pi
                        succ_x = 250 + 200 * math.cos(succ_angle)
                        succ_y = 250 + 200 * math.sin(succ_angle)
                        
                        connections.append({
                            'x': succ_x,
                            'y': succ_y,
                            'type': 'successor',
                            'target_id': f"{node['successor']['ip']}:{node['successor']['port']}"
                        })
                    
                    chord_ring.append({
                        'id': node_id,
                        'port': node['port'],
                        'chord_id': node['chord_id'],
                        'chord_id_short': node['chord_id'] % 10000,
                        'x': x,
                        'y': y,
                        'connections': connections
                    })
                
                chord_ring_data = chord_ring
                last_update = time.time()
                print(f"Updated data for {len(chord_ring)} nodes")
                
            time.sleep(10)  # Update every 10 seconds (increased to reduce load)
        except Exception as e:
            print(f"Error in update thread: {str(e)}")
            time.sleep(2)

# Start the update thread
threading.Thread(target=update_node_data, daemon=True).start()

@app.route('/')
def index():
    return render_template('visualizer.html')

@app.route('/api/nodes')
def get_nodes():
    return jsonify({
        'nodes': nodes_data,
        'ring': chord_ring_data,
        'last_update': last_update
    })

@app.route('/api/node/<port>')
def get_node(port):
    for node_id, node in nodes_data.items():
        if str(node['port']) == port:
            return jsonify(node)
    return jsonify({'error': 'Node not found'}), 404

if __name__ == '__main__':
    # Write HTML template
    with open('edge_server/templates/visualizer.html', 'w') as f:
        f.write("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chord Ring Visualization</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f8f9fa;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        #visualizer {
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }
        #ring-container {
            flex: 1;
            min-width: 550px;
            background-color: white;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            padding: 20px;
            min-height: 600px;
            position: relative;
        }
        #node-info {
            flex: 1;
            min-width: 550px;
            background-color: white;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            padding: 20px;
            min-height: 600px;
            max-height: 800px;
            overflow-y: auto;
        }
        #chord-ring {
            width: 500px;
            height: 500px;
            position: relative;
            margin: 0 auto;
        }
        .node-circle {
            position: absolute;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background-color: #007bff;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
            transform: translate(-20px, -20px);
            z-index: 3;
        }
        .node-circle:hover {
            transform: translate(-22px, -22px) scale(1.1);
            box-shadow: 0 0 12px rgba(0,123,255,0.7);
        }
        .node-circle.active {
            background-color: #dc3545;
            transform: translate(-22px, -22px) scale(1.1);
            box-shadow: 0 0 12px rgba(220,53,69,0.7);
            z-index: 4;
        }
        .node-connection {
            position: absolute;
            background-color: #28a745;
            height: 3px;
            transform-origin: left center;
            z-index: 1;
        }
        .node-connection.successor {
            background-color: #28a745;
        }
        .ring-circle {
            position: absolute;
            width: 400px;
            height: 400px;
            border-radius: 50%;
            border: 2px dashed #ccc;
            top: 50px;
            left: 50px;
            z-index: 0;
        }
        .table {
            font-size: 0.9rem;
        }
        .card {
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .card-header {
            font-weight: bold;
            background-color: #f8f9fa;
        }
        .badge {
            font-size: 0.75rem;
        }
        .refresh-time {
            position: absolute;
            bottom: 10px;
            right: 20px;
            font-size: 0.8rem;
            color: #6c757d;
        }
        .node-label {
            position: absolute;
            font-size: 10px;
            color: #333;
            font-weight: bold;
            z-index: 2;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="my-4 text-center">Chord DHT Ring Visualization</h1>
        
        <div id="visualizer">
            <div id="ring-container">
                <div class="d-flex justify-content-between">
                    <h4>Chord Ring Network</h4>
                    <div>
                        <span id="node-count" class="badge bg-primary">0 Nodes</span>
                        <button id="refresh-btn" class="btn btn-sm btn-outline-secondary ms-2">Refresh</button>
                    </div>
                </div>
                <div id="chord-ring">
                    <div class="ring-circle"></div>
                    <!-- Nodes will be added here by JavaScript -->
                </div>
                <div class="refresh-time">Last update: <span id="last-update">Never</span></div>
            </div>
            
            <div id="node-info">
                <h4>Node Details</h4>
                <p id="no-selection" class="text-muted">Click on a node to see its details</p>
                <div id="node-details" style="display: none;">
                    <div class="card">
                        <div class="card-header">Basic Information</div>
                        <div class="card-body">
                            <table class="table table-sm">
                                <tr>
                                    <th>Node ID:</th>
                                    <td id="node-id"></td>
                                </tr>
                                <tr>
                                    <th>IP:Port:</th>
                                    <td id="node-ip-port"></td>
                                </tr>
                                <tr>
                                    <th>Chord ID:</th>
                                    <td id="node-chord-id"></td>
                                </tr>
                                <tr>
                                    <th>Capacity:</th>
                                    <td><span id="node-capacity"></span> (<span id="node-load"></span>% used)</td>
                                </tr>
                            </table>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-header">Chord Neighbors</div>
                        <div class="card-body">
                            <div class="row">
                                <div class="col-6">
                                    <h6>Successor</h6>
                                    <div id="node-successor" class="small"></div>
                                </div>
                                <div class="col-6">
                                    <h6>Predecessor</h6>
                                    <div id="node-predecessor" class="small"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-header">Finger Table</div>
                        <div class="card-body">
                            <table class="table table-sm table-striped">
                                <thead>
                                    <tr>
                                        <th>Index</th>
                                        <th>Start ID</th>
                                        <th>Successor</th>
                                        <th>Distance</th>
                                    </tr>
                                </thead>
                                <tbody id="finger-table">
                                    <!-- Finger table entries -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-header">Known Peers</div>
                        <div class="card-body">
                            <table class="table table-sm table-striped">
                                <thead>
                                    <tr>
                                        <th>IP:Port</th>
                                        <th>Chord ID</th>
                                        <th>Capacity</th>
                                        <th>Distance</th>
                                    </tr>
                                </thead>
                                <tbody id="known-peers">
                                    <!-- Known peers entries -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Global variables
        let nodesData = {};
        let ringData = [];
        let selectedNode = null;
        
        // Format time
        function formatTime(timestamp) {
            if (!timestamp) return 'Never';
            const date = new Date(timestamp * 1000);
            return date.toLocaleTimeString();
        }
        
        // Calculate chord distance between two IDs
        function chordDistance(from, to) {
            // Use BigInt to properly handle the large numbers in chord IDs
            try {
                const fromBig = BigInt(from);
                const toBig = BigInt(to);
                const max = BigInt("0x" + "f".repeat(40));  // 2^160 - 1
                
                if (toBig >= fromBig) {
                    return Number((toBig - fromBig));
                } else {
                    return Number((max - fromBig + toBig + BigInt(1)));
                }
            } catch (e) {
                console.error("Error calculating distance:", e);
                return "N/A";
            }
        }
        
        // Format large numbers for display
        function formatNumber(num) {
            if (num === undefined || num === null || num === "N/A") return 'N/A';
            
            // Format as readable number with K, M suffixes
            if (num > 1000000000000) {
                return (num / 1000000000000).toFixed(2) + 'T';
            } else if (num > 1000000000) {
                return (num / 1000000000).toFixed(2) + 'B';
            } else if (num > 1000000) {
                return (num / 1000000).toFixed(2) + 'M';
            } else if (num > 1000) {
                return (num / 1000).toFixed(2) + 'K';
            }
            return num.toString();
        }
        
        // Update the visualization
        function updateVisualization() {
            fetch('/api/nodes')
                .then(response => response.json())
                .then(data => {
                    nodesData = data.nodes;
                    ringData = data.ring;
                    
                    // Update node count
                    document.getElementById('node-count').textContent = `${ringData.length} Nodes`;
                    
                    // Update last refresh time
                    document.getElementById('last-update').textContent = formatTime(data.last_update);
                    
                    renderChordRing();
                    
                    // If a node was selected, update its details
                    if (selectedNode) {
                        const nodeId = selectedNode.getAttribute('data-id');
                        for (const node of ringData) {
                            if (node.id === nodeId) {
                                showNodeDetails(nodeId);
                                break;
                            }
                        }
                    }
                })
                .catch(error => console.error('Error fetching nodes:', error));
        }
        
        // Render the Chord ring
        function renderChordRing() {
            const chordRing = document.getElementById('chord-ring');
            
            // Clear existing nodes and connections
            const existingNodes = chordRing.querySelectorAll('.node-circle, .node-connection, .node-label');
            existingNodes.forEach(node => node.remove());
            
            // Add connections first (so they appear behind nodes)
            ringData.forEach(node => {
                if (node.connections && node.connections.length > 0) {
                    node.connections.forEach(conn => {
                        const connection = document.createElement('div');
                        connection.className = `node-connection ${conn.type}`;
                        
                        // Calculate length and angle
                        const dx = conn.x - node.x;
                        const dy = conn.y - node.y;
                        const length = Math.sqrt(dx*dx + dy*dy);
                        const angle = Math.atan2(dy, dx) * 180 / Math.PI;
                        
                        connection.style.width = `${length}px`;
                        connection.style.transform = `translate(${node.x}px, ${node.y + 1}px) rotate(${angle}deg)`;
                        
                        chordRing.appendChild(connection);
                    });
                }
            });
            
            // Add node circles
            ringData.forEach(node => {
                // Add the node
                const nodeCircle = document.createElement('div');
                nodeCircle.className = 'node-circle';
                nodeCircle.style.left = `${node.x}px`;
                nodeCircle.style.top = `${node.y}px`;
                nodeCircle.textContent = node.port.toString().substring(1);  // Just show last digits
                nodeCircle.setAttribute('data-id', node.id);
                nodeCircle.addEventListener('click', (e) => {
                    document.querySelectorAll('.node-circle').forEach(n => n.classList.remove('active'));
                    e.target.classList.add('active');
                    selectedNode = e.target;
                    showNodeDetails(node.id);
                });
                
                // Add a label with the short Chord ID
                const nodeLabel = document.createElement('div');
                nodeLabel.className = 'node-label';
                nodeLabel.style.left = `${node.x + 22}px`;
                nodeLabel.style.top = `${node.y + 22}px`;
                nodeLabel.textContent = `ID: ${node.chord_id_short}`;
                
                chordRing.appendChild(nodeCircle);
                chordRing.appendChild(nodeLabel);
            });
        }
        
        // Show details for a selected node
        function showNodeDetails(nodeId) {
            const node = nodesData[nodeId];
            if (!node) return;
            
            document.getElementById('no-selection').style.display = 'none';
            document.getElementById('node-details').style.display = 'block';
            
            // Update basic info
            document.getElementById('node-id').textContent = nodeId;
            document.getElementById('node-ip-port').textContent = `${node.ip}:${node.port}`;
            document.getElementById('node-chord-id').textContent = `${node.chord_id} (${node.chord_id % 10000} mod 10000)`;
            document.getElementById('node-capacity').textContent = node.promised_capacity;
            
            const loadPercent = Math.round((node.current_load / node.promised_capacity) * 100) || 0;
            document.getElementById('node-load').textContent = loadPercent;
            
            // Update successor
            const successorElem = document.getElementById('node-successor');
            if (node.successor && node.successor.ip) {
                const succDistance = chordDistance(node.chord_id, node.successor.chord_id);
                successorElem.innerHTML = `
                    <strong>IP:Port:</strong> ${node.successor.ip}:${node.successor.port}<br>
                    <strong>Chord ID:</strong> ${node.successor.chord_id % 10000} (mod 10000)<br>
                    <strong>Distance:</strong> ${formatNumber(succDistance)}
                `;
            } else {
                successorElem.textContent = 'None';
            }
            
            // Update predecessor
            const predecessorElem = document.getElementById('node-predecessor');
            if (node.predecessor && node.predecessor.ip) {
                const predDistance = chordDistance(node.predecessor.chord_id, node.chord_id);
                predecessorElem.innerHTML = `
                    <strong>IP:Port:</strong> ${node.predecessor.ip}:${node.predecessor.port}<br>
                    <strong>Chord ID:</strong> ${node.predecessor.chord_id % 10000} (mod 10000)<br>
                    <strong>Distance:</strong> ${formatNumber(predDistance)}
                `;
            } else {
                predecessorElem.textContent = 'None';
            }
            
            // Update finger table
            const fingerTableElem = document.getElementById('finger-table');
            fingerTableElem.innerHTML = '';
            if (node.finger_table && node.finger_table.length > 0) {
                node.finger_table.forEach((finger, index) => {
                    let distanceText = 'N/A';
                    if (finger.node && finger.node.chord_id) {
                        const distance = chordDistance(finger.start, finger.node.chord_id);
                        distanceText = formatNumber(distance);
                    }
                    
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${index}</td>
                        <td>${finger.start % 10000}</td>
                        <td>${finger.node ? `${finger.node.ip}:${finger.node.port} (${finger.node.chord_id % 10000})` : 'None'}</td>
                        <td>${distanceText}</td>
                    `;
                    fingerTableElem.appendChild(row);
                });
            } else {
                const row = document.createElement('tr');
                row.innerHTML = '<td colspan="4">No finger table entries available</td>';
                fingerTableElem.appendChild(row);
            }
            
            // Update known peers
            const knownPeersElem = document.getElementById('known-peers');
            knownPeersElem.innerHTML = '';
            if (node.known_peers && node.known_peers.length > 0) {
                // Sort peers by distance from this node
                const sortedPeers = [...node.known_peers].sort((a, b) => {
                    if (a.ip === node.ip && a.port === node.port) return 1;
                    if (b.ip === node.ip && b.port === node.port) return -1;
                    
                    const distA = chordDistance(node.chord_id, a.chord_id);
                    const distB = chordDistance(node.chord_id, b.chord_id);
                    return distA - distB;
                });
                
                sortedPeers.forEach(peer => {
                    if (peer.ip === node.ip && peer.port === node.port) return; // Skip self
                    
                    const distance = chordDistance(node.chord_id, peer.chord_id);
                    const distanceText = formatNumber(distance);
                    
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${peer.ip}:${peer.port}</td>
                        <td>${peer.chord_id % 10000}</td>
                        <td>${peer.promised_capacity} (${Math.round((peer.current_load / peer.promised_capacity) * 100) || 0}% used)</td>
                        <td>${distanceText}</td>
                    `;
                    knownPeersElem.appendChild(row);
                });
            } else {
                const row = document.createElement('tr');
                row.innerHTML = '<td colspan="4">No known peers</td>';
                knownPeersElem.appendChild(row);
            }
        }
        
        // Initialize and set periodic updates
        updateVisualization();
        setInterval(updateVisualization, 10000);
        
        // Add manual refresh button handler
        document.getElementById('refresh-btn').addEventListener('click', updateVisualization);
    </script>
</body>
</html>""")

    print("Visualization server is running at http://10.1.3.199:8080")
    app.run(host="0.0.0.0", port=8080, debug=True) 