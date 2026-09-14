"""Regression test на реальном проблемном PDF (codesOrder_2026-08-10_1.pdf).

Эталонный файл содержит GS1 DataMatrix как отдельный встроенный raster
(180×180), который старый pipeline (только page render + авто-контраст)
не декодировал. Тест фиксирует полный цикл распознавания: DM → GS1 → PN/qty.
"""
import os

from czdecoder.pipeline import build_page_rows, recognize_row


FIXTURE = os.path.join(
    os.path.dirname(__file__), "fixtures", "codesOrder_2026-08-10_1.pdf")


def test_codesorder_pdf_end_to_end():
    rows = build_page_rows([FIXTURE])
    assert len(rows) == 1

    recognize_row(rows[0])
    r = rows[0]

    # Полный DM должен быть распознан (не "(не найден)").
    assert r["full_dm"] and r["full_dm"] != "(не найден)"

    # GTIN (AI 01) структурно извлекается из payload.
    assert r["gtin"] == "04670553901787"

    # PN: мягкие переносы/NBSP нормализованы, дефисы сохранены.
    assert r["pn"] == "M12-D-PMS-F-4-R-PG9"

    # Количество.
    assert r["qty"] == "200"


def test_codesorder_pdf_embedded_image_detected():
    """Embedded raster DataMatrix должен декодироваться в native-разрешении."""
    import fitz
    from czdecoder.datamatrix import decode_datamatrix_from_pil
    from czdecoder.pdf_utils import extract_embedded_images

    doc = fitz.open(FIXTURE)
    page = doc[0]
    imgs = extract_embedded_images(page)
    doc.close()

    codes = []
    for im in imgs:
        codes.extend(decode_datamatrix_from_pil(im))
    assert codes, "embedded raster должен содержать DataMatrix"
    assert codes[0].startswith("01046705539017872152")