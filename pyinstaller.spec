# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis([
    'edge_server/main.py',
],
    pathex=[],
    binaries=[],
    datas=[
        ('edge_server/*.py', 'edge_server'),
        ('cert.pem', '.'),
        ('key.pem', '.'),
    ],
    hiddenimports=[
        'flask', 'requests', 'pycryptodome', 'psutil', 'docker', 'flask_limiter'
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='edge_server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='edge_server'
)
