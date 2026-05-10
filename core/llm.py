"""
core/llm.py
Gestisce la comunicazione con Ollama.
Supporta comandi file system via [FS:cmd] nella risposta dell'AI.
"""

import requests
from core.fs_tools import execute_fs_commands

OLLAMA_URL  = "http://localhost:11434/api/chat"
MODEL       = "gemma3:latest"
MAX_HISTORY = 20

SYSTEM_PROMPT = """Sei RAZE, un assistente AI. Parli in italiano, in modo naturale e colloquiale.
Se non sai qualcosa, chi è una persona, NON PUOI CERCARE SUL WEB, devi dire che non hai accesso
a tali informazioni perché sei pensata per lavorare offline.
(non mettere emoji o faccine)

Puoi eseguire operazioni sul file system dell'utente.
Quando devi farlo, scrivi il comando su una riga separata PRIMA del testo di risposta:

  [FS:delete] percorso       → elimina file o cartella
  [FS:list]   percorso       → elenca contenuto cartella
  [FS:mkdir]  percorso       → crea cartella
  [FS:move]   src -> dst     → sposta file/cartella
  [FS:info]   percorso       → info su file/cartella

Esempi di percorsi accettati:
  download, downloads, scaricati  → cartella Downloads utente
  desktop, scrivania              → Desktop utente
  documenti, documents            → Documenti utente
  C:\\Users\\pippo\\file.txt       → percorso assoluto Windows

NON usare percorsi relativi alla directory del progetto.
Se l'utente dice "elimina la cartella download" scrivi:
  [FS:delete] download
Se l'utente dice "elenca il desktop" scrivi:
  [FS:list] desktop
"""


class Conversation:
    def __init__(self):
        self._history: list[dict] = []

    def add_user(self, text: str):
        self._history.append({"role": "user", "content": text})
        self._trim()

    def add_assistant(self, text: str):
        self._history.append({"role": "assistant", "content": text})
        self._trim()

    def _trim(self):
        if len(self._history) > MAX_HISTORY:
            self._history = self._history[-MAX_HISTORY:]

    def get_messages(self) -> list[dict]:
        return list(self._history)

    def clear(self):
        self._history.clear()


def query_raze(user_input: str, conversation: Conversation = None) -> str:
    """
    Invia il messaggio a Ollama, esegue eventuali comandi FS nella risposta
    e restituisce il testo pulito + gli esiti delle operazioni.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if conversation:
        conversation.add_user(user_input)
        messages += conversation.get_messages()
    else:
        messages.append({"role": "user", "content": user_input})

    payload = {
        "model":    MODEL,
        "messages": messages,
        "stream":   False,
        "options": {
            "temperature": 0.7,
            "top_p":       0.9,
            "num_predict": 512,
        }
    }

    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=60)
        r.raise_for_status()
        raw_text = r.json()["message"]["content"].strip()

        # Esegui comandi FS presenti nella risposta
        clean_text, fs_results = execute_fs_commands(raw_text)

        # Componi risposta finale: testo AI + esiti operazioni FS
        final = clean_text
        if fs_results:
            final = (clean_text + "\n\n" + "\n".join(fs_results)).strip()

        if conversation:
            conversation.add_assistant(final)

        return final

    except requests.exceptions.ConnectionError:
        raise ConnectionError("Ollama non raggiungibile. Avvia: ollama serve")
    except requests.exceptions.Timeout:
        raise TimeoutError("Timeout Ollama.")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"Errore HTTP Ollama: {e}")


def check_ollama_status() -> bool:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False
