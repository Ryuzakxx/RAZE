"""
ui/main_window.py - RAZE Text Mode
Stile Oxide/Warp: sfondo #0d1117, celle con border, accent arancione sparso
"""

import os
import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QLineEdit, QPushButton, QFrame, QSizePolicy
)
from PyQt6.QtCore  import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt6.QtGui   import QFontDatabase, QTextCursor, QTextCharFormat, QColor, QFont
from PyQt6.QtMultimedia        import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

from ui.theme   import get
from ui.widgets import StatusBar

try:
    import psutil as _psutil
except ImportError:
    _psutil = None

_FF = "'Space Mono','Courier New',monospace"

def _register_fonts():
    base = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets"))
    for f in ("SpaceMono-Regular.ttf","SpaceMono-Bold.ttf","SpaceMono-Italic.ttf","SpaceMono-BoldItalic.ttf"):
        p = os.path.join(base, f)
        if os.path.exists(p):
            QFontDatabase.addApplicationFont(p)

_register_fonts()

def _mono(px=12, bold=False):
    f = QFont("Space Mono")
    if not f.exactMatch(): f = QFont("Courier New")
    f.setPixelSize(px); f.setBold(bold)
    return f

def _ss(C):
    return f"""
QWidget {{ background:{C['bg']}; color:{C['text']}; font-family:{_FF}; font-size:12px; border:none; outline:none; }}
QFrame#cell {{ background:{C['bg1']}; border:1px solid {C['border']}; border-radius:6px; }}
QTextEdit#log {{ background:{C['bg']}; color:{C['text']}; font-family:{_FF}; font-size:12px; padding:16px; border:none; selection-background-color:{C['hi']}; selection-color:{C['bg']}; }}
QLineEdit#inp {{ background:transparent; color:{C['text']}; font-family:{_FF}; font-size:13px; padding:12px 14px; border:none; }}
QLineEdit#inp:focus {{ color:{C['hi2']}; }}
QPushButton#tbtn {{ background:transparent; color:{C['mid']}; font-family:{_FF}; font-size:9px; letter-spacing:1px; padding:2px 8px; border:1px solid {C['border']}; border-radius:4px; }}
QPushButton#tbtn:hover {{ color:{C['text']}; border-color:{C['mid']}; }}
QPushButton#send {{ background:transparent; color:{C['hi']}; font-family:{_FF}; font-size:10px; letter-spacing:3px; padding:12px 24px; border-left:1px solid {C['border']}; border-radius:0; }}
QPushButton#send:hover {{ background:{C['hi']}; color:{C['bg']}; }}
QPushButton#send:pressed {{ background:{C['hi2']}; color:{C['bg']}; }}
QPushButton#back {{ background:transparent; color:{C['dim']}; font-family:{_FF}; font-size:9px; letter-spacing:2px; padding:2px 10px; border:1px solid {C['border']}; border-radius:4px; }}
QPushButton#back:hover {{ color:{C['mid']}; border-color:{C['mid']}; }}
QScrollBar:vertical {{ background:{C['bg']}; width:4px; margin:0; border-radius:2px; }}
QScrollBar::handle:vertical {{ background:{C['dim']}; min-height:20px; border-radius:2px; }}
QScrollBar::handle:vertical:hover {{ background:{C['hi']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
"""


class WorkerThread(QThread):
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    def __init__(self, msg, conv=None):
        super().__init__(); self.msg = msg; self.conv = conv
    def run(self):
        try:
            from core.llm import query_raze
            self.response_ready.emit(query_raze(self.msg, self.conv))
        except Exception as e:
            self.error_occurred.emit(str(e))


