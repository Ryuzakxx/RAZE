"""
ui/widgets.py
Widget riutilizzabili: MicLevelBar, WaveformWidget, TypewriterLabel
"""

import numpy as np
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt, QThread, pyqtSignal


# ── Mic Level Bar ─────────────────────────────────────────────────────────────

class MicLevelBar(QWidget):
    """Barra livello microfono ASCII: [████░░░░░░]"""

    def __init__(self, theme: dict, width: int = 20):
        super().__init__()
        self.C = theme
        self._bars = width
        self._level = 0.0
        self._label = QLabel(self._render())
        self._label.setStyleSheet(f"color:{self.C['mid']}; font-family:'Courier New'; font-size:11px;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._label)

    def set_level(self, level: float):
        self._level = max(0.0, min(1.0, level))
        self._label.setText(self._render())
        filled_color = self.C['hi'] if self._level > 0.6 else self.C['mid'] if self._level > 0.2 else self.C['dim']
        self._label.setStyleSheet(f"color:{filled_color}; font-family:'Courier New'; font-size:11px;")

    def _render(self) -> str:
        filled = int(self._level * self._bars)
        bar = "\u2588" * filled + "\u2591" * (self._bars - filled)
        return f"[{bar}]"


# ── Waveform Widget ───────────────────────────────────────────────────────────

class WaveformWidget(QLabel):
    """Waveform ASCII: ▁▂▃▄▅▆▇█ che si anima col microfono."""
    CHARS = " ▁▂▃▄▅▆▇█"

    def __init__(self, theme: dict, cols: int = 32):
        super().__init__()
        self.C = theme
        self._cols = cols
        self._samples = [0.0] * cols
        self.setStyleSheet(f"color:{self.C['dim']}; font-family:'Courier New'; font-size:13px; letter-spacing:1px;")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update()

    def push_level(self, level: float):
        self._samples.pop(0)
        self._samples.append(level)
        self._update()

    def _update(self):
        chars = []
        for s in self._samples:
            idx = min(int(s * (len(self.CHARS) - 1)), len(self.CHARS) - 1)
            chars.append(self.CHARS[idx])
        self.setText("".join(chars))
        avg = sum(self._samples) / len(self._samples)
        color = self.C['hi'] if avg > 0.3 else self.C['mid'] if avg > 0.05 else self.C['dim']
        self.setStyleSheet(f"color:{color}; font-family:'Courier New'; font-size:13px; letter-spacing:1px;")


# ── Mic Monitor Thread ────────────────────────────────────────────────────────

class MicMonitor(QThread):
    level_updated = pyqtSignal(float)

    def __init__(self, device_index=None):
        super().__init__()
        self.device_index = device_index
        self._running = False

    def start_monitoring(self):
        self._running = True
        self.start()

    def stop_monitoring(self):
        self._running = False

    def run(self):
        try:
            import sounddevice as sd
            import time

            def callback(indata, frames, t, status):
                level = float(np.abs(indata).mean()) * 80
                level = min(1.0, level)
                try:
                    self.level_updated.emit(level)
                except RuntimeError:
                    pass

            kwargs = dict(
                samplerate=16000,
                blocksize=1600,
                dtype="float32",
                channels=1,
                callback=callback,
            )
            if self.device_index is not None:
                kwargs["device"] = self.device_index

            with sd.InputStream(**kwargs):
                while self._running:
                    time.sleep(0.05)
        except Exception:
            pass
