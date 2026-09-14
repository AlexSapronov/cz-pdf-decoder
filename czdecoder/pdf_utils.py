"""Утилиты для работы с PDF (PyMuPDF/fitz)."""
from __future__ import annotations

import io
import re

import fitz
from PIL import Image


def render_page_to_image(page, zoom: float = 3) -> Image.Image:
    """Рендер страницы PDF в RGB-изображение (PIL)."""
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)


def extract_embedded_images(page, min_dim: int = 32) -> list[Image.Image]:
    """Извлекает встроенные растровые изображения страницы в NATIVE
    разрешении (без масштабирования от page render).

    Возвращает список PIL-изображений (в порядке встраивания). Кандидаты
    фильтруются по минимальному размеру, чтобы отсечь 1×1 прозрачные
    заглушки и прочий мусор. Квадратность/контраст не требуются жёстко —
    decode сам решит, но мелкий мусор отсекается заранее.
    """
    out: list[Image.Image] = []
    for img in page.get_images(full=True):
        xref = img[0]
        try:
            info = page.parent.extract_image(xref)
        except Exception:
            continue
        w, h = info.get("width", 0), info.get("height", 0)
        if w < min_dim or h < min_dim:
            continue
        try:
            im = Image.open(io.BytesIO(info["image"]))
            im.load()  # форсируем распаковку до отдачи наружу
        except Exception:
            continue
        out.append(im)
    return out


_QTY_RE = re.compile(r"(\d+)\s*шт\.?", re.IGNORECASE)

# Символы, которые при нормализации PN считаем «мягкими» переносами/пробелами:
# NBSP, узкий пробел, line/paragraph separators, таб — всё это «склейка», но
# НЕ дефис: реальные дефисы внутри PN (M12-D-PMS-...) сохраняются как есть.
_WS_CHARS = "\u00a0\u2007\u2008\u2009\u200a\u202f\u205f\u3000\u2028\u2029\t"


def _normalize_pn_token(t: str) -> str:
    """Убирает из текстового фрагмента PN «мягкие» пробелы/переносы, но
    сохраняет дефисы (\u00ad soft hyphen → '-', видимый дефис остаётся)."""
    t = t.replace("\u00ad", "-")          # soft hyphen → обычный дефис
    t = t.replace("\r", "").replace("\n", "")
    for ch in _WS_CHARS:                   # NBSP и прочие мягкие пробелы → ''
        t = t.replace(ch, "")
    return t.replace(" ", "")


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
        t = b[4].strip()
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
            cleaned = _normalize_pn_token(t[:m.start()])
            if cleaned:
                pn_parts.append(cleaned)
        else:
            pn_parts.append(_normalize_pn_token(t))
    return "".join(pn_parts), qty