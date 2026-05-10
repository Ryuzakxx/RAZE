"""
ui/mode_select.py  –  RAZE :: SELECT_MODE
Layout minimale per la scelta della modalità, con palette dark e dettagli neon.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFontDatabase

from ui.theme import get


# ── Font setup ─────────────────────────────────────────────────────────────

def _reg_fonts():
    base = QFontDatabase.applicationFontFamilies
    path = ""
    # Carica solo se la cartella assets esiste
    try:
        base_path = __import__("os").path
        assets = base_path.normpath(base_path.join(base_path.dirname(__file__), "..", "assets"))
        for f in ("SpaceMono-Regular.ttf", "SpaceMono-Bold.ttf", "SpaceMono-Italic.ttf", "SpaceMono-BoldItalic.ttf"):
            p = base_path.join(assets, f)
            if base_path.exists(p):
                QFontDatabase.addApplicationFont(p)
    except Exception:
        pass

_reg_fonts()
_FF = "'Space Mono','Courier New',monospace"
C = get()


# ── Stylesheet globale ─────────────────────────────────────────────────────

_STYLESHEET = f"""
* {{
    background-color: {C['bg']};
    color: {C['text']};
    font-family: {_FF};
    font-size: 13px;
    border: none;
}}
QWidget {{ background-color: {C['bg']}; }}
QLabel {{ background: transparent; }}
QFrame#panel {{ background: {C['bg1']}; border: 1px solid {C['border']}; border-radius: 10px; }}
QPushButton {{
    color: {C['text']};
    background: transparent;
    border: 1px solid {C['border']};
    padding: 12px 18px;
    min-width: 140px;
}}
QPushButton:hover {{
    background: {C['border']};
    color: {C['hi']};
}}
QPushButton#accent {{
    border-color: {C['hi']};
    color: {C['hi']};
}}
QLabel#title {{
    color: {C['hi']};
    font-size: 28px;
    letter-spacing: 2px;
}}
QLabel#subtitle {{
    color: {C['text']};
    font-size: 13px;
    line-height: 1.5;
}}
QLabel#hint {{
    color: {C['mid']};
    font-size: 11px;
    letter-spacing: 1px;
}}
"""


class ModeSelectWindow(QWidget):
    mode_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("RAZE")
        self.setMinimumSize(540, 360)
        self.resize(760, 460)
        self._build()

    def _build(self):
        self.setStyleSheet(_STYLESHEET)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(24)

        header = QLabel("RAZE")
        header.setObjectName("title")
        root.addWidget(header)

        description = QLabel("Scegli la modalità e avvia l’assistente. Nessun pannello extra, solo l’essenziale.")
        description.setObjectName("subtitle")
        description.setWordWrap(True)
        root.addWidget(description)

        card = QFrame()
        card.setObjectName("panel")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 22, 22, 22)
        card_layout.setSpacing(20)

        prompt = QLabel("Seleziona la modalità:")
        prompt.setObjectName("subtitle")
        card_layout.addWidget(prompt)

        buttons = QHBoxLayout()
        buttons.setSpacing(18)
        buttons.addWidget(self._make_button("TEXT MODE", "text", accent=False))
        buttons.addWidget(self._make_button("VOICE MODE", "voice", accent=True))
        card_layout.addLayout(buttons)

        hint = QLabel("Premi ESC per chiudere o scegli una modalità per continuare.")
        hint.setObjectName("hint")
        card_layout.addWidget(hint)

        root.addWidget(card)
        root.addStretch()

    def _make_button(self, label: str, mode: str, accent: bool) -> QPushButton:
        btn = QPushButton(label)
        if accent:
            btn.setObjectName("accent")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda _, m=mode: self._select(m))
        return btn

    def _select(self, mode: str):
        self.mode_selected.emit(mode)
        self.close()

    def closeEvent(self, e):
        super().closeEvent(e)