class LogWriter:
    def __init__(self, log, C):
        self._log = log; self.C = C

    def _fmt(self, hex_color, bold=False):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(hex_color))
        f = QFont("Space Mono")
        if not f.exactMatch(): f = QFont("Courier New")
        f.setPixelSize(12); f.setBold(bold)
        fmt.setFont(f)
        return fmt

    def append(self, segs):
        doc = self._log.document()
        cur = QTextCursor(doc)
        cur.movePosition(QTextCursor.MoveOperation.End)
        if not doc.isEmpty(): cur.insertBlock()
        for txt, col, bold in segs:
            cur.insertText(txt, self._fmt(col, bold))
        self._scroll()

    def start_tw(self, prefix_segs):
        doc = self._log.document()
        cur = QTextCursor(doc)
        cur.movePosition(QTextCursor.MoveOperation.End)
        if not doc.isEmpty(): cur.insertBlock()
        for txt, col, bold in prefix_segs:
            cur.insertText(txt, self._fmt(col, bold))
        pos = cur.position(); self._scroll(); return pos

    def write_at(self, anchor, text, color):
        doc = self._log.document()
        cur = QTextCursor(doc)
        cur.setPosition(anchor)
        cur.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        cur.insertText(text, self._fmt(color))
        self._scroll()

    def _scroll(self):
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())


class Typewriter:
    def __init__(self, lw, C):
        self._lw = lw; self.C = C
        self._text = ""; self._pos = 0; self._anchor = 0
        self._timer = QTimer(); self._timer.timeout.connect(self._tick)
        self.on_done = None

    def start(self, prefix_segs, text, ms=12):
        self._text = text; self._pos = 0
        self._anchor = self._lw.start_tw(prefix_segs)
        self._timer.start(ms)

    def stop(self): self._timer.stop()

    def _tick(self):
        if self._pos < len(self._text):
            self._pos += 1
            self._lw.write_at(self._anchor, self._text[:self._pos], self.C["text"])
        else:
            self._timer.stop()
            if self.on_done: self.on_done()


