"""
ui/voice_window.py - RAZE Voice Mode
Stile Oxide/Warp con arancione accent
"""

import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QDialog, QComboBox, QSlider, QFrame
)
from PyQt6.QtCore  import Qt, QUrl, QTimer, pyqtSignal, QThread
from PyQt6.QtMultimedia        import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtGui   import QFontDatabase

from ui.theme   import get
from ui.widgets import MicLevelBar, WaveformWidget, StatusBar, MicMonitor

_FF = "'Space Mono','Courier New',monospace"

def _register_fonts():
    base = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets"))
    for f in ("SpaceMono-Regular.ttf","SpaceMono-Bold.ttf"):
        p = os.path.join(base, f)
        if os.path.exists(p): QFontDatabase.addApplicationFont(p)

_register_fonts()

def _ss(C):
    return f"""
QWidget {{ background:{C['bg']}; color:{C['text']}; font-family:{_FF}; font-size:12px; border:none; }}
QLabel {{ color:{C['mid']}; background:transparent; border:none; }}
QFrame#cell {{ background:{C['bg1']}; border:1px solid {C['border']}; border-radius:6px; }}
QPushButton#tbtn {{ background:transparent; color:{C['dim']}; border:1px solid {C['border']}; padding:0 10px; font-family:{_FF}; font-size:9px; letter-spacing:1px; border-radius:4px; }}
QPushButton#tbtn:hover {{ color:{C['text']}; border-color:{C['mid']}; }}
QPushButton#btn_hi {{ background:transparent; color:{C['hi']}; border:1px solid {C['hi']}; padding:8px 20px; font-family:{_FF}; font-size:10px; letter-spacing:2px; border-radius:4px; }}
QPushButton#btn_hi:hover {{ background:{C['hi']}; color:{C['bg']}; }}
QComboBox {{ background:{C['bg2']}; color:{C['text']}; border:1px solid {C['border']}; padding:6px 10px; min-width:260px; border-radius:4px; font-family:{_FF}; }}
QComboBox:hover {{ border-color:{C['mid']}; }}
QComboBox QAbstractItemView {{ background:{C['bg2']}; color:{C['text']}; selection-background-color:{C['hi']}; selection-color:{C['bg']}; border:1px solid {C['border']}; }}
QSlider::groove:horizontal {{ background:{C['border']}; height:3px; border-radius:1px; }}
QSlider::handle:horizontal {{ background:{C['hi']}; width:13px; height:13px; margin:-5px 0; border-radius:6px; }}
QSlider::sub-page:horizontal {{ background:{C['hi']}; border-radius:1px; }}
"""

DIALOG_EXTRA = lambda C: f"QDialog {{ background:{C['bg']}; border:1px solid {C['border']}; border-radius:8px; }}"


