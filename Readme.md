
# Decentralized Self-Healing Edge Server Framework (D-SEF)

## Overview
This project implements a **Decentralized Autonomous Edge Network** where multiple edge servers discover, authenticate, and maintain peer connections dynamically without a central controller. Each server shares load balancing duties and performs self-healing by removing dead nodes from the network.

ESP Simulators act as IoT devices, sending random load packets to the network. Edge servers coordinate to handle requests optimally.

---

## 📂 Project Structure
```
/edge_server/       -> Edge Server modules (main.py + modular files)
/esp_simulator/     -> ESP Simulator
/dashboard/         -> (Coming soon) Web dashboard for real-time stats
```

## 🔧 Requirements
- Python 3.10+
- Dependencies listed in `requirements.txt` inside each folder

## 🟢 How to Run Edge Servers

### Step 1: Navigate to the `edge_server` directory
```bash
cd edge_server
```

### Step 2: Install dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Start the first edge server (bootstrap node)
```bash
python main.py --ip 10.1.3.199 --port 5000 --promised_capacity 1000
```

### Step 4: Start additional edge servers (joining existing node)
```bash
python main.py --ip 10.1.3.199 --port 5001 --promised_capacity 800 --bootstrap http://10.1.3.199:5000
python main.py --ip YOUR_IP --port 5002 --promised_capacity 500 --bootstrap http://YOUR_IP:5000
```

---

## 🔵 How to Run ESP Simulators

### Step 1: Navigate to the `esp_simulator` directory
```bash
cd esp_simulator
```

### Step 2: Install dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Run ESP Simulator targeting your bootstrap node
```bash
python esp_simulator.py --bootstrap http://YOUR_IP:5000 --interval 5
```

ESP Simulator will automatically discover all active edge servers and redirect if one becomes unreachable.

---

## ✅ Features
- Decentralized peer discovery (no central server)
- Automatic peer gossip & table sync
- Challenge-Response authentication via ECC keys
- Self-healing network (dead node removal)
- Load balancing based on capacity and load
- ESP Simulator with auto-failover

---

