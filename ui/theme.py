"""
ui/theme.py
Gestione tema colore globale di RAZE.
Colori disponibili: white, green, purple, cyan
"""

THEMES = {
    "white":  {"hi": "#ffffff", "mid": "#888888", "dim": "#333333", "glow": "255,255,255"},
    "green":  {"hi": "#00ff41", "mid": "#007a1f", "dim": "#003b0f", "glow": "0,255,65"},
    "purple": {"hi": "#bf5fff", "mid": "#7a2fa8", "dim": "#3a1050", "glow": "191,95,255"},
    "cyan":   {"hi": "#00ffff", "mid": "#008888", "dim": "#003333", "glow": "0,255,255"},
}

_current = "white"

def set_theme(name: str):
    global _current
    if name in THEMES:
        _current = name

def get() -> dict:
    t = THEMES[_current]
    return {
        "bg":     "#000000",
        "bg1":    "#0a0a0a",
        "bg2":    "#111111",
        "border": "#1a1a1a",
        "hi":     t["hi"],
        "mid":    t["mid"],
        "dim":    t["dim"],
        "glow":   t["glow"],
        "name":   _current,
    }

def current_name() -> str:
    return _current