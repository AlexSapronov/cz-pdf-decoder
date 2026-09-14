"""Keyboard-layout-independent shortcuts для tksheet.

Штатные tksheet copy/select_all привязаны к keysym 'c'/'C'/'a'/'A'. При
русской раскладке физическая клавиша C приходит как 'Cyrillic_es', а A —
как 'Cyrillic_ef', поэтому штатный <Control-c>/<Control-a> не срабатывает.

Здесь — чистая (без GUI) логика классификации нажатия: определяется, зажат ли
shortcut, по ФИЗИЧЕСКОЙ клавише (Windows virtual key code), что не зависит от
раскладки. GUI-часть (cz_decoder.py) использует это в своём fallback handler.
"""

# Windows virtual key codes для физических клавиш C и A (не зависят от раскладки).
VK_C = 67
VK_A = 65

# keysym при РУССКОЙ раскладке: физическая C -> 'с', физическая A -> 'ф'.
CYRILLIC_C_KEYSYMS = {"Cyrillic_es", "Cyrillic_ES", "Cyrillic_ER", "Cyrillic_ERU"}
CYRILLIC_A_KEYSYMS = {"Cyrillic_ef", "Cyrillic_EF", "Cyrillic_ah", "Cyrillic_AH"}

# Латиница, которую штатно обрабатывает tksheet. На них не реагируем,
# чтобы не вызвать двойное копирование.
LATIN_C_KEYSYMS = {"c", "C"}
LATIN_A_KEYSYMS = {"a", "A"}


def classify_shortcut(ctrl_pressed, keysym, keycode):
    """Определяет зажатый shortcut независимо от раскладки клавиатуры.

    Возвращает:
      "copy"       — Ctrl + физическая C (латиница 'c' / кириллица 'с')
      "select_all" — Ctrl + физическая A (латиница 'a' / кириллица 'ф')
      None         — не наш shortcut (Ctrl не зажат, либо другая клавиша)

    Ключ определяется по ФИЗИЧЕСКОЙ клавише через virtual key code (keycode):
    VK_C=67, VK_A=65. Они стабильны при смене раскладки, в отличие от keysym.

    Для ЛАТИНИЦЫ возвращаем None: там уже отработал штатный tksheet bind
    (<Control-c>/<Control-a>), и мы сознательно не вмешиваемся, чтобы не
    вызвать двойное копирование. Срабатываем только когда keysym — не
    латиница (т.е. штатный bind гарантированно не сработал).
    """
    if not ctrl_pressed:
        return None

    is_copy_key = keycode == VK_C or keysym in CYRILLIC_C_KEYSYMS
    is_select_key = keycode == VK_A or keysym in CYRILLIC_A_KEYSYMS

    # Латиница уже обработана штатно — не вмешиваемся.
    if is_copy_key and keysym in LATIN_C_KEYSYMS:
        return None
    if is_select_key and keysym in LATIN_A_KEYSYMS:
        return None

    if is_copy_key:
        return "copy"
    if is_select_key:
        return "select_all"
    return None