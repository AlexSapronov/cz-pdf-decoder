"""Честный ЗНАК: DataMatrix декодер из PDF → Excel.

Пакет чистой логики (отдельно от GUI).

Субмодули импортируются ЛЕНИВО (через __getattr__, PEP 562). Причина:
отдельные модули тянут опциональные/требовательные зависимости (pylibdmtx
нуждается в distutils — на Python 3.12 удалён из stdlib; fitz/PyMuPDF; PIL).
Ленивый импорт гарантирует, что `import czdecoder` и импорт сугубо текстовых
модулей (gs1, excel, pipeline) не падают на стадии сбора тестов в Python 3.12.

Использование остаётся прежним:
    from czdecoder.gs1 import parse_gs1_datamatrix
    from czdecoder.pipeline import build_page_rows
    # и т.д. — точечный импорт подмодуля работает как раньше.
"""
from __future__ import annotations

__all__ = [
    "decode_datamatrix_from_pil",
    "parse_gs1_datamatrix",
    "extract_pn_and_qty",
    "render_page_to_image",
    "build_page_rows",
    "list_pdf_paths",
    "recognize_row",
    "save_excel",
]

_LAZY = {
    "decode_datamatrix_from_pil": ("czdecoder.datamatrix", "decode_datamatrix_from_pil"),
    "parse_gs1_datamatrix": ("czdecoder.gs1", "parse_gs1_datamatrix"),
    "extract_pn_and_qty": ("czdecoder.pdf_utils", "extract_pn_and_qty"),
    "render_page_to_image": ("czdecoder.pdf_utils", "render_page_to_image"),
    "build_page_rows": ("czdecoder.pipeline", "build_page_rows"),
    "list_pdf_paths": ("czdecoder.pipeline", "list_pdf_paths"),
    "recognize_row": ("czdecoder.pipeline", "recognize_row"),
    "save_excel": ("czdecoder.excel", "save_excel"),
}


def __getattr__(name: str):
    if name in _LAZY:
        import importlib
        mod_name, attr = _LAZY[name]
        module = importlib.import_module(mod_name)
        value = getattr(module, attr)
        globals()[name] = value  # кэшируем
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(list(globals().keys()) + __all__))