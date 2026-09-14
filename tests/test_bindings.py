"""Regression-тесты на GUI selection bindings.

Баг: sheet.enable_bindings включал "toggle_select" — в tksheet 7.6.0 это
делает каждый обычный левый клик АДДИТИВНЫМ (добавляет/убирает ячейку, не
сбрасывая предыдущее выделение — как будто Ctrl всегда зажат).

Фикс: замена на "single_select" — обычный левый клик сбрасывает выделение и
выбирает одну ячейку (Excel-like). Ctrl+click (ctrl_select) остаётся additive.

Эти тесты требуют Tk — запускать под xvfb (в CI headless). Маркированы, чтобы
их можно было отфильтровать при отсутствии дисплея.
"""
import os
import pytest

tk = pytest.importorskip("tkinter")


def _display_available():
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


@pytest.fixture
def sheet():
    from tksheet import Sheet
    if not _display_available():
        pytest.skip("нет графического дисплея — запускать под xvfb-run")
    root = tk.Tk()
    root.withdraw()
    s = Sheet(root, headers=["A", "B", "C"])
    s.pack()
    s.set_sheet_data([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
    yield s
    root.destroy()


def _enable_target_bindings(sheet):
    from czdecoder.bindings import SHEET_BINDINGS
    sheet.enable_bindings(SHEET_BINDINGS)


def test_single_select_enabled_toggle_disabled(sheet):
    _enable_target_bindings(sheet)
    mt = sheet.MT
    assert mt.single_selection_enabled is True
    assert mt.toggle_selection_enabled is False
    # имена зафиксированы в enabled_bindings
    assert "single_select" in mt.enabled_bindings
    assert "toggle_select" not in mt.enabled_bindings


def test_ctrl_and_drag_select_enabled(sheet):
    _enable_target_bindings(sheet)
    mt = sheet.MT
    assert mt.ctrl_select_enabled is True
    assert mt.drag_selection_enabled is True


def test_select_cell_replaces_previous_selection(sheet):
    """Обычный select_cell (как его вызывает b1_press при single_select)
    сбрасывает предыдущее выделение и оставляет только новую ячейку."""
    _enable_target_bindings(sheet)
    mt = sheet.MT

    # Сначала выделяем A1 (r=0, c=0)
    mt.select_cell(0, 0, redraw=True)
    assert mt.cell_selected(0, 0), "A1 должна быть выделена"
    n_before = len(tuple(mt.selection_boxes))

    # Потом обычный клик на B1 (r=0, c=1) — должен ЗАМЕНИТЬ выделение.
    mt.select_cell(0, 1, redraw=True)
    assert mt.cell_selected(0, 1), "B1 должна быть выделена"
    assert not mt.cell_selected(0, 0), "A1 должна быть СБРОШЕНА (не additive)"


def test_ctrl_add_selection_is_additive(sheet):
    """Ctrl+клик (add_selection через ctrl_select) — аддитивно: A1 и B1 вместе."""
    _enable_target_bindings(sheet)
    mt = sheet.MT

    mt.select_cell(0, 0, redraw=True)
    mt.add_selection(0, 1, set_as_current=True)
    assert mt.cell_selected(0, 0), "A1 остаётся выделенной"
    assert mt.cell_selected(0, 1), "B1 добавлена"


def test_readonly_edit_bindings_not_enabled(sheet):
    """Таблица read-only: edit/paste/cut/delete/undo/redo НЕ включены."""
    _enable_target_bindings(sheet)
    mt = sheet.MT
    for name in ("cut", "paste", "delete", "undo", "redo", "edit_cell", "edit", "edit_bindings"):
        assert name not in mt.enabled_bindings, f"{name} не должен быть включён"


def test_sheet_bindings_constant_uses_single_not_toggle():
    """Список SHEET_BINDINGS обязан содержать single_select, а не toggle_select."""
    from czdecoder.bindings import SHEET_BINDINGS
    assert "single_select" in SHEET_BINDINGS
    assert "toggle_select" not in SHEET_BINDINGS
    assert "ctrl_select" in SHEET_BINDINGS
    assert "drag_select" in SHEET_BINDINGS