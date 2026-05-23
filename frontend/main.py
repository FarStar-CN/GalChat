import sys
import time
import atexit
import subprocess
import urllib.request

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QStackedWidget, QFrame)
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont

from frontend.api_client import APIClient
from frontend.theme import apply_theme
from frontend.ui.logs_widget import LogsWidget
from frontend.ui.console_widget import ConsoleWidget
from frontend.ui.settings_widget import SettingsWidget
from frontend.ui.chat_widget import ChatWidget

BACKEND_PORT = 8000
BACKEND_URL = f"http://localhost:{BACKEND_PORT}"
_backend_process = None


def start_backend():
    """启动后端 FastAPI 子进程，轮询 health check 等待就绪。"""
    global _backend_process
    _backend_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.server:app", "--port", str(BACKEND_PORT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    atexit.register(stop_backend)

    deadline = time.time() + 8
    while time.time() < deadline:
        try:
            resp = urllib.request.urlopen(f"{BACKEND_URL}/api/health", timeout=1)
            if resp.status == 200:
                return
        except Exception:
            pass
        time.sleep(0.3)
    raise RuntimeError(
        f"后端启动超时，请检查端口 {BACKEND_PORT} 是否被占用。\n"
        f"后端输出: {_backend_process.stderr.read().decode(errors='replace')[-500:] if _backend_process.poll() else '(仍在运行)'}"
    )


def stop_backend():
    global _backend_process
    if _backend_process:
        _backend_process.terminate()
        try:
            _backend_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _backend_process.kill()
        _backend_process = None


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GalChat")
        self.resize(1100, 750)

        self.api = APIClient(BACKEND_URL)
        self.config_cache = {}
        self._theme_mode = "auto"

        self.init_ui()

        # 监听系统主题变化
        try:
            QApplication.styleHints().colorSchemeChanged.connect(self._on_system_theme_changed)
        except AttributeError:
            pass

        self.api.config_ready.connect(self.on_config_loaded)
        self.api.fetch_config()

    def _on_system_theme_changed(self):
        if self._theme_mode == "auto":
            apply_theme(QApplication.instance(), "auto")
            self.chat_page.refresh_theme()

    def closeEvent(self, event):
        for worker in self.api._workers[:]:
            worker.wait(3000)
        super().closeEvent(event)

    def _refresh_theme(self):
        self._theme_mode = self.config_cache.get("theme", "auto")
        apply_theme(QApplication.instance(), self._theme_mode)
        self.chat_page.refresh_theme()

    def on_config_loaded(self, config: dict):
        self.config_cache = config
        self._refresh_theme()
        QTimer.singleShot(500, self.chat_page.run_preload)
        self.chat_page.apply_config_from_cache(config)

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.stack = QStackedWidget()

        self.logs_page = LogsWidget()
        self.console_page = ConsoleWidget(self.api)
        self.chat_page = ChatWidget(self.api, self.logs_page.append_log)

        def on_settings_saved():
            def refresh_and_apply(config):
                self.api.config_ready.disconnect(refresh_and_apply)
                self.config_cache = config
                self._refresh_theme()
                self.chat_page.run_preload()
                self.chat_page.apply_config_from_cache(config)
            self.api.config_ready.connect(refresh_and_apply)
            self.api.fetch_config()

        self.settings_page = SettingsWidget(
            self.api,
            self.logs_page.append_log,
            on_save_callback=on_settings_saved,
        )

        self.chat_page.payload_captured.connect(self.console_page.append_outgoing_payload)
        self.chat_page.options_generated.connect(self.console_page.append_generated_options)
        self.chat_page.reply_received.connect(self.console_page.append_incoming_reply)

        self.stack.addWidget(self.chat_page)
        self.stack.addWidget(self.settings_page)
        self.stack.addWidget(self.logs_page)
        self.stack.addWidget(self.console_page)

        sidebar = QFrame()
        sidebar.setProperty("sidebar", True)
        sidebar.setFixedWidth(130)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setSpacing(5)
        sidebar_layout.setContentsMargins(5, 20, 5, 20)

        self.nav_btns = []
        nav_items = [("对话", 0), ("设置", 1), ("日志", 2), (">_ 终端", 3)]

        for text, idx in nav_items:
            btn = QPushButton(text)
            btn.setProperty("nav", True)
            btn.setCheckable(True)
            btn.setFixedHeight(50)
            btn.clicked.connect(lambda checked, i=idx: self.switch_page(i))
            sidebar_layout.addWidget(btn)
            self.nav_btns.append(btn)

        sidebar_layout.addStretch()
        main_layout.addWidget(self.stack)
        main_layout.addWidget(sidebar)
        self.nav_btns[0].setChecked(True)

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_btns):
            btn.setChecked(i == index)


if __name__ == "__main__":
    start_backend()
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei UI", 10))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
