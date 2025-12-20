import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QStackedWidget, QFrame)
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont

from core.config import ConfigManager
from ui.logs_widget import LogsWidget
from ui.console_widget import ConsoleWidget
from ui.settings_widget import SettingsWidget
from ui.chat_widget import ChatWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Demo")
        self.resize(1100, 750)

        # 初始化配置
        self.cfg = ConfigManager()

        self.init_ui()

        # 启动 1 秒后执行预热，避开 UI 初始化的高峰
        QTimer.singleShot(1000, self.chat_page.run_preload)

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 页面容器
        self.stack = QStackedWidget()

        # 初始化各个子页面
        self.logs_page = LogsWidget()
        self.console_page = ConsoleWidget(self.cfg)
        self.chat_page = ChatWidget(self.cfg, self.logs_page.append_log)

        # 设置页面保存时，触发 chat_page 的重新预热
        def on_settings_saved():
            self.chat_page.run_preload()  # 预热连接
            self.chat_page.apply_config()  # 应用新配置（如剪贴板开关）

        self.settings_page = SettingsWidget(
            self.cfg,
            self.logs_page.append_log,
            on_save_callback=on_settings_saved  # 使用新的回调
        )

        # 信号连接：将 ChatWidget 的监视数据传给 ConsoleWidget
        self.chat_page.payload_captured.connect(self.console_page.append_outgoing_payload)
        self.chat_page.options_generated.connect(self.console_page.append_generated_options)
        self.chat_page.reply_received.connect(self.console_page.append_incoming_reply)

        # 添加到堆栈
        self.stack.addWidget(self.chat_page)  # Index 0
        self.stack.addWidget(self.settings_page)  # Index 1
        self.stack.addWidget(self.logs_page)  # Index 2
        self.stack.addWidget(self.console_page)  # Index 3

        # 左侧导航栏
        sidebar = QFrame()
        sidebar.setFixedWidth(130)
        sidebar.setStyleSheet("background-color: #2d3436;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setSpacing(5)
        sidebar_layout.setContentsMargins(5, 20, 5, 20)

        self.nav_btns = []
        nav_items = [("对话", 0), ("设置", 1), ("日志", 2), (">_ 终端", 3)]

        for text, idx in nav_items:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setFixedHeight(50)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent; color: #b2bec3; border: none; 
                    font-size: 14px; border-radius: 5px; text-align: left; padding-left: 15px;
                } 
                QPushButton:hover { background-color: #636e72; color: white;} 
                QPushButton:checked { background-color: #0984e3; color: white; border-left: 4px solid #74b9ff;}
            """)
            btn.clicked.connect(lambda checked, i=idx: self.switch_page(i))
            sidebar_layout.addWidget(btn)
            self.nav_btns.append(btn)

        sidebar_layout.addStretch()

        main_layout.addWidget(self.stack)
        main_layout.addWidget(sidebar)

        # 默认选中第一个
        self.nav_btns[0].setChecked(True)

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_btns):
            btn.setChecked(i == index)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei UI", 10))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())