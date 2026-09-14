"""Конвейер обработки: список файлов → список строк результатов."""
from __future__ import annotations

import os

import fitz

from .datamatrix import decode_datamatrix_from_pil
from .gs1 import parse_gs1_datamatrix
from .pdf_utils import extract_embedded_images, extract_pn_and_qty, render_page_to_image


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
                # serial — НАМЕРЕННОЕ внутреннее поле: выделяется парсером, но
                # НЕ выводится ни в GUI (tksheet), ни в Excel (см. excel.py).
                # Оно есть в row для будущего использования / отладки.
                "serial": "",
                "pn": "",
                "qty": "",
                "file_path": p,
                "file_name": os.path.basename(p),
                "page_num": i + 1,
            })
    return rows


def _decode_any(images: list) -> list[str]:
    """Декодирует первый попавшийся DataMatrix из списка изображений.

    Возвращает список уникальных декодированных строк (обычно 0..1 элемент).
    Порядок изображений важен: callers передают сначала «лучшие» кандидаты
    (embedded raster в native-разрешении), затем fallback (page render).
    """
    for im in images:
        codes = decode_datamatrix_from_pil(im)
        if codes:
            return codes
    return []


def recognize_row(r: dict, zoom: float = 3) -> None:
    """Распознаёт одну страницу и заполняет строку in-place.

    Стратегия:
      1) embedded raster images (native resolution, без масштабирования) —
         это предпочтительный источник, т.к. page render дробно масштабирует
         квадратную сетку модулей и может исказить код;
      2) fallback — полный page render (как в старом поведении).
    """
    doc = fitz.open(r["file_path"])
    try:
        page = doc.load_page(r["page_num"] - 1)
        blocks = page.get_text("blocks")

        candidates = extract_embedded_images(page)
        candidates.append(render_page_to_image(page, zoom=zoom))
        dm_codes = _decode_any(candidates)

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