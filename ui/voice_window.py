"""
ui/voice_window.py - Modalità voce RAZE
Con waveform ASCII, mic level, trascrizione parziale
"""

import os

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QDialog, QComboBox, QSlider
)
from PyQt6.QtCore  import Qt, QUrl, QTimer, pyqtSignal, QThread
from PyQt6.QtMultimedia        import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtGui   import QFontDatabase

from ui.theme   import get
from ui.widgets import MicLevelBar, WaveformWidget, StatusBar, MicMonitor


# ── Font ─────────────────────────────────────────────────────────────────────

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
_FF = "'Space Mono','Courier New',monospace"


def _ss(C: dict) -> str:
    return f"""
* {{ background-color: {C['bg']}; color: {C['mid']};
     font-family: {_FF}; font-size: 12px; border: none; }}
QLabel {{ color: {C['mid']}; background: transparent; border: none; }}
QPushButton#btn {{
    background: transparent; color: {C['dim']};
    border: 1px solid {C['border']}; padding: 0 10px;
    font-family: {_FF}; font-size: 10px; letter-spacing: 1px;
}}
QPushButton#btn:hover {{ color: {C['hi']}; border: 1px solid {C['hi']}; }}
QPushButton#btn_hi {{
    background: transparent; color: {C['hi']};
    border: 1px solid {C['hi']}; padding: 6px 16px;
    font-family: {_FF}; font-size: 11px; letter-spacing: 2px;
}}
QPushButton#btn_hi:hover {{ background: {C['hi']}; color: {C['bg']}; }}
QComboBox {{
    background: {C['bg1']}; color: {C['hi']};
    border: 1px solid {C['border']}; padding: 4px 8px; min-width: 260px;
    font-family: {_FF};
}}
QComboBox QAbstractItemView {{
    background: {C['bg1']}; color: {C['hi']};
    selection-background-color: {C['hi']}; selection-color: {C['bg']};
    border: 1px solid {C['border']};
}}
QSlider::groove:horizontal {{ background: {C['border']}; height: 2px; }}
QSlider::handle:horizontal {{
    background: {C['hi']}; width: 12px; height: 12px;
    margin: -5px 0; border-radius: 6px;
}}
QSlider::sub-page:horizontal {{ background: {C['hi']}; }}
"""


# ── Model loader thread ───────────────────────────────────────────────────────

class ModelLoaderThread(QThread):
    finished = pyqtSignal()
    error    = pyqtSignal(str)

    def __init__(self, model_name: str = "small"):
        super().__init__()
        self._model_name = model_name

    def run(self):
        try:
            from core.stt import preload_model
            preload_model(self._model_name)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


# ── Settings dialog (senza ElevenLabs) ───────────────────────────────────────

