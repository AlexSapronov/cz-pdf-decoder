"""Интеграционный тест: реальный DataMatrix, вшитый в PDF, — полный цикл."""
import io
import os

import pytest
from PIL import Image

from czdecoder.pipeline import build_page_rows, recognize_row
from czdecoder.excel import save_excel


def _make_dm_png_bytes(raw: str) -> bytes:
    """Кодирует строку в DataMatrix PNG (байты) через pylibdmtx.

    pylibdmtx.encode возвращает NamedTuple (width, height, bpp, pixels),
    где pixels — сырые RGB-байты. Собираем PIL и сохраняем в PNG.
    """
    from pylibdmtx.pylibdmtx import encode
    enc = encode(raw.encode("utf-8"))
    img = Image.frombytes("RGB", (enc.width, enc.height), enc.pixels)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_pdf_with_dm(raw: str, pn_text: str, qty_text: str, path: str):
    """Одностраничный PDF: сверху текст PN и количества, ниже DataMatrix."""
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4

    page.insert_text((72, 72), pn_text, fontsize=12)
    page.insert_text((72, 100), qty_text, fontsize=12)

    dm_bytes = _make_dm_png_bytes(raw)
    page.insert_image(fitz.Rect(72, 140, 72 + 200, 140 + 200), stream=dm_bytes)

    doc.save(path)
    doc.close()


def test_end_to_end(tmp_path):
    import os
    # Канон: 01<GTIN>21<serial> (без GS между 01 и 21).
    raw = "0104640638345218" + "21SERIALXYZ"
    pdf_path = os.path.join(str(tmp_path), "sample.pdf")
    # PN латиницей: кириллица через insert_text без встроенного шрифта
    # на headless-VPS извлекается как глифы-заполнители ('·').
    _make_pdf_with_dm(raw, "Product Test", "4 шт", pdf_path)

    rows = build_page_rows([pdf_path])
    assert len(rows) == 1

    recognize_row(rows[0])
    # Core-ценность: GS1-парсинг полного DM (GTIN + serial целиком).
    assert rows[0]["full_dm"] == raw
    assert rows[0]["gtin"] == "04640638345218"
    assert rows[0]["serial"] == "SERIALXYZ"
    # PN/qty-извлечение покрыто отдельно юнитами (test_pdf_utils.py),
    # т.к. здесь текстовый слой кирилличен и деградирует на headless-VPS.


def test_excel_export(tmp_path):
    rows = [{
        "full_dm": "01...", "gtin": "04640638345218",
        "serial": "", "pn": "Тест", "qty": "1",
        "file_name": "a.pdf", "page_num": 1,
    }]
    out = os.path.join(str(tmp_path), "out.xlsx")
    save_excel(rows, out)
    assert os.path.isfile(out)