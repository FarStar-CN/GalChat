import sys
import time
import atexit
import subprocess
import urllib.request

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QStackedWidget, QFrame,
                             QDialog, QFormLayout, QLineEdit, QDialogButtonBox)
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont

from frontend.api_client import APIClient
from frontend.theme import apply_theme
from frontend.ui.logs_widget import LogsWidget
from frontend.ui.console_widget import ConsoleWidget
from frontend.ui.settings_widget import SettingsWidget
from frontend.ui.chat_widget import ChatWidget
from frontend.ui.conversation_list import ConversationList

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
        f"后端输出: {_backend_process.stderr.read().decode(errors='replace')[-500:] if _backend_process.poll() is None else '(仍在运行)'}"
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
            self.conv_list.refresh_theme()

    def closeEvent(self, event):
        for worker in self.api._workers[:]:
            worker.wait(3000)
        super().closeEvent(event)

    def _refresh_theme(self):
        self._theme_mode = self.config_cache.get("theme", "auto")
        apply_theme(QApplication.instance(), self._theme_mode)
        self.chat_page.refresh_theme()
        self.conv_list.refresh_theme()

    def on_config_loaded(self, config: dict):
        self.config_cache = config
        self._refresh_theme()
        QTimer.singleShot(500, self.chat_page.run_preload)
        self.chat_page.apply_config_from_cache(config)
        self.api.fetch_conversations()

        if config.get("enable_qq_monitor"):
            self._qq_event_seq = 0
            self._qq_timer.start(2000)
        else:
            self._qq_timer.stop()

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
        self.conv_list = ConversationList()
        self._current_conv_id = None
        self._qq_event_seq = 0
        self._qq_timer = QTimer()
        self._qq_timer.timeout.connect(self._poll_qq_events)

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

        # Chat 页面：对话列表 + 聊天区域水平分割
        chat_container = QWidget()
        chat_layout = QHBoxLayout(chat_container)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)
        chat_layout.addWidget(self.conv_list)
        chat_layout.addWidget(self.chat_page, stretch=1)
        self.stack.addWidget(chat_container)
        self.stack.addWidget(self.settings_page)
        self.stack.addWidget(self.logs_page)
        self.stack.addWidget(self.console_page)

        # ── 对话列表信号连线 ──
        self.conv_list.new_conversation_requested.connect(self._on_new_conversation)
        self.conv_list.conversation_selected.connect(self._on_conv_selected)
        self.conv_list.rename_requested.connect(self._on_rename_conv)
        self.conv_list.delete_requested.connect(self._on_delete_conv)

        self.api.conversations_ready.connect(self.conv_list.set_conversations)
        self.api.conversation_created.connect(self._on_conv_created)
        self.api.conversation_loaded.connect(self._on_conv_loaded)
        self.api.conversation_updated.connect(self._refresh_conv_list)
        self.api.conversation_deleted.connect(self._on_conv_deleted)

        self.api.qq_events_ready.connect(self._on_qq_events)

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

    # ── 对话管理处理器 ──

    def _on_new_conversation(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("新建对话")
        dlg.setMinimumWidth(320)
        layout = QFormLayout(dlg)
        name_input = QLineEdit()
        name_input.setText("新对话")
        id_input = QLineEdit()
        id_input.setPlaceholderText("留空则随机生成")
        layout.addRow("对话名称:", name_input)
        layout.addRow("ID:", id_input)
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        layout.addRow(btn_box)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        title = name_input.text().strip() or "新对话"
        conv_id = id_input.text().strip() or None
        self.api.create_conversation(title, conv_id)

    def _on_conv_created(self, conv: dict):
        self._current_conv_id = conv["id"]
        self.api.fetch_conversations()
        self.conv_list.select_conversation(conv["id"])

    def _on_conv_selected(self, conv_id: str):
        self._current_conv_id = conv_id
        self.api.fetch_conversation(conv_id)

    def _on_conv_loaded(self, conv: dict):
        self.chat_page.load_conversation(conv)

    def _on_rename_conv(self, conv_id: str, title: str):
        self.api.rename_conversation(conv_id, title)

    def _on_delete_conv(self, conv_id: str):
        self.api.delete_conversation(conv_id)

    def _refresh_conv_list(self):
        self.api.fetch_conversations()

    def _on_conv_deleted(self):
        if self._current_conv_id:
            self.chat_page.clear_conversation()
            self._current_conv_id = None
        self.api.fetch_conversations()

    # ── QQ 事件轮询 ──

    def _poll_qq_events(self):
        self.api.fetch_qq_events(self._qq_event_seq)

    def _on_qq_events(self, data: dict):
        events = data.get("events", [])
        if not events:
            return

        self._qq_event_seq = max(e["seq"] for e in events)
        self.api.fetch_conversations()

        # 若当前正在看 QQ 对话，自动刷新显示
        for evt in events:
            if evt["conv_id"] == self._current_conv_id:
                self.api.fetch_conversation(self._current_conv_id)
                break

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
