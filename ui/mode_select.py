"""
ui/mode_select.py - Selezione modalità con scelta tema
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
import os
from ui.theme import get, set_theme, THEMES


def _make_ss(C):
    return f"""
* {{ background-color: {C['bg']}; color: {C['mid']}; font-family: 'Courier New', monospace; border: none; }}
QPushButton#mode_btn {{
    background: transparent; color: {C['hi']};
    border: 1px solid {C['border']}; padding: 18px 36px;
    font-size: 13px; letter-spacing: 4px; min-width: 160px;
}}
QPushButton#mode_btn:hover {{ background: {C['hi']}; color: {C['bg']}; border-color: {C['hi']}; }}
QPushButton#theme_btn {{
    background: transparent; color: {C['dim']};
    border: 1px solid {C['border']}; padding: 4px 12px;
    font-size: 10px; letter-spacing: 2px;
}}
QPushButton#theme_btn:hover {{ color: {C['hi']}; border-color: {C['hi']}; }}
QPushButton#theme_btn[active="true"] {{
    color: {C['hi']}; border-color: {C['hi']};
    background: transparent;
}}
"""


class ModeSelectWindow(QWidget):
    mode_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("RAZE")
        self.setFixedSize(640, 500)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self._drag_pos = None
        self._player = None   # guard: inizializzato solo in _load_video
        self._ao = None
        self._build()
        self._load_video()

    def _build(self):
        C = get()
        self.setStyleSheet(_make_ss(C))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Titlebar
        bar = QWidget()
        bar.setFixedHeight(32)
        bar.setStyleSheet(f"background:{C['bg1']}; border-bottom:1px solid {C['border']};")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(14, 0, 8, 0)
        t = QLabel("RAZE // SELECT MODE")
        t.setStyleSheet(f"color:{C['hi']}; font-size:11px; letter-spacing:5px;")
        bl.addWidget(t)
        bl.addStretch()
        cb = QPushButton("×")
        cb.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['mid']};border:none;font-size:14px;}}"
            f"QPushButton:hover{{color:{C['hi']};}}"
        )
        cb.setFixedSize(28, 28)
        cb.clicked.connect(self.close)
        bl.addWidget(cb)
        lay.addWidget(bar)

        # Video placeholder / widget
        vid_wrap = QWidget()
        vid_wrap.setFixedHeight(190)
        vid_wrap.setStyleSheet(f"background:{C['bg']}; border-bottom:1px solid {C['border']};")
        vl = QVBoxLayout(vid_wrap)
        vl.setContentsMargins(0, 0, 0, 0)
        self.vid = QVideoWidget()
        self.vid.setStyleSheet(f"background:{C['bg']};")
        vl.addWidget(self.vid)
        self.vid_ph = QLabel(
            f"<pre style=\'color:{C['dim']}; font-size:12px;\'>"
            "  ██████  ███  ███ \n"
            " ██    ██ ████████ \n"
            " ██████   ████████ \n"
            " ██   ██  ████████ \n"
            " ██   ██  ██  ████ </pre>"
        )
        self.vid_ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vid_ph.setTextFormat(Qt.TextFormat.RichText)
        self.vid_ph.hide()
        vl.addWidget(self.vid_ph)
        lay.addWidget(vid_wrap)

        # Selezione tema
        theme_row = QHBoxLayout()
        theme_row.setContentsMargins(40, 14, 40, 0)
        theme_row.setSpacing(8)
        theme_lbl = QLabel("THEME //")
        theme_lbl.setStyleSheet(f"color:{C['dim']}; font-size:9px; letter-spacing:2px;")
        theme_row.addWidget(theme_lbl)

        self._theme_btns = {}
        current = C["name"]
        for name in THEMES:
            b = QPushButton(name.upper())
            b.setObjectName("theme_btn")
            b.setProperty("active", "true" if name == current else "false")
            b.clicked.connect(lambda checked, n=name: self._set_theme(n))
            theme_row.addWidget(b)
            self._theme_btns[name] = b
        theme_row.addStretch()
        lay.addLayout(theme_row)

        # Bottoni modalità
        prompt = QLabel("// SELECT_MODE")
        prompt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prompt.setStyleSheet(f"color:{C['dim']}; font-size:10px; letter-spacing:3px; padding:14px 0 8px 0;")
        lay.addWidget(prompt)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(40, 0, 40, 0)
        btn_row.setSpacing(16)
        for label, mode in [("[ TEXT ]", "text"), ("[ VOICE ]", "voice")]:
            b = QPushButton(label)
            b.setObjectName("mode_btn")
            b.clicked.connect(lambda checked, m=mode: self._select(m))
            btn_row.addWidget(b)
        lay.addLayout(btn_row)

        desc_row = QHBoxLayout()
        desc_row.setContentsMargins(40, 8, 40, 0)
        desc_row.setSpacing(16)
        for d in ["keyboard input / chat", "microphone / voice only"]:
            l = QLabel(d)
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.setStyleSheet(f"color:{C['dim']}; font-size:9px; letter-spacing:1px;")
            desc_row.addWidget(l)
        lay.addLayout(desc_row)
        lay.addStretch()

    def _set_theme(self, name: str):
        set_theme(name)
        C = get()
        # Aggiorna stylesheet globale
        self.setStyleSheet(_make_ss(C))
        # Aggiorna stato active dei pulsanti tema
        for n, b in self._theme_btns.items():
            b.setProperty("active", "true" if n == name else "false")
            b.style().unpolish(b)
            b.style().polish(b)
            b.update()
        # Riavvia il video solo se il player è già inizializzato
        if self._player is not None:
            self._restart_video()

    def _load_video(self):
        path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "assets", "raze_white.mp4")
        )
        if not os.path.exists(path):
            self.vid.hide()
            self.vid_ph.show()
            return
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
            self.vid.hide()
            self.vid_ph.show()

    def _restart_video(self):
        """Riavvia il video in sicurezza dopo cambio tema."""
        if self._player is None:
            return
        try:
            self._player.stop()
            self._player.setPosition(0)
            self._player.play()
        except Exception as e:
            print(f"[RAZE] Video restart error: {e}")

    def _on_media(self, s):
        if self._player is None:
            return
        if s == QMediaPlayer.MediaStatus.EndOfMedia:
            try:
                self._player.setPosition(0)
                self._player.play()
            except Exception:
                pass

    def _select(self, mode):
        # Ferma il player prima di chiudere per evitare crash su distruzione
        if self._player is not None:
            try:
                self._player.stop()
            except Exception:
                pass
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
            try:
                self._player.stop()
            except Exception:
                pass
        super().closeEvent(e)
