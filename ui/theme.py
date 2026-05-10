"""
ui/theme.py  –  RAZE palette fissa
Sfondo #141414, accent viola #320096.
"""

# Palette unica — nessun sistema di temi
_C = {
    "bg":     "#141414",
    "bg1":    "#0d0d0d",
    "bg2":    "#1e1e1e",
    "border": "#2a0060",
    "hi":     "#320096",
    "hi2":    "#5500cc",
    "mid":    "#cccccc",
    "dim":    "#555555",
    "text":   "#eeeeee",
    "glow":   "50,0,150",
}

def get() -> dict:
    return dict(_C)

# stub di compatibilità (nel caso altri file chiamino set_theme / current_name)
def set_theme(name: str): pass
def current_name() -> str: return "default"
THEMES = {"default": _C}
