"""GS1-aware разбор Data Matrix маркировки «Честный ЗНАК».

Формат payload (подтверждён production-парсером gis_app/datamatrix.py):
    01<GTIN-14>21<serial>[<GS>...криптохвост AI 91/92...]

Ключевые правила (НЕ выдуманы — это поведение реального ЧЗ-кода):
- GTIN ищем структурно: AI «01» + ровно 14 цифр + AI «21». Между «01» и «21»
  НЕТ GS-разделителя — AI 21 идёт сразу после GTIN (фикс. длина 14).
- Serial начинается сразу после конца «21» и идёт до ПЕРВОГО GS («\\x1d»)
  либо до конца строки. Без GS единственный надёжный маркер криптохвоста —
  литерал «91EE» (AI 91 c прикладным значением EE — кодирование криптохвоста ЧЗ).
- Произвольную последовательность цифр (91xx/92x/240/3103/93) НЕ считаем
  AI-границей внутри serial — она может быть легальной частью serial.
- GTIN проверяется по контрольной цифре (GS1 mod-10).
- Сканерные префиксы (]d2, ]C1, ]e0, ^), замены {GS} → \\x1d нормализуются.

ВАЖНО про разницу с baseline:
  - Baseline (472b7fd) брал GTIN из «первого сегмента до \\x1d» и НЕ выделял
    serial вовсе. Этот модуль добавляет корректный structural parsing serial,
    сохраняя извлечение GTIN совместимым (14 цифр после «01»).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

GS = "\x1d"  # GS1 Group Separator (FNC1 в GS1 Data Matrix)

# AI 01 + ровно 14 цифр + AI 21. Serial начинается сразу после match.end().
_PATTERN_01_21 = re.compile(r"01(\d{14})21")

# Кодирование криптохвоста ЧЗ: AI 91 c прикладным значением "EE".
# Без GS это единственный надёжный маркер криптохвоста.
_PATTERN_91EE = re.compile(r"91EE")

# Символные/scanner prefixes, которые могут оказаться перед GS1.
_SCANNER_PREFIXES = (
    "]d2",   # Data Matrix ECC200
    "]C1",   # GS1 DataMatrix (AIM)
    "]e0",   # GS1 DataMatrix (AIM, альтернативный)
    "^]",    # ASCII GS-замена (FNC1)
)


def _normalize_scanner_prefix(s: str) -> str:
    for p in _SCANNER_PREFIXES:
        if s.startswith(p):
            return s[len(p):]
    return s


def gtin_checksum_valid(gtin: str) -> bool:
    """Проверка контрольной цифры GTIN-14 (GS1 mod-10)."""
    if len(gtin) != 14 or not gtin.isdigit():
        return False
    digits = [int(c) for c in gtin]
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(digits[:13]))
    check = (10 - (total % 10)) % 10
    return check == digits[13]


def _extract_serial(full: str, pos: int) -> tuple[str, str]:
    """После `pos` (конец «21») отделяет serial от хвоста.

    Serial до первого GS; без GS — до литерала «91EE». Возвращает (serial, tail).
    """
    rest = full[pos:]
    if GS in rest:
        serial, tail = rest.split(GS, 1)
        return serial, GS + tail
    m = _PATTERN_91EE.search(rest)
    if m:
        return rest[: m.start()], rest[m.start():]
    return rest, ""


@dataclass
class ParsedResult:
    """Результат разбора одного Data Matrix кода."""
    full_dm: str = ""
    gtin: str = ""
    serial: str = ""
    tail: str = ""
    has_crypto: bool = False
    valid: bool = True
    error: str = ""


def parse_gs1_datamatrix(raw: str) -> dict:
    """Полный разбор DM. Возвращает dict {full_dm, gtin, serial, tail,
    has_crypto, valid, error} — без выброса исключений.

    Сохраняет обратную совместимость по ключам 'gtin' и 'full_dm' (baseline
    отдавал их как dict), добавляя 'serial'/'tail'/'has_crypto'/'valid'/'error'.
    """
    if not isinstance(raw, str):
        raw = ""

    out = {
        "full_dm": raw,
        "gtin": "",
        "serial": "",
        "tail": "",
        "has_crypto": False,
        "valid": True,
        "error": "",
    }

    s = raw.strip()
    if not s:
        out["valid"] = False
        out["error"] = "Пустой код"
        return out

    s = _normalize_scanner_prefix(s)
    s = s.replace("{GS}", GS).replace("^]", GS).replace("\r", "").replace("\n", "")

    m = _PATTERN_01_21.search(s)
    if not m:
        out["valid"] = False
        out["error"] = "Не найдена структура 01(GTIN)21(serial)"
        return out

    gtin = m.group(1)
    out["gtin"] = gtin

    if not gtin_checksum_valid(gtin):
        out["valid"] = False
        out["error"] = "Неверная контрольная цифра GTIN"
        return out

    serial, tail = _extract_serial(s, m.end())
    out["serial"] = serial
    out["tail"] = tail

    if not serial:
        out["valid"] = False
        out["error"] = "Не найден serial (после AI 21)"
        return out

    if tail and (("91" in tail) or ("92" in tail) or ("91EE" in tail)):
        out["has_crypto"] = True

    return out


def split_ai(raw: str) -> dict:
    """Совместимая обёртка: разбивает DM на {AI: value}, используя GS.

    Оставлена для обратной совместимости существующих вызовов; использует
    тот же структурный разбор (01 + 14 + 21), а не наивный split по GS.
    """
    parsed = parse_gs1_datamatrix(raw)
    ais: dict[str, str] = {}
    if parsed["gtin"]:
        ais["01"] = parsed["gtin"]
    if parsed["serial"]:
        ais["21"] = parsed["serial"]
    # Хвост/crypto AI (91/92) сохраняем, если есть GS-поток.
    if parsed["tail"].startswith(GS):
        for seg in parsed["tail"].split(GS)[1:]:
            if len(seg) >= 2:
                ais[seg[:2]] = seg[2:]
    return ais