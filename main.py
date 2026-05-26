"""
AiMeru Voice Studio - エントリーポイント

Usage:
  python main.py
"""
import sys
import logging

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from aimeru.gui.main_window import MainWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AiMeru Voice Studio")
    app.setOrganizationName("AiMeru")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
