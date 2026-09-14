"""Набор enable_bindings для главной таблицы распознавания.

Single-select намеренно используется ВМЕСТО toggle_select: в tksheet 7.6.0
toggle_select делает каждый левый клик АДДИТИВНЫМ (добавляет/убирает ячейку,
не сбрасывая предыдущее выделение — как будто Ctrl всегда зажат), а
single_select — обычный левый клик сбрасывает выделение и выбирает одну ячейку.
Это Excel-like поведение по умолчанию.

Таблица остаётся read-only: edit_cell/paste/cut/delete/undo/redo/edit_header/
edit_index намеренно НЕ включены.
"""

SHEET_BINDINGS = (
    "single_select",           # клик = одна ячейка; предыдущее выделение сбрасывается
    "drag_select",             # drag мышью = прямоугольный диапазон
    "column_select",           # клик по заголовку = весь столбец
    "row_select",              # клик по номеру строки = вся строка
    "select_all",              # Ctrl+A = вся таблица
    "ctrl_select",             # Ctrl+клик = добавить/убрать ячейку/область (multi-select)
    "arrowkeys",               # навигация + Shift+стрелки = расширение выделения
    "copy",                    # Ctrl+C → TAB-разделённые колонки, newline-строки
    "column_width_resize",     # менять ширину колонок
    "right_click_popup_menu",
    "rc_select",
)