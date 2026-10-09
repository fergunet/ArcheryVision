"""Punto de entrada de ArcheryVision."""

import logging
import sys

import cv2
from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    # Sondear índices de cámara sin dispositivo real (detect_available_cameras
    # prueba hasta 10 índices) hace que cada backend de OpenCV (V4L2, FFMPEG,
    # etc.) escriba su propio aviso en stderr al descartarlos; no son errores
    # de la app (el índice se descarta correctamente), así que se silencian
    # dejando pasar solo fallos realmente fatales.
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_FATAL)
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
