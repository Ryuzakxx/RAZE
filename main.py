import sys
from PyQt6.QtWidgets import QApplication
from ui.theme import get


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("RAZE")
    app.setStyle("Fusion")

    _wins = {}

    def show_selector():
        from ui.mode_select import ModeSelectWindow
        sel = ModeSelectWindow()
        sel.mode_selected.connect(on_mode)
        _wins["sel"] = sel
        sel.show()

    def on_mode(mode: str):
        if mode == "text":
            from ui.main_window import RazeWindow
            w = RazeWindow()
            _wins["main"] = w
            w.show()
        elif mode == "voice":
            from ui.voice_window import VoiceWindow
            w = VoiceWindow()
            w.back_requested.connect(show_selector)
            _wins["voice"] = w
            w.show()

    # Boot screen
    from ui.boot_screen import BootScreen
    boot = BootScreen(get())
    boot.boot_finished.connect(show_selector)
    _wins["boot"] = boot
    boot.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()