"""
ui/theme.py  –  RAZE palette
Sfondo grigio scuro (#1a1a1a / #111) con accent colore.
"""

THEMES = {
    "orange": {"hi": "#e86c2f", "hi2": "#f0a060", "mid": "#cccccc", "dim": "#666666", "glow": "232,108,47"},
    "green":  {"hi": "#39ff6e", "hi2": "#7effaa", "mid": "#cccccc", "dim": "#666666", "glow": "57,255,110"},
    "purple": {"hi": "#bc8cff", "hi2": "#d2a8ff", "mid": "#cccccc", "dim": "#666666", "glow": "188,140,255"},
    "cyan":   {"hi": "#00e5ff", "hi2": "#79e8f0", "mid": "#cccccc", "dim": "#666666", "glow": "0,229,255"},
}

_current = "orange"

def set_theme(name: str):
    global _current
    if name in THEMES:
        _current = name

def get() -> dict:
    t = THEMES[_current]
    return {
        "bg":     "#1a1a1a",   # grigio scuro principale
        "bg1":    "#111111",   # grigio quasi nero (titlebar, statusbar)
        "bg2":    "#222222",   # grigio medio (card hover)
        "border": "#333333",   # bordo a riposo
        "hi":     t["hi"],
        "hi2":    t["hi2"],
        "mid":    t["mid"],    # testo principale (#ccc)
        "dim":    t["dim"],    # testo secondario (#666)
        "text":   "#eeeeee",
        "glow":   t["glow"],
        "name":   _current,
    }

def current_name() -> str:
    return _current
