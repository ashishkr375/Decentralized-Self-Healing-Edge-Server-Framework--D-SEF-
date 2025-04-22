# Decentralized Self-Healing Edge Server Framework (D-SEF)

## Overview
This project implements a **Decentralized Autonomous Edge Network** where multiple edge servers discover, authenticate, and maintain peer connections dynamically without a central controller. Each server shares load balancing duties and performs self-healing by removing dead nodes from the network.

ESP Simulators act as IoT devices, sending random load packets to the network. Edge servers coordinate to handle requests optimally.

---

## 📂 Project Structure
```
/edge_server/       -> Edge Server modules (main.py + modular files)
/esp_simulator/     -> ESP Simulator
/run_all_servers.py -> Helper script to launch multiple edge servers
/pyinstaller.spec   -> (Optional) PyInstaller config for packaging
```

## 🔧 Requirements
- Python 3.11+
- Dependencies managed via [uv](https://github.com/astral-sh/uv)

---

## 🚀 Quickstart with uv

### 1. Install uv (if not installed)
```sh
pip install uv
```

### 2. Install Project Dependencies
```sh
uv sync
```

### 3. Add a New Dependency (if needed)
```sh
uv add <package-name>
uv sync
```

---

## 🟢 How to Run Edge Servers

### 1. Start the Bootstrap (First) Edge Server
```sh
uv run python edge_server/main.py --ip <BOOTSTRAP_IP> --port <BOOTSTRAP_PORT>
```
Example:
```sh
uv run python edge_server/main.py --ip 10.1.3.199 --port 5000
```

### 2. Start Additional Edge Servers (Join Existing Network)
```sh
uv run python edge_server/main.py --ip <NEW_IP> --port <NEW_PORT> --bootstrap http://<BOOTSTRAP_IP>:<BOOTSTRAP_PORT>
```
Example:
```sh
uv run python edge_server/main.py --ip 10.1.3.199 --port 5001 --bootstrap http://10.1.3.199:5000
```

You can use the provided helper script to launch multiple servers:
```sh
uv run python run_all_servers.py
```

---

## 🔵 How to Run ESP Simulators

### 1. Start ESP Simulator
```sh
uv run python esp_simulator/esp_simulator.py --bootstrap http://<BOOTSTRAP_IP>:<BOOTSTRAP_PORT> --interval <SECONDS>
```
Example:
```sh
uv run python esp_simulator/esp_simulator.py --bootstrap http://10.1.3.199:5000 --interval 5
```

ESP Simulator will automatically discover all active edge servers and redirect if one becomes unreachable.

---

## 📊 How to Start the Visualizer

```sh
uv run python edge_server/visualizer.py
```

---

## ⚡ Packaging as Standalone Executable (Optional)
- If you want to create a standalone executable, you can use PyInstaller.
- The `pyinstaller.spec` file is provided for advanced packaging and custom data inclusion.
- To build:
```sh
uv run pyinstaller pyinstaller.spec
```
- This step is optional if you only want to run via uv and Python.

---

## ✅ Features
- Decentralized peer discovery (no central server)
- Automatic peer gossip & table sync
- Challenge-Response authentication via ECC keys
- Self-healing network (dead node removal)
- Load balancing based on capacity and load
- ESP Simulator with auto-failover
- Web-based Visualizer for network status

---

## Notes
- Use uv for all dependency and environment management. **Do not use pip or requirements.txt** anymore.
- The `pyinstaller.spec` file is only needed if you want to build a distributable binary. For development and running, uv is sufficient.
- For advanced packaging, see [PyInstaller documentation](https://pyinstaller.org/en/stable/).

---

## Troubleshooting
- If you encounter issues with uv, see the [uv documentation](https://github.com/astral-sh/uv).
- For packaging issues, refer to the PyInstaller docs.

---
