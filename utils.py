# -*- coding: utf-8 -*-
"""
utils.py — helpers for iVMS/Hikvision attlog viewer

Key point: iVMS-4200 sometimes writes Russian text into DB as mojibake like
'РџСЂРѕС…РѕРґРЅР°СЏ' instead of 'Проходная'. We fix it in code.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Optional

# ===== Time helpers =====

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_dt(s: Optional[str], default: Optional[datetime] = None) -> Optional[datetime]:
    """Parse 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DD'. Return default if empty/invalid."""
    if not s:
        return default
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return default


def format_duration(td: timedelta) -> str:
    total = int(td.total_seconds())
    if total < 0:
        total = 0
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


# ===== Direction helpers =====

def normalize_direction(d: Any) -> str:
    """Normalize direction to 'vhod' / 'vihod' where possible."""
    if not isinstance(d, str):
        return ""
    d = d.strip().lower()
    if d in ("vhod", "in", "enter", "entry", "вход"):
        return "vhod"
    if d in ("vihod", "out", "exit", "выход"):
        return "vihod"
    return d


# ===== Hikvision mojibake fix =====

_MOJIBAKE_MARKERS = (
    "Рџ", "РЎ", "Р°", "Рµ", "Рё", "РЅ", "Рѕ", "Рї",
    "СЂ", "СЃ", "С‚", "Сѓ", "С…", "СЏ", "СЌ", "СЋ", "СЊ"
)

def is_mojibake_ru(s: str) -> bool:
    """Detect typical 'РџСЂ...' style mojibake."""
    if not s:
        return False
    if any(m in s for m in _MOJIBAKE_MARKERS):
        return True
    rs = s.count("Р") + s.count("С")
    return rs >= 3 and rs / max(1, len(s)) > 0.12


def score_russian(s: str) -> int:
    return len(re.findall(r"[А-Яа-яЁё]", s))


def fix_hik_text(s: Any) -> Any:
    """
    Fix Hikvision/iVMS mojibake and return best candidate.
    Keeps original type for non-strings.
    """
    if not isinstance(s, str) or not s:
        return s

    candidates: list[str] = [s]

    # 1) Classic: UTF-8 bytes were decoded as CP1251 and stored as Unicode
    # Example: 'РџСЂ...' -> should become 'Про...'
    if is_mojibake_ru(s):
        try:
            candidates.append(s.encode("cp1251", errors="strict").decode("utf-8", errors="strict"))
        except Exception:
            try:
                candidates.append(s.encode("cp1251", errors="ignore").decode("utf-8", errors="ignore"))
            except Exception:
                pass

    # 2) Rare case: latin-1 -> cp1251 garbage like '» µ¶ °'
    if any(ch in s for ch in ("»", "µ", "¶", "°", "¬", "¦")):
        try:
            candidates.append(s.encode("latin-1", errors="ignore").decode("cp1251", errors="ignore"))
        except Exception:
            pass

    def score(c: str) -> tuple[int, int, int]:
        # prefer non-mojibake; then more Cyrillic; then fewer 'Р'/'С'
        moj = 1 if is_mojibake_ru(c) else 0
        rus = score_russian(c)
        penalty = (c.count("Р") + c.count("С"))
        return (moj, -rus, penalty)

    best = sorted(candidates, key=score)[0]
    return best.strip()


def to_hik_mojibake(s: Any) -> Any:
    """
    Convert normal Russian text to the *same* mojibake form that iVMS stores in DB,
    so we can match rows by deviceName/personName in SQL.

    'Проходная' -> 'РџСЂРѕС…РѕРґРЅР°СЏ'
    """
    if not isinstance(s, str) or not s:
        return s
    try:
        return s.encode("utf-8").decode("cp1251", errors="ignore")
    except Exception:
        return s

# Backward compatible alias used by older files
try_fix_cp1251_mojibake = fix_hik_text
