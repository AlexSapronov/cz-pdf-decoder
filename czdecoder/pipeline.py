"""Конвейер обработки: список файлов → список строк результатов."""
from __future__ import annotations

import os

import fitz

from .datamatrix import decode_datamatrix_from_pil
from .gs1 import parse_gs1_datamatrix
from .pdf_utils import extract_pn_and_qty, render_page_to_image


def list_pdf_paths(folder: str) -> list[str]:
    out = []
    for root_dir, _, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(".pdf"):
                out.append(os.path.join(root_dir, f))
    return sorted(out)


def build_page_rows(paths: list[str]) -> list[dict]:
    """Создаёт пустые строки-заготовки (одна на страницу PDF)."""
    rows = []
    for p in paths:
        try:
            doc = fitz.open(p)
            n_pages = len(doc)
            doc.close()
        except Exception:
            continue
        for i in range(n_pages):
            rows.append({
                "full_dm": "",
                "gtin": "",
                "serial": "",
                "pn": "",
                "qty": "",
                "file_path": p,
                "file_name": os.path.basename(p),
                "page_num": i + 1,
            })
    return rows


def recognize_row(r: dict, zoom: float = 3) -> None:
    """Распознаёт одну страницу и заполняет строку in-place."""
    doc = fitz.open(r["file_path"])
    try:
        page = doc.load_page(r["page_num"] - 1)
        img = render_page_to_image(page, zoom=zoom)
        dm_codes = decode_datamatrix_from_pil(img)
        blocks = page.get_text("blocks")

        if dm_codes:
            dm_raw = dm_codes[0]
            parsed = parse_gs1_datamatrix(dm_raw)
            pn, qty = extract_pn_and_qty(blocks)
            r["full_dm"] = dm_raw
            r["gtin"] = parsed["gtin"]
            r["serial"] = parsed["serial"]
            r["pn"] = pn
            r["qty"] = qty
        else:
            r["full_dm"] = "(не найден)"
            r["gtin"] = ""
            r["serial"] = ""
            r["pn"] = ""
            r["qty"] = ""
    finally:
        doc.close()