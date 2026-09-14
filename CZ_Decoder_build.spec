# -*- mode: python ; coding: utf-8 -*-

import os, sys, site

# ---------------------------------------------------------------------------
# Поиск libdmtx DLL для pylibdmtx.
#
# pylibdmtx загружает DLL через ctypes. В frozen-приложении (PyInstaller)
# первый вызов `cdll.LoadLibrary('libdmtx-64.dll')` ищет DLL РЯДОМ С EXE
# (в корне runtime-директории `_MEIxxxxx`), затем в системном PATH.
# Фолбэк на `Path(__file__).parent` указывает в `_MEIxxxxx\pylibdmtx\`,
# но полагаться на него при onefile/onedir ненадёжно.
#
# Поэтому кладём DLL в КОРЕНЬ frozen-приложения ('.'), а не в 'pylibdmtx'.
# ---------------------------------------------------------------------------

def _find_libdmtx_dll():
    """Возвращает путь к libdmtx DLL или None.

    Имя зависит от разрядности интерпретатора (как в pylibdmtx.dmtx_library):
      - 64-бит  -> libdmtx-64.dll
      - 32-бит  -> libdmtx-32.dll
    Ищем в site-packages и user-site, без хардкода имени пользователя.
    """
    dll_name = 'libdmtx-64.dll' if sys.maxsize > 2**32 else 'libdmtx-32.dll'

    candidates = []
    try:
        candidates.extend(site.getsitepackages())      # системные site-packages
    except Exception:
        pass
    usersite = site.getusersitepackages()               # user-site (Roaming)
    if usersite:
        candidates.append(usersite)

    for sp in candidates:
        if not sp:
            continue
        dmtx_dir = os.path.join(sp, 'pylibdmtx')
        if not os.path.isdir(dmtx_dir):
            continue
        dll_path = os.path.join(dmtx_dir, dll_name)
        if os.path.isfile(dll_path):
            return dll_path
    return None


binaries = []
dll_src = _find_libdmtx_dll()

if dll_src is None:
    # Заведомо нерабочий EXE не собираем — падаем с понятной ошибкой.
    raise FileNotFoundError(
        "Не найдена libdmtx DLL (pylibdmtx). Ожидался файл "
        "`libdmtx-64.dll` для 64-бит (или `libdmtx-32.dll` для 32-бит) "
        "в папке `pylibdmtx` внутри site-packages или user-site. "
        "Установите pylibdmtx с DLL, затем перезапустите сборку."
    )

# Кладём DLL в корень frozen-приложения, чтобы cdll.LoadLibrary() находил её
# рядом с exe (см. pylibdmtx.dmtx_library.load()).
binaries.append((dll_src, '.'))
print(f'ADDING DLL: {dll_src} -> .', file=sys.stderr)

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
        # Тяжёлые/ненужные для GUI зависимости (безопасно исключить).
        'matplotlib', 'numpy', 'scipy', 'pandas',
        'tornado', 'zmq', 'IPython', 'jupyter',
        'cryptography', 'bcrypt',
        'sqlalchemy', 'psycopg2',
        'cv2', 'torch', 'tensorflow',
        'pytest', 'pip',
        # ВАЖНО: НЕ исключаем 'setuptools' и 'distutils' — pylibdmtx и
        # PyInstaller-анализ на Python 3.12+ полагаются на setuptools._distutils.
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