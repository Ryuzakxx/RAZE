"""
ui/main_window.py
"""

import os
import sys
import subprocess
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

from ui.theme import get


# ── Font ──────────────────────────────────────────────────────────────────

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
_FONT_FAMILY  = "Space Mono"
_FONT_FALLBACK = "Courier New"
_FF = f"'{_FONT_FAMILY}','{_FONT_FALLBACK}',monospace"


def _mono(size: int = 12, bold: bool = False) -> QFont:
    f = QFont(_FONT_FAMILY)
    if not f.exactMatch():
        f = QFont(_FONT_FALLBACK)
    f.setPixelSize(size)
    f.setBold(bold)
    return f


# ── CPU / RAM (stdlib puro) ─────────────────────────────────────────────────

class _SysPoller(QThread):
    ready = pyqtSignal(str, str)   # cpu_str, ram_str

    def run(self):
        self.ready.emit(self._cpu(), self._ram())

    # ---- CPU ----
    def _cpu(self) -> str:
        try:
            if sys.platform == "win32":
                return self._cpu_windows()
            elif sys.platform == "darwin":
                return self._cpu_macos()
            else:
                return self._cpu_linux()
        except Exception:
            return "n/a"

    def _cpu_linux(self) -> str:
        import time
        s1 = self._stat()
        time.sleep(0.3)
        s2 = self._stat()
        total = sum(s2) - sum(s1)
        idle  = s2[3] - s1[3]
        if total <= 0:
            return "n/a"
        return f"{100.0 * (1 - idle / total):.0f}%"

    def _stat(self) -> list:
        with open("/proc/stat", "r") as f:
            row = f.readline()
        return [int(x) for x in row.split()[1:]]

    def _cpu_windows(self) -> str:
        out = subprocess.check_output(
            ["wmic", "cpu", "get", "loadpercentage"],
            timeout=4, stderr=subprocess.DEVNULL
        ).decode(errors="ignore")
        for ln in out.splitlines():
            ln = ln.strip()
            if ln.isdigit():
                return f"{ln}%"
        return "n/a"

    def _cpu_macos(self) -> str:
        import re
        out = subprocess.check_output(
            ["sh", "-c", "top -l1 -n0 | grep 'CPU usage'"],
            timeout=6, stderr=subprocess.DEVNULL
        ).decode(errors="ignore")
        m = re.search(r"([\d.]+)%\s*idle", out)
        if m:
            return f"{100 - float(m.group(1)):.0f}%"
        return "n/a"

    # ---- RAM ----
    def _ram(self) -> str:
        try:
            if sys.platform == "win32":
                return self._ram_windows()
            elif sys.platform == "darwin":
                return self._ram_macos()
            else:
                return self._ram_linux()
        except Exception:
            return "n/a"

    def _ram_linux(self) -> str:
        info = {}
        with open("/proc/meminfo", "r") as f:
            for ln in f:
                k, _, v = ln.partition(":")
                info[k.strip()] = int(v.strip().split()[0])  # kB
        total     = info.get("MemTotal", 0)
        available = info.get("MemAvailable", info.get("MemFree", 0))
        used_gb   = (total - available) / (1024 ** 2)
        return f"{used_gb:.1f} GB"

    def _ram_windows(self) -> str:
        out = subprocess.check_output(
            ["wmic", "OS", "get",
             "TotalVisibleMemorySize,FreePhysicalMemory"],
            timeout=4, stderr=subprocess.DEVNULL
        ).decode(errors="ignore")
        lines = [l.strip() for l in out.splitlines() if l.strip()]
        if len(lines) >= 2:
            vals = lines[1].split()
            if len(vals) == 2:
                free_kb  = int(vals[0])
                total_kb = int(vals[1])
                return f"{(total_kb - free_kb) / (1024**2):.1f} GB"
        return "n/a"

    def _ram_macos(self) -> str:
        import re
        vm = subprocess.check_output(
            ["vm_stat"], timeout=4, stderr=subprocess.DEVNULL
        ).decode(errors="ignore")
        def pages(pat):
            m = re.search(pat, vm)
            return int(m.group(1)) if m else 0
        used = (pages(r"Pages active:\s+(\d+)") +
                pages(r"Pages wired down:\s+(\d+)")) * 4096
        return f"{used / (1024**3):.1f} GB"


# ── Stylesheet ─────────────────────────────────────────────────────────────

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
QFrame#cell {{
    background-color: {C['bg1']};
    border: 1px solid {C['border']};
}}
QTextEdit#log {{
    background-color: {C['bg']};
    color: {C['hi']};
    font-family: {_FF};
    font-size: 12px;
    padding: 14px;
    border: none;
}}
QLineEdit#inp {{
    background-color: {C['bg']};
    color: {C['hi']};
    font-family: {_FF};
    font-size: 13px;
    padding: 10px 14px;
    border: none;
    border-top: 1px solid {C['border']};
}}
QLineEdit#inp:focus {{ border-top: 1px solid {C['hi']}; }}

