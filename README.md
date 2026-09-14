# CZ PDF Decoder

Декодер DataMatrix (кодов маркировки Честный ЗНАК) из PDF-документов в Excel.

Программа берёт PDF с этикетками маркировки, находит на каждой странице
DataMatrix-код (GS1), извлекает GTIN, серийный номер, наименование товара (PN)
и количество, и выгружает результат в Excel.

## Возможности

- Загрузка PDF файлов по одному, папкой, или drag-and-drop.
- Распознавание DataMatrix (через `pylibdmtx`) с несколькими вариантами
  предобработки изображения (grayscale, autocontrast, бинаризация, quiet zone,
  увеличение NEAREST).
- Полный структурный разбор GS1 DataMatrix: GTIN (AI `01`, с проверкой
  контрольной цифры) + серийный номер (AI `21`).
- Извлечение наименования (PN) и количества из текстового слоя страницы.
- Экспорт в Excel (`result.xlsx`).

## Структура проекта

```
cz_decoder.py      — GUI (точка входа, tkinter + tksheet)
czdecoder/         — пакет чистой логики (без GUI):
    gs1.py         — разбор GS1 DataMatrix (GTIN, serial)
    datamatrix.py  — декодирование DataMatrix из изображения
    pdf_utils.py   — рендер страницы, извлечение PN/количества
    excel.py       — экспорт в Excel
    pipeline.py    — конвейер файлы → строки результатов
tests/             — тесты pytest
CZ_Decoder_build.spec — конфигурация PyInstaller для сборки EXE
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

## Запуск

```bash
python cz_decoder.py
```

## Тесты

```bash
python -m pytest
```

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

### Требования к среде

- **libdmtx DLL** должна быть установлена вместе с `pylibdmtx` (она не входит
  в pip-wheel `pylibdmtx`, ставится/кладётся отдельно рядом с `pylibdmtx`).
- **Visual C++ Redistributable 2013 x64** может потребоваться на целевой
  машине, если используемая сборка `libdmtx-64.dll` слинкована против
  `msvcr120.dll` / `msvcp120.dll`. Уточните это для вашей конкретной DLL;
  универсального требования нет.

### Локальная последовательность сборки

```powershell
git pull
Remove-Item -Recurse -Force .\build -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\dist  -ErrorAction SilentlyContinue
python -m PyInstaller --clean CZ_Decoder_build.spec
.\dist\CZ_Decoder.exe
```

## Формат GS1 DataMatrix

```
01<GTIN-14>21<serial>[<GS>91… крипто.хвост …]
```

- **GTIN** — 14 цифр после AI `01` (проверяется по контрольной цифре GS1 mod-10).
- **Serial (AI `21`)** — идёт **сразу после GTIN**, без GS-разделителя между
  `01` и `21` (AI `21` имеет переменную длину). Serial читается до первого
  GS (`\x1d`, Group Separator) либо до конца строки.
- **Криптохвост** — AI `91`/`92` идёт **после** serial, отделённый GS. Без GS
  единственный надёжный маркер — литерал `91EE`.
- Сканерные префиксы (`]d2`, `]C1`, `]e0`, `^]`) и `{GS}` нормализуются.

> **Serial — внутреннее поле.** Оно выделяется парсером и хранится в строке
> результата, но **не выводится** ни в таблице GUI, ни в Excel. Вывод Excel
> ограничен колонками: Полный DM, GTIN, PN, Кол-во, Файл, Страница.

## Зависимости

- PyMuPDF (`fitz`)
- Pillow
- pylibdmtx
- openpyxl
- tksheet
- tkinterdnd2 (опционально, drag-and-drop)

## Лицензия

Приватный проект. Все права защищены.
