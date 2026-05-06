"""
ui/main_window.py
Layout: sidebar sinistra (stats/info) + area chat destra, stile terminale.
"""

import os
import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QLineEdit, QPushButton, QFrame,
    QScrollArea
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


# ── Font ────────────────────────────────────────────────────────────────────────

def _register_fonts():
    base = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "assets")
    )
    for fname in (
        "SpaceMono-Regular.ttf", "SpaceMono-Bold.ttf",
        "SpaceMono-Italic.ttf",  "SpaceMono-BoldItalic.ttf",
    ):
        p = os.path.join(base, fname)
        if os.path.exists(p):
            QFontDatabase.addApplicationFont(p)

_register_fonts()
_FF  = "'Space Mono','Courier New',monospace"
_FONT_FAMILY   = "Space Mono"
_FONT_FALLBACK = "Courier New"


def _mono(size: int = 12, bold: bool = False) -> QFont:
    f = QFont(_FONT_FAMILY)
    if not f.exactMatch():
        f = QFont(_FONT_FALLBACK)
    f.setPixelSize(size)
    f.setBold(bold)
    return f


# ── Stylesheet ────────────────────────────────────────────────────────────────

def _ss(C):
    return f"""
* {{
    background-color: {C['bg']};
    color: {C['mid']};
    font-family: {_FF};
    font-size: 12px;
    border: none;
    outline: none;
}}
QTextEdit#log {{
    background-color: {C['bg']};
    color: {C['hi']};
    font-family: {_FF};
    font-size: 12px;
    padding: 16px 20px;
    border: none;
}}
QLineEdit#inp {{
    background-color: {C['bg']};
    color: {C['hi']};
    font-family: {_FF};
    font-size: 12px;
    padding: 0 14px;
    border: none;
}}
QLineEdit#inp:focus {{ border: none; }}
QPushButton#send_btn {{
    background: transparent;
    color: {C['hi']};
    font-family: {_FF};
    font-size: 10px;
    letter-spacing: 2px;
    padding: 0 18px;
    border-left: 1px solid {C['border']};
    min-width: 70px;
}}
QPushButton#send_btn:hover {{ background: {C['hi']}; color: {C['bg']}; }}
QPushButton#icon_btn {{
    background: transparent;
    color: {C['dim']};
    font-family: {_FF};
    font-size: 9px;
    letter-spacing: 1px;
    padding: 2px 8px;
    border: 1px solid {C['border']};
}}
QPushButton#icon_btn:hover {{ color: {C['hi']}; border-color: {C['hi']}; }}
QScrollBar:vertical {{ background: {C['bg']}; width: 2px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {C['dim']}; min-height: 20px; }}
QScrollBar::handle:vertical:hover {{ background: {C['hi']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ height: 0; }}
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


# ── LogWriter / Typewriter ────────────────────────────────────────────────────

class LogWriter:
    def __init__(self, log: QTextEdit, C: dict):
        self._log = log
        self.C    = C

    def _fmt(self, hex_color: str, bold: bool = False) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(hex_color))
        f = QFont(_FONT_FAMILY)
        if not f.exactMatch():
            f = QFont(_FONT_FALLBACK)
        f.setPixelSize(12)
        f.setBold(bold)
        fmt.setFont(f)
        return fmt

    def append_line(self, segments: list) -> None:
        doc = self._log.document()
        cur = QTextCursor(doc)
        cur.movePosition(QTextCursor.MoveOperation.End)
        if not doc.isEmpty():
            cur.insertBlock()
        for text, color, bold in segments:
            cur.insertText(text, self._fmt(color, bold))
        self._scroll()

    def start_typewriter_line(self, prefix_segments: list) -> int:
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

    def start(self, prefix_segments: list, full_text: str, speed_ms: int = 14):
        self._text   = full_text
        self._pos    = 0
        self._anchor = self._w.start_typewriter_line(prefix_segments)
        self._timer.start(speed_ms)

    def stop(self):
        self._timer.stop()

    def _tick(self):
        if self._pos < len(self._text):
            self._pos += 1
            self._w.overwrite_from(self._anchor, self._text[:self._pos], self.C["hi"])
        else:
            self._timer.stop()
            if self.on_finished:
                self.on_finished()


# ── RazeWindow ────────────────────────────────────────────────────────────────

class RazeWindow(QMainWindow):
    back_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.C = get()
        self.setWindowTitle("RAZE")
        self.setMinimumSize(860, 580)
        self.resize(1060, 680)
        self.setStyleSheet(_ss(self.C))
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self._drag_pos  = None
        self._player    = None
        self._worker    = None
        self._closing   = False
        self._msg_count = 0
        self._busy      = False

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
            ("RAZE ── TEXT_MODE", self.C["hi"], True),
        ])
        self._lw.append_line([
            ("ready. type a message below.", self.C["dim"], False),
        ])
        self._lw.append_line([(" ", self.C["dim"], False)])

    # ── Build ───────────────────────────────────────────────────────────────

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        vlay = QVBoxLayout(root)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)

        vlay.addWidget(self._make_titlebar())

        # ─ body: sidebar | divider | chat area
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._make_sidebar(), stretch=0)
        body.addWidget(self._hdivider())
        body.addWidget(self._make_chat_area(), stretch=1)
        vlay.addLayout(body, stretch=1)

        self._statusbar = StatusBar(self.C)
        vlay.addWidget(self._statusbar)

    # ── Title bar ────────────────────────────────────────────────────────────

    def _make_titlebar(self):
        bar = QWidget()
        bar.setFixedHeight(36)
        bar.setStyleSheet(
            f"background:{self.C['bg1']}; border-bottom:1px solid {self.C['border']};"
        )
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(14, 0, 8, 0)
        hl.setSpacing(0)

        # logo
        logo = QLabel("RAZE")
        logo.setStyleSheet(
            f"color:{self.C['hi']}; font-size:13px; letter-spacing:6px;"
            f" font-weight:bold; background:transparent; border:none; padding-right:20px;"
        )
        hl.addWidget(logo)

        # tab attivo
        tab = QLabel("TEXT_MODE")
        tab.setFixedHeight(36)
        tab.setStyleSheet(
            f"color:{self.C['hi']}; font-size:10px; letter-spacing:3px;"
            f" background:{self.C['bg']}; border:none;"
            f" padding: 0 18px;"
            f" border-right: 1px solid {self.C['border']};"
        )
        hl.addWidget(tab)

        hl.addStretch()

        # status pill
        self._status_title = QLabel("■ STANDBY")
        self._status_title.setStyleSheet(
            f"color:{self.C['dim']}; font-size:9px; letter-spacing:3px;"
            f" background:transparent; border:none; padding-right:16px;"
        )
        hl.addWidget(self._status_title)

        # back
        back_btn = QPushButton("◀ MODE")
        back_btn.setObjectName("icon_btn")
        back_btn.setFixedHeight(22)
        back_btn.clicked.connect(self._go_back)
        hl.addWidget(back_btn)
        hl.addSpacing(10)

        # wm buttons
        for sym, slot in [("–", self.showMinimized), ("□", self._toggle_max), ("×", self.close)]:
            b = QPushButton(sym)
            b.setFixedSize(28, 28)
            b.setStyleSheet(
                f"QPushButton{{background:transparent;color:{self.C['dim']};border:none;font-size:13px;}}"
                f"QPushButton:hover{{color:{self.C['hi']};background:{self.C['border']};}}"
            )
            b.clicked.connect(slot)
            hl.addWidget(b)
        return bar

    # ── Sidebar ─────────────────────────────────────────────────────────────

    def _make_sidebar(self):
        sb = QWidget()
        sb.setFixedWidth(220)
        sb.setStyleSheet(f"background:{self.C['bg1']}; border:none;")
        lay = QVBoxLayout(sb)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ─ video preview
        vid_wrap = QWidget()
        vid_wrap.setFixedHeight(160)
        vid_wrap.setStyleSheet(f"background:{self.C['bg']}; border-bottom:1px solid {self.C['border']};")
        self.vid = QVideoWidget(vid_wrap)
        self.vid.setStyleSheet(f"background:{self.C['bg']};")
        self.vid_placeholder = QLabel(vid_wrap)
        self.vid_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vid_placeholder.setStyleSheet(
            f"color:{self.C['dim']}; background:transparent; border:none; font-family:{_FF};"
        )
        self.vid_placeholder.hide()
        def _r(e):
            self.vid.setGeometry(vid_wrap.rect())
            self.vid_placeholder.setGeometry(vid_wrap.rect())
        vid_wrap.resizeEvent = _r
        lay.addWidget(vid_wrap)

        # ─ sezione stats
        lay.addWidget(self._sb_section("SYSTEM"))
        self._sys_labels = {}
        for key, val in [
            ("STATUS",  "STANDBY"),
            ("THEME",   self.C["name"].upper()),
            ("MSGS",    "0"),
            ("CPU",     "—"),
            ("RAM",     "—"),
            ("TIME",    "—"),
        ]:
            row = self._sb_row(key, val)
            lay.addWidget(row)
            self._sys_labels[key] = row._val_lbl

        lay.addWidget(self._sb_divider())

        # ─ sezione session
        lay.addWidget(self._sb_section("SESSION"))
        self._session_log = QTextEdit()
        self._session_log.setReadOnly(True)
        self._session_log.setFont(_mono(9))
        self._session_log.setFixedHeight(120)
        self._session_log.setStyleSheet(
            f"background:{self.C['bg1']}; color:{self.C['dim']};"
            f" font-family:{_FF}; font-size:9px; padding:6px 10px; border:none;"
        )
        lay.addWidget(self._session_log)

        lay.addWidget(self._sb_divider())

        # ─ clear button
        clr = QPushButton("CLR MEMORY")
        clr.setObjectName("icon_btn")
        clr.setFixedHeight(28)
        clr.setStyleSheet(
            f"QPushButton#icon_btn{{"
            f"background:transparent; color:{self.C['dim']};"
            f" font-family:{_FF}; font-size:9px; letter-spacing:2px;"
            f" border-top:1px solid {self.C['border']}; border-bottom:1px solid {self.C['border']};"
            f" border-left:none; border-right:none; padding:0 10px;"
            f"}}"
            f"QPushButton#icon_btn:hover{{color:{self.C['hi']};}}"
        )
        clr.clicked.connect(self._clear_log)
        lay.addWidget(clr)

        lay.addStretch()

        # ─ footer sidebar
        footer = QLabel("RAZE v0.1-dev")
        footer.setFixedHeight(28)
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet(
            f"color:{self.C['dim']}; font-size:8px; letter-spacing:2px;"
            f" background:{self.C['bg1']}; border-top:1px solid {self.C['border']}; border:none;"
            f" border-top:1px solid {self.C['border']};"
        )
        lay.addWidget(footer)
        return sb

    def _sb_section(self, title: str) -> QWidget:
        w = QWidget()
        w.setFixedHeight(22)
        w.setStyleSheet(f"background:{self.C['bg1']}; border-bottom:1px solid {self.C['border']};")
        l = QHBoxLayout(w)
        l.setContentsMargins(10, 0, 10, 0)
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"color:{self.C['dim']}; font-size:8px; letter-spacing:3px; background:transparent; border:none;"
        )
        l.addWidget(lbl)
        l.addStretch()
        return w

    def _sb_row(self, key: str, val: str) -> QWidget:
        w = QWidget()
        w.setFixedHeight(22)
        w.setStyleSheet(f"background:{self.C['bg1']};")
        hl = QHBoxLayout(w)
        hl.setContentsMargins(10, 0, 10, 0)
        hl.setSpacing(0)
        k = QLabel(key)
        k.setStyleSheet(
            f"color:{self.C['dim']}; font-size:9px; letter-spacing:1px; background:transparent; border:none;"
        )
        v = QLabel(val)
        v.setAlignment(Qt.AlignmentFlag.AlignRight)
        v.setStyleSheet(
            f"color:{self.C['mid']}; font-size:9px; background:transparent; border:none;"
        )
        hl.addWidget(k)
        hl.addStretch()
        hl.addWidget(v)
        w._val_lbl = v
        return w

    def _sb_divider(self) -> QWidget:
        d = QWidget()
        d.setFixedHeight(1)
        d.setStyleSheet(f"background:{self.C['border']};")
        return d

    # ── Chat area ───────────────────────────────────────────────────────────

    def _make_chat_area(self):
        wrap = QWidget()
        wrap.setStyleSheet(f"background:{self.C['bg']}; border:none;")
        vlay = QVBoxLayout(wrap)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)

        # chat sub-header
        subhdr = QWidget()
        subhdr.setFixedHeight(28)
        subhdr.setStyleSheet(
            f"background:{self.C['bg1']}; border-bottom:1px solid {self.C['border']};"
        )
        shl = QHBoxLayout(subhdr)
        shl.setContentsMargins(16, 0, 12, 0)
        path_lbl = QLabel("OUTPUT_LOG")
        path_lbl.setStyleSheet(
            f"color:{self.C['dim']}; font-size:9px; letter-spacing:2px;"
            f" background:transparent; border:none;"
        )
        shl.addWidget(path_lbl)
        shl.addStretch()
        line_lbl = QLabel("MSGS: 0")
        line_lbl.setStyleSheet(
            f"color:{self.C['dim']}; font-size:9px; background:transparent; border:none;"
        )
        self._msgs_lbl = line_lbl
        shl.addWidget(line_lbl)
        vlay.addWidget(subhdr)

        # log
        self.log = QTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log.setFont(_mono(12))
        vlay.addWidget(self.log, stretch=1)

        # input bar
        vlay.addWidget(self._make_input_bar())
        return wrap

    def _make_input_bar(self):
        bar = QWidget()
        bar.setFixedHeight(44)
        bar.setStyleSheet(
            f"background:{self.C['bg1']};"
            f" border-top:1px solid {self.C['border']};"
        )
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)

        prompt = QLabel("  ❯_  ")
        prompt.setFixedWidth(44)
        prompt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prompt.setStyleSheet(
            f"color:{self.C['hi']}; font-size:13px;"
            f" background:{self.C['bg1']}; border-right:1px solid {self.C['border']};"
            f" border:none; border-right:1px solid {self.C['border']};"
        )
        hl.addWidget(prompt)

        self.inp = QLineEdit()
        self.inp.setObjectName("inp")
        self.inp.setFont(_mono(12))
        self.inp.setPlaceholderText("insert command...")
        self.inp.returnPressed.connect(self._send)
        hl.addWidget(self.inp, stretch=1)

        send_btn = QPushButton("SEND")
        send_btn.setObjectName("send_btn")
        send_btn.setFixedHeight(44)
        send_btn.clicked.connect(self._send)
        hl.addWidget(send_btn)
        return bar

    def _hdivider(self):
        d = QFrame()
        d.setFixedWidth(1)
        d.setStyleSheet(f"background:{self.C['border']}; border:none;")
        return d

    # ── Video ────────────────────────────────────────────────────────────────

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

    # ── Logic ─────────────────────────────────────────────────────────────────

    def _send(self):
        text = self.inp.text().strip()
        if not text or self._closing or self._busy:
            return
        self._busy = True
        self.inp.clear()
        self.inp.setEnabled(False)
        ts = datetime.datetime.now().strftime("%H:%M:%S")

        self._lw.append_line([
            (f"[{ts}] ", self.C["dim"], False),
            (f"> ", self.C["dim"], False),
            (text, self.C["mid"], False),
        ])
        self._session_log.append(f"> {text[:30]}{'...' if len(text) > 30 else ''}")

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
        self._msgs_lbl.setText(f"MSGS: {self._msg_count}")
        self._statusbar.inc_messages()
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._session_log.append(f"< {text[:30]}{'...' if len(text) > 30 else ''}")

        self._tw.start(
            prefix_segments=[(f"[{ts}] RAZE ❯ ", self.C["dim"], False)],
            full_text=text,
        )

    def _on_typewriter_done(self):
        if self._closing:
            return
        self._busy = False
        self._lw.append_line([(" ", self.C["dim"], False)])
        self._set_status("STANDBY")
        self._set_sys("STATUS", "STANDBY")

    def _on_err(self, err):
        if self._closing:
            return
        self._busy = False
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
        self._session_log.clear()
        self._conv.clear()
        self._msg_count = 0
        self._set_sys("MSGS", "0")
        self._msgs_lbl.setText("MSGS: 0")
        self._lw.append_line([("// memory cleared — ready", self.C["dim"], False)])
        self._lw.append_line([(" ", self.C["dim"], False)])

    # ── Helpers ──────────────────────────────────────────────────────────────

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

    def _toggle_max(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()

    def _go_back(self):
        self._closing = True
        self._blink_timer.stop()
        self._sys_timer.stop()
        self._tw.stop()
        if self._worker and self._worker.isRunning():
            self._worker.wait(2000)
        if self._player:
            try: self._player.stop()
            except Exception: pass
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
            try: self._player.stop()
            except Exception: pass
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
