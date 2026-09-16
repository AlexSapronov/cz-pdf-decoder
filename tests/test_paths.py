"""Unit-тесты для определения общей папки PDF (фича «Сохранить рядом с PDF»)."""
import os
import sys

import pytest

from czdecoder.paths import (
    can_save_next_to_pdf,
    get_common_pdf_directory,
    result_filename_from_directory,
)


def _row(path):
    return {"file_path": path}


def _norm(p):
    return os.path.normcase(os.path.normpath(os.path.abspath(p)))


# --- get_common_pdf_directory ---

def test_empty_rows_returns_none():
    assert get_common_pdf_directory([]) is None


def test_single_pdf_returns_its_directory(tmp_path):
    f = tmp_path / "a.pdf"
    f.write_bytes(b"%PDF")
    assert get_common_pdf_directory([_row(str(f))]) == _norm(str(tmp_path))


def test_multiple_pdfs_same_dir(tmp_path):
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    a.write_bytes(b"%PDF")
    b.write_bytes(b"%PDF")
    rows = [_row(str(a)), _row(str(b))]
    assert get_common_pdf_directory(rows) == _norm(str(tmp_path))


def test_multiple_pages_of_one_pdf(tmp_path):
    """Один PDF с несколькими страницами => несколько rows с одним file_path."""
    a = tmp_path / "a.pdf"
    a.write_bytes(b"%PDF")
    rows = [
        {"file_path": str(a), "page_num": 1},
        {"file_path": str(a), "page_num": 2},
    ]
    assert get_common_pdf_directory(rows) == _norm(str(tmp_path))


def test_pdfs_in_different_dirs_returns_none(tmp_path):
    d1 = tmp_path / "x"
    d2 = tmp_path / "y"
    d1.mkdir()
    d2.mkdir()
    a = d1 / "a.pdf"
    b = d2 / "b.pdf"
    a.write_bytes(b"%PDF")
    b.write_bytes(b"%PDF")
    assert get_common_pdf_directory([_row(str(a)), _row(str(b))]) is None


def test_nested_dirs_not_same_folder(tmp_path):
    """C:\\Orders\\a\\a.pdf и C:\\Orders\\b\\b.pdf — общий родитель, но разные папки."""
    sub_a = tmp_path / "a"
    sub_b = tmp_path / "b"
    sub_a.mkdir()
    sub_b.mkdir()
    a = sub_a / "a.pdf"
    b = sub_b / "b.pdf"
    a.write_bytes(b"%PDF")
    b.write_bytes(b"%PDF")
    assert get_common_pdf_directory([_row(str(a)), _row(str(b))]) is None


def test_duplicate_file_paths_do_not_break(tmp_path):
    a = tmp_path / "a.pdf"
    a.write_bytes(b"%PDF")
    rows = [_row(str(a)), _row(str(a)), _row(str(a))]
    assert get_common_pdf_directory(rows) == _norm(str(tmp_path))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only case variance test")
def test_windows_case_insensitive_dir(tmp_path):
    """На Windows C:\\X и c:\\x — одна директория (normcase это учитывает)."""
    a = tmp_path / "a.pdf"
    a.write_bytes(b"%PDF")
    rows = [_row(str(a))]
    # normcase на Windows приводит к lowercase — проверяем контракт функции.
    assert get_common_pdf_directory(rows) == os.path.normcase(_norm(str(tmp_path)))


def test_rows_without_file_path_returns_none():
    assert get_common_pdf_directory([{"page_num": 1}]) is None


# --- can_save_next_to_pdf ---

def test_can_save_empty_false():
    assert can_save_next_to_pdf([], True) is False


def test_can_save_common_dir_recognized_true(tmp_path):
    a = tmp_path / "a.pdf"
    a.write_bytes(b"%PDF")
    assert can_save_next_to_pdf([_row(str(a))], True) is True


def test_can_save_common_dir_not_recognized_false(tmp_path):
    a = tmp_path / "a.pdf"
    a.write_bytes(b"%PDF")
    assert can_save_next_to_pdf([_row(str(a))], False) is False


def test_can_save_mixed_dirs_false(tmp_path):
    d1 = tmp_path / "x"
    d2 = tmp_path / "y"
    d1.mkdir()
    d2.mkdir()
    a = d1 / "a.pdf"
    b = d2 / "b.pdf"
    a.write_bytes(b"%PDF")
    b.write_bytes(b"%PDF")
    assert can_save_next_to_pdf([_row(str(a)), _row(str(b))], True) is False


# --- result_filename_from_directory ---

@pytest.mark.parametrize(
    "folder, expected",
    [
        ("ABC123", "result_ABC123.xlsx"),
        ("ЭМ_ABC123", "result_ABC123.xlsx"),
        ("ВВО_ABC123", "result_ABC123.xlsx"),
        ("ООН_ABC123", "result_ABC123.xlsx"),
        ("ЭМ_ABC_123", "result_ABC_123.xlsx"),
        ("TEST_ЭМ_ABC", "result_TEST_ЭМ_ABC.xlsx"),
        ("эм_abc123", "result_abc123.xlsx"),
        ("ЭМ_RXFJ5_20.09", "result_RXFJ5_20.09.xlsx"),
    ],
)
def test_result_filename(folder, expected):
    assert result_filename_from_directory(folder) == expected


def test_result_filename_from_full_path(tmp_path):
    d = tmp_path / "ЭМ_ABC123"
    d.mkdir()
    assert result_filename_from_directory(str(d)) == "result_ABC123.xlsx"