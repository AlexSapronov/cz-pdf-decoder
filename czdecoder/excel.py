"""Экспорт результатов в Excel (openpyxl)."""
from __future__ import annotations

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE


def clean_for_excel(value) -> str:
    if value is None:
        return ""
    value = ILLEGAL_CHARACTERS_RE.sub("", str(value))
    return " ".join(value.split())


HEADERS = ["Полный DM", "GTIN", "PN", "Кол-во", "Файл", "Страница"]


def row_to_cells(r: dict) -> list:
    return [
        clean_for_excel(r.get("full_dm", "")),
        clean_for_excel(r.get("gtin", "")),
        clean_for_excel(r.get("pn", "")),
        clean_for_excel(r.get("qty", "")),
        clean_for_excel(r.get("file_name", "")),
        clean_for_excel(r.get("page_num", "")),
    ]


def save_excel(rows: list[dict], path: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "DataMatrix"
    ws.append(HEADERS)
    for r in rows:
        ws.append(row_to_cells(r))

    widths = {"A": 55, "B": 18, "C": 40, "D": 10, "E": 24, "F": 10}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w

    wb.save(path)