class VoiceSettingsDialog(QDialog):
    def __init__(self, parent=None, cur_in=None, cur_out=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setMinimumWidth(460)
        C = get()
        self.setStyleSheet(_ss(C) + f"QDialog {{ background:{C['bg']}; border:1px solid {C['border']}; }}")
        self.C = C
        self.selected_input  = cur_in
        self.selected_output = cur_out
        self._in_devs = self._out_devs = self._models = []
        self._build()
        self._populate()

    def _build(self):
        C = self.C
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)

        hdr = QLabel("> VOICE_CONFIG")
        hdr.setStyleSheet(
            f"color:{C['hi']}; font-size:13px; letter-spacing:4px;"
            f" padding-bottom:10px; border-bottom:1px solid {C['border']};"
        )
        lay.addWidget(hdr)

        for attr, label in [
            ("in_combo",  "INPUT // MICROPHONE"),
            ("out_combo", "OUTPUT // SPEAKER"),
        ]:
            lay.addWidget(self._lbl(label))
            combo = QComboBox()
            setattr(self, attr, combo)
            lay.addWidget(combo)

        self.in_combo.currentIndexChanged.connect(self._on_in)
        self.out_combo.currentIndexChanged.connect(self._on_out)

        lay.addWidget(self._lbl("TTS // VOICE MODEL"))
        self.voice_combo = QComboBox()
        lay.addWidget(self.voice_combo)

        lay.addWidget(self._lbl("TTS // SPEED"))
        row = QHBoxLayout()
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(50, 200)
        self.speed_slider.setValue(100)
        self.speed_val = QLabel("1.0x")
        self.speed_val.setStyleSheet(f"color:{C['hi']}; min-width:36px; background:transparent;")
        self.speed_slider.valueChanged.connect(
            lambda v: self.speed_val.setText(f"{v/100:.1f}x")
        )
        row.addWidget(self.speed_slider)
        row.addWidget(self.speed_val)
        lay.addLayout(row)

        lay.addStretch()
        row2 = QHBoxLayout()
        row2.addStretch()
        for txt, slot in [("CANCEL", self.reject), ("APPLY", self.accept)]:
            b = QPushButton(txt)
            b.setObjectName("btn_hi")
            b.clicked.connect(slot)
            row2.addWidget(b)
        lay.addLayout(row2)

    def _lbl(self, t: str) -> QLabel:
        l = QLabel(t)
        l.setStyleSheet(
            f"color:{self.C['dim']}; font-size:10px;"
            f" letter-spacing:1px; margin-top:4px; background:transparent;"
        )
        return l

    def _populate(self):
        try:
            import sounddevice as sd
            devs = list(enumerate(sd.query_devices()))
            self._in_devs  = [(i, d["name"]) for i, d in devs if d["max_input_channels"]  > 0]
            self._out_devs = [(i, d["name"]) for i, d in devs if d["max_output_channels"] > 0]
        except Exception:
            pass

        for combo, devs, cur in [
            (self.in_combo,  self._in_devs,  self.selected_input),
            (self.out_combo, self._out_devs, self.selected_output),
        ]:
            combo.blockSignals(True)
            sel = 0
            for i, (idx, name) in enumerate(devs):
                combo.addItem(f"[{idx}] {name}", idx)
                if idx == cur:
                    sel = i
            if devs:
                combo.setCurrentIndex(sel)
                if combo is self.in_combo:
                    self.selected_input  = devs[sel][0]
                else:
                    self.selected_output = devs[sel][0]
            combo.blockSignals(False)

        try:
            from core.tts import TTSEngine
            self._models = TTSEngine.list_models()
        except Exception:
            self._models = []
        for m in self._models:
            self.voice_combo.addItem(m, m)

    def _on_in(self, i):
        if 0 <= i < len(self._in_devs):  self.selected_input  = self._in_devs[i][0]

    def _on_out(self, i):
        if 0 <= i < len(self._out_devs): self.selected_output = self._out_devs[i][0]

    def get_input(self):  return self.selected_input
    def get_output(self): return self.selected_output
    def get_speed(self):  return self.speed_slider.value()
    def get_model(self):
        i = self.voice_combo.currentIndex()
        return self._models[i] if 0 <= i < len(self._models) else None


# ── VoiceWindow ───────────────────────────────────────────────────────────────

