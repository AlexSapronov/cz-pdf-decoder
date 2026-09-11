"""Parsing строк DataMatrix ЧЗ по правилам GS1.

Формат DataMatrix маркировки (Честный ЗНАК):
    01<GTIN-14>21<serial>[-ограниченное число GS, если они есть]

Ключевое правило (см. память/опыт):
  - GTIN = 14 цифр после AI '01'.
  - Serial (AI '21') — это ВСЁ, что идёт после GTIN до разделителя группы `\\x1d`
    (GS1 Group Separator) или до конца строки. НЕ отрезать по фиксированной длине 13.
"""

from __future__ import annotations

GS = "\x1d"  # GS1 Group Separator


def split_ai(raw: str) -> dict:
    """Разбивает строку DM на пары AI:value, используя GS-разделители.

    Первая группа «01GTIN» фиксированной длины (без GS), последующие AI
    отделены GS. Возвращает dict {AI(str): value(str)} в порядке появления листе.
    """
    result: dict[str, str] = {}
    parts = raw.split(GS)
    # Часть 0 — «01» + GTIN (фикс. 2+14)
    first = parts[0]
    if first.startswith("01") and len(first) >= 16:
        result["01"] = first[2:16]
    # Остальные — «AIn» + value (переменной длины, до конца фрагмента)
    for seg in parts[1:]:
        if not seg:
            continue
        if len(seg) >= 2:
            result[seg[:2]] = seg[2:]
    return result


def parse_gs1_datamatrix(raw: str) -> dict:
    """Полный разбор DM. Возвращает {gtin, serial, full_dm}."""
    fields = split_ai(raw)
    return {
        "full_dm": raw,
        "gtin": fields.get("01", ""),
        "serial": fields.get("21", ""),
        "ais": fields,
    }