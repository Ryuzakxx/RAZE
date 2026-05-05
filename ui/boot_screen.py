"""
ui/boot_screen.py
Schermata di avvio ASCII con sequenza di inizializzazione.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont


BOOT_LINES = [
    ("RAZE // NEURAL ASSISTANT v0.1.0", 0),
    ("", 300),
    ("INITIALIZING CORE SYSTEMS...", 400),
    ("  [OK] PYTORCH BACKEND", 600),
    ("  [OK] OLLAMA INTERFACE", 750),
    ("  [OK] FASTER-WHISPER STT", 900),
    ("  [OK] PIPER TTS ENGINE", 1050),
    ("  [OK] PYQT6 DISPLAY LAYER", 1200),
    ("", 1350),
    ("CHECKING NEURAL MODULES...", 1450),
    ("  [OK] MEMORY SUBSYSTEM", 1600),
    ("  [OK] CONVERSATION CONTEXT", 1750),
    ("  [OK] VIDEO PIPELINE", 1900),
    ("", 2050),
    ("ALL SYSTEMS NOMINAL.", 2200),
    ("BOOT COMPLETE.", 2500),
]


class BootScreen(QWidget):
    boot_finished = pyqtSignal()

    def __init__(self, theme: dict):
        super().__init__()
        self.C = theme
        self.setWindowTitle("RAZE")
        self.setFixedSize(640, 420)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet(f"background: {self.C['bg']}; border: 1px solid {self.C['dim']};")
        self._lines_shown = []
        self._build()
        self._schedule()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 40, 40, 40)
        lay.setSpacing(0)

        # ASCII logo
        logo = QLabel(
            "██████╗  █████╗ ███████╗███████╗\n"
            "██╔══██╗██╔══██╗╚══███╔╝██╔════╝\n"
            "██████╔╝███████║  ███╔╝ █████╗  \n"
            "██╔══██╗██╔══██║ ███╔╝  ██╔══╝  \n"
            "██║  ██║██║  ██║███████╗███████╗\n"
            "╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝"
        )
        logo.setStyleSheet(f"""
            color: {self.C['hi']};
            font-family: 'Courier New', monospace;
            font-size: 11px;
            line-height: 1.4;
            margin-bottom: 20px;
        """)
        lay.addWidget(logo)

        # Separatore
        sep = QLabel("─" * 52)
        sep.setStyleSheet(f"color: {self.C['dim']}; font-family: 'Courier New', monospace; font-size: 11px;")
        lay.addWidget(sep)
        lay.addSpacing(12)

        # Area testo boot
        self.text_area = QLabel("")
        self.text_area.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.text_area.setStyleSheet(f"""
            color: {self.C['mid']};
            font-family: 'Courier New', monospace;
            font-size: 11px;
            line-height: 1.6;
        """)
        self.text_area.setWordWrap(True)
        lay.addWidget(self.text_area, stretch=1)

        # Cursore lampeggiante
        self.cursor = QLabel("_")
        self.cursor.setStyleSheet(f"color: {self.C['hi']}; font-family: 'Courier New'; font-size: 13px;")
        lay.addWidget(self.cursor)

        self._cursor_timer = QTimer(self)
        self._cursor_timer.timeout.connect(self._blink_cursor)
        self._cursor_timer.start(500)
        self._cursor_state = True

    def _schedule(self):
        for text, delay in BOOT_LINES:
            QTimer.singleShot(delay, lambda t=text: self._add_line(t))
        QTimer.singleShot(3200, self._finish)

    def _add_line(self, text: str):
        self._lines_shown.append(text)
        color = self.C['hi'] if text and not text.startswith(" ") else self.C['mid']
        ok_color = self.C['hi']

        html_lines = []
        for line in self._lines_shown:
            if "[OK]" in line:
                html_lines.append(
                    f"<span style='color:{self.C['dim']}'>&nbsp;&nbsp;</span>"
                    f"<span style='color:{ok_color}'>[OK]</span>"
                    f"<span style='color:{self.C['mid']}'>{line.strip()[4:]}</span>"
                )
            elif line and not line.startswith(" "):
                html_lines.append(f"<span style='color:{self.C['hi']}'>{line}</span>")
            elif line == "":
                html_lines.append("<br>")
            else:
                html_lines.append(f"<span style='color:{self.C['mid']}'>{line}</span>")

        self.text_area.setText("<br>".join(html_lines))

    def _blink_cursor(self):
        self._cursor_state = not self._cursor_state
        self.cursor.setText("_" if self._cursor_state else " ")

    def _finish(self):
        self._cursor_timer.stop()
        self.boot_finished.emit()
        self.close()

    def mousePressEvent(self, e):
        # Click per saltare il boot
        self._finish()