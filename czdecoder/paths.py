"""Помощники для работы с путями PDF и общей папкой сохранения.

Правило «общая папка»: результат можно сохранить «рядом с PDF» только если
ВСЕ исходные PDF лежат физически в ОДНОЙ И ТОЙ ЖЕ директории. Общий родитель
(через os.path.commonpath) НЕ считается: C:\\Orders\\a\\a.pdf и
C:\\Orders\\b\\b.pdf лежат в разных папках, хотя и имеют общего предка.
"""
from __future__ import annotations

import os


def get_common_pdf_directory(rows: list[dict]) -> str | None:
    """Возвращает единственную общую директорию исходных PDF, либо None.

    - rows пуст → None;
    - все уникальные file_path в одной директории → эта директория (нормализованная);
    - файлы в разных директориях → None.
    """
    if not rows:
        return None

    dirs = set()
    seen_paths = set()
    for r in rows:
        fp = r.get("file_path")
        if not fp:
            continue
        if fp in seen_paths:
            continue
        seen_paths.add(fp)
        d = os.path.dirname(os.path.abspath(fp))
        dirs.add(os.path.normcase(os.path.normpath(d)))

    if not dirs:
        return None
    if len(dirs) != 1:
        return None
    return next(iter(dirs))


def can_save_next_to_pdf(rows: list[dict], recognized: bool) -> bool:
    """Можно ли сохранить «рядом с PDF»: есть строки, распознано, общая папка одна."""
    if not rows:
        return False
    if not recognized:
        return False
    return get_common_pdf_directory(rows) is not None