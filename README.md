# CZ PDF Decoder

Декодер DataMatrix (кодов маркировки Честный ЗНАК) из PDF-документов в Excel.

Программа берёт PDF с этикетками маркировки, находит на каждой странице
DataMatrix-код (GS1), извлекает GTIN, серийный номер, наименование товара (PN)
и количество, и выгружает результат в Excel.

## Возможности

- Загрузка PDF файлов по одному, папкой, или drag-and-drop.
- Распознавание DataMatrix (через `pylibdmtx`) с несколькими вариантами
  предобработки изображения (grayscale, autocontrast, увеличение, sharpen).
- Полный разбор GS1 DataMatrix: GTIN (AI `01`) + серийный номер (AI `21`).
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
pyinstaller CZ_Decoder_build.spec
```

`.spec` автоматически подхватывает `libdmtx-64.dll` из папки `pylibdmtx`.

## Формат GS1 DataMatrix

```
01<GTIN-14>21<serial>
```

- **GTIN** — 14 цифр после AI `01`.
- **Serial** — вся строка после GTIN до разделителя группы `\x1d` (не обрезается
  по фиксированной длине).

## Зависимости

- PyMuPDF (`fitz`)
- Pillow
- pylibdmtx
- openpyxl
- tksheet
- tkinterdnd2 (опционально, drag-and-drop)

## Лицензия

Приватный проект. Все права защищены.
