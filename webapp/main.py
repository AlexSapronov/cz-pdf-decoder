"""Web CZ PDF Decoder — FastAPI приложение поверх модулей ``czdecoder``.

Запуск (из корня репозитория)::

    python -m uvicorn webapp.main:app --reload

Структура endpoints:

    GET  /                     — HTML-интерфейс (Jinja2)
    POST /api/decode           — мультипарт-upload PDF → распознавание → job
    GET  /api/result/{job_id}  — результат (rows) в JSON + имя excel-файла
    GET  /api/download/{job_id}— скачивание сформированного .xlsx

Архитектурно результат существует как Python list[dict] (rows) в job-контексте,
а НЕ как HTML-таблица: из него потом равно собираются и Excel (уже собирается
через существующий ``save_excel``), и в будущем — manifest JSON для
``gis-trueapi``. Точка расширения JSON/manifest помечена TODO — схема ещё не
утверждена, придумывать её заранее не нужно.
"""
from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from czdecoder.excel import save_excel
from czdecoder.paths import result_filename_from_directory
from czdecoder.pipeline import build_page_rows, recognize_row

from . import jobs

_BASE_DIR = Path(__file__).resolve().parent
_TEMPLATES = Jinja2Templates(directory=str(_BASE_DIR / "templates"))

app = FastAPI(title="CZ PDF Decoder (web)", version="0.1.0-experimental")
app.mount("/static", StaticFiles(directory=str(_BASE_DIR / "static")), name="static")

# --- In-process job store -------------------------------------------------

# job_id -> {"rows": list[dict], "excel_name": str, "jdir": str,
#            "created": float, "excel_path": str | None}
# Для MVP достаточно in-process решения (без Redis/Celery/DB). Данные разных
# обработок изолированы уникальным job_id + отдельным tempdir на batch.
# Ограничение по сроку жизни — см. cleanup_jobs (ниже) — защищает от утечек.
_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()

# Job живёт не более 60 минут, затем чистится.
_JOB_TTL_SECONDS = 60 * 60


def _excel_name_from_shipment(shipment: str | None) -> str:
    """Имя Excel по правилам проекта.

    Переиспользует существующий helper ``result_filename_from_directory``,
    который (а) отбрасывает статусные префиксы ``ЭМ_``/``ВВО_``/``ООН_`` и
    (б) формирует ``result_<name>.xlsx``. Для web имя груза — это НЕ директория
    на диске (браузер не передаёт путь Windows), поэтому передаём shipment как
    «имя директории», чтобы префикс-логика осталась единой (не дублируем её).
    """
    if not shipment:
        return "result.xlsx"
    # Нормализуем: убираем расширение, если пользователь случайно вписал .xlsx.
    name = shipment.strip()
    if name.lower().endswith(".xlsx"):
        name = name[:-5]
    if not name:
        return "result.xlsx"
    return result_filename_from_directory(name)


def cleanup_jobs(now: float | None = None) -> None:
    """Удаляет просроченные job'ы (rows + tempdir). Потокобезопасно."""
    now = time.time() if now is None else now
    with _JOBS_LOCK:
        expired = [j for j, d in _JOBS.items() if now - d["created"] > _JOB_TTL_SECONDS]
        for j in expired:
            jobs.cleanup_job_dir(_JOBS[j]["jdir"])
            del _JOBS[j]


def _decode_uploaded(paths: list[str], display_names: list[str] | None = None) -> list[dict]:
    """Распознаёт загруженные PDF используя СУЩЕСТВУЮЩУЮ логику pipeline.

    ``build_page_rows`` + ``recognize_row`` — ровно тот же путь, что и в
    desktop (``cz_decoder.py::recognize``). Ничего не переписываем с нуля.

    ``display_names`` (в порядке ``paths``) — оригинальные имена файлов для
    отображения: подменяем ``file_name`` (которое pipeline берёт из basename
    внутреннего уникального пути) обратно на имя пользователя.
    """
    rows = build_page_rows(paths)
    if display_names:
        name_by_path = dict(zip(paths, display_names))
        for r in rows:
            orig = name_by_path.get(r["file_path"])
            if orig:
                r["file_name"] = orig
    for r in rows:
        recognize_row(r)
    return rows


# --- Endpoints ------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return _TEMPLATES.TemplateResponse(request=request, name="index.html")


