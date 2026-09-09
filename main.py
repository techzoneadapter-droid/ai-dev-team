from PySide6.QtWidgets import QApplication

from aidevteam.integrations import install_integration_review
from aidevteam.ui import APP_STYLE, MainWindow


def run() -> None:
    app = QApplication([])
    app.setApplicationName("AI Dev Team")
    app.setOrganizationName("AI Dev Team")
    app.setStyleSheet(APP_STYLE)
    win = MainWindow()
    install_integration_review(win)
    win.show()
    app.exec()


if __name__ == "__main__":
    run()
