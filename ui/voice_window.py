"""
ui/voice_window.py - Modalità voce RAZE
Con waveform ASCII, mic level, trascrizione parziale, scanlines
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QDialog, QComboBox, QSlider, QLineEdit
)
from PyQt6.QtCore import Qt, QUrl, QTimer, pyqtSignal
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
import os
from ui.theme import get
from ui.widgets import MicLevelBar, WaveformWidget, StatusBar, MicMonitor
from ui.main_window import ScanlineOverlay


def _ss(C):
    return f"""
* {{ background-color: {C['bg']}; color: {C['mid']}; font-family: 'Courier New', monospace; font-size: 12px; border: none; }}
QPushButton#btn {{
    background: transparent; color: {C['dim']};
    border: 1px solid {C['border']}; padding: 0 10px;
    font-family: 'Courier New', monospace; font-size: 10px; letter-spacing: 1px;
}}
QPushButton#btn:hover {{ color: {C['hi']}; border: 1px solid {C['hi']}; background: transparent; }}
QPushButton#btn_hi {{
    background: transparent; color: {C['hi']};
    border: 1px solid {C['hi']}; padding: 6px 16px;
    font-family: 'Courier New', monospace; font-size: 11px; letter-spacing: 2px;
}}
QPushButton#btn_hi:hover {{ background: {C['hi']}; color: {C['bg']}; border: 1px solid {C['hi']}; }}
QComboBox {{
    background: {C['bg1']}; color: {C['hi']};
    border: 1px solid {C['border']}; padding: 4px 8px; min-width: 260px;
}}
QComboBox QAbstractItemView {{
    background: {C['bg1']}; color: {C['hi']};
    selection-background-color: {C['hi']}; selection-color: {C['bg']};
    border: 1px solid {C['border']};
}}
QSlider::groove:horizontal {{ background: {C['border']}; height: 2px; }}
QSlider::handle:horizontal {{ background: {C['hi']}; width: 12px; height: 12px; margin: -5px 0; border-radius: 6px; }}
QSlider::sub-page:horizontal {{ background: {C['hi']}; }}
QLineEdit {{
    background: {C['bg1']}; color: {C['hi']};
    border: 1px solid {C['border']}; padding: 4px 8px;
    font-family: 'Courier New', monospace; font-size: 11px;
}}
"""


class VoiceSettingsDialog(QDialog):
    def __init__(self, parent=None, cur_in=None, cur_out=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setMinimumWidth(500)
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
        hdr.setStyleSheet(f"color:{C['hi']}; font-size:13px; letter-spacing:4px; padding-bottom:10px; border-bottom:1px solid {C['border']};")
        lay.addWidget(hdr)

        for attr, label in [("in_combo", "INPUT // MICROPHONE"), ("out_combo", "OUTPUT // SPEAKER")]:
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
        self.speed_val.setStyleSheet(f"color:{C['hi']}; min-width:36px;")
        self.speed_slider.valueChanged.connect(lambda v: self.speed_val.setText(f"{v/100:.1f}x"))
        row.addWidget(self.speed_slider)
        row.addWidget(self.speed_val)
        lay.addLayout(row)

        lay.addWidget(self._lbl("ELEVENLABS // API KEY (vuoto = Piper offline)"))
        self.api_inp = QLineEdit()
        self.api_inp.setPlaceholderText("sk-...")
        self.api_inp.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_inp.setText(os.environ.get("ELEVENLABS_API_KEY", ""))
        lay.addWidget(self.api_inp)

        lay.addStretch()
        row2 = QHBoxLayout()
        row2.addStretch()
        for txt, slot in [("CANCEL", self.reject), ("APPLY", self.accept)]:
            b = QPushButton(txt)
            b.setObjectName("btn_hi")
            b.clicked.connect(slot)
            row2.addWidget(b)
        lay.addLayout(row2)

    def _lbl(self, t):
        l = QLabel(t)
        l.setStyleSheet(f"color:{self.C['dim']}; font-size:10px; letter-spacing:1px; margin-top:4px;")
        return l

    def _populate(self):
        try:
            import sounddevice as sd
            devs = list(enumerate(sd.query_devices()))
            self._in_devs  = [(i, d["name"]) for i, d in devs if d["max_input_channels"] > 0]
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
                    self.selected_input = devs[sel][0]
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
        if 0 <= i < len(self._in_devs):
            self.selected_input = self._in_devs[i][0]

    def _on_out(self, i):
        if 0 <= i < len(self._out_devs):
            self.selected_output = self._out_devs[i][0]

    def get_input(self):  return self.selected_input
    def get_output(self): return self.selected_output
    def get_speed(self):  return self.speed_slider.value()
    def get_api_key(self): return self.api_inp.text().strip()
    def get_model(self):
        i = self.voice_combo.currentIndex()
        return self._models[i] if 0 <= i < len(self._models) else None


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
        self._drag_pos       = None
        self._mic_in         = mic_in
        self._mic_out        = mic_out
        self._busy           = False
        self._listener       = None
        self._worker         = None
        self._old_listeners  = []

        from core.llm import Conversation
        self._conv = Conversation()

        from core.tts import TTSEngine
        self._tts = TTSEngine()
        self._tts.speech_finished.connect(self._on_tts_done)

        self._build()
        self._load_video()

        # Mic monitor per waveform e level bar
        self._mic_monitor = MicMonitor(device_index=mic_in)
        self._mic_monitor.level_updated.connect(self._on_mic_level)
        self._mic_monitor.start_monitoring()

        from core.stt import preload_model
        preload_model("small")
        QTimer.singleShot(700, self._listen)

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Titlebar
        bar = QWidget()
        bar.setFixedHeight(36)
        bar.setStyleSheet(f"background:{self.C['bg1']}; border-bottom:1px solid {self.C['border']};")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(14, 0, 8, 0)
        t = QLabel("RAZE // VOICE MODE")
        t.setStyleSheet(f"color:{self.C['hi']}; font-size:11px; letter-spacing:5px;")
        bl.addWidget(t)
        bl.addStretch()
        for txt, slot in [("CFG", self._settings), ("MENU", self._back), ("×", self.close)]:
            b = QPushButton(txt)
            b.setFixedHeight(24)
            b.setStyleSheet(f"""
                QPushButton {{ background:transparent; color:{self.C['dim']}; border:1px solid {self.C['border']}; padding:0 10px; font-family:'Courier New'; font-size:10px; letter-spacing:1px; }}
                QPushButton:hover {{ color:{self.C['hi']}; border:1px solid {self.C['hi']}; background:transparent; }}
            """)
            b.clicked.connect(slot)
            bl.addWidget(b)
            bl.addSpacing(2)
        lay.addWidget(bar)

        # Video container con scanlines
        vid_container = QWidget()
        self.vid = QVideoWidget(vid_container)
        self.vid.setStyleSheet(f"background:{self.C['bg']};")
        self.vid_ph = QLabel(vid_container)
        self.vid_ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vid_ph.setTextFormat(Qt.TextFormat.RichText)
        self.vid_ph.hide()
        self._scanline = ScanlineOverlay(vid_container, self.C)

        def resize_vid(e):
            self.vid.setGeometry(vid_container.rect())
            self.vid_ph.setGeometry(vid_container.rect())
            self._scanline.setGeometry(vid_container.rect())
        vid_container.resizeEvent = resize_vid
        lay.addWidget(vid_container, stretch=1)

        # Waveform
        wf_bar = QWidget()
        wf_bar.setFixedHeight(28)
        wf_bar.setStyleSheet(f"background:{self.C['bg1']}; border-top:1px solid {self.C['border']};")
        wfl = QHBoxLayout(wf_bar)
        wfl.setContentsMargins(8, 2, 8, 2)
        self._waveform = WaveformWidget(self.C, cols=40)
        wfl.addWidget(self._waveform)
        lay.addWidget(wf_bar)

        # Status bar
        sb = QWidget()
        sb.setFixedHeight(72)
        sb.setStyleSheet(f"background:{self.C['bg1']}; border-top:1px solid {self.C['border']};")
        sl = QVBoxLayout(sb)
        sl.setContentsMargins(16, 8, 16, 8)
        sl.setSpacing(4)

        self.status_lbl = QLabel("[ INITIALIZING ]")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet(f"color:{self.C['hi']}; font-size:11px; letter-spacing:3px;")
        sl.addWidget(self.status_lbl)

        # Trascrizione parziale
        self.transcript_lbl = QLabel("")
        self.transcript_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.transcript_lbl.setStyleSheet(f"color:{self.C['dim']}; font-size:10px;")
        sl.addWidget(self.transcript_lbl)

        # Mic level bar
        mic_row = QHBoxLayout()
        mic_row.setContentsMargins(0, 0, 0, 0)
        mic_lbl = QLabel("MIC ")
        mic_lbl.setStyleSheet(f"color:{self.C['dim']}; font-size:9px;")
        mic_row.addWidget(mic_lbl)
        self._mic_bar = MicLevelBar(self.C, width=24)
        mic_row.addWidget(self._mic_bar)
        mic_row.addStretch()
        sl.addLayout(mic_row)

        lay.addWidget(sb)

        # Bottom status bar
        self._statusbar = StatusBar(self.C)
        lay.addWidget(self._statusbar)

        # Blink
        self._blink_state = True
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink)
        self._blink_timer.start(800)

    def _load_video(self):
        base = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets"))
        self._vid_idle     = os.path.join(base, "raze_white.mp4")
        self._vid_thinking = os.path.join(base, "loading.mp4")
        if not os.path.exists(self._vid_idle):
            self.vid.hide()
            self.vid_ph.show()
            self.vid_ph.setText(
                f"<pre style='color:{self.C['dim']}; font-size:13px; line-height:1.5;'>"
                "  ██████  ███  ███ \n"
                " ██    ██ ████████ \n"
                " ██████   ████████ \n"
                " ██   ██  ████████ \n"
                " ██   ██  ██  ████ </pre>"
            )
            return
        self.player = QMediaPlayer(self)
        self.ao = QAudioOutput(self)
        self.ao.setVolume(0)
        self.player.setAudioOutput(self.ao)
        self.player.setVideoOutput(self.vid)
        self.player.mediaStatusChanged.connect(self._on_media)
        self._play_video(self._vid_idle)

    def _play_video(self, path):
        if not os.path.exists(path):
            path = self._vid_idle
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()

    def _on_media(self, s):
        if s == QMediaPlayer.MediaStatus.EndOfMedia:
            self.player.setPosition(0)
            self.player.play()

    def _set_thinking(self, on: bool):
        if not hasattr(self, "player"):
            return
        self._play_video(self._vid_thinking if on else self._vid_idle)

    def _on_mic_level(self, level: float):
        self._mic_bar.set_level(level)
        self._waveform.push_level(level)

    # ── Ascolto ───────────────────────────────────────────────────────────────

    def _listen(self):
        if self._busy:
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
            print(f"[RAZE] Ascolto — device={self._mic_in}")
        except Exception as e:
            self._on_stt_err(str(e))

    def _on_phrase(self, text: str):
        try:
            self._listener.phrase_ready.disconnect(self._on_phrase)
        except Exception:
            pass
        print(f"[RAZE] Frase: '{text}'")
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
        print(f"[RAZE] Risposta: {text[:80]}")
        self._set_thinking(False)
        self.transcript_lbl.setText(text[:100] + ("..." if len(text) > 100 else ""))
        self._set_status("SPEAKING")
        self._statusbar.inc_messages()
        self._tts.speak(text)

    def _on_tts_done(self):
        self._busy = False
        self._set_status("LISTENING")
        QTimer.singleShot(500, self._listen)

    def _on_stt_err(self, err: str):
        print(f"[RAZE] STT err: {err}")
        self._set_status("MIC_ERROR")
        self.transcript_lbl.setText(err[:80])

    def _on_llm_err(self, err: str):
        print(f"[RAZE] LLM err: {err}")
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
            api   = d.get_api_key()
            self._tts.set_speed(speed / 100.0)
            self._tts.set_api_key(api)
            if self._mic_out is not None:
                self._tts.set_output_device(self._mic_out)
            if model:
                from core.tts import MODELS_DIR
                self._tts.set_model(os.path.join(MODELS_DIR, model))
            # Aggiorna mic monitor col nuovo device
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
        if "LISTENING" in self.status_lbl.text():
            self._blink_state = not self._blink_state
            sym = "LISTENING" if self._blink_state else "_ _ _ _ _ _"
            self.status_lbl.setText(f"[ {sym} ]")

    def _back(self):
        self._cleanup()
        self.back_requested.emit()
        self.close()

    def _cleanup(self):
        self._mic_monitor.stop_monitoring()
        if self._listener:
            self._listener.stop()

    def closeEvent(self, e):
        self._cleanup()
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