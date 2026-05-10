"""
ui/mode_select.py  –  RAZE :: SELECT_MODE
Palette fissa: bg #141414, accent #320096.
Finestra con frame nativo → ridimensionabile nativamente.
"""

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSizeGrip, QSizePolicy, QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QUrl, QTimer,
    QPropertyAnimation, QEasingCurve, pyqtProperty,
)
from PyQt6.QtMultimedia        import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtGui import QFontDatabase, QPixmap, QColor

from ui.theme import get


# ── Font ──────────────────────────────────────────────────────────────

def _reg_fonts():
    base = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets"))
    for f in ("SpaceMono-Regular.ttf", "SpaceMono-Bold.ttf",
              "SpaceMono-Italic.ttf",  "SpaceMono-BoldItalic.ttf"):
        p = os.path.join(base, f)
        if os.path.exists(p):
            QFontDatabase.addApplicationFont(p)

_reg_fonts()
_FF     = "'Space Mono','Courier New',monospace"
_ASSETS = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets"))
C       = get()  # palette fissa, caricata una volta


# ── Stylesheet globale ─────────────────────────────────────────────────────

_STYLESHEET = f"""
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
    clicked = pyqtSignal()

    def _get_glow(self): return self._glow_r
    def _set_glow(self, v):
        self._glow_r = v
        if self._fx: self._fx.setBlurRadius(v)
    glowRadius = pyqtProperty(float, fget=_get_glow, fset=_set_glow)

    def __init__(self, mode: str, icon_file: str, title: str, sub: str):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(200, 180)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._mode   = mode
        self._title  = title
        self._sub    = sub
        self._glow_r = 0.0
        self._fx     = None
        self._tw_pos = 0
        self._tw_tmr = QTimer(self)
        self._tw_tmr.timeout.connect(self._tick)

        self._build(icon_file)
        self._init_fx()
        self._init_anim()

    # ─ layout ───────────────────────────────────────────────────────────
    def _build(self, icon_file: str):
        self._set_border(False)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(10)

        # header: id sinistra, tag destra
        hdr = QHBoxLayout()
        id_lbl = QLabel(f"{self._mode.upper()}-MODE")
        id_lbl.setStyleSheet(
            f"color:{C['dim']}; font-size:9px; letter-spacing:3px;"
            " background:transparent; border:none;"
        )
        hdr.addWidget(id_lbl)
        hdr.addStretch()
        tag = QLabel(f"[ {self._mode.upper()} ]")
        tag.setStyleSheet(
            f"color:{C['hi']}; font-size:9px; letter-spacing:3px;"
            " background:transparent; border:none;"
        )
        hdr.addWidget(tag)
        lay.addLayout(hdr)

        # separatore
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        sep.setStyleSheet(f"background:{C['border']}; border:none;")
        lay.addWidget(sep)

        # icona
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

        # titolo
        title_lbl = QLabel(self._title)
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setStyleSheet(
            f"color:{C['mid']}; font-size:14px; font-family:{_FF};"
            " letter-spacing:3px; background:transparent; border:none;"
        )
        lay.addWidget(title_lbl)

        # typewriter
        self._tw_lbl = QLabel("")
        self._tw_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tw_lbl.setMinimumHeight(20)
        self._tw_lbl.setStyleSheet(
            f"color:{C['hi']}; font-size:10px; font-family:{_FF};"
            " letter-spacing:1px; background:transparent; border:none;"
        )
        lay.addWidget(self._tw_lbl)
        lay.addStretch()

    def _set_border(self, hovered: bool):
        bc = C['hi2'] if hovered else C['border']
        bg = C['bg2'] if hovered else C['bg']
        self.setStyleSheet(f"ModeCard {{ background:{bg}; border:1px solid {bc}; }}")

    # ─ fx / anim ─────────────────────────────────────────────────────────
    def _init_fx(self):
        self._fx = QGraphicsDropShadowEffect(self)
        self._fx.setColor(QColor(C['hi']))
        self._fx.setOffset(0, 0)
        self._fx.setBlurRadius(0)
        self.setGraphicsEffect(self._fx)

    def _init_anim(self):
        self._ain = QPropertyAnimation(self, b"glowRadius", self)
        self._ain.setDuration(200)
        self._ain.setStartValue(0.0); self._ain.setEndValue(30.0)
        self._ain.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._aout = QPropertyAnimation(self, b"glowRadius", self)
        self._aout.setDuration(280)
        self._aout.setStartValue(30.0); self._aout.setEndValue(0.0)
        self._aout.setEasingCurve(QEasingCurve.Type.InCubic)

    # ─ typewriter ────────────────────────────────────────────────────────
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

    # ─ eventi ─────────────────────────────────────────────────────────────
    def enterEvent(self, e):
        self._aout.stop()
        self._ain.setStartValue(self._glow_r); self._ain.start()
        self._set_border(True)
        self._tw_start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._ain.stop()
        self._aout.setStartValue(self._glow_r); self._aout.start()
        self._set_border(False)
        self._tw_stop()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


# ── ModeSelectWindow ──────────────────────────────────────────────────────────

class ModeSelectWindow(QWidget):
    mode_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("RAZE")
        self.setMinimumSize(520, 420)
        self.resize(680, 520)
        self._player = None
        self._ao     = None
        self._build()
        self._load_video()

    # ─ build ──────────────────────────────────────────────────────────────
    def _build(self):
        self.setStyleSheet(_STYLESHEET)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._mk_header())
        root.addWidget(self._mk_video(), stretch=3)
        root.addWidget(self._mk_bottom(), stretch=2)

    # ─ header ─────────────────────────────────────────────────────────────
    def _mk_header(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(40)
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bar.setStyleSheet(
            f"background:{C['bg1']};"
            f" border-bottom:1px solid {C['border']};"
        )
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(18, 0, 18, 0)
        bl.setSpacing(10)

        bullet = QLabel("\u25b8")
        bullet.setStyleSheet(
            f"color:{C['hi']}; font-size:16px; background:transparent; border:none;"
        )
        bl.addWidget(bullet)

        title = QLabel("RAZE  \u2022  SELECT_MODE")
        title.setStyleSheet(
            f"color:{C['mid']}; font-size:13px; letter-spacing:4px;"
            " background:transparent; border:none;"
        )
        bl.addWidget(title)
        bl.addStretch()
        return bar

    # ─ video ─────────────────────────────────────────────────────────────
    def _mk_video(self) -> QWidget:
        wrap = QWidget()
        wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        wrap.setStyleSheet(
            f"background:{C['bg']};"
            f" border-bottom:1px solid {C['border']};"
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

    # ─ bottom panel ────────────────────────────────────────────────────────
    def _mk_bottom(self) -> QWidget:
        panel = QWidget()
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        panel.setStyleSheet(f"background:{C['bg']};")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        vl = QVBoxLayout(panel)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)
        vl.addLayout(self._mk_cards(), stretch=1)
        vl.addWidget(self._mk_statusbar())
        return panel

    # ─ card row ───────────────────────────────────────────────────────────
    def _mk_cards(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(24, 16, 24, 8)
        row.setSpacing(20)
        specs = [
            ("text",  "chat_icon.png",  "TEXT  MODE", "chat with RAZE"),
            ("voice", "voice_icon.png", "VOICE MODE", "speak with RAZE"),
        ]
        for mode, icon, lbl, sub in specs:
            card = ModeCard(mode, icon, lbl, sub)
            card.clicked.connect(lambda m=mode: self._select(m))
            row.addWidget(card)
        return row

    # ─ statusbar ───────────────────────────────────────────────────────────
    def _mk_statusbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(24)
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bar.setStyleSheet(
            f"background:{C['bg1']};"
            f" border-top:1px solid {C['border']};"
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

    # ─ video logic ────────────────────────────────────────────────────────
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

    def _on_media(self, s):
        if self._player and s == QMediaPlayer.MediaStatus.EndOfMedia:
            try: self._player.setPosition(0); self._player.play()
            except Exception: pass

    # ─ select / close ─────────────────────────────────────────────────────
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
