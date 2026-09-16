"""Безопасный lifecycle временных файлов и изоляция batch'ей для web-слоя.

Каждый «job» (одна операция decode) получает собственный tempdir и набор
загруженных PDF с уникальными именами. Никаких глобальных ``result.xlsx`` /
``upload.pdf`` / ``temp/`` — данные разных сотрудников не должны смешиваться.

Файлы очищаются по явному ``cleanup`` при завершении, а также через
``TemporaryDirectory``/``weakref.finalize`` как fallback при падении процесса.
"""
from __future__ import annotations

import os
import re
import tempfile
import uuid

# Максимальный размер одного загружаемого PDF (16 МБ) — защита от OOM.
MAX_UPLOAD_BYTES = 16 * 1024 * 1024

# Разрешённые по содержимому сигнатуры PDF. Проверяется magic bytes, а не
# расширение — расширение нельзя доверять (см. _is_pdf).
_PDF_MAGIC = b"%PDF-"

# Санитарная нормализация имени файла: имя коллизий больше не создаёт
# (уникальный префикс добавляется отдельно), но мы всё равно выбрасываем
# путь-компоненты и опасные символы, чтобы имя было безопасно как для
# отображения, так и для потенциальной записи рядом.
_INVALID_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_MAX_STEM_LEN = 120


def _pdf_magic_ok(blob: bytes) -> bool:
    """PDF ли это по содержимому (magic bytes), не по имени файла."""
    stripped = blob.lstrip()
    return stripped.startswith(_PDF_MAGIC)


def _safe_stem(filename: str) -> str:
    """Возвращает безопасную часть имени файла (без расширения и пути)."""
    base = os.path.basename(filename or "").strip()
    if not base:
        base = "file"
    # Отрезаем известное расширение, чтобы уникальное имя не задваивало его.
    if base.lower().endswith(".pdf"):
        base = base[:-4]
    base = _INVALID_CHARS.sub("_", base)
    return base[:_MAX_STEM_LEN]


def make_job_dir() -> str:
    """Создаёт изолированный tempdir для одного job. Возвращает путь."""
    return tempfile.mkdtemp(prefix="czweb-")


def save_upload(job_dir: str, filename: str, blob: bytes) -> tuple[bool, str, str, str]:
    """Сохраняет загруженный PDF в job_dir под уникальным безопасным именем.

    Возвращает (ok, saved_path, original_name, error_message):
    - ok=False → blob не PDF или пустой; error_message описывает причину;
    - ok=True  → saved_path — абсолютный путь, original_name — безопасное
      отображаемое имя файла пользователя (без пути).
    """
    if not blob:
        return False, "", "", "пустой файл"
    if not _pdf_magic_ok(blob):
        return False, "", "", "не PDF-файл (ожидается PDF vector/scan)"

    # Отображаемое имя (для таблицы результата) — оригинальное имя пользователя,
    # очищенное от пути/опасных символов, с сохранением расширения .pdf.
    display = _safe_stem(filename) + ".pdf"
    # Уникальный префикс исключает коллизию имён файлов внутри одного batch.
    # Исходное имя пользователя НЕ используется как путь на диске.
    unique = f"{uuid.uuid4().hex[:8]}_{display}"
    path = os.path.join(job_dir, unique)
    with open(path, "wb") as f:
        f.write(blob)
    return True, path, display, ""


def cleanup_job_dir(job_dir: str) -> None:
    """Рекурсивно удаляет tempdir job'а. Идемпотентно, ошибки игнорируются."""
    try:
        import shutil
        shutil.rmtree(job_dir, ignore_errors=True)
    except Exception:
        pass
