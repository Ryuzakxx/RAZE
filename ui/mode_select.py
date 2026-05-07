"""
ui/mode_select.py - Selezione modalità con scelta tema
"""

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QGraphicsDropShadowEffect,
)
from PyQt6.QtCore    import (
    Qt, pyqtSignal, QUrl, QTimer,
    QPropertyAnimation, QEasingCurve, pyqtProperty,
)
from PyQt6.QtMultimedia        import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtGui   import QFontDatabase, QPixmap, QColor

from ui.theme import get, set_theme, THEMES


# ── Font registration ──────────────────────────────────────────────────────

def _register_fonts():
    base = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "assets")
    )
    for fname in (
        "SpaceMono-Regular.ttf",
        "SpaceMono-Bold.ttf",
        "SpaceMono-Italic.ttf",
        "SpaceMono-BoldItalic.ttf",
    ):
        p = os.path.join(base, fname)
        if os.path.exists(p):
            QFontDatabase.addApplicationFont(p)

_register_fonts()
_FF      = "'Space Mono','Courier New',monospace"
_ASSETS  = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets"))


def _make_ss(C: dict) -> str:
    return f"""
* {{ background-color:{C['bg']}; color:{C['mid']};
     font-family:{_FF}; font-size:12px; border:none; }}
QLabel {{ color:{C['mid']}; background:transparent; border:none; }}

/* ─ Theme combobox ─ */
QComboBox#theme_combo {{
    background:{C['bg1']}; color:{C['mid']};
    border:1px solid {C['border']};
    padding:4px 10px;
    font-family:{_FF}; font-size:9px; letter-spacing:2px;
    min-width:110px; border-radius:0;
}}
QComboBox#theme_combo:hover {{ border-color:{C['hi']}; color:{C['hi']}; }}
QComboBox#theme_combo::drop-down {{ border:none; width:20px; }}
QComboBox#theme_combo::down-arrow {{
    image:none; width:0; height:0;
    border-left:4px solid transparent;
    border-right:4px solid transparent;
    border-top:5px solid {C['mid']};
}}
QComboBox#theme_combo QAbstractItemView {{
    background:{C['bg1']}; color:{C['mid']};
    selection-background-color:{C['hi']}; selection-color:{C['bg']};
    border:1px solid {C['border']};
    font-family:{_FF}; font-size:9px; letter-spacing:2px;
}}
"""


# ── ModeCard ───────────────────────────────────────────────────────────────────

