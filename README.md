# CZ PDF Decoder v3.1

GUI-утилита для пакетного декодирования DataMatrix кодов маркировки
«Честный ЗНАК» из PDF-файлов с выгрузкой результата в Excel.

Работает с:

- отдельными PDF;
- несколькими выбранными PDF;
- целой папкой;
- drag-and-drop.

## Возможности

- Пакетная загрузка PDF (файлы, папка, drag-and-drop).
- Обработка многостраничных PDF (по одной строке результата на страницу).
- Распознавание одного DataMatrix на страницу (через `pylibdmtx`).
- Несколько fallback-вариантов предобработки изображения:
  - legacy: grayscale, autocontrast, увеличение ×2, sharpen;
  - enhanced: бинаризация, quiet zone, NEAREST upscale;
  - embedded raster images в native-разрешении.
- Структурный разбор GS1 DataMatrix:
  - GTIN (AI `01`, 14 цифр, проверка контрольной цифры GS1 mod-10);
  - serial (AI `21`) — выделяется и хранится **внутренне**;
  - полный DM сохраняется целиком.
- Извлечение PN и количества из **текстового слоя** PDF (не OCR).
- Таблица результатов:
  - read-only;
  - Excel-like single selection;
  - Ctrl+click — multi-select;
  - drag-select — прямоугольный диапазон;
  - выбор строки / столбца (клик по заголовку / номеру строки);
  - Ctrl+A — выделить всё;
  - Ctrl+C — копировать (TAB / перевод строки);
  - Ctrl+C / Ctrl+A работают и при русской раскладке Windows.
- Экспорт результата в `result.xlsx`.
- Две кнопки сохранения:
  1. **«Сохранить Excel»** — открывает выбор папки;
  2. **«Сохранить рядом с PDF»** — доступна, если все исходные PDF
     находятся в одной и той же папке, и сохраняет `result.xlsx` туда
     автоматически (без диалога).

> Программа **не OCR'ит сканы**. PN и количество извлекаются из текстового
> слоя PDF. Распознаётся один DataMatrix на страницу.

## Формат Excel

Колонки выходного файла `result.xlsx`:

- Полный DM
- GTIN
- PN
- Кол-во
- Файл
- Страница

> **Serial (AI 21)** парсится и хранится во внутреннем поле строки результата,
> но **не выводится** отдельной колонкой ни в GUI, ни в Excel.

## Структура проекта

```
cz_decoder.py      — GUI (точка входа, tkinter + tksheet)
czdecoder/         — пакет чистой логики (без GUI):
    gs1.py         — структурный разбор GS1 DataMatrix (GTIN, serial)
    datamatrix.py  — декодирование DataMatrix (pylibdmtx + distutils-совместимость)
    pipeline.py    — конвейер файлы → строки результатов
    pdf_utils.py   — рендер страницы, извлечение PN/количества
    excel.py       — экспорт в Excel
    paths.py       — определение общей папки PDF для «Сохранить рядом с PDF»
    shortcuts.py   — layout-independent классификация Ctrl+C / Ctrl+A
    bindings.py    — набор selection-биндингов tksheet (read-only таблица)
    version.py     — версия приложения (APP_VERSION)
tests/             — набор pytest
CZ_Decoder_build.spec — конфигурация PyInstaller для сборки EXE
requirements.txt  — зависимости
```

## Установка

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

> Для `pylibdmtx` на Windows нужна библиотека `libdmtx` (DLL). См. раздел «Сборка EXE».

## Использование

1. Загрузить PDF — файл, папку или drag-and-drop.
2. Нажать «Распознать».
3. Проверить таблицу результатов.
4. При необходимости скопировать ячейки / диапазоны через Ctrl+C.
5. Сохранить результат:
   - «Сохранить Excel» (выбрать папку) или
   - «Сохранить рядом с PDF» (если все PDF в одной папке).

## Тесты

```bash
python -m pytest
```

