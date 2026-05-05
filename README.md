<div align="center">

```
██████╗  █████╗ ███████╗███████╗
██╔══██╗██╔══██╗╚══███╔╝██╔════╝
██████╔╝███████║  ███╔╝ █████╗  
██╔══██╗██╔══██║ ███╔╝  ██╔══╝  
██║  ██║██║  ██║███████╗███████╗
╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝
```

**AI assistant · voice & text · offline-first**

![Python](https://img.shields.io/badge/Python-3.11+-00d4aa?style=flat-square&logo=python&logoColor=white)
![PyQt6](https://img.shields.io/badge/PyQt6-UI-5c6bc0?style=flat-square)
![Whisper](https://img.shields.io/badge/Faster--Whisper-STT-ff6b35?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-brightgreen?style=flat-square)

</div>

---

## `> OVERVIEW`

RAZE è un assistente AI con interfaccia terminale sci-fi, pensato per girare **completamente offline**.  
Supporta sia modalità testuale che vocale, con riconoscimento vocale locale via Faster-Whisper e sintesi TTS.

---

## `> FEATURES`

| | |
|---|---|
| 🎙️ **Voice Mode** | STT con Faster-Whisper (`small`), TTS locale, waveform in tempo reale |
| 💬 **Text Mode** | Chat con LLM locale, storico conversazione, temi personalizzabili |
| 🎨 **Temi** | Dark / Light / Cyber — cambio live senza restart |
| 📡 **Offline** | Nessuna API esterna richiesta |

---

## `> SETUP`

```bash
git clone https://github.com/Ryuzakxx/RAZE.git
cd RAZE
pip install -r requirements.txt
python main.py
```

> Assicurati di avere i modelli TTS nella cartella `models/` e i video in `assets/`.

---

## `> STRUCTURE`

```
RAZE/
├── core/          # LLM · STT · TTS
├── ui/            # Finestre PyQt6 · Tema · Widget
├── assets/        # Font · Video · Immagini
├── models/        # Modelli TTS locali
└── main.py
```

---

## `> STATUS`

```
[██████████░░░░░░░░░░] v0.1-dev — work in progress
```

<div align="center">
<sub>built with 🖤 by <a href="https://github.com/Ryuzakxx">Ryuzakxx</a></sub>
</div>
