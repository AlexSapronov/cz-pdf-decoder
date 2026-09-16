"""CZ PDF Decoder — веб-интерфейс (FastAPI) вокруг проверенной логики czdecoder.

Это НЕ новый декодер. Это тонкий web-слой над уже доказанно рабочими модулями
``czdecoder`` (pipeline/gs1/datamatrix/pdf_utils/excel/paths) и desktop-версии
(``cz_decoder.py``), которые не изменяются.

Ключевые требования реализации:
- один batch/job = отдельный изолированный tempdir (no shared result.xlsx / temp/);
- пользовательские PDF не хранятся постоянно — очистка по lifecycle;
- исходный filename пользователя никогда не используется как путь на диске;
- принимаются только PDF;
- API никогда не отдаёт traceback наружу.
"""
