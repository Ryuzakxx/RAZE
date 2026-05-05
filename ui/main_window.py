"""
ui/main_window.py
"""

import os
import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QLineEdit, QPushButton, QFrame
)
from PyQt6.QtCore  import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt6.QtGui   import (
    QFontDatabase, QTextCursor, QTextCharFormat, QColor, QFont
)
from PyQt6.QtMultimedia        import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

from ui.theme   import get
from ui.widgets import StatusBar

try:
    import psutil as _psutil
except ImportError:
    _psutil = None


# ── Registra Space Mono ────────────────────────────────────────────────────────

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
_FONT_FAMILY = "Space Mono"
_FONT_FALLBACK = "Courier New"


def _mono(size: int = 12, bold: bool = False) -> QFont:
    f = QFont(_FONT_FAMILY)
    if not f.exactMatch():
        f = QFont(_FONT_FALLBACK)
    f.setPixelSize(size)
    f.setBold(bold)
    return f


# ── Stylesheet (solo per widget non-log) ───────────────────────────────────────

def _ss(C):
    fm = f"'{_FONT_FAMILY}', '{_FONT_FALLBACK}', monospace"
    return f"""
* {{
    background-color: {C['bg']};
    color: {C['mid']};
    font-family: {fm};
    font-size: 12px;
    border: none;
    outline: none;
}}
QFrame#cell {{
    background-color: {C['bg1']};
    border: 1px solid {C['border']};
}}
QTextEdit#log {{
    background-color: {C['bg']};
    color: {C['hi']};
    font-family: {fm};
    font-size: 12px;
    padding: 14px;
    border: none;
}}
QLineEdit#inp {{
    background-color: {C['bg']};
    color: {C['hi']};
    font-family: {fm};
    font-size: 13px;
    padding: 10px 14px;
    border: none;
    border-top: 1px solid {C['border']};
}}
QLineEdit#inp:focus {{ border-top: 1px solid {C['hi']}; }}
QPushButton#btn {{
    background: transparent; color: {C['dim']};
    font-family: {fm}; font-size: 9px; letter-spacing: 1px;
    padding: 3px 8px; border: 1px solid {C['border']};
}}
QPushButton#btn:hover {{ color: {C['hi']}; border: 1px solid {C['hi']}; }}
QPushButton#send_btn {{
    background: transparent; color: {C['hi']};
    font-family: {fm}; font-size: 10px; letter-spacing: 3px;
    padding: 10px 22px; border: 1px solid {C['hi']}; min-width: 80px;
}}
QPushButton#send_btn:hover {{ background: {C['hi']}; color: {C['bg']}; }}
QPushButton#send_btn:pressed {{
    background: {C['mid']}; border-color: {C['mid']}; color: {C['bg']};
}}
QPushButton#back_btn {{
    background: transparent; color: {C['dim']};
    font-family: {fm}; font-size: 9px; letter-spacing: 2px;
    padding: 3px 10px; border: 1px solid {C['border']};
}}
QPushButton#back_btn:hover {{ color: {C['mid']}; border-color: {C['mid']}; }}
QScrollBar:vertical {{ background: {C['bg']}; width: 3px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {C['dim']}; min-height: 20px; }}
QScrollBar::handle:vertical:hover {{ background: {C['hi']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
"""


# ── Worker ─────────────────────────────────────────────────────────────────────

class WorkerThread(QThread):
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, message, conversation=None):
        super().__init__()
        self.message      = message
        self.conversation = conversation

    def run(self):
        try:
            from core.llm import query_raze
            self.response_ready.emit(query_raze(self.message, self.conversation))
        except Exception as e:
            self.error_occurred.emit(str(e))


# ── Log writer — usa QTextCursor plain-text, NIENTE insertHtml ────────────────

class LogWriter:
    def __init__(self, log: QTextEdit, C: dict):
        self._log = log
        self.C    = C
        self._font_size = 12

    def _fmt(self, hex_color: str, bold: bool = False) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(hex_color))
        f = QFont(_FONT_FAMILY)
        if not f.exactMatch():
            f = QFont(_FONT_FALLBACK)
        f.setPixelSize(self._font_size)
        f.setBold(bold)
        fmt.setFont(f)
        return fmt

    def append_line(self, segments: list[tuple[str, str, bool]]) -> None:
        doc = self._log.document()
        cur = QTextCursor(doc)
        cur.movePosition(QTextCursor.MoveOperation.End)
        if not doc.isEmpty():
            cur.insertBlock()
        for text, color, bold in segments:
            cur.insertText(text, self._fmt(color, bold))
        self._scroll()

    def start_typewriter_line(
        self, prefix_segments: list[tuple[str, str, bool]]
    ) -> int:
        doc = self._log.document()
        cur = QTextCursor(doc)
        cur.movePosition(QTextCursor.MoveOperation.End)
        if not doc.isEmpty():
            cur.insertBlock()
        for text, color, bold in prefix_segments:
            cur.insertText(text, self._fmt(color, bold))
        pos = cur.position()
        self._scroll()
        return pos

    def overwrite_from(self, anchor: int, new_text: str, color: str) -> None:
        doc = self._log.document()
        cur = QTextCursor(doc)
        cur.setPosition(anchor)
        cur.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        cur.insertText(new_text, self._fmt(color))
        self._scroll()

    def _scroll(self):
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())


