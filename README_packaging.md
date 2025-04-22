# Edge Server Packaging & Deployment Guide

This guide describes how to build standalone executables for the Edge Server framework for Windows, Linux, and macOS using PyInstaller.

## 1. Prerequisites
- Python 3.8+
- pip (Python package manager)
- [PyInstaller](https://pyinstaller.org/) (`pip install pyinstaller`)
- OpenSSL (for generating cert.pem/key.pem if not present)
- Docker (for task execution)

## 2. Install Dependencies
```
pip install -r requirements.txt
```

## 3. Generate SSL Certificates (if not present)
```
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"
```

## 4. Build the Executable
```
pyinstaller pyinstaller.spec
```
- The output will be in the `dist/edge_server` directory.
- All Python modules, certs, and dependencies will be bundled.

## 5. Running the Executable
```
cd dist/edge_server
./edge_server --ip <IP> --port <PORT> --promised_capacity <CAP> [--bootstrap <BOOTSTRAP_URL>]
```
- Example:
```
./edge_server --ip 127.0.0.1 --port 5000 --promised_capacity 1000
```

## 6. Notes
- For Linux/macOS, you may need to make the binary executable: `chmod +x edge_server`
- For Windows, run `edge_server.exe` from a terminal.
- All config/cert files must be present in the same directory as the executable.

## 7. Troubleshooting
- If you get missing module errors, add them to `hiddenimports` in `pyinstaller.spec`.
- For packaging issues on macOS, see PyInstaller docs for signing and notarization.

---

For further customization (branding, icons, GUI), see [PyInstaller documentation](https://pyinstaller.org/en/stable/).
