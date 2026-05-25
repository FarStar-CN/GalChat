"""GalChat 启动入口。"""

import os
import sys

# QQ-nt 运行在 XWayland，必须用 X11 后端才能读剪贴板
os.environ["QT_QPA_PLATFORM"] = "xcb"

from frontend.main import start_backend, MainWindow
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

if __name__ == "__main__":
    start_backend()
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei UI", 10))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
