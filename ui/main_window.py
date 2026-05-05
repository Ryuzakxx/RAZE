"""
ui/main_window.py - Modalità testo RAZE
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QLineEdit, QPushButton, QFrame,
    QDialog, QComboBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
import os
from ui.theme import get
from ui.widgets import StatusBar


def _ss(C):
    return f"""
* {{ background-color: {C['bg']}; color: {C['mid']}; font-family: 'Courier New', monospace; font-size: 12px; border: none; outline: none; }}
QFrame#panel {{ background-color: {C['bg1']}; border: 1px solid {C['border']}; }}
QTextEdit#log {{
    background-color: {C['bg']}; color: {C['mid']};
    font-family: 'Courier New', monospace; font-size: 12px;
    padding: 10px; border: none;
    selection-background-color: {C['hi']}; selection-color: {C['bg']};
}}
QLineEdit#inp {{
    background-color: {C['bg']}; color: {C['hi']};
    font-family: 'Courier New', monospace; font-size: 12px;
    padding: 8px 12px; border: none;
}}
QLineEdit#inp:focus {{ border-bottom: 1px solid {C['hi']}; }}
QPushButton#btn {{
    background: transparent; color: {C['dim']};
    font-family: 'Courier New', monospace; font-size: 10px;
    letter-spacing: 1px; padding: 4px 10px;
    border: 1px solid {C['border']};
}}
QPushButton#btn:hover {{ color: {C['hi']}; border: 1px solid {C['hi']}; background: transparent; }}
QPushButton#btn_hi {{
    background: transparent; color: {C['hi']};
    font-family: 'Courier New', monospace; font-size: 11px;
    letter-spacing: 2px; padding: 8px 20px;
    border: 1px solid {C['hi']};
}}
QPushButton#btn_hi:hover {{ background: {C['hi']}; color: {C['bg']}; border: 1px solid {C['hi']}; }}
QPushButton#btn_hi:pressed {{ background: {C['mid']}; border: 1px solid {C['mid']}; color: {C['bg']}; }}
QScrollBar:vertical {{ background: {C['bg']}; width: 4px; }}
QScrollBar::handle:vertical {{ background: {C['dim']}; min-height: 20px; }}
QScrollBar::handle:vertical:hover {{ background: {C['mid']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
"""


class WorkerThread(QThread):
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, message: str, conversation=None):
        super().__init__()
        self.message      = message
        self.conversation = conversation

    def run(self):
        try:
            from core.llm import query_raze
            response = query_raze(self.message, self.conversation)
            self.response_ready.emit(response)
        except Exception as e:
            self.error_occurred.emit(str(e))


class TypewriterLabel(QLabel):
    finished = pyqtSignal()

    def __init__(self, theme: dict):
        super().__init__()
        self.C = theme
        self._full_text = ""
        self._pos = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def type_text(self, text: str, speed_ms: int = 18):
        self._full_text = text
        self._pos = 0
        self.setText("")
        self._timer.start(speed_ms)

    def stop_typing(self):
        """Ferma l'animazione in sicurezza."""
        self._timer.stop()

    def _tick(self):
        if self._pos < len(self._full_text):
            self._pos += 1
            self.setText(self._full_text[:self._pos])
        else:
            self._timer.stop()
            self.finished.emit()


class ScanlineOverlay(QWidget):
    def __init__(self, parent, theme: dict):
        super().__init__(parent)
        self.C = theme
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.raise_()

    def resizeEvent(self, e):
        self.setGeometry(self.parent().rect())

    def paintEvent(self, e):
        from PyQt6.QtGui import QPainter, QColor
        painter = QPainter(self)
        color = QColor(f"#{self.C['hi'][1:]}")
        color.setAlpha(15)
        painter.setPen(color)
        y = 0
        while y < self.height():
            painter.drawLine(0, y, self.width(), y)
            y += 3
        painter.end()


class RazeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.C = get()
        self.setWindowTitle("RAZE")
        self.setMinimumSize(860, 620)
        self.resize(960, 680)
        self.setStyleSheet(_ss(self.C))
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self._drag_pos = None
        self._player = None      # guard
        self._worker = None      # guard
        self._closing = False    # flag per evitare callback dopo chiusura
        from core.llm import Conversation
        self._conv = Conversation()
        self._build()
        self._load_video()
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink)
        self._blink_timer.start(800)
        self._blink_state = True

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._titlebar())
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._left(), stretch=2)
        body.addWidget(self._vline())
        body.addWidget(self._right(), stretch=3)
        lay.addLayout(body)
        self._statusbar = StatusBar(self.C)
        lay.addWidget(self._statusbar)

    def _titlebar(self):
        bar = QWidget()
        bar.setFixedHeight(36)
        bar.setStyleSheet(f"background:{self.C['bg1']}; border-bottom:1px solid {self.C['border']};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 8, 0)
        title = QLabel("RAZE // TEXT MODE")
        title.setStyleSheet(f"color:{self.C['hi']}; font-size:12px; letter-spacing:5px;")
        lay.addWidget(title)
        lay.addStretch()
        self.status_bar_lbl = QLabel("STANDBY")
        self.status_bar_lbl.setStyleSheet(f"color:{self.C['dim']}; font-size:10px; letter-spacing:3px;")
        lay.addWidget(self.status_bar_lbl)
        lay.addSpacing(20)
        for sym, slot in [("_", self.showMinimized), ("□", self._toggle_max), ("×", self.close)]:
            b = QPushButton(sym)
            b.setFixedSize(28, 28)
            b.setStyleSheet(f"""
                QPushButton {{ background:transparent; color:{self.C['dim']}; border:none; font-size:14px; font-family:'Courier New'; }}
                QPushButton:hover {{ color:{self.C['hi']}; background:{self.C['border']}; }}
            """)
            b.clicked.connect(slot)
            lay.addWidget(b)
        return bar

    def _left(self):
        panel = QFrame()
        panel.setObjectName("panel")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        vid_container = QWidget()
        vid_container.setMinimumHeight(240)
        self.vid = QVideoWidget(vid_container)
        self.vid.setStyleSheet(f"background:{self.C['bg']};")
        self.vid_placeholder = QLabel(vid_container)
        self.vid_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vid_placeholder.setTextFormat(Qt.TextFormat.RichText)
        self.vid_placeholder.hide()
        self._scanline = ScanlineOverlay(vid_container, self.C)
        def resize_vid(e):
            self.vid.setGeometry(vid_container.rect())
            self.vid_placeholder.setGeometry(vid_container.rect())
            self._scanline.setGeometry(vid_container.rect())
        vid_container.resizeEvent = resize_vid
        lay.addWidget(vid_container, stretch=1)
        info_bar = QWidget()
        info_bar.setFixedHeight(90)
        info_bar.setStyleSheet(f"background:{self.C['bg1']}; border-top:1px solid {self.C['border']};")
        info_lay = QVBoxLayout(info_bar)
        info_lay.setContentsMargins(12, 8, 12, 8)
        info_lay.setSpacing(6)
        self.status_lbl = QLabel("[ STANDBY ]")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet(f"color:{self.C['hi']}; font-size:11px; letter-spacing:2px;")
        info_lay.addWidget(self.status_lbl)
        self.info_lbl = QLabel(f"SYS:RAZE  LLM:GEMMA3  THEME:{self.C['name'].upper()}")
        self.info_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_lbl.setStyleSheet(f"color:{self.C['dim']}; font-size:9px; letter-spacing:1px;")
        info_lay.addWidget(self.info_lbl)
        lay.addWidget(info_bar)
        return panel

    def _right(self):
        panel = QFrame()
        panel.setObjectName("panel")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        hdr = QWidget()
        hdr.setFixedHeight(28)
        hdr.setStyleSheet(f"background:{self.C['bg1']}; border-bottom:1px solid {self.C['border']};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(12, 0, 12, 0)
        hl.addWidget(QLabel("// OUTPUT_LOG"))
        hl.addStretch()
        clr = QPushButton("CLR")
        clr.setObjectName("btn")
        clr.setFixedSize(36, 18)
        clr.clicked.connect(self._clear_log)
        hl.addWidget(clr)
        lay.addWidget(hdr)
        self.log = QTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        lay.addWidget(self.log, stretch=1)
        self._tw = TypewriterLabel(self.C)
        self._tw.setStyleSheet(f"color:{self.C['hi']}; font-family:'Courier New'; font-size:12px; padding:4px 10px; background:{self.C['bg']};")
        self._tw.setWordWrap(True)
        self._tw.hide()
        self._tw.finished.connect(self._on_typewriter_done)
        lay.addWidget(self._tw)
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{self.C['border']};")
        lay.addWidget(sep)
        inp_bar = QWidget()
        inp_bar.setFixedHeight(44)
        inp_bar.setStyleSheet(f"background:{self.C['bg1']};")
        ib = QHBoxLayout(inp_bar)
        ib.setContentsMargins(0, 0, 8, 0)
        ib.setSpacing(0)
        prompt = QLabel(" > ")
        prompt.setStyleSheet(f"color:{self.C['hi']}; font-size:14px; padding:0 4px;")
        ib.addWidget(prompt)
        self.inp = QLineEdit()
        self.inp.setObjectName("inp")
        self.inp.setPlaceholderText("insert command...")
        self.inp.returnPressed.connect(self._send)
        ib.addWidget(self.inp, stretch=1)
        send_btn = QPushButton("SEND")
        send_btn.setObjectName("btn_hi")
        send_btn.clicked.connect(self._send)
        ib.addWidget(send_btn)
        lay.addWidget(inp_bar)
        return panel

    def _vline(self):
        l = QFrame()
        l.setFixedWidth(1)
        l.setStyleSheet(f"background:{self.C['border']};")
        return l

    def _load_video(self):
        base = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets"))
        self._vid_idle     = os.path.join(base, "raze_white.mp4")
        self._vid_thinking = os.path.join(base, "loading.mp4")
        if not os.path.exists(self._vid_idle):
            self.vid.hide()
            self.vid_placeholder.show()
            self.vid_placeholder.setText(
                f"<pre style='color:{self.C['dim']}; font-size:11px;'>"
                "  ██████  ███  ███ \n"
                " ██    ██ ████████ \n"
                " ██████   ████████ \n"
                " ██   ██  ████████ \n"
                " ██   ██  ██  ████ </pre>"
            )
            return
        try:
            self._player = QMediaPlayer(self)
            self._ao = QAudioOutput(self)
            self._ao.setVolume(0)
            self._player.setAudioOutput(self._ao)
            self._player.setVideoOutput(self.vid)
            self._player.mediaStatusChanged.connect(self._on_media)
            self._play_video(self._vid_idle)
        except Exception as e:
            print(f"[RAZE] Video init error: {e}")
            self._player = None
            self.vid.hide()
            self.vid_placeholder.show()

    def _play_video(self, path):
        if self._player is None:
            return
        if not os.path.exists(path):
            path = self._vid_idle
        try:
            self._player.setSource(QUrl.fromLocalFile(path))
            self._player.play()
        except Exception as e:
            print(f"[RAZE] Video play error: {e}")

    def _on_media(self, s):
        if self._player is None or self._closing:
            return
        if s == QMediaPlayer.MediaStatus.EndOfMedia:
            try:
                self._player.setPosition(0)
                self._player.play()
            except Exception:
                pass

    def _set_thinking(self, on: bool):
        self._play_video(self._vid_thinking if on else self._vid_idle)

    def _send(self):
        text = self.inp.text().strip()
        if not text:
            return
        self.inp.clear()
        self._log(f"<span style='color:{self.C['dim']}'>&gt;&nbsp;{text}</span>")
        self._set_status("PROCESSING")
        self._set_thinking(True)
        self._worker = WorkerThread(text, self._conv)
        self._worker.response_ready.connect(self._on_resp)
        self._worker.error_occurred.connect(self._on_err)
        self._worker.start()

    def _on_resp(self, text):
        if self._closing:
            return
        self._set_thinking(False)
        self._set_status("RESPONDING")
        self._statusbar.inc_messages()
        self._tw.show()
        self._tw.type_text(text)

    def _on_typewriter_done(self):
        if self._closing:
            return
        text = self._tw.text()
        self._tw.hide()
        self._tw.setText("")
        self._log(f"<span style='color:{self.C['hi']}'>{text}</span>")
        self._set_status("STANDBY")

    def _on_err(self, err):
        if self._closing:
            return
        self._set_thinking(False)
        self._log(f"<span style='color:{self.C['mid']}'>ERR: {err}</span>")
        self._set_status("ERROR")

    def _log(self, html):
        self.log.append(html)

    def _clear_log(self):
        self.log.clear()
        self._conv.clear()
        self._log(f"<span style='color:{self.C['dim']}'>// memory cleared</span>")

    def _set_status(self, text):
        self.status_bar_lbl.setText(text)
        self.status_lbl.setText(f"[ {text} ]")
        self._statusbar.set_status(text)

    def _blink(self):
        if self._closing:
            return
        if "STANDBY" in self.status_bar_lbl.text():
            self._blink_state = not self._blink_state
            self.status_bar_lbl.setText("STANDBY" if self._blink_state else "_ _ _ _ _")

    def closeEvent(self, e):
        self._closing = True
        self._blink_timer.stop()
        # Ferma il typewriter
        if hasattr(self, "_tw"):
            self._tw.stop_typing()
        # Attendi che il worker finisca (max 3s) prima di chiudere
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(3000)
        # Ferma il player
        if self._player is not None:
            try:
                self._player.stop()
            except Exception:
                pass
        super().closeEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            self.move(self.pos() + e.globalPosition().toPoint() - self._drag_pos)
            self._drag_pos = e.globalPosition().toPoint()

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    def _toggle_max(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()
