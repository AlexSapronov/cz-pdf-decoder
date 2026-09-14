"""Диагностический логгер для отладки распознавания DataMatrix.

Пишет в `CZ_Decoder_debug.log` рядом с исполняемым файлом (EXE в frozen-режиме,
скрипт — при обычном Python), поэтому работает и в console=False PyInstaller
сборке, где stdout/stderr недоступны.

НЕ влияет на логику распознавания: все вызовы — best-effort, любой сбой
логгера гасится (никогда не должен ломать production pipeline).
"""
from __future__ import annotations

import hashlib
import os
import sys
import traceback
from datetime import datetime


def _log_path() -> str:
    """Возвращает путь к debug-log рядом с EXE/скриптом."""
    # В frozen-режиме sys.executable — путь к EXE; иначе — к python.exe,
    # поэтому используем каталог исполняемого файла (или скрипта).
    base = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else sys.argv[0]))
    # Сценарий запуска через `python cz_decoder.py`: sys.argv[0] — сам скрипт.
    return os.path.join(base, "CZ_Decoder_debug.log")


LOGPATH = _log_path()


def _write(line: str) -> None:
    try:
        with open(LOGPATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass  # логгер никогда не должен ронять основную программу


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def log(msg: str) -> None:
    _write(f"[{_ts()}] {msg}")


def log_exception(context: str, exc: BaseException) -> None:
    _write(f"[{_ts()}] EXCEPTION in {context}: {exc!r}")
    _write(traceback.format_exc())


def file_sha256(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return "<unable-to-hash>"


def image_fingerprint(img) -> str:
    """SHA256 от raw-байтов изображения + размер/режим — для сравнения
    normal Python vs frozen EXE (совпадают ли создаваемые Pillow изображения)."""
    try:
        raw = img.tobytes()
        digest = hashlib.sha256(raw).hexdigest()
        return f"{img.size} mode={img.mode} sha256={digest} bytes={len(raw)}"
    except Exception as e:
        return f"fingerprint-error={e!r}"


def log_runtime_info() -> None:
    """Записывает сводную информацию о рантайме при первом decode."""
    log("=" * 72)
    log("RUNTIME INFO")
    log("=" * 72)
    log(f"timestamp: {_ts()}")
    log(f"frozen: {getattr(sys, 'frozen', False)}")
    log(f"sys.executable: {sys.executable}")
    log(f"sys.argv: {sys.argv}")
    log(f"_MEIPASS: {getattr(sys, '_MEIPASS', None)}")
    log(f"sys.version: {sys.version}")
    try:
        log("sys.path:")
        for p in sys.path:
            log(f"    {p}")
    except Exception:
        pass

    # Pillow
    try:
        import PIL
        log(f"Pillow version: {PIL.__version__}")
        log(f"Pillow file: {PIL.__file__}")
    except Exception as e:
        log_exception("Pillow import", e)

    # PyMuPDF
    try:
        import fitz
        log(f"PyMuPDF (fitz) version: {getattr(fitz, 'version', ('?','?'))}")
        log(f"PyMuPDF file: {fitz.__file__}")
        log(f"PyMuPDF document version: {getattr(fitz, '__doc__', '?')[:0]}")
    except Exception as e:
        log_exception("fitz import", e)

    # pylibdmtx
    try:
        import pylibdmtx
        log(f"pylibdmtx file: {pylibdmtx.__file__}")
        import pylibdmtx.pylibdmtx as pl
        log(f"pylibdmtx.pylibdmtx file: {pl.__file__}")
        import pylibdmtx.wrapper as wr
        log(f"pylibdmtx.wrapper file: {wr.__file__}")
        import pylibdmtx.dmtx_library as dl
        log(f"pylibdmtx.dmtx_library file: {dl.__file__}")
    except Exception as e:
        log_exception("pylibdmtx import", e)

    log("=" * 72)


def log_libdmtx_runtime() -> None:
    """После загрузки pylibdmtx: версия libdmtx, имя/путь DLL."""
    try:
        import pylibdmtx.wrapper as wr
        try:
            v = wr.dmtxVersion()
            log(f"libdmtx dmtxVersion(): {v}")
        except Exception as e:
            log_exception("dmtxVersion()", e)

        lib = getattr(wr, "LIBDMTX", None)
        if lib is not None:
            try:
                log(f"LIBDMTX._name: {lib._name}")
            except Exception as e:
                log_exception("LIBDMTX._name", e)
        else:
            log("LIBDMTX: None (ещё не загружен)")

        # Какой LooseVersion реально используется и какую ветку struct выбрал wrapper.
        try:
            import distutils.version as dv
            log(f"distutils.version.LooseVersion type: {dv.LooseVersion}")
            log(f"distutils version module: {dv.__file__}")
        except Exception as e:
            log_exception("distutils.version introspection", e)
        try:
            v = wr.dmtxVersion()
            less_075 = wr.LooseVersion(v) < wr.LooseVersion('0.7.5')
            log(f"wrapper struct branch: LooseVersion('{v}') < LooseVersion('0.7.5') = {less_075!r} "
                f"({'OLD struct (no fnc1)' if less_075 else 'NEW struct (>=0.7.5, with fnc1)'})")
        except Exception as e:
            log_exception("wrapper struct branch check", e)

        deps = getattr(wr, "EXTERNAL_DEPENDENCIES", None)
        if deps:
            for d in deps:
                try:
                    log(f"EXTERNAL_DEPENDENCY: name={d._name}")
                except Exception as e:
                    log_exception("EXTERNAL_DEPENDENCY name", e)
    except Exception as e:
        log_exception("log_libdmtx_runtime", e)


def log_dll_candidates() -> None:
    """Ищет libdmtx-*.dll во frozen runtime и рядом с EXE, логирует размер/SHA.

    Помогает понять, какую DLL реально подхватывает cdll.LoadLibrary() в EXE,
    и совпадает ли она с той, что использует обычный Python.
    """
    log("--- libdmtx DLL search ---")
    fname = "libdmtx-64.dll" if sys.maxsize > 2**32 else "libdmtx-32.dll"

    search_dirs = []
    # корень frozen runtime (однофайловый EXE распаковывается в _MEIPASS)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        search_dirs.append(meipass)
    # рядом с EXE
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    search_dirs.append(exe_dir)
    # каталог скрипта (обычный Python)
    try:
        search_dirs.append(os.path.dirname(os.path.abspath(__file__)))
    except Exception:
        pass

    seen = set()
    for d in search_dirs:
        if not d or d in seen:
            continue
        seen.add(d)
        p = os.path.join(d, fname)
        exists = os.path.isfile(p)
        if exists:
            try:
                size = os.path.getsize(p)
            except Exception:
                size = -1
            log(f"DLL FOUND: {p} size={size} sha256={file_sha256(p)}")
        else:
            log(f"DLL absent: {p}")

    # также пробуем найти через pylibdmtx.dmtx_library (фолбэк Path(__file__).parent)
    try:
        import pylibdmtx.dmtx_library as dl
        pkg_dll = os.path.join(os.path.dirname(dl.__file__), fname)
        log(f"pylibdmtx package dir DLL: {pkg_dll} exists={os.path.isfile(pkg_dll)}")
        if os.path.isfile(pkg_dll):
            log(f"    size={os.path.getsize(pkg_dll)} sha256={file_sha256(pkg_dll)}")
    except Exception as e:
        log_exception("pylibdmtx package DLL check", e)

    log("--- end DLL search ---")


def log_decode_attempt(source: str, idx: int, variant_name: str, img) -> None:
    """Логирует параметры одной попытки декодирования."""
    fp = image_fingerprint(img)
    log(f"DECODE attempt: source={source} idx={idx} variant={variant_name}")
    log(f"    image: {fp}")