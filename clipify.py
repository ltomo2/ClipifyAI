"""Clipify AI desktop entry point."""
import logging
import sys
from logging.handlers import RotatingFileHandler
from app.core.storage import ROOT


def main():
    for name in ['Projects', 'Exports', 'Logs', 'Backups']:
        (ROOT / name).mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
        handlers=[RotatingFileHandler(ROOT / 'Logs' / 'clipify.log', maxBytes=2_000_000, backupCount=3, encoding='utf-8')])
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        from PySide6.QtCore import QLockFile
        from app.ui.main import Window, STYLE
    except ImportError as e:
        print('Clipify needs the existing PySide6 installation. Run install_dependencies.bat first.\n' + str(e))
        return 1
    app = QApplication(sys.argv)
    lock = QLockFile(str(ROOT / 'Logs' / 'clipify.lock'))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(None, 'Clipify is already open', 'Use the existing Clipify window. Only one instance can use this project folder at a time.')
        return 0
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    window = Window()
    window.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
