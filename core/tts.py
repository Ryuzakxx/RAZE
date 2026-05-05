"""
core/tts.py
Text-to-Speech con Piper (offline, voci neurali).
"""

import subprocess
import threading
import os
import tempfile
from PyQt6.QtCore import QObject, pyqtSignal

# Percorsi default
PIPER_DIR   = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "piper"))
PIPER_EXE   = os.path.join(PIPER_DIR, "piper.exe")
MODELS_DIR  = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "models"))
DEFAULT_MODEL = "it_IT-paola-medium.onnx"


class TTSEngine(QObject):
    speech_started  = pyqtSignal()
    speech_finished = pyqtSignal()
    error_occurred  = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._model   = os.path.join(MODELS_DIR, DEFAULT_MODEL)
        self._speed   = 1.0
        self._device_index = None  # indice output sounddevice

    def speak(self, text: str):
        """Sintetizza e riproduce in un thread separato."""
        t = threading.Thread(target=self._run, args=(text,), daemon=True)
        t.start()

    def _run(self, text: str):
        try:
            self.speech_started.emit()

            if not os.path.exists(PIPER_EXE):
                raise FileNotFoundError(f"piper.exe non trovato in: {PIPER_DIR}")
            if not os.path.exists(self._model):
                raise FileNotFoundError(f"Modello non trovato: {self._model}")

            # Genera WAV con Piper
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name

            cmd = [
                PIPER_EXE,
                "--model", self._model,
                "--output_file", tmp_path,
                "--length_scale", str(1.0 / self._speed),
            ]

            proc = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )

            if proc.returncode != 0:
                raise RuntimeError(f"Piper error: {proc.stderr.decode()}")

            # Riproduci il WAV
            import sounddevice as sd
            import soundfile as sf

            data, samplerate = sf.read(tmp_path, dtype="float32")

            kwargs = {"samplerate": samplerate, "blocking": True}
            if self._device_index is not None:
                kwargs["device"] = self._device_index

            sd.play(data, **kwargs)
            sd.wait()

            os.unlink(tmp_path)
            self.speech_finished.emit()

        except Exception as e:
            print(f"[TTS] Errore: {e}")
            self.error_occurred.emit(str(e))

    def set_speed(self, speed: float):
        """Velocità parlato — 1.0 normale, 0.8 lento, 1.3 veloce."""
        self._speed = max(0.5, min(2.0, speed))

    def set_model(self, model_path: str):
        self._model = model_path

    def set_output_device(self, device_index: int):
        self._device_index = device_index

    @staticmethod
    def list_models() -> list[str]:
        """Elenca i modelli .onnx disponibili in models/."""
        try:
            return [
                f for f in os.listdir(MODELS_DIR)
                if f.endswith(".onnx")
            ]
        except Exception:
            return []