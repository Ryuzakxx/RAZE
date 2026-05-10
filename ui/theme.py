"""
ui/theme.py  –  RAZE palette fissa
Sfondo nero #000000, accent viola #320096.
"""

_C = {
    "bg":     "#000000",
    "bg1":    "#0a0a0a",
    "bg2":    "#111111",
    "border": "#2a0060",
    "hi":     "#320096",
    "hi2":    "#5500cc",
    "mid":    "#cccccc",
    "dim":    "#555555",
    "text":   "#eeeeee",
    "glow":   "50,0,150",
    "name":   "default",   # stub: evita KeyError nei file che usano C['name']
}

def get() -> dict:
    return dict(_C)

def set_theme(name: str): pass
def current_name() -> str: return "default"
THEMES = {"default": _C}
