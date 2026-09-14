"""Декодирование DataMatrix из изображений (обёртка над pylibdmtx).

ВНИМАНИЕ: pylibdmtx импортируется ЛЕНИВО (внутри decode_datamatrix_from_pil),
потому что pylibdmtx>=0.1.10 в top-level делает `from distutils.version import
LooseVersion`, а `distutils` удалён из stdlib в Python 3.12 (доступен только
через setuptools). Ленивый импорт позволяет `import czdecoder` и импорт сугубо
текстовых модулей (gs1/pdf_utils/pipeline/excel) работать на 3.12 без
pylibdmtx, который нужен лишь при реальном decode растра.
"""
from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from PIL import Image, ImageOps, ImageFilter

if TYPE_CHECKING:
    from pylibdmtx.pylibdmtx import decode as _decode

# pylibdmtx (wrapper.py) требует distutils.version.LooseVersion. На Python 3.12
# distutils удалён из stdlib; ставку делаем на setuptools._distutils (есть на
# CI-раннерах). Подставляем только если distutils реально отсутствует — это
# идемпотентный shim, не ломающий 3.11.
def _ensure_distutils():
    try:
        import distutils.version  # noqa: F401
        return
    except ImportError:
        pass
    try:
        import setuptools  # noqa: F401
        from setuptools import _distutils  # noqa: F401
        sys.modules.setdefault("distutils", _distutils)
    except ImportError:
        pass


def clean_text(value: str) -> str:
    """Нормализует декодированный текст DM, НЕ трогая GS-разделители.

    CRITICAL: \\x1d (GS1 Group Separator) — это ЗНАЧИМЫЕ данные (разделяет AI),
    его нельзя превращать в пробел через str.split(). Удаляем только
    окаймляющие whitespace и непечатаемые символы по краям.
    """
    return str(value).strip()


def _legacy_variants(img: Image.Image) -> list[Image.Image]:
    """ТОЧНЫЙ репродукция raster preprocessing из доказанно рабочего
    baseline (cz_decoder(1).py).

    Порядок и параметры обязаны совпадать байт-в-байт с рабочим файлом:
      - original
      - grayscale
      - autocontrast(grayscale)
      - autocontrast(grayscale) resize ×2 (resampling НЕ указан — дефолт Pillow)
      - тот же resize ×2 + ImageFilter.SHARPEN
    """
    variants = [
        img,
        ImageOps.grayscale(img),
        ImageOps.autocontrast(ImageOps.grayscale(img)),
    ]
    enlarged = variants[2].resize((variants[2].width * 2, variants[2].height * 2))
    variants.append(enlarged)
    variants.append(enlarged.filter(ImageFilter.SHARPEN))
    return variants


def _binarize(img: Image.Image, threshold: int = 128) -> Image.Image:
    """Строгая бинаризация в ч/б (0/255).

    pylibdmtx/libdmtx чувствителен к полутонам и антиалиасингу: embedded
    raster DataMatrix часто имеет серые пиксели по краям модулей, из-за чего
    decode на «сыром» изображении возвращает пустой результат, хотя модули
    визуально различимы. Жёсткий порог убирает серые переходы.
    """
    gray = ImageOps.grayscale(img)
    return gray.point(lambda p: 0 if p < threshold else 255)


def _enhanced_variants(img: Image.Image) -> list[Image.Image]:
    """Дополнительные fallback-стратегии (НЕ заменяют legacy, а идут после).

    Используются только если ни один legacy-вариант не декодировал код.
    Покрывают embedded raster с антиалиасингом: бинаризация + нарастающая
    quiet zone (border) + NEAREST upscale.
    """
    variants: list[Image.Image] = []

    binimg = _binarize(img)
    for border in (0, 4, 8, 16):
        bordered = binimg if border == 0 else ImageOps.expand(
            binimg, border=border, fill=255)
        variants.append(bordered)

    # Увеличение бинаризованного символа через NEAREST (не размывает модули).
    enlarged = binimg.resize(
        (binimg.width * 3, binimg.height * 3), Image.Resampling.NEAREST)
    enlarged = ImageOps.expand(enlarged, border=16, fill=255)
    variants.append(enlarged)

    return variants


def decode_datamatrix_from_pil(img: Image.Image) -> list[str]:
    """Пробует несколько предобработок изображения и возвращает
    список уникальных декодированных строк (обычно 0 или 1 элемент).

    Стратегия:
      1) legacy variants (доказанно рабочий baseline);
      2) enhanced variants (бинаризация/quiet zone/NEAREST) — fallback.
    """
    _ensure_distutils()
    from pylibdmtx.pylibdmtx import decode  # ленивый импорт (см. docstring)

    found: list[str] = []
    seen: set[str] = set()
    for variant in _legacy_variants(img) + _enhanced_variants(img):
        try:
            results = decode(variant)
        except Exception:
            continue
        for item in results:
            text = clean_text(item.data.decode("utf-8", errors="ignore"))
            if text and text not in seen:
                seen.add(text)
                found.append(text)
        if found:
            break
    return found