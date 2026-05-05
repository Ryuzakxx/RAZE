"""
core/stt.py
Speech-to-Text con faster-whisper (offline, 4x più veloce).
Modello caricato una volta sola in memoria.
"""

import threading
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal

SAMPLE_RATE       = 16000
SILENCE_THRESHOLD = 0.0005
MAX_SILENCE       = 10    # chunk da 100ms → ~1s di silenzio
MAX_RECORD_SEC    = 12

_model      = None
_model_lock = threading.Lock()

def get_model(size: str = "small"):
    global _model
    with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel
            print(f"[STT] Carico faster-whisper '{size}'...")
            _model = WhisperModel(size, device="cpu", compute_type="int8")
            print("[STT] Modello pronto.")
        return _model


class PhraseListener(QObject):
    phrase_ready   = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, device_index: int = None, model_size: str = "small"):
        super().__init__()
        self.device_index = device_index
        self.model_size   = model_size
        self._running     = False
        self._thread      = None

    def listen_once(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _run(self):
        try:
            import sounddevice as sd
            import time

            model = get_model(self.model_size)
            print(f"[STT] Ascolto su device={self.device_index}")

            audio_buffer = []
            silence_chunks = 0
            talking = False
            max_chunks = int(MAX_RECORD_SEC / 0.1)

            def callback(indata, frames, t, status):
                audio_buffer.append(indata.copy())

            kwargs = dict(
                samplerate=SAMPLE_RATE,
                blocksize=int(SAMPLE_RATE * 0.1),
                dtype="float32",
                channels=1,
                callback=callback,
            )
            if self.device_index is not None:
                kwargs["device"] = self.device_index

            with sd.InputStream(**kwargs):
                while self._running:
                    time.sleep(0.1)
                    if not audio_buffer:
                        continue

                    amplitude = np.abs(audio_buffer[-1]).mean()
                    print(f"[STT] amp={amplitude:.5f} talk={talking} sil={silence_chunks}", end="\r")

                    if amplitude > SILENCE_THRESHOLD:
                        talking = True
                        silence_chunks = 0
                    elif talking:
                        silence_chunks += 1
                        if silence_chunks >= MAX_SILENCE:
                            print()
                            break

                    if len(audio_buffer) >= max_chunks:
                        print()
                        break

            if not talking or len(audio_buffer) < 3:
                print("[STT] Nessun audio rilevato")
                try:
                    self.phrase_ready.emit("")
                except RuntimeError:
                    pass
                return

            audio_np = np.concatenate(audio_buffer).flatten()
            duration = len(audio_np) / SAMPLE_RATE
            print(f"[STT] Trascrivo {duration:.1f}s...")

            segments, info = model.transcribe(
                audio_np,
                language="it",
                beam_size=3,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=400,
                    speech_pad_ms=100,
                ),
            )

            text = " ".join(seg.text.strip() for seg in segments).strip()
            print(f"[STT] Trascritto: '{text}'")
            try:
                self.phrase_ready.emit(text)
            except RuntimeError:
                pass  # oggetto già distrutto, ignora

        except Exception as e:
            print(f"[STT] Errore: {e}")
            try:
                self.error_occurred.emit(str(e))
            except RuntimeError:
                pass  # oggetto già distrutto
        finally:
            self._running = False


def preload_model(size: str = "small"):
    t = threading.Thread(target=get_model, args=(size,), daemon=True)
    t.start()


def list_input_devices() -> list[tuple[int, str]]:
    try:
        import sounddevice as sd
        return [
            (i, d["name"])
            for i, d in enumerate(sd.query_devices())
            if d["max_input_channels"] > 0
        ]
    except Exception:
        return []