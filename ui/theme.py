"""
ui/theme.py  –  RAZE palette fissa
Palette globale usata per tutte le finestre.
"""

_C = {
    "bg":     "#100A1C",
    "bg1":    "#080013",
    "bg2":    "#080411",
    "border": "#34006E",
    "hi":     "#A366FF",
    "hi2":    "#CFA0FF",
    "mid":    "#9C7AD2",
    "dim":    "#7F6B9A",
    "text":   "#EAE4FF",
    "glow":   "163,102,255",
    "name":   "default",
}

def get() -> dict:
    return dict(_C)

def set_theme(name: str): pass
def current_name() -> str: return "default"
THEMES = {"default": _C}