class Typewriter:
    def __init__(self, writer: LogWriter, C: dict):
        self._w          = writer
        self.C           = C
        self._text       = ""
        self._pos        = 0
        self._anchor     = 0
        self._timer      = QTimer()
        self._timer.timeout.connect(self._tick)
        self.on_finished = None

    def start(
        self,
        prefix_segments: list[tuple[str, str, bool]],
        full_text: str,
        speed_ms: int = 14,
    ):
        self._text   = full_text
        self._pos    = 0
        self._anchor = self._w.start_typewriter_line(prefix_segments)
        self._timer.start(speed_ms)

    def stop(self):
        self._timer.stop()

    def _tick(self):
        if self._pos < len(self._text):
            self._pos += 1
            self._w.overwrite_from(
                self._anchor,
                self._text[: self._pos],
                self.C["hi"],
            )
        else:
            self._timer.stop()
            if self.on_finished:
                self.on_finished()


def _cell_header(label: str, C: dict, right_widget=None) -> QWidget:
    hdr = QWidget()
    hdr.setFixedHeight(24)
    hdr.setStyleSheet(
        f"background:{C['bg1']}; border-bottom:1px solid {C['border']};"
    )
    hl = QHBoxLayout(hdr)
    hl.setContentsMargins(10, 0, 8, 0)
    hl.setSpacing(6)
    lbl = QLabel(label)
    lbl.setStyleSheet(
        f"color:{C['dim']}; font-size:9px; letter-spacing:2px; "
        f"background:transparent; border:none;"
    )
    hl.addWidget(lbl)
    hl.addStretch()
    if right_widget:
        hl.addWidget(right_widget)
    return hdr