class ModeCard(QWidget):
    """Card con bordo visibile, glow al hover e typewriter."""

    clicked = pyqtSignal()

    # pyqtProperty per animare il raggio del drop-shadow
    def _get_glow(self): return self._glow_r
    def _set_glow(self, v):
        self._glow_r = v
        if self._shadow:
            self._shadow.setBlurRadius(v)

    glowRadius = pyqtProperty(float, fget=_get_glow, fset=_set_glow)

    def __init__(self, mode: str, icon_file: str, tw_text: str, C: dict):
        super().__init__()
        self._mode     = mode
        self._tw_full  = tw_text
        self._tw_pos   = 0
        self._tw_timer = QTimer(self)
        self._tw_timer.timeout.connect(self._tick)
        self._C        = C
        self._glow_r   = 0.0
        self._shadow   = None
        self._anim_in  = None
        self._anim_out = None

        self.setFixedSize(220, 140)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build(icon_file, C)
        self._setup_shadow(C)
        self._setup_animations(C)

    # ─ Build
    def _build(self, icon_file: str, C: dict):
        self._apply_border(C, hovered=False)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 16, 12, 12)
        lay.setSpacing(10)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon_lbl = QLabel()
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_lbl.setStyleSheet("background:transparent; border:none;")
        icon_path = os.path.join(_ASSETS, icon_file)
        if os.path.exists(icon_path):
            px = QPixmap(icon_path).scaled(
                48, 48,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._icon_lbl.setPixmap(px)
        else:
            self._icon_lbl.setText("A" if self._mode == "text" else "🎤")
            self._icon_lbl.setStyleSheet(
                f"color:{C['hi']}; font-size:28px; background:transparent; border:none;"
            )
        lay.addWidget(self._icon_lbl)

        self._tw_lbl = QLabel("")
        self._tw_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_tw_style(C)
        lay.addWidget(self._tw_lbl)

    def _apply_border(self, C: dict, hovered: bool):
        border_color = C['hi'] if hovered else C['border']
        bg_color     = C.get('bg1', C['bg']) if hovered else C['bg']
        self.setStyleSheet(
            f"ModeCard {{"
            f"  background:{bg_color};"
            f"  border:1px solid {border_color};"
            f"}}"
        )

    def _apply_tw_style(self, C: dict):
        self._tw_lbl.setStyleSheet(
            f"color:{C['hi']}; font-family:{_FF}; font-size:9px;"
            f" letter-spacing:1px; background:transparent; border:none;"
        )

    # ─ Drop-shadow glow
    def _setup_shadow(self, C: dict):
        hi = QColor(C['hi'])
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setColor(hi)
        self._shadow.setOffset(0, 0)
        self._shadow.setBlurRadius(0)
        self.setGraphicsEffect(self._shadow)

    def _setup_animations(self, C: dict):
        self._anim_in = QPropertyAnimation(self, b"glowRadius", self)
        self._anim_in.setDuration(220)
        self._anim_in.setStartValue(0.0)
        self._anim_in.setEndValue(22.0)
        self._anim_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._anim_out = QPropertyAnimation(self, b"glowRadius", self)
        self._anim_out.setDuration(300)
        self._anim_out.setStartValue(22.0)
        self._anim_out.setEndValue(0.0)
        self._anim_out.setEasingCurve(QEasingCurve.Type.InCubic)

    # ─ Typewriter
    def _start_typewriter(self):
        self._tw_pos = 0
        self._tw_lbl.setText("")
        self._tw_timer.start(55)

    def _stop_typewriter(self):
        self._tw_timer.stop()
        self._tw_lbl.setText("")
        self._tw_pos = 0

    def _tick(self):
        self._tw_pos += 1
        self._tw_lbl.setText(self._tw_full[:self._tw_pos] + "▁")
        if self._tw_pos >= len(self._tw_full):
            self._tw_timer.stop()
            self._tw_lbl.setText(self._tw_full + "▁")

    # ─ Theme update
    def update_theme(self, C: dict):
        self._C = C
        self._apply_border(C, hovered=False)
        self._apply_tw_style(C)
        if self._shadow:
            self._shadow.setColor(QColor(C['hi']))
        if self._anim_in:
            self._anim_in.setEndValue(22.0)
        if self._anim_out:
            self._anim_out.setStartValue(22.0)

    # ─ Events
    def enterEvent(self, e):
        if self._anim_out: self._anim_out.stop()
        self._anim_in.setStartValue(self._glow_r)
        self._anim_in.start()
        self._apply_border(self._C, hovered=True)
        self._start_typewriter()
        super().enterEvent(e)

    def leaveEvent(self, e):
        if self._anim_in: self._anim_in.stop()
        self._anim_out.setStartValue(self._glow_r)
        self._anim_out.start()
        self._apply_border(self._C, hovered=False)
        self._stop_typewriter()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


# ── ModeSelectWindow ──────────────────────────────────────────────────────────────

class ModeSelectWindow(QWidget):
    mode_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("RAZE")
        self.setFixedSize(640, 500)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self._drag_pos   = None
        self._player     = None
        self._ao         = None
        self._mode_cards = []
        self._build()
        self._load_video()

    def _build(self):
        C = get()
        self.setStyleSheet(_make_ss(C))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._make_titlebar(C))
        lay.addWidget(self._make_video_cell(C))
        lay.addLayout(self._make_theme_row(C))
        lay.addWidget(self._make_prompt_lbl(C))
        lay.addLayout(self._make_mode_row(C))
        lay.addStretch()

    def _make_titlebar(self, C) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(32)
        bar.setStyleSheet(
            f"background:{C['bg1']}; border-bottom:1px solid {C['border']};"
        )
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(14, 0, 8, 0)
        t = QLabel("RAZE // SELECT_MODE")
        t.setStyleSheet(
            f"color:{C['hi']}; font-size:11px; letter-spacing:5px;"
            f" background:transparent; border:none;"
        )
        bl.addWidget(t)
        bl.addStretch()
        cb = QPushButton("×")
        cb.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['mid']};"
            f"border:none;font-size:14px;font-family:{_FF};}}"
            f"QPushButton:hover{{color:{C['hi']};}}"
        )
        cb.setFixedSize(28, 28)
        cb.clicked.connect(self.close)
        bl.addWidget(cb)
        return bar

    def _make_video_cell(self, C) -> QWidget:
        vid_wrap = QWidget()
        vid_wrap.setFixedHeight(190)
        vid_wrap.setStyleSheet(
            f"background:{C['bg']}; border-bottom:1px solid {C['border']};"
        )
        vl = QVBoxLayout(vid_wrap)
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
            f"color:{C['dim']}; font-size:11px; background:transparent;"
            f" font-family:{_FF}; letter-spacing:1px;"
        )
        self.vid_ph.hide()
        vl.addWidget(self.vid_ph)
        return vid_wrap

    def _make_theme_row(self, C) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(40, 14, 40, 0)
        row.setSpacing(10)
        lbl = QLabel("THEME //")
        lbl.setStyleSheet(
            f"color:{C['dim']}; font-size:9px; letter-spacing:2px;"
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

    def _make_prompt_lbl(self, C) -> QLabel:
        prompt = QLabel("// SELECT_MODE")
        prompt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prompt.setStyleSheet(
            f"color:{C['dim']}; font-size:10px; letter-spacing:3px;"
            f" padding:14px 0 8px 0; background:transparent; border:none;"
        )
        return prompt

    def _make_mode_row(self, C) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(40, 0, 40, 0)
        row.setSpacing(32)
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mode_cards = []
        specs = [
            ("text",  "chat_icon.png",  "chat with RAZE via text_"),
            ("voice", "voice_icon.png", "speak with RAZE_"),
        ]
        for mode, icon, tw_text in specs:
            card = ModeCard(mode, icon, tw_text, C)
            card.clicked.connect(lambda m=mode: self._select(m))
            row.addWidget(card)
            self._mode_cards.append(card)
        return row

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
            print(f"[RAZE] Video error: {e}")
            self._player = None
            self.vid.hide(); self.vid_ph.show()

    def _restart_video(self):
        if self._player is None: return
        try:
            self._player.stop()
            self._player.setPosition(0)
            self._player.play()
        except Exception as e:
            print(f"[RAZE] Video restart error: {e}")

    def _on_media(self, s):
        if self._player is None: return
        if s == QMediaPlayer.MediaStatus.EndOfMedia:
            try: self._player.setPosition(0); self._player.play()
            except Exception: pass

    def _select(self, mode: str):
        if self._player is not None:
            try: self._player.stop()
            except Exception: pass
        self.mode_selected.emit(mode)
        self.close()

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