@app.post("/api/decode")
async def decode_endpoint(
    shipment: str | None = Form(default=None),
    files: list[UploadFile] = File(default=[]),
):
    """Принимает 1..N PDF, распознаёт их, возвращает job_id для result/download.

    Не отдаёт traceback наружу: любые ошибки нормализуются в HTTPException /
    JSON с concept message.
    """
    cleanup_jobs()

    if not files:
        raise HTTPException(status_code=400, detail="Не передано ни одного файла.")

    jdir = jobs.make_job_dir()
    saved_paths: list[str] = []
    # Отображаемое имя файла (оригинальное имя пользователя) — для file_name.
    saved_names: list[str] = []
    rejected: list[str] = []
    try:
        for uf in files:
            # Не доверяем filename как пути и читаем содержимое в память.
            name = uf.filename or "upload.pdf"
            if not name.lower().endswith(".pdf"):
                # Отбрасываем НЕ-PDF сразу по расширению (быстрая ветка).
                rejected.append(name)
                continue
            blob = await uf.read()
            if len(blob) > jobs.MAX_UPLOAD_BYTES:
                rejected.append(name)
                continue
            ok, path, display, err = jobs.save_upload(jdir, name, blob)
            if not ok:
                rejected.append(name)
            else:
                saved_paths.append(path)
                saved_names.append(display)
    except Exception:
        # Любой сбой до decode → чистим tempdir и не оставляем мусор.
        jobs.cleanup_job_dir(jdir)
        raise HTTPException(
            status_code=400, detail="Не удалось сохранить загруженные файлы."
        )

    if not saved_paths:
        jobs.cleanup_job_dir(jdir)
        raise HTTPException(
            status_code=400,
            detail="Ни один файл не является корректным PDF. Загрузите PDF-файлы.",
        )

    try:
        rows = _decode_uploaded(saved_paths, saved_names)
    except Exception:
        jobs.cleanup_job_dir(jdir)
        raise HTTPException(
            status_code=500,
            detail="Ошибка распознавания. Проверьте, что PDF содержат DataMatrix.",
        )

    excel_name = _excel_name_from_shipment(shipment)
    job_id = uuid.uuid4().hex
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "rows": rows,
            "excel_name": excel_name,
            "jdir": jdir,
            "created": time.time(),
            "excel_path": None,
        }

    return JSONResponse({
        "job_id": job_id,
        "total_pages": len(rows),
        "rows": _public_rows(rows),
        "excel_name": excel_name,
        "rejected_files": rejected,
    })


def _public_rows(rows: list[dict]) -> list[dict]:
    """Сериализуемая проекция строк результата для фронтенда.

    Отдаём только отображаемые поля (как в desktop-таблице). Внутренние поля
    (file_path, serial) остаются в job-контексте для Excel/будущего manifest.
    """
    return [
        {
            "full_dm": r.get("full_dm", ""),
            "gtin": r.get("gtin", ""),
            "pn": r.get("pn", ""),
            "qty": r.get("qty", ""),
            "file_name": r.get("file_name", ""),
            "page_num": r.get("page_num", ""),
        }
        for r in rows
    ]


def _get_job(job_id: str) -> dict:
    cleanup_jobs()
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Обработка не найдена или истекла.")
        return job


@app.get("/api/result/{job_id}")
def result_endpoint(job_id: str):
    """Возвращает распознанные rows + имя excel-файла для job'а.

    Результат — нормальный Python list[dict], а не HTML. Из него фронтенд
    рисует таблицу, а download-эндпоинт собирает Excel через ``save_excel``.
    """
    job = _get_job(job_id)
    return JSONResponse({
        "job_id": job_id,
        "excel_name": job["excel_name"],
        "rows": _public_rows(job["rows"]),
    })


@app.get("/api/download/{job_id}")
def download_endpoint(job_id: str):
    """Собирает (лениво, кэшируя) и отдаёт Excel через существующий save_excel."""
    job = _get_job(job_id)
    # TODO(manifest): в будущем здесь же (не здесь — рядом) будет формироваться
    # manifest_<name>.json для gis-trueapi. Excel остаётся единственным output
    # на этапе MVP; точка расширения — rows в job['rows'].
    excel_path = job.get("excel_path")
    if not excel_path:
        path = str(Path(job["jdir"]) / job["excel_name"])
        save_excel(job["rows"], path)
        with _JOBS_LOCK:
            job["excel_path"] = path
        excel_path = path
    return FileResponse(
        excel_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=job["excel_name"],
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Любая необработанная ошибка — в JSON без traceback."""
    return JSONResponse(
        status_code=500,
        content={"detail": "Внутренняя ошибка сервера."},
    )
