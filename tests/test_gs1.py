"""Тесты GS1-парсинга DataMatrix."""
import pytest

from czdecoder.gs1 import parse_gs1_datamatrix, split_ai

GS = "\x1d"


def test_split_ai_basic():
    raw = "0104650074900017" + GS + "21ABC123XYZ"
    fields = split_ai(raw)
    assert fields["01"] == "04650074900017"
    assert fields["21"] == "ABC123XYZ"


def test_split_ai_gtin_only():
    raw = "0104650074900017"
    fields = split_ai(raw)
    assert fields["01"] == "04650074900017"
    assert "21" not in fields


def test_parse_full():
    raw = "0104650074900017" + GS + "21A1B2C3D4"
    r = parse_gs1_datamatrix(raw)
    assert r["gtin"] == "04650074900017"
    assert r["serial"] == "A1B2C3D4"
    assert r["full_dm"] == raw


def test_serial_not_truncated():
    """Serial должен сохраняться ПОЛНОСТЬЮ, а не резаться по фикс. длине."""
    long_serial = "X" * 50
    raw = "0104650074900017" + GS + "21" + long_serial
    r = parse_gs1_datamatrix(raw)
    assert r["serial"] == long_serial


def test_serial_with_multiple_ais():
    raw = "0104650074900017" + GS + "21SERIAL01" + GS + "93abcdef"
    r = parse_gs1_datamatrix(raw)
    assert r["gtin"] == "04650074900017"
    assert r["serial"] == "SERIAL01"
    assert r["ais"]["93"] == "abcdef"


def test_empty_input():
    r = parse_gs1_datamatrix("")
    assert r["gtin"] == ""
    assert r["serial"] == ""