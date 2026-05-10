"""
core/llm.py
Gestisce la comunicazione con Ollama usando l'API /chat.
"""

import requests

OLLAMA_URL  = "http://localhost:11434/api/chat"
MODEL       = "gemma3:latest"
MAX_HISTORY = 20

SYSTEM_PROMPT = """Sei RAZE, un assistente AI. Parli in italiano, in modo naturale e colloquiale.
Se non sai qualcosa o chi è una persona, NON PUOI CERCARE SUL WEB, devi dire che non hai accesso
a tali informazioni perché sei pensata per lavorare offline e quindi non puoi utilizzare la ricerca web.
(non mettere emoji o faccine)"""


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
        response_text = r.json()["message"]["content"].strip()

        if conversation:
            conversation.add_assistant(response_text)

        return response_text

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
