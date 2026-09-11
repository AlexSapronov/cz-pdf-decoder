"""Утилиты для работы с PDF (PyMuPDF/fitz)."""
from __future__ import annotations

import re

import fitz
from PIL import Image


def render_page_to_image(page, zoom: float = 3) -> Image.Image:
    """Рендер страницы PDF в RGB-изображение (PIL)."""
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)


_QTY_RE = re.compile(r"(\d+)\s*шт\.?", re.IGNORECASE)


def extract_pn_and_qty(blocks) -> tuple[str, str]:
    """Извлекает PN (product name) и количество из текстовых блоков страницы.

    Логика (сохранена из оригинального cz_decoder.py):
      - блок DataMatrix (начинается с '01') задаёт границу по Y;
      - PN собирается из текстовых блоков ВЫШЕ DM-блока (без пробелов);
      - количество — из подстроки вида '<N> шт'.
    """
    text_blocks = []
    dm_block_y = None
    for b in blocks:
        t = b[4].strip().replace("\xa0", "").replace("\xad", "-")
        if t.startswith("01"):
            dm_block_y = b[1]
            continue
        if t:
            text_blocks.append((b[1], t))

    text_blocks.sort(key=lambda x: x[0])

    pn_parts: list[str] = []
    qty = ""
    for y, t in text_blocks:
        if dm_block_y is not None and y > dm_block_y:
            continue
        m = _QTY_RE.search(t)
        if m:
            qty = m.group(1)
            cleaned = t.replace(m.group(0), "").strip()
            if cleaned:
                pn_parts.append(cleaned.replace(" ", ""))
        else:
            pn_parts.append(t.replace(" ", ""))
    return "".join(pn_parts), qty