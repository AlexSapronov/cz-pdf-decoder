"""Декодирование DataMatrix из изображений (обёртка над pylibdmtx)."""
from __future__ import annotations

from PIL import Image, ImageOps, ImageFilter
from pylibdmtx.pylibdmtx import decode


def clean_text(value: str) -> str:
    """Нормализует декодированный текст DM, НЕ трогая GS-разделители.

    CRITICAL: \x1d (GS1 Group Separator) — это ЗНАЧИМЫЕ данные (разделяет AI),
    его нельзя превращать в пробел через str.split(). Удаляем только
    окаймляющие whitespace и непечатаемые символы по краям.
    """
    return str(value).strip()


def decode_datamatrix_from_pil(img: Image.Image) -> list[str]:
    """Пробует несколько предобработок изображения и возвращает
    список уникальных декодированных строк (обычно 0 или 1 элемент)."""
    variants = [
        img,
        ImageOps.grayscale(img),
        ImageOps.autocontrast(ImageOps.grayscale(img)),
    ]
    enlarged = variants[2].resize((variants[2].width * 2, variants[2].height * 2))
    variants.append(enlarged)
    variants.append(enlarged.filter(ImageFilter.SHARPEN))

    found: list[str] = []
    seen: set[str] = set()
    for variant in variants:
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