Набор regression/unit-тестов покрывает GS1 parsing, DataMatrix preprocessing,
version compatibility, GUI bindings, keyboard shortcuts и path logic.

## Сборка Windows EXE

```bash
pip install pyinstaller
python -m PyInstaller --clean CZ_Decoder_build.spec
```

Файл `CZ_Decoder_build.spec`:

- автоматически находит `libdmtx-64.dll` (для 64-бит Python) или
  `libdmtx-32.dll` (для 32-бит) в `pylibdmtx` внутри `site-packages`
  или user-site (`%APPDATA%\Roaming\Python\Python3xx\site-packages`);
- кладёт DLL в **корень** собранного приложения (рядом с `CZ_Decoder.exe`),
  чтобы `pylibdmtx` нашёл её при запуске EXE;
- если DLL не найдена — сборка падает с понятным сообщением, а не собирает
  заведомо нерабочий EXE.

### Зависимость от libdmtx DLL

- **libdmtx DLL** должна быть доступна в каталоге `pylibdmtx` (она не входит
  в pip-wheel `pylibdmtx`, ставится/кладётся отдельно).
- **Visual C++ Redistributable 2013 x64** может потребоваться на целевой
  машине, если используемая сборка `libdmtx-64.dll` слинкована против
  `msvcr120.dll` / `msvcp120.dll`. Для конкретной DLL это уточняется отдельно;
  универсального требования нет.

### Совместимость distutils (Python 3.12+)

`pylibdmtx` использует `distutils.version.LooseVersion` для выбора ctypes-layout
в зависимости от версии `libdmtx`. На Python 3.12+ `distutils` удалён из
stdlib, поэтому проект через `_ensure_distutils()` подставляет настоящий
`setuptools._distutils.version.LooseVersion` (compatibility shim).

> Troubleshooting: ранее использовался самописный `_FakeLooseVersion`, чей
> некорректный компаратор заставлял `pylibdmtx` выбирать неверный layout для
> libdmtx 0.7.4 и приводил к access violation. Исторический баг исправлен
> переходом на настоящий `LooseVersion`; самописного компаратора больше нет.

### Локальная последовательность сборки

```powershell
git pull
Get-Process CZ_Decoder -ErrorAction SilentlyContinue | Stop-Process -Force
Remove-Item -Recurse -Force .\build -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\dist  -ErrorAction SilentlyContinue
python -m PyInstaller --clean CZ_Decoder_build.spec
.\dist\CZ_Decoder.exe
```

> `Stop-Process` нужен потому, что Windows не даст PyInstaller перезаписать
> запущенный `CZ_Decoder.exe`.

## Формат GS1 DataMatrix

```
01<GTIN-14>21<serial>[<GS>91… крипто.хвост …]
```

- **GTIN** — 14 цифр после AI `01` (проверяется по контрольной цифре GS1 mod-10).
- **Serial (AI 21)** — идёт **сразу после GTIN**, без GS-разделителя. Читается
  до первого GS (`\x1d`) либо до конца строки.
- **Криптохвост** — AI `91`/`92` идёт после serial, отделённый GS (без GS —
  маркер `91EE`).
- Сканерные префиксы (`]d2`, `]C1`, `]e0`, `^]`) и `{GS}` нормализуются.

## Зависимости

- PyMuPDF (`fitz`)
- Pillow
- pylibdmtx
- openpyxl
- tksheet
- tkinterdnd2

## Что нового в v3.1

- исправлена стабильность DataMatrix decoding на Windows / Python 3.14;
- исправлена совместимость с libdmtx 0.7.4;
- улучшена обработка PDF и fallback decoding;
- Excel-like selection в таблице;
- Ctrl+C / Ctrl+A не зависят от EN/RU раскладки;
- добавлено «Сохранить рядом с PDF»;
- проведена проверка на большом реальном наборе PDF.

## Лицензия

Приватный проект. Все права защищены.