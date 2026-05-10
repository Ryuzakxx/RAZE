"""
core/tts.py
Text-to-Speech con XTTS v2 (Coqui TTS) - offline, qualità neurale.

Installazione:
    pip install TTS sounddevice soundfile

Al primo avvio scarica automaticamente il modello XTTS v2 (~1.8 GB).
Opzionale: fornisci un file WAV di riferimento (3-10 sec) per clonare la voce.
"""

import os
import threading
import tempfile

from PyQt6.QtCore import QObject, pyqtSignal

# Voce di riferimento opzionale per voice cloning
# Metti un file WAV in assets/reference_voice.wav per attivare il cloning.
_ASSETS_DIR    = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets"))
REFERENCE_WAV  = os.path.join(_ASSETS_DIR, "reference_voice.wav")

# Lingua usata da XTTS v2 per la sintesi
DEFAULT_LANG   = "it"

# Modello XTTS v2 (scaricato automaticamente la prima volta)
XTTS_MODEL     = "tts_models/multilingual/multi-dataset/xtts_v2"


class TTSEngine(QObject):
    speech_started  = pyqtSignal()
    speech_finished = pyqtSignal()
    error_occurred  = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._lang          = DEFAULT_LANG
        self._reference_wav = REFERENCE_WAV if os.path.exists(REFERENCE_WAV) else None
        self._speed         = 1.0
        self._device_index  = None
        self._tts           = None   # istanza TTS, lazy-loaded
        self._lock          = threading.Lock()

    # ── inizializzazione lazy ────────────────────────────────────────────────
    def _load(self):
        """Carica XTTS v2 la prima volta che viene usato (thread-safe)."""
        if self._tts is not None:
            return
        with self._lock:
            if self._tts is not None:
                return
            try:
                from TTS.api import TTS
                # gpu=False per compatibilità universale; metti gpu=True se hai CUDA
                self._tts = TTS(model_name=XTTS_MODEL, gpu=False)
                print("[TTS] XTTS v2 caricato.")
            except Exception as e:
                raise RuntimeError(f"Impossibile caricare XTTS v2: {e}")

    # ── API pubblica ────────────────────────────────────────────────────────────
    def speak(self, text: str):
        """Sintetizza e riproduce in un thread separato (non blocca la UI)."""
        t = threading.Thread(target=self._run, args=(text,), daemon=True)
        t.start()

    def set_speed(self, speed: float):
        """Velocità parlato: 1.0 normale, 0.8 lento, 1.3 veloce."""
        self._speed = max(0.5, min(2.0, speed))

    def set_language(self, lang: str):
        """Imposta la lingua di sintesi (es. 'it', 'en', 'fr')."""
        self._lang = lang

    def set_reference_wav(self, path: str):
        """
        Imposta la voce di riferimento per il voice cloning.
        Il file deve essere un WAV mono/stereo di 3-10 secondi.
        Passa None per usare la voce italiana di default.
        """
        self._reference_wav = path if path and os.path.exists(path) else None

    def set_output_device(self, device_index: int):
        self._device_index = device_index

    # ── sintesi interna ───────────────────────────────────────────────────────────
    def _run(self, text: str):
        tmp_path = None
        try:
            self.speech_started.emit()
            self._load()

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name

            if self._reference_wav:
                # Voice cloning: usa la voce di riferimento
                self._tts.tts_to_file(
                    text=text,
                    speaker_wav=self._reference_wav,
                    language=self._lang,
                    file_path=tmp_path,
                    speed=self._speed,
                )
            else:
                # Voce italiana standard di XTTS v2 ("Ana Florence" o simile)
                self._tts.tts_to_file(
                    text=text,
                    language=self._lang,
                    file_path=tmp_path,
                    speed=self._speed,
                )

            # Riproduzione
            import sounddevice as sd
            import soundfile as sf

            data, samplerate = sf.read(tmp_path, dtype="float32")
            kwargs = {"samplerate": samplerate, "blocking": True}
            if self._device_index is not None:
                kwargs["device"] = self._device_index

            sd.play(data, **kwargs)
            sd.wait()

            self.speech_finished.emit()

        except Exception as e:
            print(f"[TTS] Errore: {e}")
            self.error_occurred.emit(str(e))
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
