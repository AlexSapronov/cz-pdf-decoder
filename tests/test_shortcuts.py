"""Regression-тесты на keyboard-layout-independent shortcuts.

Баг: штатные tksheet copy/select_all привязаны к keysym 'c'/'a'. При русской
раскладке физическая C приходит как 'Cyrillic_es', а A — как 'Cyrillic_ef',
поэтому Ctrl+C/Ctrl+A не срабатывали.

Фикс: классификация нажатия по ФИЗИЧЕСКОЙ клавише (Windows virtual key code),
что не зависит от раскладки. Для ЛАТИНИЦЫ возвращаем None, чтобы не дублировать
штатный bind (избегаем двойного копирования).
"""
from czdecoder.shortcuts import (
    classify_shortcut,
    VK_C,
    VK_A,
    CYRILLIC_C_KEYSYMS,
    CYRILLIC_A_KEYSYMS,
)


def test_copy_english_layout():
    # EN: физическая C, латинский keysym 'c' (или 'C' при Shift).
    # Штатный tksheet уже обработает -> мы возвращаем None (без двойного копирования).
    assert classify_shortcut(True, "c", VK_C) is None
    assert classify_shortcut(True, "C", VK_C) is None


def test_copy_russian_layout():
    # RU: физическая C, кириллический keysym. Штатный bind НЕ сработает -> copy.
    assert classify_shortcut(True, "Cyrillic_es", VK_C) == "copy"
    assert classify_shortcut(True, "Cyrillic_ES", VK_C) == "copy"


def test_copy_russian_layout_by_keycode_only():
    # Даже если keysym пришёл неожиданный, физическая клавиша C (keycode 67)
    # всё равно должна классифицироваться как copy.
    assert classify_shortcut(True, "unknown_cyrillic", VK_C) == "copy"


def test_select_all_english_layout():
    assert classify_shortcut(True, "a", VK_A) is None
    assert classify_shortcut(True, "A", VK_A) is None


def test_select_all_russian_layout():
    assert classify_shortcut(True, "Cyrillic_ef", VK_A) == "select_all"
    assert classify_shortcut(True, "Cyrillic_EF", VK_A) == "select_all"


def test_select_all_by_keycode_only():
    assert classify_shortcut(True, "weird", VK_A) == "select_all"


def test_no_ctrl_returns_none():
    # Ctrl не зажат — никакой shortcut не срабатывает, даже при совпадении клавиши.
    assert classify_shortcut(False, "c", VK_C) is None
    assert classify_shortcut(False, "Cyrillic_ef", VK_A) is None


def test_other_keys_do_not_trigger():
    # Другие физические клавиши (например V=86) не должны классифицироваться.
    assert classify_shortcut(True, "v", 86) is None
    assert classify_shortcut(True, "Cyrillic_em", 77) is None  # 'м' (M)


def test_cyrillic_c_values_are_consistent():
    # Защита от случайного расширения наборов: все кириллические 'с' дают copy,
    # все кириллические 'ф' дают select_all.
    for ks in CYRILLIC_C_KEYSYMS:
        assert classify_shortcut(True, ks, VK_C) == "copy"
    for ks in CYRILLIC_A_KEYSYMS:
        assert classify_shortcut(True, ks, VK_A) == "select_all"