class RazeWindow(QMainWindow):
    back_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.C = get()
        self.setWindowTitle("RAZE")
        self.setMinimumSize(900, 640)
        self.resize(1020, 700)
        self.setStyleSheet(_ss(self.C))
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self._drag_pos  = None
        self._player    = None
        self._worker    = None
        self._closing   = False
        self._msg_count = 0

        from core.llm import Conversation
        self._conv = Conversation()

        self._build()
        self._load_video()

        self._lw = LogWriter(self.log, self.C)
        self._tw = Typewriter(self._lw, self.C)
        self._tw.on_finished = self._on_typewriter_done

        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink)
        self._blink_timer.start(900)
        self._blink_state = True

        self._sys_timer = QTimer(self)
        self._sys_timer.timeout.connect(self._update_sys)
        self._sys_timer.start(2000)
        self._update_sys()

        self._lw.append_line([
            ("RAZE // TEXT_MODE — ready. type a message and press ENTER.", self.C["dim"], False)
        ])

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        vlay = QVBoxLayout(root)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)
        vlay.addWidget(self._make_titlebar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        left_col = QVBoxLayout()
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(0)
        left_col.addWidget(self._make_video_cell(), stretch=3)
        left_col.addWidget(self._make_sys_cell(),   stretch=2)
        left_wrap = QWidget()
        left_wrap.setLayout(left_col)

        body.addWidget(left_wrap, stretch=2)
        body.addWidget(self._vdivider())
        body.addWidget(self._make_log_cell(), stretch=3)

        vlay.addLayout(body, stretch=1)
        self._statusbar = StatusBar(self.C)
        vlay.addWidget(self._statusbar)

    def _make_titlebar(self):
        bar = QWidget()
        bar.setFixedHeight(34)
        bar.setStyleSheet(
            f"background:{self.C['bg1']}; border-bottom:1px solid {self.C['border']};"
        )
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(14, 0, 6, 0)
        hl.setSpacing(0)

        for col in ["#3a3a3a", "#3a3a3a", "#3a3a3a"]:
            dot = QLabel("●")
            dot.setStyleSheet(
                f"color:{col}; font-size:9px; background:transparent; border:none; padding:0 3px;"
            )
            hl.addWidget(dot)

        hl.addSpacing(12)
        title = QLabel("RAZE  //  TEXT_MODE")
        title.setStyleSheet(
            f"color:{self.C['hi']}; font-size:10px; letter-spacing:5px; background:transparent; border:none;"
        )
        hl.addWidget(title)
        hl.addStretch()

        self._status_title = QLabel("■ STANDBY")
        self._status_title.setStyleSheet(
            f"color:{self.C['dim']}; font-size:9px; letter-spacing:3px; background:transparent; border:none;"
        )
        hl.addWidget(self._status_title)
        hl.addSpacing(16)

        back_btn = QPushButton("◀ MODE")
        back_btn.setObjectName("back_btn")
        back_btn.setFixedHeight(22)
        back_btn.clicked.connect(self._go_back)
        hl.addWidget(back_btn)
        hl.addSpacing(8)

        for sym, slot in [("—", self.showMinimized), ("□", self._toggle_max), ("×", self.close)]:
            b = QPushButton(sym)
            b.setFixedSize(26, 26)
            b.setStyleSheet(
                f"QPushButton{{background:transparent;color:{self.C['dim']};border:none;font-size:13px;font-family:'{_FONT_FAMILY}','{_FONT_FALLBACK}';}}"
                f"QPushButton:hover{{color:{self.C['hi']};background:{self.C['border']};}}"
            )
            b.clicked.connect(slot)
            hl.addWidget(b)
        return bar

    def _make_video_cell(self):
        cell = QFrame()
        cell.setObjectName("cell")
        vlay = QVBoxLayout(cell)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)
        vlay.addWidget(_cell_header("VISUAL_OUTPUT", self.C))
        vc = QWidget()
        vc.setStyleSheet(f"background:{self.C['bg']}; border:none;")
        self.vid = QVideoWidget(vc)
        self.vid.setStyleSheet(f"background:{self.C['bg']};")
        self.vid_placeholder = QLabel(vc)
        self.vid_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vid_placeholder.hide()
        def _r(e):
            self.vid.setGeometry(vc.rect())
            self.vid_placeholder.setGeometry(vc.rect())
        vc.resizeEvent = _r
        vlay.addWidget(vc, stretch=1)
        return cell

    def _make_sys_cell(self):
        cell = QFrame()
        cell.setObjectName("cell")
        cell.setStyleSheet(
            f"QFrame#cell{{background:{self.C['bg1']}; border:1px solid {self.C['border']}; border-top:none;}}"
        )
        vlay = QVBoxLayout(cell)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)
        vlay.addWidget(_cell_header("SYSTEM_STATS", self.C))
        content = QWidget()
        content.setStyleSheet(f"background:{self.C['bg1']}; border:none;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(14, 10, 14, 10)
        cl.setSpacing(7)
        self._sys_labels = {}
        for key, val in [
            ("STATUS", "STANDBY"), ("MODE", "TEXT"),
            ("THEME", self.C["name"].upper()), ("MSGS", "0"),
            ("CPU", "—"), ("RAM", "—"), ("TIME", "—"),
        ]:
            row = QHBoxLayout()
            row.setSpacing(0)
            k = QLabel(key)
            k.setStyleSheet(
                f"color:{self.C['dim']}; font-size:9px; letter-spacing:2px; background:transparent; border:none;"
            )
            v = QLabel(val)
            v.setAlignment(Qt.AlignmentFlag.AlignRight)
            v.setStyleSheet(
                f"color:{self.C['mid']}; font-size:9px; letter-spacing:1px; background:transparent; border:none;"
            )
            row.addWidget(k)
            row.addStretch()
            row.addWidget(v)
            cl.addLayout(row)
            self._sys_labels[key] = v
        cl.addStretch()
        vlay.addWidget(content, stretch=1)
        return cell

    def _make_log_cell(self):
        cell = QFrame()
        cell.setObjectName("cell")
        cell.setStyleSheet(
            f"QFrame#cell{{background:{self.C['bg']}; border:1px solid {self.C['border']}; border-left:none;}}"
        )
        vlay = QVBoxLayout(cell)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)

        clr_btn = QPushButton("CLR")
        clr_btn.setObjectName("btn")
        clr_btn.setFixedSize(32, 16)
        clr_btn.clicked.connect(self._clear_log)
        vlay.addWidget(_cell_header("OUTPUT_LOG", self.C, clr_btn))

        self.log = QTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log.setFont(_mono(12))
        vlay.addWidget(self.log, stretch=1)

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{self.C['border']};")
        vlay.addWidget(sep)

        inp_bar = QWidget()
        inp_bar.setFixedHeight(46)
        inp_bar.setStyleSheet(f"background:{self.C['bg1']}; border:none;")
        ib = QHBoxLayout(inp_bar)
        ib.setContentsMargins(0, 0, 0, 0)
        ib.setSpacing(0)

        prompt_lbl = QLabel("  >_  ")
        prompt_lbl.setStyleSheet(
            f"color:{self.C['hi']}; font-size:13px; background:{self.C['bg1']}; border:none; border-right:1px solid {self.C['border']}; padding:0 8px;"
        )
        ib.addWidget(prompt_lbl)

        self.inp = QLineEdit()
        self.inp.setObjectName("inp")
        self.inp.setFont(_mono(13))
        self.inp.setPlaceholderText("insert command...")
        self.inp.returnPressed.connect(self._send)
        ib.addWidget(self.inp, stretch=1)

        send_btn = QPushButton("SEND")
        send_btn.setObjectName("send_btn")
        send_btn.clicked.connect(self._send)
        ib.addWidget(send_btn)

        vlay.addWidget(inp_bar)
        return cell

    def _vdivider(self):
        d = QFrame()
        d.setFixedWidth(1)
        d.setStyleSheet(f"background:{self.C['border']}; border:none;")
        return d

    def _load_video(self):
        base = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets"))
        self._vid_idle     = os.path.join(base, "raze_white.mp4")
        self._vid_thinking = os.path.join(base, "loading.mp4")
        if not os.path.exists(self._vid_idle):
            self.vid.hide()
            self.vid_placeholder.show()
            self.vid_placeholder.setText("[ NO VIDEO ]")
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
        if not text or self._closing:
            return
        self.inp.clear()
        self.inp.setEnabled(False)
        ts = datetime.datetime.now().strftime("%H:%M:%S")

        self._lw.append_line([
            (f"[{ts}] ", self.C["dim"], False),
            (f"> {text}", self.C["mid"], False),
        ])

        self._set_status("PROCESSING")
        self._set_sys("STATUS", "PROCESSING")
        self._set_thinking(True)

        self._worker = WorkerThread(text, self._conv)
        self._worker.response_ready.connect(self._on_resp)
        self._worker.error_occurred.connect(self._on_err)
        self._worker.finished.connect(
            lambda: self.inp.setEnabled(True) if not self._closing else None
        )
        self._worker.start()

    def _on_resp(self, text):
        if self._closing:
            return
        self._set_thinking(False)
        self._set_status("RESPONDING")
        self._set_sys("STATUS", "RESPONDING")
        self._msg_count += 1
        self._set_sys("MSGS", str(self._msg_count))
        self._statusbar.inc_messages()
        ts = datetime.datetime.now().strftime("%H:%M:%S")

        self._tw.start(
            prefix_segments=[(f"[{ts}] RAZE> ", self.C["dim"], False)],
            full_text=text,
        )

    def _on_typewriter_done(self):
        if self._closing:
            return
        self._set_status("STANDBY")
        self._set_sys("STATUS", "STANDBY")

    def _on_err(self, err):
        if self._closing:
            return
        self._set_thinking(False)
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._lw.append_line([
            (f"[{ts}] ", self.C["dim"], False),
            (f"ERR: {err}", self.C["mid"], False),
        ])
        self._set_status("ERROR")
        self._set_sys("STATUS", "ERROR")

    def _clear_log(self):
        self.log.clear()
        self._conv.clear()
        self._msg_count = 0
        self._set_sys("MSGS", "0")
        self._lw.append_line([("// memory cleared — ready", self.C["dim"], False)])

    def _set_status(self, text):
        self._status_title.setText(f"■ {text}")
        self._statusbar.set_status(text)

    def _set_sys(self, key, val):
        if key in self._sys_labels:
            self._sys_labels[key].setText(val)

    def _update_sys(self):
        if self._closing:
            return
        self._set_sys("TIME", datetime.datetime.now().strftime("%H:%M:%S"))
        self._set_sys("THEME", self.C["name"].upper())
        try:
            if _psutil is not None:
                self._set_sys("CPU", f"{_psutil.cpu_percent(interval=None):.0f}%")
                self._set_sys("RAM", f"{_psutil.virtual_memory().used/(1024**3):.1f} GB")
        except Exception:
            pass

    def _blink(self):
        if self._closing:
            return
        if "STANDBY" in self._status_title.text():
            self._blink_state = not self._blink_state
            self._status_title.setText("■ STANDBY" if self._blink_state else "□ STANDBY")

    def _go_back(self):
        self._closing = True
        self._blink_timer.stop()
        self._sys_timer.stop()
        self._tw.stop()
        if self._worker and self._worker.isRunning():
            self._worker.wait(2000)
        if self._player:
            try:
                self._player.stop()
            except Exception:
                pass
        self.back_requested.emit()
        self.close()

    def closeEvent(self, e):
        self._closing = True
        self._blink_timer.stop()
        self._sys_timer.stop()
        self._tw.stop()
        if self._worker and self._worker.isRunning():
            self._worker.wait(3000)
        if self._player:
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
