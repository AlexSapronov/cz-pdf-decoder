"""Тесты web-слоя (FastAPI) поверх существующей decoder-логики.

Проверяем:
- GET главной страницы;
- upload PDF → decode;
- reject non-PDF;
- отсутствие смешивания batch'ей (изоляция job'ов);
- формирование имени Excel (префиксы ЭМ_/ВВО_/ООН_);
- корректную передачу результата существующей decoder logic.

Используем реальный PDF с настоящим DataMatrix (как в test_integration.py),
а не пустой мок — чтобы тест проверял реальный путь, а не заглушку.
"""
from __future__ import annotations

import io
import os

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from webapp.main import app, _excel_name_from_shipment, _JOBS
from webapp import jobs

client = TestClient(app)


def _make_dm_png_bytes(raw: str) -> bytes:
    from pylibdmtx.pylibdmtx import encode
    enc = encode(raw.encode("utf-8"))
    img = Image.frombytes("RGB", (enc.width, enc.height), enc.pixels)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_pdf_bytes(raw: str) -> bytes:
    """Одностраничный PDF с DataMatrix внутри (тот же приём, что в integration)."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "Product Test", fontsize=12)
    page.insert_text((72, 100), "4 шт", fontsize=12)
    dm_bytes = _make_dm_png_bytes(raw)
    page.insert_image(fitz.Rect(72, 140, 72 + 200, 140 + 200), stream=dm_bytes)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


RAW = "0104640638345218" + "21SERIALXYZ"


# --- фикстура: чистим глобальный job store до/после тестов -----------------

@pytest.fixture(autouse=True)
def _clean_jobs():
    for j, d in list(_JOBS.items()):
        jobs.cleanup_job_dir(d["jdir"])
    _JOBS.clear()
    yield
    for j, d in list(_JOBS.items()):
        jobs.cleanup_job_dir(d["jdir"])
    _JOBS.clear()


# --- GET главной страницы -------------------------------------------------

def test_index_returns_html():
    r = client.get("/")
    assert r.status_code == 200
    assert "декодер" in r.text.lower() or "datamatrix" in r.text.lower()


# --- upload PDF / decode ---------------------------------------------------

def test_decode_endpoint_single_pdf():
    pdf = _make_pdf_bytes(RAW)
    r = client.post(
        "/api/decode",
        files=[("files", ("a.pdf", pdf, "application/pdf"))],
        data={"shipment": "56N1P"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["job_id"]
    assert data["total_pages"] == 1
    # Core-ценность: GTIN распознан существующим GS1-парсером.
    assert data["rows"][0]["gtin"] == "04640638345218"
    assert data["rows"][0]["file_name"] == "a.pdf"
    # Поля таблицы — ровно 6, как в desktop.
    assert set(data["rows"][0].keys()) == {
        "full_dm", "gtin", "pn", "qty", "file_name", "page_num",
    }
    assert data["excel_name"] == "result_56N1P.xlsx"


def test_decode_returns_result_via_result_endpoint():
    pdf = _make_pdf_bytes(RAW)
    r = client.post(
        "/api/decode",
        files=[("files", ("a.pdf", pdf, "application/pdf"))],
    )
    job_id = r.json()["job_id"]

    rr = client.get(f"/api/result/{job_id}")
    assert rr.status_code == 200
    assert rr.json()["rows"][0]["gtin"] == "04640638345218"


# --- reject non-PDF --------------------------------------------------------

def test_reject_non_pdf_returns_400():
    # Передаём файл, который не является PDF (txt) с правильным расширением .pdf,
    # чтобы проверить проверку по содержимому (magic bytes), а не по имени.
    r = client.post(
        "/api/decode",
        files=[("files", ("fake.pdf", b"hello world", "application/pdf"))],
    )
    assert r.status_code == 400
    assert "PDF" in r.json()["detail"]


def test_reject_wrong_extension():
    # Файл .txt отклоняется по расширению и попадает в rejected_files.
    r = client.post(
        "/api/decode",
        files=[("files", ("notes.txt", b"not a pdf", "text/plain"))],
    )
    assert r.status_code == 400
    # ни один файл не сохранён → 400
    assert r.json()["detail"]


def test_no_files_returns_400():
    r = client.post("/api/decode")
    assert r.status_code == 400


# --- отсутствие смешивания batch'ей ---------------------------------------

def test_jobs_do_not_mix():
    pdf1 = _make_pdf_bytes(RAW)
    pdf2 = _make_pdf_bytes("0104640638345218" + "21OTHERSRL")

    r1 = client.post(
        "/api/decode",
        files=[("files", ("one.pdf", pdf1, "application/pdf"))],
    )
    r2 = client.post(
        "/api/decode",
        files=[("files", ("two.pdf", pdf2, "application/pdf"))],
    )
    j1, j2 = r1.json()["job_id"], r2.json()["job_id"]
    assert j1 != j2

    rr1 = client.get(f"/api/result/{j1}").json()
    rr2 = client.get(f"/api/result/{j2}").json()
    # разные сериалы → разные строки
    assert rr1["rows"][0]["gtin"] == "04640638345218"
    assert rr2["rows"][0]["gtin"] == "04640638345218"
    # файлы разные (не перепутались между job'ами)
    assert rr1["rows"][0]["file_name"] == "one.pdf"
    assert rr2["rows"][0]["file_name"] == "two.pdf"


# --- Excel download --------------------------------------------------------

def test_download_excel(tmp_path):
    pdf = _make_pdf_bytes(RAW)
    r = client.post(
        "/api/decode",
        files=[("files", ("a.pdf", pdf, "application/pdf"))],
        data={"shipment": "56N1P"},
    )
    job_id = r.json()["job_id"]

    dl = client.get(f"/api/download/{job_id}")
    assert dl.status_code == 200
    assert dl.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument"
    )
    # проверяем, что excel реально сформирован и валиден (откроется openpyxl)
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(dl.content))
    ws = wb["DataMatrix"]
    header = [c.value for c in ws[1]]
    assert header == ["Полный DM", "GTIN", "PN", "Кол-во", "Файл", "Страница"]


def test_download_unknown_job_404():
    r = client.get("/api/download/deadbeef")
    assert r.status_code == 404


# --- формирование имени Excel ---------------------------------------------

@pytest.mark.parametrize(
    "shipment, expected",
    [
        (None, "result.xlsx"),
        ("", "result.xlsx"),
        ("   ", "result.xlsx"),
        ("56N1P", "result_56N1P.xlsx"),
        ("ЭМ_56N1P", "result_56N1P.xlsx"),
        ("ВВО_56N1P", "result_56N1P.xlsx"),
        ("ООН_56N1P", "result_56N1P.xlsx"),
        ("эм_abc123", "result_abc123.xlsx"),
        ("56N1P.xlsx", "result_56N1P.xlsx"),
    ],
)
def test_excel_name_from_shipment(shipment, expected):
    assert _excel_name_from_shipment(shipment) == expected


# --- API не отдаёт traceback ----------------------------------------------

def test_error_does_not_leak_traceback():
    # Вызываем несуществующий job — ответ JSON, без 'Traceback' строки.
    r = client.get("/api/result/nope")
    assert r.status_code == 404
    assert "Traceback" not in r.text
    assert "detail" in r.json()
