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


def test_codesorder_pdf_legacy_page_render_path():
    """Доказанно рабочий на Windows baseline: page render zoom=3 + legacy
    preprocessing должен декодировать target PDF БЕЗ enhanced-стратегий.

    Это отдельно гарантирует, что legacy raster-путь (а не бинаризация/embedded)
    первым находит код — т.к. именно он подтверждён на Windows.
    """
    import fitz
    from czdecoder.datamatrix import _legacy_variants, clean_text
    from czdecoder.pdf_utils import render_page_to_image

    doc = fitz.open(FIXTURE)
    page = doc[0]
    img = render_page_to_image(page, zoom=3)
    doc.close()

    from pylibdmtx.pylibdmtx import decode

    found = []
    for variant in _legacy_variants(img):
        try:
            for item in decode(variant):
                text = clean_text(item.data.decode("utf-8", errors="ignore"))
                if text and text not in found:
                    found.append(text)
        except Exception:
            continue
        if found:
            break

    assert found, "legacy page render + exact baseline variants должны декодировать"
    assert found[0].startswith("01046705539017872152")