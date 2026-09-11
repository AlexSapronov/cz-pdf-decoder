"""Тесты извлечения PN и количества из текстовых блоков PDF."""
import pytest

from czdecoder.pdf_utils import extract_pn_and_qty


def _block(y, text):
    # fitz block shape: (x0, y0, x1, y1, text, block_no, block_type)
    return (0, y, 0, y + 10, text, 0, 0)


GTIN = "04640638345218"  # валидная контрольная цифра (из ТЗ)
PRE = "01" + GTIN

def test_pn_and_qty_simple():
    blocks = [
        _block(10, "Товар Пример"),
        _block(30, "5 шт"),
        _block(50, PRE),
    ]
    pn, qty = extract_pn_and_qty(blocks)
    assert pn == "ТоварПример"
    assert qty == "5"


def test_pn_below_dm_ignored():
    blocks = [
        _block(10, PRE),  # DM-блок сверху
        _block(30, "Это Итог"),
    ]
    pn, qty = extract_pn_and_qty(blocks)
    assert pn == ""
    assert qty == ""


def test_qty_only_no_pn():
    blocks = [
        _block(10, "3 шт"),
        _block(20, PRE),
    ]
    pn, qty = extract_pn_and_qty(blocks)
    assert pn == ""
    assert qty == "3"


def test_no_dm_block():
    blocks = [
        _block(10, "Какойто Товар"),
        _block(20, "7 шт"),
    ]
    pn, qty = extract_pn_and_qty(blocks)
    assert pn == "КакойтоТовар"
    assert qty == "7"


def test_nbsp_and_soft_hyphen():
    blocks = [
        _block(10, "Товар\xa0с\xadпереносом"),
        _block(20, "2 шт"),
        _block(30, PRE),
    ]
    pn, qty = extract_pn_and_qty(blocks)
    # \xa0 (nbsp) удаляется, \xad (мягкий перенос) → '-'
    assert pn == "Товарс-переносом"
    assert qty == "2"