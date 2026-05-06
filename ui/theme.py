"""
ui/theme.py - Temi RAZE con accent arancione come riferimento
"""

THEMES = {
    "orange": {"hi": "#e86c2f", "hi2": "#f0a060", "mid": "#8b949e", "dim": "#30363d", "glow": "232,108,47"},
    "green":  {"hi": "#3fb950", "hi2": "#7ee787", "mid": "#8b949e", "dim": "#30363d", "glow": "63,185,80"},
    "purple": {"hi": "#bc8cff", "hi2": "#d2a8ff", "mid": "#8b949e", "dim": "#30363d", "glow": "188,140,255"},
    "cyan":   {"hi": "#39c5cf", "hi2": "#79e8f0", "mid": "#8b949e", "dim": "#30363d", "glow": "57,197,207"},
}

_current = "orange"

def set_theme(name: str):
    global _current
    if name in THEMES:
        _current = name

def get() -> dict:
    t = THEMES[_current]
    return {
        "bg":     "#0d1117",
        "bg1":    "#161b22",
        "bg2":    "#1c2128",
        "border": "#21262d",
        "hi":     t["hi"],
        "hi2":    t["hi2"],
        "mid":    t["mid"],
        "dim":    t["dim"],
        "text":   "#c9d1d9",
        "glow":   t["glow"],
        "name":   _current,
    }

def current_name() -> str:
    return _current