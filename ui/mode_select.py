"""
ui/mode_select.py  –  RAZE :: SELECT_MODE
Redesign cyberpunk minimal ispirato a schede dati / terminale CyberOS.
"""

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QSizeGrip,
    QGraphicsDropShadowEffect, QSizePolicy,
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QUrl, QTimer,
    QPropertyAnimation, QEasingCurve, pyqtProperty, QSize,
)
from PyQt6.QtMultimedia        import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtGui import QFontDatabase, QPixmap, QColor, QResizeEvent

from ui.theme import get, set_theme, THEMES


# ── fonts ─────────────────────────────────────────────────────────────────────

def _register_fonts():
    base = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets"))
    for fname in (
        "SpaceMono-Regular.ttf", "SpaceMono-Bold.ttf",
        "SpaceMono-Italic.ttf",  "SpaceMono-BoldItalic.ttf",
    ):
        p = os.path.join(base, fname)
        if os.path.exists(p):
            QFontDatabase.addApplicationFont(p)

_register_fonts()
_FF     = "'Space Mono','Courier New',monospace"
_ASSETS = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets"))


# ── stylesheet globale ────────────────────────────────────────────────────────

def _make_ss(C: dict) -> str:
    return f"""
* {{
    background-color: {C['bg']};
    color: {C['mid']};
    font-family: {_FF};
    font-size: 13px;
    border: none;
}}
QLabel {{
    color: {C['mid']};
    background: transparent;
    border: none;
}}

/* ─ combobox tema ─ */
QComboBox#theme_combo {{
    background: {C['bg1']};
    color: {C['hi']};
    border: 1px solid {C['border']};
    padding: 5px 12px;
    font-family: {_FF};
    font-size: 11px;
    letter-spacing: 2px;
    min-width: 130px;
    min-height: 28px;
    border-radius: 0;
}}
QComboBox#theme_combo:hover {{
    border-color: {C['hi']};
}}
QComboBox#theme_combo::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox#theme_combo::down-arrow {{
    image: none;
    width: 0; height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {C['hi']};
}}
QComboBox#theme_combo QAbstractItemView {{
    background: {C['bg1']};
    color: {C['hi']};
    selection-background-color: {C['hi']};
    selection-color: {C['bg']};
    border: 1px solid {C['border']};
    font-family: {_FF};
    font-size: 11px;
    letter-spacing: 2px;
    padding: 4px;
}}
"""


# ── ModeCard ──────────────────────────────────────────────────────────────────

