"""
ui/mode_select.py  –  RAZE :: SELECT_MODE
Redesign completo: sfondo grigio scuro, finestra ridimensionabile nativa,
layout minimal cyberpunk ispirato a schede dati / terminale.
"""

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QSizeGrip, QSizePolicy,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QUrl, QTimer,
    QPropertyAnimation, QEasingCurve, pyqtProperty,
)
from PyQt6.QtMultimedia        import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtGui import QFontDatabase, QPixmap, QColor

from ui.theme import get, set_theme, THEMES


# ── Font ──────────────────────────────────────────────────────────────────────

def _reg_fonts():
    base = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets"))
    for f in ("SpaceMono-Regular.ttf", "SpaceMono-Bold.ttf",
              "SpaceMono-Italic.ttf", "SpaceMono-BoldItalic.ttf"):
        p = os.path.join(base, f)
        if os.path.exists(p):
            QFontDatabase.addApplicationFont(p)

_reg_fonts()
_FF     = "'Space Mono','Courier New',monospace"
_ASSETS = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets"))


# ── Stylesheet globale ────────────────────────────────────────────────────────

def _ss(C: dict) -> str:
    return f"""
/* reset globale */
* {{
    background-color: {C['bg']};
    color: {C['mid']};
    font-family: {_FF};
    font-size: 13px;
    border: none;
    outline: none;
}}
QWidget {{ background-color: {C['bg']}; }}
QLabel  {{ background: transparent; color: {C['mid']}; border: none; }}

/* combobox tema */
QComboBox#theme_combo {{
    background: {C['bg1']};
    color: {C['hi']};
    border: 1px solid {C['border']};
    padding: 6px 14px;
    font-family: {_FF};
    font-size: 12px;
    letter-spacing: 2px;
    min-width: 140px;
    min-height: 32px;
    border-radius: 0;
}}
QComboBox#theme_combo:hover {{
    border-color: {C['hi']};
    background: {C['bg2']};
}}
QComboBox#theme_combo::drop-down {{ border: none; width: 24px; }}
QComboBox#theme_combo::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {C['hi']};
    width: 0; height: 0;
}}
QComboBox#theme_combo QAbstractItemView {{
    background: {C['bg1']};
    color: {C['hi']};
    selection-background-color: {C['hi']};
    selection-color: {C['bg']};
    border: 1px solid {C['border']};
    font-family: {_FF};
    font-size: 12px;
    padding: 4px;
}}

/* scrollbar minimalista */
QScrollBar:vertical {{
    background: {C['bg1']}; width: 6px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {C['border']}; min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: {C['hi']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


# ── ModeCard ──────────────────────────────────────────────────────────────────

class ModeCard(QWidget):
    """Card cyberpunk: bordo sempre visibile, glow animato + typewriter on hover."""

    clicked = pyqtSignal()

    # ── pyqtProperty per animare blurRadius ──────────────────────────────────
    def _get_glow(self): return self._glow_r
    def _set_glow(self, v):
        self._glow_r = v
        if self._fx: self._fx.setBlurRadius(v)
    glowRadius = pyqtProperty(float, fget=_get_glow, fset=_set_glow)

    def __init__(self, mode: str, icon_file: str, title: str, sub: str, C: dict):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(200, 180)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._mode   = mode
        self._title  = title
        self._sub    = sub
        self._C      = C
        self._glow_r = 0.0
        self._fx     = None
        self._tw_pos = 0
        self._tw_tmr = QTimer(self)
        self._tw_tmr.timeout.connect(self._tick)

        self._build(icon_file, C)
        self._init_fx(C)
        self._init_anim()

    # ── costruzione layout ────────────────────────────────────────────────────
    def _build(self, icon_file: str, C: dict):
        self._refresh_border(C, False)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(10)

        # — header: tag modalità a destra —
        hdr = QHBoxLayout()
        hdr.setSpacing(0)
        self._id_lbl = QLabel(f"{self._mode.upper()}-MODE")
        self._id_lbl.setStyleSheet(
            f"color:{C['dim']}; font-size:9px; letter-spacing:3px;"
            " background:transparent; border:none;"
        )
        hdr.addWidget(self._id_lbl)
        hdr.addStretch()
        self._tag_lbl = QLabel(f"[ {self._mode.upper()} ]")
        self._tag_lbl.setStyleSheet(
            f"color:{C['hi']}; font-size:9px; letter-spacing:3px;"
            " background:transparent; border:none;"
        )
        hdr.addWidget(self._tag_lbl)
        lay.addLayout(hdr)

        # — separatore orizzontale —
        self._sep = QWidget()
        self._sep.setFixedHeight(1)
        self._sep.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._sep.setStyleSheet(f"background:{C['border']}; border:none;")
        lay.addWidget(self._sep)

        # — icona —
        self._icon_lbl = QLabel()
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_lbl.setStyleSheet("background:transparent; border:none;")
        p = os.path.join(_ASSETS, icon_file)
        if os.path.exists(p):
            px = QPixmap(p).scaled(56, 56,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            self._icon_lbl.setPixmap(px)
        else:
            self._icon_lbl.setText("[TXT]" if self._mode == "text" else "[MIC]")
            self._icon_lbl.setStyleSheet(
                f"color:{C['hi']}; font-size:18px; font-family:{_FF};"
                " background:transparent; border:none;"
            )
        lay.addWidget(self._icon_lbl)

        # — titolo principale —
        self._title_lbl = QLabel(self._title)
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_lbl.setStyleSheet(
            f"color:{C['mid']}; font-size:14px; font-family:{_FF};"
            " letter-spacing:3px; background:transparent; border:none;"
        )
        lay.addWidget(self._title_lbl)

        # — typewriter sublabel —
        self._tw_lbl = QLabel("")
        self._tw_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tw_lbl.setMinimumHeight(20)
        self._tw_lbl.setStyleSheet(
            f"color:{C['hi']}; font-size:10px; font-family:{_FF};"
            " letter-spacing:1px; background:transparent; border:none;"
        )
        lay.addWidget(self._tw_lbl)
        lay.addStretch()

    def _refresh_border(self, C: dict, hovered: bool):
        bc = C['hi']  if hovered else C['border']
        bg = C['bg2'] if hovered else C['bg']
        self.setStyleSheet(f"ModeCard {{ background:{bg}; border:1px solid {bc}; }}")

    # ── effetti / animazioni ──────────────────────────────────────────────────
    def _init_fx(self, C: dict):
        self._fx = QGraphicsDropShadowEffect(self)
        self._fx.setColor(QColor(C['hi']))
        self._fx.setOffset(0, 0)
        self._fx.setBlurRadius(0)
        self.setGraphicsEffect(self._fx)

    def _init_anim(self):
        self._ain = QPropertyAnimation(self, b"glowRadius", self)
        self._ain.setDuration(200)
        self._ain.setStartValue(0.0); self._ain.setEndValue(28.0)
        self._ain.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._aout = QPropertyAnimation(self, b"glowRadius", self)
        self._aout.setDuration(280)
        self._aout.setStartValue(28.0); self._aout.setEndValue(0.0)
        self._aout.setEasingCurve(QEasingCurve.Type.InCubic)

    # ── typewriter ────────────────────────────────────────────────────────────
    def _tw_start(self):
        self._tw_pos = 0
        self._tw_lbl.setText("")
        self._tw_tmr.start(48)

    def _tw_stop(self):
        self._tw_tmr.stop()
        self._tw_lbl.setText("")

    def _tick(self):
        self._tw_pos += 1
        self._tw_lbl.setText(self._sub[:self._tw_pos] + "\u258c")
        if self._tw_pos >= len(self._sub):
            self._tw_tmr.stop()
            self._tw_lbl.setText(self._sub + "\u258c")

    # ── theme update ──────────────────────────────────────────────────────────
    def update_theme(self, C: dict):
        self._C = C
        self._refresh_border(C, False)
        if self._fx:      self._fx.setColor(QColor(C['hi']))
        if hasattr(self, '_tag_lbl'):
            self._tag_lbl.setStyleSheet(
                f"color:{C['hi']}; font-size:9px; letter-spacing:3px;"
                " background:transparent; border:none;"
            )
            self._id_lbl.setStyleSheet(
                f"color:{C['dim']}; font-size:9px; letter-spacing:3px;"
                " background:transparent; border:none;"
            )
            self._title_lbl.setStyleSheet(
                f"color:{C['mid']}; font-size:14px; font-family:{_FF};"
                " letter-spacing:3px; background:transparent; border:none;"
            )
            self._tw_lbl.setStyleSheet(
                f"color:{C['hi']}; font-size:10px; font-family:{_FF};"
                " letter-spacing:1px; background:transparent; border:none;"
            )
            self._sep.setStyleSheet(f"background:{C['border']}; border:none;")

    # ── eventi ───────────────────────────────────────────────────────────────
    def enterEvent(self, e):
        self._aout.stop()
        self._ain.setStartValue(self._glow_r); self._ain.start()
        self._refresh_border(self._C, True)
        self._tw_start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._ain.stop()
        self._aout.setStartValue(self._glow_r); self._aout.start()
        self._refresh_border(self._C, False)
        self._tw_stop()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


# ── ModeSelectWindow ──────────────────────────────────────────────────────────

class ModeSelectWindow(QWidget):
    """
    Finestra principale selezione modalità.
    Usa il frame nativo del sistema operativo → ridimensionabile nativamente.
    La titlebar custom rimane DENTRO la finestra (sopra il contenuto).
    """
    mode_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("RAZE")
        self.setMinimumSize(520, 420)
        self.resize(680, 520)
        # ── niente FramelessWindowHint: il resize lo gestisce il sistema ──
        self._player     = None
        self._ao         = None
        self._mode_cards = []
        self._build()
        self._load_video()

    # ── build ─────────────────────────────────────────────────────────────────
    def _build(self):
        C = get()
        self.setStyleSheet(_ss(C))

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._mk_header(C))
        root.addWidget(self._mk_video(C), stretch=3)
        root.addWidget(self._mk_bottom(C), stretch=2)

    # ── header (barra interna, NON titlebar OS) ───────────────────────────────
    def _mk_header(self, C) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(40)
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bar.setStyleSheet(
            f"background:{C['bg1']};"
            f"border-bottom:1px solid {C['border']};"
        )
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(18, 0, 14, 0)
        bl.setSpacing(12)

        # bullet + titolo
        bullet = QLabel("\u25b8")
        bullet.setStyleSheet(f"color:{C['hi']}; font-size:16px; background:transparent; border:none;")
        bl.addWidget(bullet)

        title = QLabel("RAZE  •  SELECT_MODE")
        title.setStyleSheet(
            f"color:{C['hi']}; font-size:13px; letter-spacing:4px;"
            " background:transparent; border:none;"
        )
        bl.addWidget(title)
        bl.addStretch()

        # selettore tema nella header
        lbl_theme = QLabel("THEME:")
        lbl_theme.setStyleSheet(
            f"color:{C['dim']}; font-size:10px; letter-spacing:2px;"
            " background:transparent; border:none;"
        )
        bl.addWidget(lbl_theme)

        self._theme_combo = QComboBox()
        self._theme_combo.setObjectName("theme_combo")
        for name in THEMES:
            self._theme_combo.addItem(name.upper(), name)
        current = C["name"]
        idx = list(THEMES.keys()).index(current) if current in THEMES else 0
        self._theme_combo.setCurrentIndex(idx)
        self._theme_combo.currentIndexChanged.connect(
            lambda i: self._set_theme(self._theme_combo.itemData(i))
        )
        bl.addWidget(self._theme_combo)

        return bar

    # ── video ─────────────────────────────────────────────────────────────────
    def _mk_video(self, C) -> QWidget:
        wrap = QWidget()
        wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        wrap.setStyleSheet(
            f"background:{C['bg']};"
            f"border-bottom:1px solid {C['border']};"
        )
        wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        vl = QVBoxLayout(wrap)
        vl.setContentsMargins(0, 0, 0, 0)

        self.vid = QVideoWidget()
        self.vid.setStyleSheet(f"background:{C['bg']};")
        vl.addWidget(self.vid)

        self.vid_ph = QLabel(
            "  \u2588\u2588\u2588\u2588\u2588\u2588  \u2588\u2588\u2588  \u2588\u2588\u2588\n"
            " \u2588\u2588    \u2588\u2588 \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\n"
            " \u2588\u2588\u2588\u2588\u2588\u2588   \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\n"
            " \u2588\u2588   \u2588\u2588  \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\n"
            " \u2588\u2588   \u2588\u2588  \u2588\u2588  \u2588\u2588\u2588\u2588"
        )
        self.vid_ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vid_ph.setStyleSheet(
            f"color:{C['dim']}; font-size:14px; background:transparent;"
            f" font-family:{_FF}; letter-spacing:2px;"
        )
        self.vid_ph.hide()
        vl.addWidget(self.vid_ph)
        return wrap

    # ── bottom: card row + statusbar ─────────────────────────────────────────
    def _mk_bottom(self, C) -> QWidget:
        panel = QWidget()
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        panel.setStyleSheet(f"background:{C['bg']};")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        vl = QVBoxLayout(panel)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        vl.addLayout(self._mk_cards(C), stretch=1)
        vl.addWidget(self._mk_statusbar(C))
        return panel

    # ── card row ──────────────────────────────────────────────────────────────
    def _mk_cards(self, C) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(24, 16, 24, 8)
        row.setSpacing(20)

        self._mode_cards = []
        specs = [
            ("text",  "chat_icon.png",  "TEXT  MODE",  "chat with RAZE"),
            ("voice", "voice_icon.png", "VOICE MODE",  "speak with RAZE"),
        ]
        for mode, icon, lbl, sub in specs:
            card = ModeCard(mode, icon, lbl, sub, C)
            card.clicked.connect(lambda m=mode: self._select(m))
            row.addWidget(card)
            self._mode_cards.append(card)
        return row

    # ── statusbar ─────────────────────────────────────────────────────────────
    def _mk_statusbar(self, C) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(24)
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bar.setStyleSheet(
            f"background:{C['bg1']};"
            f"border-top:1px solid {C['border']};"
        )
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(18, 0, 6, 0)
        bl.setSpacing(0)

        st = QLabel("SYS:ONLINE  //  RAZE v0.1")
        st.setStyleSheet(
            f"color:{C['dim']}; font-size:9px; letter-spacing:2px;"
            " background:transparent; border:none;"
        )
        bl.addWidget(st)
        bl.addStretch()

        grip = QSizeGrip(bar)
        grip.setFixedSize(14, 14)
        grip.setStyleSheet("background:transparent;")
        bl.addWidget(grip, 0, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        return bar

    # ── tema ──────────────────────────────────────────────────────────────────
    def _set_theme(self, name: str):
        set_theme(name)
        C = get()
        self.setStyleSheet(_ss(C))
        self._repolish(self)
        for card in self._mode_cards:
            card.update_theme(C)
        if self._player:
            self._restart_video()

    def _repolish(self, w):
        w.style().unpolish(w); w.style().polish(w); w.update()
        for c in w.findChildren(QWidget):
            c.style().unpolish(c); c.style().polish(c); c.update()

    # ── video ─────────────────────────────────────────────────────────────────
    def _load_video(self):
        path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "assets", "raze_white.mp4")
        )
        if not os.path.exists(path):
            self.vid.hide(); self.vid_ph.show(); return
        try:
            self._player = QMediaPlayer(self)
            self._ao = QAudioOutput(self)
            self._ao.setVolume(0)
            self._player.setAudioOutput(self._ao)
            self._player.setVideoOutput(self.vid)
            self._player.mediaStatusChanged.connect(self._on_media)
            self._player.setSource(QUrl.fromLocalFile(path))
            self._player.play()
        except Exception as e:
            print(f"[RAZE] video: {e}")
            self._player = None
            self.vid.hide(); self.vid_ph.show()

    def _restart_video(self):
        if not self._player: return
        try: self._player.stop(); self._player.setPosition(0); self._player.play()
        except Exception as e: print(f"[RAZE] restart: {e}")

    def _on_media(self, s):
        if self._player and s == QMediaPlayer.MediaStatus.EndOfMedia:
            try: self._player.setPosition(0); self._player.play()
            except Exception: pass

    # ── select / close ────────────────────────────────────────────────────────
    def _select(self, mode: str):
        if self._player:
            try: self._player.stop()
            except Exception: pass
        self.mode_selected.emit(mode)
        self.close()

    def closeEvent(self, e):
        if self._player:
            try: self._player.stop()
            except Exception: pass
        super().closeEvent(e)
