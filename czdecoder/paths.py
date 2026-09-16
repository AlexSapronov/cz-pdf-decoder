"""Помощники для работы с путями PDF и общей папкой сохранения.

Правило «общая папка»: результат можно сохранить «рядом с PDF» только если
ВСЕ исходные PDF лежат физически в ОДНОЙ И ТОЙ ЖЕ директории. Общий родитель
(через os.path.commonpath) НЕ считается: C:\\Orders\\a\\a.pdf и
C:\\Orders\\b\\b.pdf лежат в разных папках, хотя и имеют общего предка.
"""
from __future__ import annotations

import os


#: Служебные статусные префиксы, которые могут стоять в начале имени папки.
_STATUS_PREFIXES = ("ЭМ_", "ВВО_", "ООН_")


def result_filename_from_directory(directory: str) -> str:
    """Формирует имя файла результата из имени директории PDF.

    Имя папки может начинаться с одного из служебных статусных префиксов
    (``ЭМ_``, ``ВВО_``, ``ООН_``) — такой префикс отбрасывается (сравнение
    case-insensitive, только в начале). Остальная часть имени сохраняется
    без изменений.

    >>> result_filename_from_directory("ABC123")
    'result_ABC123.xlsx'
    >>> result_filename_from_directory("ЭМ_ABC123")
    'result_ABC123.xlsx'
    """
    base = os.path.basename(os.path.normpath(directory))
    for prefix in _STATUS_PREFIXES:
        if base.lower().startswith(prefix.lower()):
            base = base[len(prefix):]
            break
    return f"result_{base}.xlsx"


def get_common_pdf_directory(rows: list[dict]) -> str | None:
    """Возвращает единственную общую директорию исходных PDF, либо None.

    - rows пуст → None;
    - все уникальные file_path в одной директории → эта директория (нормализованная);
    - файлы в разных директориях → None.
    """
    if not rows:
        return None

    dirs: dict[str, str] = {}
    seen_paths = set()
    for r in rows:
        fp = r.get("file_path")
        if not fp:
            continue
        if fp in seen_paths:
            continue
        seen_paths.add(fp)
        d = os.path.normpath(os.path.dirname(os.path.abspath(fp)))
        key = os.path.normcase(d)
        dirs.setdefault(key, d)

    if not dirs:
        return None
    if len(dirs) != 1:
        return None
    return next(iter(dirs.values()))


def can_save_next_to_pdf(rows: list[dict], recognized: bool) -> bool:
    """Можно ли сохранить «рядом с PDF»: есть строки, распознано, общая папка одна."""
    if not rows:
        return False
    if not recognized:
        return False
    return get_common_pdf_directory(rows) is not None