class RazeWindow(QMainWindow):
    back_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.C = get()
        self.setWindowTitle("RAZE")
        self.setMinimumSize(960, 660)
        self.resize(1080, 720)
        self.setStyleSheet(_ss(self.C))
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self._drag_pos = None; self._player = None
        self._worker = None; self._closing = False; self._msgs = 0

        from core.llm import Conversation
        self._conv = Conversation()
        self._build()
        self._load_video()
        self._lw = LogWriter(self.log, self.C)
        self._tw = Typewriter(self._lw, self.C)
        self._tw.on_done = self._on_tw_done

        self._blink_t = QTimer(self); self._blink_t.timeout.connect(self._blink); self._blink_t.start(900)
        self._sys_t   = QTimer(self); self._sys_t.timeout.connect(self._upd_sys); self._sys_t.start(2000)
        self._blink_s = True
        self._upd_sys()
        self._lw.append([(f"RAZE // TEXT_MODE  —  ready.", self.C["dim"], False)])

    def _build(self):
        root = QWidget(); self.setCentralWidget(root)
        vl = QVBoxLayout(root); vl.setContentsMargins(0,0,0,0); vl.setSpacing(0)
        vl.addWidget(self._titlebar())
        body = QHBoxLayout(); body.setContentsMargins(12,12,8,8); body.setSpacing(8)
        body.addWidget(self._left_col(), stretch=5)
        body.addWidget(self._right_col(), stretch=7)
        vl.addLayout(body, stretch=1)
        self._sb = StatusBar(self.C); vl.addWidget(self._sb)

    def _titlebar(self):
        bar = QWidget(); bar.setFixedHeight(38)
        bar.setStyleSheet(f"background:{self.C['bg1']}; border-bottom:1px solid {self.C['border']};")
        hl = QHBoxLayout(bar); hl.setContentsMargins(16,0,8,0); hl.setSpacing(0)

        # Traffic light dots (decorativi)
        for c in ["#ff5f57","#febc2e","#28c840"]:
            d = QLabel("●"); d.setFixedSize(14,14)
            d.setStyleSheet(f"color:{c}; font-size:9px; background:transparent; border:none;")
            hl.addWidget(d)
        hl.addSpacing(14)

        title = QLabel("RAZE")
        title.setStyleSheet(f"color:{self.C['text']}; font-size:11px; letter-spacing:4px; background:transparent; border:none;")
        hl.addWidget(title)
        hl.addSpacing(8)

        # Tab attivo stile Oxide
        tab = QWidget(); tab.setFixedHeight(38)
        tab.setStyleSheet(f"background:{self.C['bg']}; border-left:1px solid {self.C['border']}; border-right:1px solid {self.C['border']}; border-bottom:2px solid {self.C['hi']};")
        tl = QHBoxLayout(tab); tl.setContentsMargins(16,0,16,0)
        tl.addWidget(QLabel("TEXT_MODE") if False else self._tab_lbl("TEXT_MODE"))
        hl.addWidget(tab)
        hl.addStretch()

        self._status_lbl = QLabel("● STANDBY")
        self._status_lbl.setStyleSheet(f"color:{self.C['dim']}; font-size:9px; letter-spacing:2px; background:transparent; border:none;")
        hl.addWidget(self._status_lbl)
        hl.addSpacing(20)

        back = QPushButton("◀ MODE"); back.setObjectName("back"); back.setFixedHeight(24)
        back.clicked.connect(self._go_back); hl.addWidget(back); hl.addSpacing(8)

        for sym, slot in [("—", self.showMinimized),("□",self._toggle_max),("×",self.close)]:
            b = QPushButton(sym); b.setFixedSize(28,28)
            b.setStyleSheet(f"QPushButton{{background:transparent;color:{self.C['dim']};border:none;font-size:14px;font-family:{_FF};}} QPushButton:hover{{color:{self.C['text']};background:{self.C['border']};border-radius:4px;}}")
            b.clicked.connect(slot); hl.addWidget(b)
        return bar

    def _tab_lbl(self, text):
        l = QLabel(text)
        l.setStyleSheet(f"color:{self.C['hi']}; font-size:10px; letter-spacing:2px; background:transparent; border:none;")
        return l

    def _left_col(self):
        w = QWidget(); w.setStyleSheet("background:transparent; border:none;")
        vl = QVBoxLayout(w); vl.setContentsMargins(0,0,0,0); vl.setSpacing(8)

        # Video cell
        vid_cell = QFrame(); vid_cell.setObjectName("cell")
        vcl = QVBoxLayout(vid_cell); vcl.setContentsMargins(0,0,0,0); vcl.setSpacing(0)
        vcl.addWidget(self._cell_hdr("VISUAL_OUTPUT"))
        vc = QWidget(); vc.setStyleSheet(f"background:{self.C['bg']}; border:none; border-radius:0;")
        self.vid = QVideoWidget(vc); self.vid.setStyleSheet(f"background:{self.C['bg']};")
        self.vid_ph = QLabel(vc)
        self.vid_ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vid_ph.setStyleSheet(f"color:{self.C['dim']}; font-size:11px; background:transparent; border:none; font-family:{_FF};")
        self.vid_ph.hide()
        def _r(e): self.vid.setGeometry(vc.rect()); self.vid_ph.setGeometry(vc.rect())
        vc.resizeEvent = _r
        vcl.addWidget(vc, stretch=1)
        vl.addWidget(vid_cell, stretch=3)

        # Stats cell
        stats_cell = QFrame(); stats_cell.setObjectName("cell")
        scl = QVBoxLayout(stats_cell); scl.setContentsMargins(0,0,0,0); scl.setSpacing(0)
        scl.addWidget(self._cell_hdr("SYSTEM_STATS"))
        sc = QWidget(); sc.setStyleSheet(f"background:transparent; border:none;")
        sl = QVBoxLayout(sc); sl.setContentsMargins(16,12,16,12); sl.setSpacing(8)
        self._sys_vals = {}
        rows = [("STATUS","STANDBY"),("THEME",self.C["name"].upper()),("MSGS","0"),("CPU","—"),("RAM","—"),("TIME","—")]
        for k,v in rows:
            row = QHBoxLayout(); row.setSpacing(0)
            kl = QLabel(k)
            kl.setStyleSheet(f"color:{self.C['dim']}; font-size:9px; letter-spacing:2px; background:transparent; border:none;")
            vl2 = QLabel(v); vl2.setAlignment(Qt.AlignmentFlag.AlignRight)
            vl2.setStyleSheet(f"color:{self.C['hi']}; font-size:9px; letter-spacing:1px; background:transparent; border:none;")
            row.addWidget(kl); row.addStretch(); row.addWidget(vl2)
            sl.addLayout(row); self._sys_vals[k] = vl2
        sl.addStretch()
        scl.addWidget(sc, stretch=1)
        vl.addWidget(stats_cell, stretch=2)
        return w

    def _right_col(self):
        cell = QFrame(); cell.setObjectName("cell")
        vl = QVBoxLayout(cell); vl.setContentsMargins(0,0,0,0); vl.setSpacing(0)

        clr = QPushButton("CLR"); clr.setObjectName("tbtn"); clr.setFixedSize(34,18)
        clr.clicked.connect(self._clear)
        vl.addWidget(self._cell_hdr("OUTPUT_LOG", clr))

        self.log = QTextEdit(); self.log.setObjectName("log")
        self.log.setReadOnly(True); self.log.setFont(_mono(12))
        vl.addWidget(self.log, stretch=1)

        # Divider
        div = QWidget(); div.setFixedHeight(1)
        div.setStyleSheet(f"background:{self.C['border']};")
        vl.addWidget(div)

        # Input row — stile Oxide con → prefix
        inp_row = QWidget(); inp_row.setFixedHeight(48)
        inp_row.setStyleSheet(f"background:{self.C['bg1']}; border:none;")
        ir = QHBoxLayout(inp_row); ir.setContentsMargins(0,0,0,0); ir.setSpacing(0)

        arrow = QLabel("  →  ")
        arrow.setStyleSheet(f"color:{self.C['hi']}; font-size:14px; font-family:{_FF}; background:transparent; border:none; border-right:1px solid {self.C['border']}; padding:0 4px;")
        ir.addWidget(arrow)

        self.inp = QLineEdit(); self.inp.setObjectName("inp"); self.inp.setFont(_mono(13))
        self.inp.setPlaceholderText("type a message...")
        self.inp.returnPressed.connect(self._send)
        ir.addWidget(self.inp, stretch=1)

        send = QPushButton("SEND ↵"); send.setObjectName("send")
        send.clicked.connect(self._send); ir.addWidget(send)
        vl.addWidget(inp_row)
        return cell

    def _cell_hdr(self, label, right_w=None):
        hdr = QWidget(); hdr.setFixedHeight(28)
        hdr.setStyleSheet(f"background:{self.C['bg2']}; border-bottom:1px solid {self.C['border']}; border-radius:0;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(12,0,8,0); hl.setSpacing(6)
        l = QLabel(label)
        l.setStyleSheet(f"color:{self.C['dim']}; font-size:9px; letter-spacing:2px; background:transparent; border:none;")
        hl.addWidget(l); hl.addStretch()
        if right_w: hl.addWidget(right_w)
        return hdr

    def _load_video(self):
        base = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets"))
        self._vid_idle     = os.path.join(base, "raze_white.mp4")
        self._vid_thinking = os.path.join(base, "loading.mp4")
        if not os.path.exists(self._vid_idle):
            self.vid.hide(); self.vid_ph.show(); self.vid_ph.setText("[ NO VIDEO ]"); return
        try:
            self._player = QMediaPlayer(self); self._ao = QAudioOutput(self)
            self._ao.setVolume(0); self._player.setAudioOutput(self._ao)
            self._player.setVideoOutput(self.vid)
            self._player.mediaStatusChanged.connect(self._on_media)
            self._play(self._vid_idle)
        except Exception as e:
            print(f"[RAZE] video err: {e}"); self._player = None
            self.vid.hide(); self.vid_ph.show()

    def _play(self, path):
        if not self._player: return
        if not os.path.exists(path): path = self._vid_idle
        try: self._player.setSource(QUrl.fromLocalFile(path)); self._player.play()
        except Exception as e: print(f"[RAZE] play err: {e}")

    def _on_media(self, s):
        if not self._player or self._closing: return
        if s == QMediaPlayer.MediaStatus.EndOfMedia:
            try: self._player.setPosition(0); self._player.play()
            except Exception: pass

    def _set_thinking(self, on):
        self._play(self._vid_thinking if on else self._vid_idle)

    def _send(self):
        text = self.inp.text().strip()
        if not text or self._closing: return
        self.inp.clear(); self.inp.setEnabled(False)
        ts = datetime.datetime.now().strftime("%H:%M")
        self._lw.append([(f"{ts}  ", self.C["dim"], False), (f"{text}", self.C["mid"], False)])
        self._set_status("PROCESSING"); self._set_val("STATUS", "PROCESSING")
        self._set_thinking(True)
        self._worker = WorkerThread(text, self._conv)
        self._worker.response_ready.connect(self._on_resp)
        self._worker.error_occurred.connect(self._on_err)
        self._worker.finished.connect(lambda: self.inp.setEnabled(True) if not self._closing else None)
        self._worker.start()

    def _on_resp(self, text):
        if self._closing: return
        self._set_thinking(False); self._set_status("RESPONDING")
        self._msgs += 1; self._set_val("MSGS", str(self._msgs)); self._sb.inc_messages()
        ts = datetime.datetime.now().strftime("%H:%M")
        self._tw.start([(f"{ts}  ", self.C["dim"], False), ("RAZE  ", self.C["hi"], True)], text)

    def _on_tw_done(self):
        if self._closing: return
        self._set_status("STANDBY"); self._set_val("STATUS", "STANDBY")

    def _on_err(self, err):
        if self._closing: return
        self._set_thinking(False)
        ts = datetime.datetime.now().strftime("%H:%M")
        self._lw.append([(f"{ts}  ERR  {err}", self.C["dim"], False)])
        self._set_status("ERROR"); self._set_val("STATUS", "ERROR")

    def _clear(self):
        self.log.clear(); self._conv.clear(); self._msgs = 0
        self._set_val("MSGS", "0")
        self._lw.append([("memory cleared  —  ready", self.C["dim"], False)])

    def _set_status(self, t):
        self._status_lbl.setText(f"● {t}"); self._sb.set_status(t)

    def _set_val(self, k, v):
        if k in self._sys_vals: self._sys_vals[k].setText(v)

    def _upd_sys(self):
        if self._closing: return
        self._set_val("TIME", datetime.datetime.now().strftime("%H:%M:%S"))
        self._set_val("THEME", self.C["name"].upper())
        if _psutil:
            try:
                self._set_val("CPU", f"{_psutil.cpu_percent(interval=None):.0f}%")
                self._set_val("RAM", f"{_psutil.virtual_memory().used/(1024**3):.1f}GB")
            except Exception: pass

    def _blink(self):
        if self._closing: return
        if "STANDBY" in self._status_lbl.text():
            self._blink_s = not self._blink_s
            self._status_lbl.setText("● STANDBY" if self._blink_s else "○ STANDBY")

    def _go_back(self):
        self._closing = True; self._blink_t.stop(); self._sys_t.stop(); self._tw.stop()
        if self._worker and self._worker.isRunning(): self._worker.wait(2000)
        if self._player:
            try: self._player.stop()
            except Exception: pass
        self.back_requested.emit(); self.close()

    def closeEvent(self, e):
        self._closing = True; self._blink_t.stop(); self._sys_t.stop(); self._tw.stop()
        if self._worker and self._worker.isRunning(): self._worker.wait(3000)
        if self._player:
            try: self._player.stop()
            except Exception: pass
        super().closeEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self._drag_pos = e.globalPosition().toPoint()
    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            self.move(self.pos() + e.globalPosition().toPoint() - self._drag_pos)
            self._drag_pos = e.globalPosition().toPoint()
    def mouseReleaseEvent(self, e): self._drag_pos = None
    def _toggle_max(self): self.showNormal() if self.isMaximized() else self.showMaximized()