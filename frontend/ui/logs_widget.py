# ----------------------------
# 日志界面
# ----------------------------
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from datetime import datetime

from frontend.theme import get_color


class LogsWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet(f"""
            background-color: {get_color("log_bg")};
            color: {get_color("log_text")};
            border: none;
            font-family: Consolas;
            font-size: 12px;
        """)
        layout.addWidget(self.log_area)
        self.setLayout(layout)

    def append_log(self, text):
        time_str = datetime.now().strftime("%H:%M:%S")
        self.log_area.append(f"[{time_str}] {text}")
