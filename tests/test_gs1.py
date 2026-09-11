"""Тесты GS1-парсинга DataMatrix.

Формат (канон из gis_app/datamatrix.py): 01<GTIN-14>21<serial>[<GS>…91/92…].
GS между «01» и «21» НЕТ — AI 21 идёт сразу после GTIN.
"""
import pytest

from czdecoder.gs1 import parse_gs1_datamatrix, split_ai, gtin_checksum_valid

GS = "\x1d"
# GTIN из ТЗ (валидная контрольная цифра).
VALID_GTIN = "04640638345218"


def test_split_ai_basic():
    raw = "0104640638345218" + "21ABC123XYZ"
    fields = split_ai(raw)
    assert fields["01"] == VALID_GTIN
    assert fields["21"] == "ABC123XYZ"


def test_parse_full():
    raw = "0104640638345218" + "21A1B2C3D4"
    r = parse_gs1_datamatrix(raw)
    assert r["valid"] is True
    assert r["gtin"] == VALID_GTIN
    assert r["serial"] == "A1B2C3D4"
    assert r["full_dm"] == raw


def test_serial_not_truncated():
    """Serial сохраняется ПОЛНОСТЬЮ, не режется по фикс. длине."""
    long_serial = "X" * 50
    raw = "0104640638345218" + "21" + long_serial
    r = parse_gs1_datamatrix(raw)
    assert r["serial"] == long_serial


def test_serial_with_crypto_tail():
    """GS идёт ПОСЛЕ serial, отделяя криптохвост (AI 91)."""
    raw = "0104640638345218" + "21SERIAL01" + GS + "91EE06"
    r = parse_gs1_datamatrix(raw)
    assert r["gtin"] == VALID_GTIN
    assert r["serial"] == "SERIAL01"
    assert r["has_crypto"] is True


def test_serial_91_like_sequence_not_split():
    """Цифровая последовательность '91xx' внутри serial — НЕ граница AI."""
    raw = "0104640638345218" + "21ABC91ABDEF"
    r = parse_gs1_datamatrix(raw)
    assert r["serial"] == "ABC91ABDEF"
    assert r["has_crypto"] is False


def test_91ee_fallback_no_gs():
    """Без GS литерал '91EE' — маркер криптохвоста."""
    raw = "0104640638345218" + "21SERIAL91EE06"
    r = parse_gs1_datamatrix(raw)
    assert r["serial"] == "SERIAL"
    assert r["has_crypto"] is True


def test_scanner_prefix_normalized():
    raw = "]d2" + "0104640638345218" + "21SERIAL"
    r = parse_gs1_datamatrix(raw)
    assert r["gtin"] == VALID_GTIN
    assert r["serial"] == "SERIAL"


def test_gs_placeholder_brace():
    raw = "0104640638345218" + "21SERIAL{GS}91EE06"
    r = parse_gs1_datamatrix(raw)
    assert r["serial"] == "SERIAL"
    assert r["has_crypto"] is True


def test_empty_input():
    r = parse_gs1_datamatrix("")
    assert r["gtin"] == ""
    assert r["serial"] == ""


def test_gtin_only_missing_ai21():
    r = parse_gs1_datamatrix("01" + VALID_GTIN)
    assert r["valid"] is False


def test_gtin_checksum_valid():
    assert gtin_checksum_valid(VALID_GTIN) is True
    assert gtin_checksum_valid("04640638345219") is False  # испорченная контрольная
    assert gtin_checksum_valid("123") is False
