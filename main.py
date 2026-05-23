"""GalChat 启动入口。"""

from frontend.main import start_backend, MainWindow
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

if __name__ == "__main__":
    start_backend()
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei UI", 10))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
