"""
core/fs_tools.py  -  RAZE File System Tools
Risolve percorsi relativi/keyword in percorsi assoluti Windows e
esegue operazioni su cartelle/file richieste dall'AI.
"""

import os
import re
import shutil
from pathlib import Path


# ── Mappa keyword → cartelle utente Windows ──────────────────────────────────

HOME = Path.home()

# Tutte le varianti italiane/inglesi comuni
_KNOWN_DIRS: dict[str, Path] = {
    # download
    "download":   HOME / "Downloads",
    "downloads":  HOME / "Downloads",
    "scaricati":  HOME / "Downloads",
    "scaricato":  HOME / "Downloads",
    # desktop
    "desktop":    HOME / "Desktop",
    "scrivania":  HOME / "Desktop",
    # documenti
    "documenti":  HOME / "Documents",
    "documents":  HOME / "Documents",
    "docs":       HOME / "Documents",
    # immagini
    "immagini":   HOME / "Pictures",
    "pictures":   HOME / "Pictures",
    "foto":       HOME / "Pictures",
    # musica
    "musica":     HOME / "Music",
    "music":      HOME / "Music",
    # video
    "video":      HOME / "Videos",
    "videos":     HOME / "Videos",
    # home
    "home":       HOME,
    "utente":     HOME,
    "user":       HOME,
    # temp
    "temp":       Path(os.environ.get("TEMP", HOME / "AppData" / "Local" / "Temp")),
    "tmp":        Path(os.environ.get("TEMP", HOME / "AppData" / "Local" / "Temp")),
}

# Directory base del progetto RAZE
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resolve_path(raw: str) -> Path:
    """
    Converte una stringa di percorso in un Path assoluto.
    Priorità:
      1. già assoluto  → usalo direttamente
      2. keyword nota  → cartella utente corrispondente
      3. percorso relativo → relativo a HOME (non alla CWD del progetto)
    """
    p = raw.strip().strip('"').strip("'")

    # 1. percorso assoluto
    candidate = Path(p)
    if candidate.is_absolute():
        return candidate

    # 2. keyword (es. "download", "Desktop")
    key = p.lower().rstrip("/\\").split("/")[-1].split("\\")[-1]
    if key in _KNOWN_DIRS:
        return _KNOWN_DIRS[key]

    # Prova anche la prima parte del percorso come keyword
    first = p.replace("\\", "/").split("/")[0].lower()
    if first in _KNOWN_DIRS:
        rest = Path(*p.replace("\\", "/").split("/")[1:]) if len(p.split("/")) > 1 else Path("")
        return _KNOWN_DIRS[first] / rest if rest != Path("") else _KNOWN_DIRS[first]

    # 3. relativo a HOME
    return HOME / p


# ── Operazioni ────────────────────────────────────────────────────────────────────

def delete_path(raw: str) -> str:
    """
    Elimina file o cartella al percorso risolto.
    Ritorna un messaggio di esito.
    """
    target = resolve_path(raw)
    if not target.exists():
        return f"[RAZE] Percorso non trovato: {target}"
    try:
        if target.is_dir():
            shutil.rmtree(target)
            return f"[RAZE] Cartella eliminata: {target}"
        else:
            target.unlink()
            return f"[RAZE] File eliminato: {target}"
    except PermissionError:
        return f"[RAZE] Permesso negato: {target}"
    except Exception as e:
        return f"[RAZE] Errore durante eliminazione di {target}: {e}"


def list_dir(raw: str) -> str:
    """Elenca contenuto di una cartella."""
    target = resolve_path(raw)
    if not target.exists():
        return f"[RAZE] Cartella non trovata: {target}"
    if not target.is_dir():
        return f"[RAZE] Non è una cartella: {target}"
    try:
        items = sorted(target.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        lines = [f"Contenuto di {target}:"]
        for item in items:
            tag = "[DIR] " if item.is_dir() else "[FILE]"
            lines.append(f"  {tag} {item.name}")
        return "\n".join(lines) if len(lines) > 1 else f"{target}: cartella vuota."
    except PermissionError:
        return f"[RAZE] Permesso negato: {target}"


def create_dir(raw: str) -> str:
    """Crea una cartella (incluse le parent mancanti)."""
    target = resolve_path(raw)
    try:
        target.mkdir(parents=True, exist_ok=True)
        return f"[RAZE] Cartella creata: {target}"
    except PermissionError:
        return f"[RAZE] Permesso negato: {target}"
    except Exception as e:
        return f"[RAZE] Errore: {e}"


def move_path(src_raw: str, dst_raw: str) -> str:
    """Sposta file o cartella."""
    src = resolve_path(src_raw)
    dst = resolve_path(dst_raw)
    if not src.exists():
        return f"[RAZE] Sorgente non trovata: {src}"
    try:
        shutil.move(str(src), str(dst))
        return f"[RAZE] Spostato: {src} → {dst}"
    except Exception as e:
        return f"[RAZE] Errore spostamento: {e}"


def path_info(raw: str) -> str:
    """Mostra informazioni su un percorso (esiste? tipo? dimensione?)."""
    target = resolve_path(raw)
    if not target.exists():
        return f"[RAZE] Non esiste: {target}"
    kind = "Cartella" if target.is_dir() else "File"
    size = ""
    if target.is_file():
        s = target.stat().st_size
        size = f", {s} byte" if s < 1024 else f", {s/1024:.1f} KB" if s < 1024**2 else f", {s/1024**2:.1f} MB"
    return f"[RAZE] {kind}: {target}{size}"


# ── Parser comandi (usato da llm.py) ─────────────────────────────────────────────

# Pattern per riconoscere comandi file nella risposta dell'AI
# L'AI deve scrivere comandi in blocchi speciali:
#   [FS:delete] percorso
#   [FS:list]   percorso
#   [FS:mkdir]  percorso
#   [FS:move]   sorgente -> destinazione
#   [FS:info]   percorso
_FS_PATTERN = re.compile(
    r"\[FS:(?P<cmd>delete|list|mkdir|move|info)\]\s*(?P<args>.+)",
    re.IGNORECASE
)


def execute_fs_commands(text: str) -> tuple[str, list[str]]:
    """
    Scansiona il testo della risposta AI cercando comandi [FS:...] e li esegue.
    Ritorna (testo_pulito, lista_esiti).
    """
    results = []
    clean_lines = []

    for line in text.splitlines():
        m = _FS_PATTERN.match(line.strip())
        if m:
            cmd  = m.group("cmd").lower()
            args = m.group("args").strip()
            if cmd == "delete":
                results.append(delete_path(args))
            elif cmd == "list":
                results.append(list_dir(args))
            elif cmd == "mkdir":
                results.append(create_dir(args))
            elif cmd == "move":
                parts = re.split(r"\s*->\s*", args, maxsplit=1)
                if len(parts) == 2:
                    results.append(move_path(parts[0], parts[1]))
                else:
                    results.append(f"[RAZE] Sintassi move errata. Usa: sorgente -> destinazione")
            elif cmd == "info":
                results.append(path_info(args))
        else:
            clean_lines.append(line)

    return "\n".join(clean_lines).strip(), results
