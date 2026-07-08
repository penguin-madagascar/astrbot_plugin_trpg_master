from __future__ import annotations


def detect_language_from_theme(theme: str) -> str:
    text = (theme or "").strip()
    if not text:
        return "zh"

    counts = {
        "zh": 0,
        "ja": 0,
        "ko": 0,
        "latin": 0,
    }
    meaningful = 0
    for char in text:
        code = ord(char)
        if "\u4e00" <= char <= "\u9fff":
            counts["zh"] += 1
            meaningful += 1
        elif ("\u3040" <= char <= "\u30ff") or ("\u31f0" <= char <= "\u31ff"):
            counts["ja"] += 1
            meaningful += 1
        elif "\uac00" <= char <= "\ud7af":
            counts["ko"] += 1
            meaningful += 1
        elif char.isalpha() and code < 0x024F:
            counts["latin"] += 1
            meaningful += 1

    if counts["ja"] >= 2:
        return "ja"
    if counts["ko"] >= 2:
        return "ko"
    if counts["zh"] >= 2:
        return "zh"
    if meaningful and counts["latin"] / meaningful >= 0.7:
        return "en"
    return "zh"
