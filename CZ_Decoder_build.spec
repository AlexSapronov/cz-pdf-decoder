# -*- mode: python ; coding: utf-8 -*-

import os, sys, site

# Ищем libdmtx-64.dll в папке pylibdmtx
binaries = []
for sp in site.getsitepackages():
    dmtx_dir = os.path.join(sp, 'pylibdmtx')
    if os.path.isdir(dmtx_dir):
        for f in os.listdir(dmtx_dir):
            if f.endswith('.dll'):
                src = os.path.join(dmtx_dir, f)
                binaries.append((src, 'pylibdmtx'))
                print(f'ADDING DLL: {src}', file=sys.stderr)
        break

a = Analysis(
    ['cz_decoder.py'],
    pathex=[],
    binaries=binaries,
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'numpy', 'scipy', 'pandas',
        'tornado', 'zmq', 'IPython', 'jupyter',
        'cryptography', 'bcrypt',
        'sqlalchemy', 'psycopg2',
        'cv2', 'torch', 'tensorflow',
        'pytest', 'pip', 'setuptools',
        'distutils',
    ],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CZ_Decoder',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)