class VoiceWindow(QMainWindow):
    back_requested = pyqtSignal()

    def __init__(self, mic_in=None, mic_out=None):
        super().__init__()
        self.C = get()
        self.setWindowTitle("RAZE")
        self.setMinimumSize(480, 580)
        self.resize(520, 620)
        self.setStyleSheet(_ss(self.C))
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self._drag_pos      = None
        self._mic_in        = mic_in
        self._mic_out       = mic_out
        self._busy          = False
        self._listener      = None
        self._worker        = None
        self._old_listeners = []
        self._closing       = False
        self._player        = None
        self._model_ready   = False

        from core.llm import Conversation
        self._conv = Conversation()

        from core.tts import TTSEngine
        self._tts = TTSEngine()
        self._tts.speech_finished.connect(self._on_tts_done)

        self._build()
        self._load_video()

        self._mic_monitor = MicMonitor(device_index=mic_in)
        self._mic_monitor.level_updated.connect(self._on_mic_level)
        self._mic_monitor.start_monitoring()

        # Carica modello Whisper in background
        self._set_status("CARICAMENTO MODELLO...")
        self._loader = ModelLoaderThread("small")
        self._loader.finished.connect(self._on_model_ready)
        self._loader.error.connect(self._on_model_error)
        self._loader.start()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build(self):
        C = self.C
        root = QWidget()
        self.setCentralWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._make_titlebar(C))
        lay.addWidget(self._make_video_area(C), stretch=1)
        lay.addWidget(self._make_waveform_bar(C))
        lay.addWidget(self._make_status_bar(C))
        self._statusbar = StatusBar(C)
        lay.addWidget(self._statusbar)

        self._blink_state = True
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink)
        self._blink_timer.start(800)

    def _make_titlebar(self, C):
        bar = QWidget()
        bar.setFixedHeight(36)
        bar.setStyleSheet(
            f"background:{C['bg1']}; border-bottom:1px solid {C['border']};"
        )
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(14, 0, 8, 0)
        t = QLabel("RAZE // VOICE_MODE")
        t.setStyleSheet(
            f"color:{C['hi']}; font-size:11px; letter-spacing:5px;"
            f" background:transparent; border:none;"
        )
        bl.addWidget(t)
        bl.addStretch()
        for txt, slot in [("CFG", self._settings), ("MENU", self._back), ("×", self.close)]:
            b = QPushButton(txt)
            b.setFixedHeight(24)
            b.setStyleSheet(
                f"QPushButton{{background:transparent;color:{C['dim']};"
                f"border:1px solid {C['border']};padding:0 10px;"
                f"font-family:{_FF};font-size:10px;letter-spacing:1px;}}"
                f"QPushButton:hover{{color:{C['hi']};border:1px solid {C['hi']};}}"
            )
            b.clicked.connect(slot)
            bl.addWidget(b)
            bl.addSpacing(2)
        return bar

    def _make_video_area(self, C):
        vc = QWidget()
        vc.setStyleSheet(f"background:{C['bg']}; border:none;")
        self.vid = QVideoWidget(vc)
        self.vid.setStyleSheet(f"background:{C['bg']};")
        self.vid_ph = QLabel(vc)
        self.vid_ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vid_ph.setStyleSheet(
            f"color:{C['dim']}; background:transparent; border:none; font-family:{_FF};"
        )
        self.vid_ph.hide()
        def _resize(e):
            self.vid.setGeometry(vc.rect())
            self.vid_ph.setGeometry(vc.rect())
        vc.resizeEvent = _resize
        return vc

    def _make_waveform_bar(self, C):
        wf_bar = QWidget()
        wf_bar.setFixedHeight(28)
        wf_bar.setStyleSheet(
            f"background:{C['bg1']}; border-top:1px solid {C['border']};"
        )
        wfl = QHBoxLayout(wf_bar)
        wfl.setContentsMargins(8, 2, 8, 2)
        self._waveform = WaveformWidget(C, cols=40)
        wfl.addWidget(self._waveform)
        return wf_bar

    def _make_status_bar(self, C):
        sb = QWidget()
        sb.setFixedHeight(72)
        sb.setStyleSheet(
            f"background:{C['bg1']}; border-top:1px solid {C['border']};"
        )
        sl = QVBoxLayout(sb)
        sl.setContentsMargins(16, 8, 16, 8)
        sl.setSpacing(4)

        self.status_lbl = QLabel("[ CARICAMENTO MODELLO... ]")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet(
            f"color:{C['hi']}; font-size:11px; letter-spacing:3px;"
            f" background:transparent; border:none;"
        )
        sl.addWidget(self.status_lbl)

        self.transcript_lbl = QLabel("")
        self.transcript_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.transcript_lbl.setStyleSheet(
            f"color:{C['dim']}; font-size:10px; background:transparent; border:none;"
        )
        sl.addWidget(self.transcript_lbl)

        mic_row = QHBoxLayout()
        mic_row.setContentsMargins(0, 0, 0, 0)
        mic_lbl = QLabel("MIC ")
        mic_lbl.setStyleSheet(
            f"color:{C['dim']}; font-size:9px; background:transparent; border:none;"
        )
        mic_row.addWidget(mic_lbl)
        self._mic_bar = MicLevelBar(C, width=24)
        mic_row.addWidget(self._mic_bar)
        mic_row.addStretch()
        sl.addLayout(mic_row)
        return sb

    # ── Video ─────────────────────────────────────────────────────────────────

    def _load_video(self):
        base = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "assets")
        )
        self._vid_idle     = os.path.join(base, "raze_white.mp4")
        self._vid_thinking = os.path.join(base, "loading.mp4")
        if not os.path.exists(self._vid_idle):
            self.vid.hide()
            self.vid_ph.show()
            self.vid_ph.setText("[ NO VIDEO ]")
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
            print(f"[RAZE] Voice video init error: {e}")
            self._player = None
            self.vid.hide()
            self.vid_ph.show()

    def _play_video(self, path: str):
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

    # ── Model loading ─────────────────────────────────────────────────────────

    def _on_model_ready(self):
        if self._closing:
            return
        self._model_ready = True
        self._set_status("LISTENING")
        self.transcript_lbl.setText("")
        QTimer.singleShot(200, self._listen)

    def _on_model_error(self, err: str):
        self._set_status("MODEL_ERROR")
        self.transcript_lbl.setText(err[:80])

    # ── Mic ───────────────────────────────────────────────────────────────────

    def _on_mic_level(self, level: float):
        self._mic_bar.set_level(level)
        self._waveform.push_level(level)

    # ── STT loop ──────────────────────────────────────────────────────────────

    def _listen(self):
        if self._busy or self._closing or not self._model_ready:
            return
        if self._listener and self._listener._running:
            return
        if self._listener:
            try:
                self._listener.phrase_ready.disconnect()
                self._listener.error_occurred.disconnect()
            except Exception:
                pass
            self._old_listeners.append(self._listener)
            self._listener = None
        self._old_listeners = [l for l in self._old_listeners if l._running]

        try:
            from core.stt import PhraseListener
            self._listener = PhraseListener(device_index=self._mic_in)
            self._listener.phrase_ready.connect(self._on_phrase)
            self._listener.error_occurred.connect(self._on_stt_err)
            self._listener.listen_once()
            dev = f" [{self._mic_in}]" if self._mic_in is not None else ""
            self._set_status(f"LISTENING{dev}")
            self.transcript_lbl.setText("")
        except Exception as e:
            self._on_stt_err(str(e))

    def _on_phrase(self, text: str):
        try:
            self._listener.phrase_ready.disconnect(self._on_phrase)
        except Exception:
            pass
        if not text:
            QTimer.singleShot(300, self._listen)
            return
        self._busy = True
        self.transcript_lbl.setText(f'"{text}"')
        self._set_status("THINKING")
        self._set_thinking(True)

        from ui.main_window import WorkerThread
        self._worker = WorkerThread(text, self._conv)
        self._worker.response_ready.connect(self._on_response)
        self._worker.error_occurred.connect(self._on_llm_err)
        self._worker.start()

    def _on_response(self, text: str):
        if self._closing:
            return
        self._set_thinking(False)
        # Non mostrare il testo della risposta durante SPEAKING
        self.transcript_lbl.setText("")
        self._set_status("SPEAKING")
        self._statusbar.inc_messages()
        self._tts.speak(text)

    def _on_tts_done(self):
        self._busy = False
        self.transcript_lbl.setText("")
        self._set_status("LISTENING")
        QTimer.singleShot(500, self._listen)

    def _on_stt_err(self, err: str):
        self._set_status("MIC_ERROR")
        self.transcript_lbl.setText(err[:80])

    def _on_llm_err(self, err: str):
        self._busy = False
        self._set_thinking(False)
        self._set_status("LLM_ERROR")
        self.transcript_lbl.setText(err[:60])
        QTimer.singleShot(3000, self._listen)

    # ── Settings ──────────────────────────────────────────────────────────────

    def _settings(self):
        self._busy = True
        if self._listener:
            self._listener.stop()
        d = VoiceSettingsDialog(self, cur_in=self._mic_in, cur_out=self._mic_out)
        if d.exec() == QDialog.DialogCode.Accepted:
            self._mic_in  = d.get_input()
            self._mic_out = d.get_output()
            speed = d.get_speed()
            model = d.get_model()
            self._tts.set_speed(speed / 100.0)
            if self._mic_out is not None:
                self._tts.set_output_device(self._mic_out)
            if model:
                from core.tts import MODELS_DIR
                self._tts.set_model(os.path.join(MODELS_DIR, model))
            self._mic_monitor.stop_monitoring()
            self._mic_monitor = MicMonitor(device_index=self._mic_in)
            self._mic_monitor.level_updated.connect(self._on_mic_level)
            self._mic_monitor.start_monitoring()
        self._busy = False
        QTimer.singleShot(400, self._listen)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_status(self, text: str):
        self.status_lbl.setText(f"[ {text} ]")
        self._statusbar.set_status(text)

    def _blink(self):
        if self._closing:
            return
        if "LISTENING" in self.status_lbl.text():
            self._blink_state = not self._blink_state
            sym = "LISTENING" if self._blink_state else "_ _ _ _ _ _"
            self.status_lbl.setText(f"[ {sym} ]")

    def _back(self):
        self._closing = True
        self._cleanup()
        if self._player is not None:
            try: self._player.stop()
            except Exception: pass
        self.back_requested.emit()
        self.close()

    def _cleanup(self):
        if hasattr(self, "_blink_timer"):
            self._blink_timer.stop()
        if hasattr(self, "_loader") and self._loader.isRunning():
            self._loader.wait(3000)
        if hasattr(self, "_mic_monitor"):
            self._mic_monitor.stop_monitoring()
        if self._listener:
            self._listener.stop()

    def closeEvent(self, e):
        self._closing = True
        self._cleanup()
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(3000)
        if self._player is not None:
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