QPushButton#mode_btn {{
    background: transparent;
    color: {C['hi']};
    border: 1px solid {C['border']};
    padding: 10px 22px;
    font-family: {_FF};
    font-size: 10px;
    letter-spacing: 3px;
    min-width: 80px;
    min-height: 46px;
}}
QPushButton#mode_btn:hover {{
    background: {C['hi']};
    color: {C['bg']};
    border-color: {C['hi']};
}}
QPushButton#mode_btn:pressed {{
    background: {C['mid']};
    color: {C['bg']};
    border-color: {C['mid']};
}}

QPushButton#btn {{
    background: transparent;
    color: {C['dim']};
    font-family: {_FF};
    font-size: 9px;
    letter-spacing: 1px;
    padding: 3px 8px;
    border: 1px solid {C['border']};
}}
QPushButton#btn:hover {{ color: {C['hi']}; border: 1px solid {C['hi']}; }}

QPushButton#back_btn {{
    background: transparent;
    color: {C['dim']};
    font-family: {_FF};
    font-size: 9px;
    letter-spacing: 2px;
    padding: 3px 10px;
    border: 1px solid {C['border']};
}}
QPushButton#back_btn:hover {{ color: {C['mid']}; border-color: {C['mid']}; }}

QScrollBar:vertical {{ background: {C['bg']}; width: 3px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {C['dim']}; min-height: 20px; }}
QScrollBar::handle:vertical:hover {{ background: {C['hi']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
"""


# ── Worker ─────────────────────────────────────────────────────────────────

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


# ── LogWriter ────────────────────────────────────────────────────────────────

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

    def append_line(self, segments):
        doc = self._log.document()
        cur = QTextCursor(doc)
        cur.movePosition(QTextCursor.MoveOperation.End)
        if not doc.isEmpty():
            cur.insertBlock()
        for text, color, bold in segments:
            cur.insertText(text, self._fmt(color, bold))
        self._scroll()

    def start_typewriter_line(self, prefix_segments) -> int:
        doc = self._log.document()
        cur = QTextCursor(doc)
        cur.movePosition(QTextCursor.MoveOperation.End)
        if not doc.isEmpty():
            cur.insertBlock()
        for text, color, bold in prefix_segments:
            cur.insertText(text, self._fmt(color, bold))
        self._scroll()
        return cur.position()

    def overwrite_from(self, anchor: int, new_text: str, color: str):
        doc = self._log.document()
        cur = QTextCursor(doc)
        cur.setPosition(anchor)
        cur.movePosition(QTextCursor.MoveOperation.End,
                         QTextCursor.MoveMode.KeepAnchor)
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

    def start(self, prefix_segments, full_text: str, speed_ms: int = 14):
        self._text   = full_text
        self._pos    = 0
        self._anchor = self._w.start_typewriter_line(prefix_segments)
        self._timer.start(speed_ms)

    def stop(self):
        self._timer.stop()

    def _tick(self):
        if self._pos < len(self._text):
            self._pos += 1
            self._w.overwrite_from(self._anchor,
                                   self._text[:self._pos],
                                   self.C["hi"])
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
        f"color:{C['dim']}; font-size:9px; letter-spacing:2px;"
        f" background:transparent; border:none;"
    )
    hl.addWidget(lbl)
    hl.addStretch()
    if right_widget:
        hl.addWidget(right_widget)
    return hdr


# ── RazeWindow ──────────────────────────────────────────────────────────────

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
        self._drag_pos   = None
        self._player     = None
        self._worker     = None
        self._closing    = False
        self._msg_count  = 0
        self._sys_poller = None

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
        self._sys_timer.start(4000)
        # primo poll immediato
        self._update_sys()

        self._lw.append_line([
            ("RAZE // TEXT_MODE — ready. type a message and press ENTER.",
             self.C["dim"], False)
        ])

    # ── build ─────────────────────────────────────────────────────────────

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
            dot = QLabel("\u25cf")
            dot.setStyleSheet(
                f"color:{col}; font-size:9px; background:transparent;"
                f" border:none; padding:0 3px;"
            )
            hl.addWidget(dot)

        hl.addSpacing(12)
        title = QLabel("RAZE  //  TEXT_MODE")
        title.setStyleSheet(
            f"color:{self.C['hi']}; font-size:10px; letter-spacing:5px;"
            f" background:transparent; border:none;"
        )
        hl.addWidget(title)
        hl.addStretch()

        self._status_title = QLabel("\u25a0 STANDBY")
        self._status_title.setStyleSheet(
            f"color:{self.C['dim']}; font-size:9px; letter-spacing:3px;"
            f" background:transparent; border:none;"
        )
        hl.addWidget(self._status_title)
        hl.addSpacing(16)

        back_btn = QPushButton("\u25c0 MODE")
        back_btn.setObjectName("back_btn")
        back_btn.setFixedHeight(22)
        back_btn.clicked.connect(self._go_back)
        hl.addWidget(back_btn)
        hl.addSpacing(8)

        for sym, slot in [
            ("\u2014", self.showMinimized),
            ("\u25a1", self._toggle_max),
            ("\u00d7", self.close),
        ]:
            b = QPushButton(sym)
            b.setFixedSize(26, 26)
            b.setStyleSheet(
                f"QPushButton{{background:transparent;color:{self.C['dim']};"
                f"border:none;font-size:13px;font-family:{_FF};}}"
                f"QPushButton:hover{{color:{self.C['hi']};"
                f"background:{self.C['border']};}}"
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
            f"QFrame#cell{{background:{self.C['bg1']};"
            f" border:1px solid {self.C['border']}; border-top:none;}}"
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
            ("STATUS", "STANDBY"),
            ("MODE",   "TEXT"),
            ("THEME",  self.C["name"].upper()),
            ("MSGS",   "0"),
            ("CPU",    "..."),
            ("RAM",    "..."),
            ("TIME",   "\u2014"),
        ]:
            row = QHBoxLayout()
            row.setSpacing(0)
            k = QLabel(key)
            k.setStyleSheet(
                f"color:{self.C['dim']}; font-size:9px; letter-spacing:2px;"
                f" background:transparent; border:none;"
            )
            v = QLabel(val)
            v.setAlignment(Qt.AlignmentFlag.AlignRight)
            v.setStyleSheet(
                f"color:{self.C['mid']}; font-size:9px; letter-spacing:1px;"
                f" background:transparent; border:none;"
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
            f"QFrame#cell{{background:{self.C['bg']};"
            f" border:1px solid {self.C['border']}; border-left:none;}}"
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

        # ─ input bar ────────────────────────────────────────────────
        inp_bar = QWidget()
        inp_bar.setFixedHeight(46)
        inp_bar.setStyleSheet(f"background:{self.C['bg1']}; border:none;")
        ib = QHBoxLayout(inp_bar)
        ib.setContentsMargins(0, 0, 0, 0)
        ib.setSpacing(0)

        prompt_lbl = QLabel("  >_  ")
        prompt_lbl.setStyleSheet(
            f"color:{self.C['hi']}; font-size:13px;"
            f" background:{self.C['bg1']}; border:none;"
            f" border-right:1px solid {self.C['border']}; padding:0 8px;"
        )
        ib.addWidget(prompt_lbl)

        self.inp = QLineEdit()
        self.inp.setObjectName("inp")
        self.inp.setFont(_mono(13))
        self.inp.setPlaceholderText("insert command...")
        self.inp.returnPressed.connect(self._send)
        ib.addWidget(self.inp, stretch=1)

        vlay.addWidget(inp_bar)
        return cell

    def _vdivider(self):
        d = QFrame()
        d.setFixedWidth(1)
        d.setStyleSheet(f"background:{self.C['border']}; border:none;")
        return d

    # ── video ──────────────────────────────────────────────────────────────

    def _load_video(self):
        base = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "assets")
        )
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

    # ── chat ───────────────────────────────────────────────────────────────

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
        self._lw.append_line(
            [("// memory cleared — ready", self.C["dim"], False)]
        )

    # ── sys stats ──────────────────────────────────────────────────────

    def _set_status(self, text: str):
        self._status_title.setText(f"\u25a0 {text}")

    def _set_sys(self, key: str, val: str):
        if key in self._sys_labels:
            self._sys_labels[key].setText(val)

    def _update_sys(self):
        if self._closing:
            return
        self._set_sys("TIME",  datetime.datetime.now().strftime("%H:%M:%S"))
        self._set_sys("THEME", self.C["name"].upper())
        if self._sys_poller is None or not self._sys_poller.isRunning():
            self._sys_poller = _SysPoller()
            self._sys_poller.ready.connect(self._on_sys_ready)
            self._sys_poller.start()

    def _on_sys_ready(self, cpu: str, ram: str):
        if not self._closing:
            self._set_sys("CPU", cpu)
            self._set_sys("RAM", ram)

    # ── blink ─────────────────────────────────────────────────────────────

    def _blink(self):
        if self._closing:
            return
        if "STANDBY" in self._status_title.text():
            self._blink_state = not self._blink_state
            self._status_title.setText(
                "\u25a0 STANDBY" if self._blink_state else "\u25a1 STANDBY"
            )

    # ── nav ───────────────────────────────────────────────────────────────

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

    # ── drag ───────────────────────────────────────────────────────────────

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            self.move(
                self.pos() + e.globalPosition().toPoint() - self._drag_pos
            )
            self._drag_pos = e.globalPosition().toPoint()

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    def _toggle_max(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()