class ModeCard(QWidget):
    """Card stile scheda dati cyberpunk: bordo sempre visibile, glow + typewriter on hover."""

    clicked = pyqtSignal()

    def _get_glow(self): return self._glow_r
    def _set_glow(self, v):
        self._glow_r = v
        if self._shadow:
            self._shadow.setBlurRadius(v)

    glowRadius = pyqtProperty(float, fget=_get_glow, fset=_set_glow)

    def __init__(self, mode: str, icon_file: str, label: str, sublabel: str, C: dict):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(180, 160)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._mode     = mode
        self._label    = label
        self._sublabel = sublabel
        self._tw_full  = sublabel
        self._tw_pos   = 0
        self._tw_timer = QTimer(self)
        self._tw_timer.timeout.connect(self._tick)
        self._C        = C
        self._glow_r   = 0.0
        self._shadow   = None
        self._anim_in  = None
        self._anim_out = None

        self._build(icon_file, C)
        self._setup_shadow(C)
        self._setup_animations()

    # ─ build ─────────────────────────────────────────────────────────────────
    def _build(self, icon_file: str, C: dict):
        self._apply_style(C, hovered=False)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        # ── header riga: ID / tag modo ──
        hdr = QHBoxLayout()
        hdr.setSpacing(6)

        id_lbl = QLabel(f"ID: {self._mode.upper()}-01")
        id_lbl.setStyleSheet(
            f"color:{C['dim']}; font-size:9px; letter-spacing:2px;"
            f" background:transparent; border:none;"
        )
        hdr.addWidget(id_lbl)
        hdr.addStretch()

        tag = QLabel(f"[ {self._mode.upper()} ]")
        tag.setStyleSheet(
            f"color:{C['hi']}; font-size:9px; letter-spacing:3px;"
            f" background:transparent; border:none;"
        )
        hdr.addWidget(tag)
        lay.addLayout(hdr)

        # ── separatore ──
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        sep.setStyleSheet(f"background:{C['border']}; border:none;")
        lay.addWidget(sep)

        # ── icona ──
        self._icon_lbl = QLabel()
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_lbl.setStyleSheet("background:transparent; border:none;")
        icon_path = os.path.join(_ASSETS, icon_file)
        if os.path.exists(icon_path):
            px = QPixmap(icon_path).scaled(
                52, 52,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._icon_lbl.setPixmap(px)
        else:
            self._icon_lbl.setText("[TXT]" if self._mode == "text" else "[MIC]")
            self._icon_lbl.setStyleSheet(
                f"color:{C['hi']}; font-size:20px; font-family:{_FF};"
                f" background:transparent; border:none;"
            )
        lay.addWidget(self._icon_lbl)

        # ── label principale ──
        self._main_lbl = QLabel(self._label)
        self._main_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._main_lbl.setStyleSheet(
            f"color:{C['mid']}; font-size:13px; font-family:{_FF};"
            f" letter-spacing:2px; background:transparent; border:none;"
        )
        lay.addWidget(self._main_lbl)

        # ── typewriter sublabel ──
        self._tw_lbl = QLabel("")
        self._tw_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tw_lbl.setMinimumHeight(18)
        self._apply_tw_style(C)
        lay.addWidget(self._tw_lbl)

        lay.addStretch()

    def _apply_style(self, C: dict, hovered: bool):
        border_color = C['hi']               if hovered else C['border']
        bg_color     = C.get('bg1', C['bg']) if hovered else C['bg']
        self.setStyleSheet(
            f"ModeCard {{"
            f" background: {bg_color};"
            f" border: 1px solid {border_color};"
            f"}}"
        )

    def _apply_tw_style(self, C: dict):
        self._tw_lbl.setStyleSheet(
            f"color:{C['hi']}; font-family:{_FF}; font-size:10px;"
            f" letter-spacing:1px; background:transparent; border:none;"
        )

    # ─ shadow / anim ─────────────────────────────────────────────────────────
    def _setup_shadow(self, C: dict):
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setColor(QColor(C['hi']))
        self._shadow.setOffset(0, 0)
        self._shadow.setBlurRadius(0)
        self.setGraphicsEffect(self._shadow)

    def _setup_animations(self):
        self._anim_in = QPropertyAnimation(self, b"glowRadius", self)
        self._anim_in.setDuration(200)
        self._anim_in.setStartValue(0.0)
        self._anim_in.setEndValue(24.0)
        self._anim_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._anim_out = QPropertyAnimation(self, b"glowRadius", self)
        self._anim_out.setDuration(280)
        self._anim_out.setStartValue(24.0)
        self._anim_out.setEndValue(0.0)
        self._anim_out.setEasingCurve(QEasingCurve.Type.InCubic)

    # ─ typewriter ─────────────────────────────────────────────────────────────
    def _start_typewriter(self):
        self._tw_pos = 0
        self._tw_lbl.setText("")
        self._tw_timer.start(50)

    def _stop_typewriter(self):
        self._tw_timer.stop()
        self._tw_lbl.setText("")

    def _tick(self):
        self._tw_pos += 1
        self._tw_lbl.setText(self._tw_full[:self._tw_pos] + "▌")
        if self._tw_pos >= len(self._tw_full):
            self._tw_timer.stop()
            self._tw_lbl.setText(self._tw_full + "▌")

    # ─ theme update ───────────────────────────────────────────────────────────
    def update_theme(self, C: dict):
        self._C = C
        self._apply_style(C, hovered=False)
        self._apply_tw_style(C)
        if self._shadow:
            self._shadow.setColor(QColor(C['hi']))
        if hasattr(self, '_main_lbl'):
            self._main_lbl.setStyleSheet(
                f"color:{C['mid']}; font-size:13px; font-family:{_FF};"
                f" letter-spacing:2px; background:transparent; border:none;"
            )

    # ─ events ─────────────────────────────────────────────────────────────────
    def enterEvent(self, e):
        if self._anim_out: self._anim_out.stop()
        self._anim_in.setStartValue(self._glow_r)
        self._anim_in.start()
        self._apply_style(self._C, hovered=True)
        self._start_typewriter()
        super().enterEvent(e)

    def leaveEvent(self, e):
        if self._anim_in: self._anim_in.stop()
        self._anim_out.setStartValue(self._glow_r)
        self._anim_out.start()
        self._apply_style(self._C, hovered=False)
        self._stop_typewriter()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


# ── ModeSelectWindow ──────────────────────────────────────────────────────────

class ModeSelectWindow(QWidget):
    mode_selected = pyqtSignal(str)

    _MIN_W, _MIN_H = 560, 440

    def __init__(self):
        super().__init__()
        self.setWindowTitle("RAZE")
        self.setMinimumSize(self._MIN_W, self._MIN_H)
        self.resize(700, 520)
        # frameless ma ridimensionabile tramite SizeGrip
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowMinMaxButtonsHint
        )
        self._drag_pos   = None
        self._player     = None
        self._ao         = None
        self._mode_cards = []
        self._build()
        self._load_video()

    # ─ build ─────────────────────────────────────────────────────────────────
    def _build(self):
        C = get()
        self.setStyleSheet(_make_ss(C))

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._make_titlebar(C))
        root.addWidget(self._make_video_cell(C), stretch=3)
        root.addWidget(self._make_bottom_panel(C), stretch=2)

    # ─ titlebar ───────────────────────────────────────────────────────────────
    def _make_titlebar(self, C) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(36)
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bar.setStyleSheet(
            f"background:{C['bg1']}; border-bottom:1px solid {C['border']};"
        )
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(16, 0, 8, 0)
        bl.setSpacing(12)

        # bullet decorativo
        dot = QLabel("▸")
        dot.setStyleSheet(
            f"color:{C['hi']}; font-size:14px; background:transparent; border:none;"
        )
        bl.addWidget(dot)

        title = QLabel("RAZE  //  SELECT_MODE")
        title.setStyleSheet(
            f"color:{C['hi']}; font-size:12px; letter-spacing:5px;"
            f" background:transparent; border:none;"
        )
        bl.addWidget(title)
        bl.addStretch()

        # bottoni finestra: minimizza / chiudi
        for symbol, action in (("−", self.showMinimized), ("×", self.close)):
            btn = QPushButton(symbol)
            btn.setFixedSize(32, 32)
            btn.setStyleSheet(
                f"QPushButton{{"
                f" background:transparent; color:{C['dim']};"
                f" border:none; font-size:16px; font-family:{_FF};"
                f"}}"
                f"QPushButton:hover{{"
                f" color:{C['hi']};"
                f" border:1px solid {C['border']};"
                f"}}"
            )
            btn.clicked.connect(action)
            bl.addWidget(btn)

        return bar

    # ─ video cell ─────────────────────────────────────────────────────────────
    def _make_video_cell(self, C) -> QWidget:
        wrap = QWidget()
        wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        wrap.setStyleSheet(
            f"background:{C['bg']}; border-bottom:1px solid {C['border']};"
        )
        wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        vl = QVBoxLayout(wrap)
        vl.setContentsMargins(0, 0, 0, 0)

        self.vid = QVideoWidget()
        self.vid.setStyleSheet(f"background:{C['bg']};")
        vl.addWidget(self.vid)

        self.vid_ph = QLabel(
            "  ██████  ███  ███\n"
            " ██    ██ ████████\n"
            " ██████   ████████\n"
            " ██   ██  ████████\n"
            " ██   ██  ██  ████"
        )
        self.vid_ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vid_ph.setStyleSheet(
            f"color:{C['dim']}; font-size:13px; background:transparent;"
            f" font-family:{_FF}; letter-spacing:2px;"
        )
        self.vid_ph.hide()
        vl.addWidget(self.vid_ph)

        return wrap

    # ─ bottom panel: theme row + card row + size grip ─────────────────────────
    def _make_bottom_panel(self, C) -> QWidget:
        panel = QWidget()
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        panel.setStyleSheet(f"background:{C['bg']};")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        vl = QVBoxLayout(panel)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        vl.addLayout(self._make_theme_row(C))
        vl.addLayout(self._make_mode_row(C), stretch=1)
        vl.addWidget(self._make_statusbar(C))

        return panel

    # ─ theme row ──────────────────────────────────────────────────────────────
    def _make_theme_row(self, C) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(20, 10, 20, 8)
        row.setSpacing(10)

        lbl = QLabel("THEME //")
        lbl.setStyleSheet(
            f"color:{C['dim']}; font-size:10px; letter-spacing:2px;"
            f" background:transparent; border:none;"
        )
        row.addWidget(lbl)

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
        row.addWidget(self._theme_combo)
        row.addStretch()
        return row

    # ─ card row ───────────────────────────────────────────────────────────────
    def _make_mode_row(self, C) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(20, 0, 20, 0)
        row.setSpacing(20)

        self._mode_cards = []
        specs = [
            ("text",  "chat_icon.png",  "TEXT MODE",  "chat with RAZE"),
            ("voice", "voice_icon.png", "VOICE MODE", "speak with RAZE"),
        ]
        for mode, icon, label, sub in specs:
            card = ModeCard(mode, icon, label, sub, C)
            card.clicked.connect(lambda m=mode: self._select(m))
            row.addWidget(card)
            self._mode_cards.append(card)

        return row

    # ─ status bar (contiene SizeGrip) ─────────────────────────────────────────
    def _make_statusbar(self, C) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(22)
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bar.setStyleSheet(
            f"background:{C['bg1']}; border-top:1px solid {C['border']};"
        )
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(16, 0, 4, 0)
        bl.setSpacing(0)

        status = QLabel("SYS:ONLINE  //  RAZE v0.1")
        status.setStyleSheet(
            f"color:{C['dim']}; font-size:9px; letter-spacing:2px;"
            f" background:transparent; border:none;"
        )
        bl.addWidget(status)
        bl.addStretch()

        grip = QSizeGrip(bar)
        grip.setStyleSheet("background:transparent;")
        bl.addWidget(grip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        return bar

    # ─ theme / repolish ───────────────────────────────────────────────────────
    def _set_theme(self, name: str):
        set_theme(name)
        C = get()
        self.setStyleSheet(_make_ss(C))
        self._repolish(self)
        for card in self._mode_cards:
            card.update_theme(C)
        if self._player is not None:
            self._restart_video()

    def _repolish(self, widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()
        for child in widget.findChildren(QWidget):
            child.style().unpolish(child)
            child.style().polish(child)
            child.update()

    # ─ video ─────────────────────────────────────────────────────────────────
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
            print(f"[RAZE] video error: {e}")
            self._player = None
            self.vid.hide(); self.vid_ph.show()

    def _restart_video(self):
        if self._player is None: return
        try:
            self._player.stop()
            self._player.setPosition(0)
            self._player.play()
        except Exception as e:
            print(f"[RAZE] video restart error: {e}")

    def _on_media(self, s):
        if self._player is None: return
        if s == QMediaPlayer.MediaStatus.EndOfMedia:
            try: self._player.setPosition(0); self._player.play()
            except Exception: pass

    # ─ select ────────────────────────────────────────────────────────────────
    def _select(self, mode: str):
        if self._player is not None:
            try: self._player.stop()
            except Exception: pass
        self.mode_selected.emit(mode)
        self.close()

    # ─ drag + resize events ──────────────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            self.move(self.pos() + e.globalPosition().toPoint() - self._drag_pos)
            self._drag_pos = e.globalPosition().toPoint()

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    def closeEvent(self, e):
        if self._player is not None:
            try: self._player.stop()
            except Exception: pass
        super().closeEvent(e)
