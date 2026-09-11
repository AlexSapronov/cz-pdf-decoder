"""Честный ЗНАК: DataMatrix декодер из PDF → Excel.

Пакет чистой логики (отдельно от GUI).
"""
from __future__ import annotations

from .datamatrix import decode_datamatrix_from_pil
from .excel import save_excel
from .gs1 import parse_gs1_datamatrix
from .pdf_utils import extract_pn_and_qty, render_page_to_image
from .pipeline import build_page_rows, list_pdf_paths, recognize_row

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