class ModelLoaderThread(QThread):
    finished = pyqtSignal()
    error    = pyqtSignal(str)
    def __init__(self, model="small"):
        super().__init__(); self._m = model
    def run(self):
        try:
            from core.stt import preload_model
            preload_model(self._m); self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class VoiceSettingsDialog(QDialog):
    def __init__(self, parent=None, cur_in=None, cur_out=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setMinimumWidth(480)
        C = get()
        self.setStyleSheet(_ss(C) + DIALOG_EXTRA(C))
        self.C = C
        self.selected_input  = cur_in
        self.selected_output = cur_out
        self._in_devs = self._out_devs = self._models = []
        self._build(); self._populate()

    def _build(self):
        C = self.C
        lay = QVBoxLayout(self); lay.setContentsMargins(24,24,24,24); lay.setSpacing(14)

        hdr = QLabel("VOICE_CONFIG")
        hdr.setStyleSheet(f"color:{C['hi']}; font-size:12px; letter-spacing:4px; padding-bottom:12px; border-bottom:1px solid {C['border']}; background:transparent;")
        lay.addWidget(hdr)

        for attr, lbl in [("in_combo","INPUT // MICROPHONE"),("out_combo","OUTPUT // SPEAKER")]:
            l = QLabel(lbl); l.setStyleSheet(f"color:{C['dim']}; font-size:9px; letter-spacing:2px; background:transparent;")
            lay.addWidget(l)
            combo = QComboBox(); setattr(self, attr, combo); lay.addWidget(combo)

        self.in_combo.currentIndexChanged.connect(self._on_in)
        self.out_combo.currentIndexChanged.connect(self._on_out)

        tts_l = QLabel("TTS // VOICE MODEL"); tts_l.setStyleSheet(f"color:{C['dim']}; font-size:9px; letter-spacing:2px; background:transparent;")
        lay.addWidget(tts_l)
        self.voice_combo = QComboBox(); lay.addWidget(self.voice_combo)

        spd_l = QLabel("TTS // SPEED"); spd_l.setStyleSheet(f"color:{C['dim']}; font-size:9px; letter-spacing:2px; background:transparent;")
        lay.addWidget(spd_l)
        row = QHBoxLayout()
        self.speed_s = QSlider(Qt.Orientation.Horizontal); self.speed_s.setRange(50,200); self.speed_s.setValue(100)
        self.speed_v = QLabel("1.0×"); self.speed_v.setStyleSheet(f"color:{C['hi']}; min-width:40px; background:transparent;")
        self.speed_s.valueChanged.connect(lambda v: self.speed_v.setText(f"{v/100:.1f}×"))
        row.addWidget(self.speed_s); row.addWidget(self.speed_v); lay.addLayout(row)

        lay.addStretch()
        br = QHBoxLayout(); br.addStretch()
        for t, s in [("CANCEL",self.reject),("APPLY",self.accept)]:
            b = QPushButton(t); b.setObjectName("btn_hi"); b.clicked.connect(s); br.addWidget(b)
        lay.addLayout(br)

    def _populate(self):
        try:
            import sounddevice as sd
            devs = list(enumerate(sd.query_devices()))
            self._in_devs  = [(i,d["name"]) for i,d in devs if d["max_input_channels"]>0]
            self._out_devs = [(i,d["name"]) for i,d in devs if d["max_output_channels"]>0]
        except Exception: pass

        for combo, devs, cur, attr in [
            (self.in_combo, self._in_devs, self.selected_input, "selected_input"),
            (self.out_combo, self._out_devs, self.selected_output, "selected_output"),
        ]:
            combo.blockSignals(True)
            sel = 0
            for i,(idx,name) in enumerate(devs):
                combo.addItem(f"[{idx}]  {name}", idx)
                if idx == cur: sel = i
            if devs:
                combo.setCurrentIndex(sel)
                setattr(self, attr, devs[sel][0])
            combo.blockSignals(False)

        try:
            from core.tts import TTSEngine
            self._models = TTSEngine.list_models()
        except Exception: self._models = []
        for m in self._models: self.voice_combo.addItem(m, m)

    def _on_in(self, i):
        if 0 <= i < len(self._in_devs): self.selected_input = self._in_devs[i][0]
    def _on_out(self, i):
        if 0 <= i < len(self._out_devs): self.selected_output = self._out_devs[i][0]
    def get_input(self):  return self.selected_input
    def get_output(self): return self.selected_output
    def get_speed(self):  return self.speed_s.value()
    def get_model(self):
        i = self.voice_combo.currentIndex()
        return self._models[i] if 0<=i<len(self._models) else None


class VoiceWindow(QMainWindow):
    back_requested = pyqtSignal()

    def __init__(self, mic_in=None, mic_out=None):
        super().__init__()
        self.C = get()
        self.setWindowTitle("RAZE")
        self.setMinimumSize(500,600); self.resize(540,660)
        self.setStyleSheet(_ss(self.C))
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self._drag_pos = None; self._mic_in = mic_in; self._mic_out = mic_out
        self._busy = False; self._listener = None; self._worker = None
        self._old_listeners = []; self._closing = False; self._player = None
        self._model_ready = False

        from core.llm import Conversation
        self._conv = Conversation()
        from core.tts import TTSEngine
        self._tts = TTSEngine()
        self._tts.speech_finished.connect(self._on_tts_done)

        self._build(); self._load_video()

        self._mic_mon = MicMonitor(device_index=mic_in)
        self._mic_mon.level_updated.connect(self._on_mic_level)
        self._mic_mon.start_monitoring()

        self._set_status("LOADING MODEL")
        self._loader = ModelLoaderThread("small")
        self._loader.finished.connect(self._on_model_ready)
        self._loader.error.connect(lambda e: self._set_status(f"MODEL ERR"))
        self._loader.start()

    def _build(self):
        C = self.C
        root = QWidget(); self.setCentralWidget(root)
        vl = QVBoxLayout(root); vl.setContentsMargins(0,0,0,0); vl.setSpacing(0)
        vl.addWidget(self._titlebar(C))

        # Video area — senza celle, diretto
        vc = QWidget(); vc.setStyleSheet(f"background:{C['bg']}; border:none;")
        self.vid = QVideoWidget(vc); self.vid.setStyleSheet(f"background:{C['bg']};")
        self.vid_ph = QLabel(vc); self.vid_ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vid_ph.setStyleSheet(f"color:{C['dim']}; background:transparent; border:none; font-family:{_FF}; font-size:10px;")
        self.vid_ph.hide()
        def _r(e): self.vid.setGeometry(vc.rect()); self.vid_ph.setGeometry(vc.rect())
        vc.resizeEvent = _r
        vl.addWidget(vc, stretch=1)

        # Status panel
        sp = QWidget(); sp.setFixedHeight(80)
        sp.setStyleSheet(f"background:{C['bg']}; border-top:none;")
        spl = QVBoxLayout(sp); spl.setContentsMargins(20,12,20,12); spl.setSpacing(6)

        self.status_lbl = QLabel("[ LOADING ]")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet(f"color:{C['hi']}; font-size:11px; letter-spacing:3px; background:transparent; border:none;")
        spl.addWidget(self.status_lbl)

        self.transcript_lbl = QLabel("")
        self.transcript_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.transcript_lbl.setStyleSheet(f"color:{C['mid']}; font-size:10px; background:transparent; border:none;")
        spl.addWidget(self.transcript_lbl)

        vl.addWidget(sp)

        self._sb = StatusBar(C); vl.addWidget(self._sb)

        self._blink_s = True
        self._blink_t = QTimer(self); self._blink_t.timeout.connect(self._blink); self._blink_t.start(800)

    def _titlebar(self, C):
        bar = QWidget(); bar.setFixedHeight(38)
        bar.setStyleSheet(f"background:{C['bg1']}; border-bottom:1px solid {C['border']};")
        hl = QHBoxLayout(bar); hl.setContentsMargins(16,0,8,0); hl.setSpacing(0)

        for c in ["#ff5f57","#febc2e","#28c840"]:
            d = QLabel("●"); d.setFixedSize(14,14)
            d.setStyleSheet(f"color:{c}; font-size:9px; background:transparent; border:none;")
            hl.addWidget(d)
        hl.addSpacing(14)

        # Tab attivo
        tab = QWidget(); tab.setFixedHeight(38)
        tab.setStyleSheet(f"background:{C['bg']}; border-left:1px solid {C['border']}; border-right:1px solid {C['border']}; border-bottom:2px solid {C['hi']};")
        tl = QHBoxLayout(tab); tl.setContentsMargins(16,0,16,0)
        lbl = QLabel("VOICE_MODE"); lbl.setStyleSheet(f"color:{C['hi']}; font-size:10px; letter-spacing:2px; background:transparent; border:none;")
        tl.addWidget(lbl); hl.addWidget(tab)
        hl.addStretch()

        for txt, slot in [("CFG",self._settings),("MENU",self._back),("×",self.close)]:
            b = QPushButton(txt); b.setFixedHeight(26)
            b.setStyleSheet(
                f"QPushButton{{background:transparent;color:{C['dim']};border:1px solid {C['border']};padding:0 10px;font-family:{_FF};font-size:9px;letter-spacing:1px;border-radius:4px;}}"
                f"QPushButton:hover{{color:{C['text']};border-color:{C['mid']};}}"
            )
            b.clicked.connect(slot); hl.addWidget(b); hl.addSpacing(4)
        return bar

    def _load_video(self):
        base = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets"))
        self._vid_idle     = os.path.join(base, "raze_purple.mp4")
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

    def _on_mic_level(self, lv):
        if hasattr(self, '_wf'): self._wf.push_level(lv)

    def _on_model_ready(self):
        if self._closing: return
        self._model_ready = True; self._set_status("LISTENING")
        self.transcript_lbl.setText(""); QTimer.singleShot(200, self._listen)

    def _listen(self):
        if self._busy or self._closing or not self._model_ready: return
        if self._listener and self._listener._running: return
        if self._listener:
            try: self._listener.phrase_ready.disconnect(); self._listener.error_occurred.disconnect()
            except Exception: pass
            self._old_listeners.append(self._listener); self._listener = None
        self._old_listeners = [l for l in self._old_listeners if l._running]
        try:
            from core.stt import PhraseListener
            self._listener = PhraseListener(device_index=self._mic_in)
            self._listener.phrase_ready.connect(self._on_phrase)
            self._listener.error_occurred.connect(self._on_stt_err)
            self._listener.listen_once()
            dev = f"  [{self._mic_in}]" if self._mic_in is not None else ""
            self._set_status(f"LISTENING{dev}"); self.transcript_lbl.setText("")
        except Exception as e: self._on_stt_err(str(e))

    def _on_phrase(self, text):
        try: self._listener.phrase_ready.disconnect(self._on_phrase)
        except Exception: pass
        if not text: QTimer.singleShot(300, self._listen); return
        self._busy = True
        self.transcript_lbl.setText(f'"{text}"')
        self._set_status("THINKING"); self._set_thinking(True)
        from ui.main_window import WorkerThread
        self._worker = WorkerThread(text, self._conv)
        self._worker.response_ready.connect(self._on_resp)
        self._worker.error_occurred.connect(self._on_llm_err)
        self._worker.start()

    def _on_resp(self, text):
        if self._closing: return
        self._set_thinking(False); self.transcript_lbl.setText("")
        self._set_status("SPEAKING"); self._sb.inc_messages(); self._tts.speak(text)

    def _on_tts_done(self):
        self._busy = False; self._set_status("LISTENING"); QTimer.singleShot(500, self._listen)

    def _on_stt_err(self, err):
        self._set_status("MIC_ERROR"); self.transcript_lbl.setText(err[:80])

    def _on_llm_err(self, err):
        self._busy = False; self._set_thinking(False)
        self._set_status("LLM_ERROR"); self.transcript_lbl.setText(err[:60])
        QTimer.singleShot(3000, self._listen)

    def _settings(self):
        self._busy = True
        if self._listener: self._listener.stop()
        d = VoiceSettingsDialog(self, cur_in=self._mic_in, cur_out=self._mic_out)
        if d.exec() == QDialog.DialogCode.Accepted:
            self._mic_in = d.get_input(); self._mic_out = d.get_output()
            spd = d.get_speed(); mdl = d.get_model()
            self._tts.set_speed(spd/100.0)
            if self._mic_out is not None: self._tts.set_output_device(self._mic_out)
            if mdl:
                from core.tts import MODELS_DIR
                self._tts.set_model(os.path.join(MODELS_DIR, mdl))
            self._mic_mon.stop_monitoring()
            self._mic_mon = MicMonitor(device_index=self._mic_in)
            self._mic_mon.level_updated.connect(self._on_mic_level)
            self._mic_mon.start_monitoring()
        self._busy = False; QTimer.singleShot(400, self._listen)

    def _set_status(self, t):
        self.status_lbl.setText(f"[ {t} ]"); self._sb.set_status(t)

    def _blink(self):
        if self._closing: return
        if "LISTENING" in self.status_lbl.text():
            self._blink_s = not self._blink_s
            self.status_lbl.setText("[ LISTENING ]" if self._blink_s else "[  ·  ·  ·  ]")

    def _back(self):
        self._closing = True; self._blink_t.stop(); self._cleanup()
        if self._player:
            try: self._player.stop()
            except Exception: pass
        self.back_requested.emit(); self.close()

    def _cleanup(self):
        if hasattr(self,"_loader") and self._loader.isRunning(): self._loader.wait(3000)
        if hasattr(self,"_mic_mon"): self._mic_mon.stop_monitoring()
        if self._listener: self._listener.stop()

    def closeEvent(self, e):
        self._closing = True; self._blink_t.stop(); self._cleanup()
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