"""
core/llm.py
Gestisce la comunicazione con Ollama usando l'API /chat
che supporta la storia della conversazione nativa.
"""

import requests
import os
import shutil
from pathlib import Path
from duckduckgo_search import DDGS

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma3:latest"
MAX_HISTORY = 20
SYSTEM_PROMPT = """Sei RAZE, un assistente AI avanzato. Parli in italiano, in modo naturale e colloquiale.
Hai capacità di agente: puoi cercare informazioni sul web e manipolare file e cartelle nel sistema.
Quando l'utente ti chiede di fare qualcosa che richiede queste capacità, rispondi usando un formato speciale per le "tool call":

Per cercare sul web: [WEB_SEARCH: query]
Per leggere un file: [READ_FILE: path]
Per scrivere/modificare un file: [WRITE_FILE: path | content]
Per creare una cartella: [MKDIR: path]
Per eliminare un file/cartella: [DELETE: path]
Per elencare i file in una cartella: [LIST_DIR: path]

Dopo aver ricevuto il risultato della tool call, integra l'informazione nella tua risposta finale.
Non usare emoji o faccine."""


class Conversation:
    """
    Mantiene la storia della conversazione.
    Usane una per sessione (testo o voce).
    """
    def __init__(self):
        self._history: list[dict] = []

    def add_user(self, text: str):
        self._history.append({"role": "user", "content": text})
        self._trim()

    def add_assistant(self, text: str):
        self._history.append({"role": "assistant", "content": text})
        self._trim()

    def _trim(self):
        """Mantiene solo gli ultimi MAX_HISTORY messaggi."""
        if len(self._history) > MAX_HISTORY:
            self._history = self._history[-MAX_HISTORY:]

    def get_messages(self) -> list[dict]:
        return list(self._history)

    def clear(self):
        self._history.clear()


def query_raze(user_input: str, conversation: Conversation = None) -> str:
    """
    Manda un messaggio a Ollama con la storia completa della conversazione.
    Gestisce le tool call per web search e file system.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if conversation:
        conversation.add_user(user_input)
        messages += conversation.get_messages()
    else:
        messages.append({"role": "user", "content": user_input})

    def get_llm_response(msgs):
        payload = {
            "model":    MODEL,
            "messages": msgs,
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
            return r.json()["message"]["content"].strip()
        except Exception as e:
            raise RuntimeError(f"Errore Ollama: {e}")

    max_iterations = 5
    
    for _ in range(max_iterations):
        response_text = get_llm_response(messages)
        
        # Normalizzazione percorso
        def normalize_path(p):
            p = p.strip()
            # Mappatura cartelle utente comuni
            user_home = Path.home()
            mappings = {
                "download": user_home / "Downloads",
                "downloads": user_home / "Downloads",
                "documenti": user_home / "Documents",
                "documents": user_home / "Documents",
                "desktop": user_home / "Desktop",
            }
            for key, full_path in mappings.items():
                if p.lower() == key:
                    return str(full_path)
            
            # Se è un percorso relativo, lo rende assoluto rispetto alla root del progetto
            if not os.path.isabs(p):
                return str(Path(os.getcwd()) / p)
            return p

        # Controllo tool call [TOOL: args]
        if "[WEB_SEARCH:" in response_text:
            query = response_text.split("[WEB_SEARCH:")[1].split("]")[0].strip()
            with DDGS() as ddgs:
                results = [r['body'] for r in ddgs.text(query, max_results=3)]
                tool_result = "\n".join(results) if results else "Nessun risultato trovato."
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": f"[RESULT: {tool_result}]"})
            continue
            
        elif "[READ_FILE:" in response_text:
            path = response_text.split("[READ_FILE:")[1].split("]")[0].strip()
            print(f"[DEBUG] Tentativo di lettura file: {path}")
            try:
                with open(path, 'r', encoding='utf-8') as f: tool_result = f.read()
            except Exception as e: 
                print(f"[DEBUG] Errore lettura file {path}: {e}")
                tool_result = f"Errore lettura: {e}"
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": f"[RESULT: {tool_result}]"})
            continue
            
        elif "[WRITE_FILE:" in response_text:
            try:
                parts = response_text.split("[WRITE_FILE:")[1].split("]")[0].split("|")
                path, content = parts[0].strip(), parts[1].strip()
                print(f"[DEBUG] Tentativo di scrittura file: {path}")
                with open(path, 'w', encoding='utf-8') as f: f.write(content)
                tool_result = "File scritto con successo."
            except Exception as e: 
                print(f"[DEBUG] Errore scrittura file {path}: {e}")
                tool_result = f"Errore scrittura: {e}"
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": f"[RESULT: {tool_result}]"})
            continue
            
        elif "[MKDIR:" in response_text:
            path = response_text.split("[MKDIR:")[1].split("]")[0].strip()
            print(f"[DEBUG] Tentativo di creazione cartella: {path}")
            try:
                os.makedirs(path, exist_ok=True)
                tool_result = "Cartella creata con successo."
            except Exception as e: 
                print(f"[DEBUG] Errore creazione cartella {path}: {e}")
                tool_result = f"Errore creazione cartella: {e}"
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": f"[RESULT: {tool_result}]"})
            continue
            
        elif "[DELETE:" in response_text:
            path = response_text.split("[DELETE:")[1].split("]")[0].strip()
            print(f"[DEBUG] Tentativo di eliminazione: {path}")
            try:
                if os.path.isdir(path): shutil.rmtree(path)
                else: os.remove(path)
                tool_result = "Eliminato con successo."
            except Exception as e: 
                print(f"[DEBUG] Errore eliminazione {path}: {e}")
                tool_result = f"Errore eliminazione: {e}"
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": f"[RESULT: {tool_result}]"})
            continue
            
        elif "[LIST_DIR:" in response_text:
            path = response_text.split("[LIST_DIR:")[1].split("]")[0].strip()
            print(f"[DEBUG] Tentativo di listdir: {path}")
            try:
                tool_result = os.listdir(path)
                tool_result = ", ".join(tool_result) if tool_result else "Cartella vuota."
            except Exception as e: 
                print(f"[DEBUG] Errore listdir {path}: {e}")
                tool_result = f"Errore listdir: {e}"
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": f"[RESULT: {tool_result}]"})
            continue
            
        break

    if conversation:
        conversation.add_assistant(response_text)

    return response_text


def check_ollama_status() -> bool:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False