"""输入处理：剪贴板监听 + 轮询回退（Wayland 兼容）。"""

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication


class InputHandler(QObject):
    """同时使用信号和定时轮询进行剪贴板监听，确保 Wayland 下可靠。"""

    new_message_received = pyqtSignal(str)

    def __init__(self, poll_interval_ms: int = 500):
        super().__init__()
        self.clipboard = QApplication.clipboard()

        # 信号监听（X11 下可靠，Wayland 下可能不触发）
        self.clipboard.dataChanged.connect(self._on_signal)

        # 定时轮询（Wayland 回退）
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._on_poll)
        self._poll_interval = poll_interval_ms

        self.last_ai_reply = ""
        self._last_clipboard_text = self.clipboard.text() or ""
        self.is_enabled = True

        # 默认启动轮询（Wayland 兼容）
        self._poll_timer.start(self._poll_interval)

    def set_enabled(self, enabled: bool):
        self.is_enabled = enabled
        if enabled:
            self._ensure_polling()
        elif self._poll_timer.isActive():
            self._poll_timer.stop()

    def _ensure_polling(self):
        """确保轮询定时器在运行（幂等）。"""
        if not self._poll_timer.isActive():
            self._poll_timer.start(self._poll_interval)

    def start(self):
        """显式启动轮询（QQ 集成初始化时调用）。"""
        if not self._poll_timer.isActive():
            self._poll_timer.start(self._poll_interval)

    def stop(self):
        self._poll_timer.stop()

    def update_ai_reply(self, text):
        """通知处理器 AI 生成了新回复，防止自循环。"""
        if not text:
            return
        self.last_ai_reply = text
        self._last_clipboard_text = text
        # 写入剪贴板，也会触发 dataChanged / 轮询，但都会被过滤
        self.clipboard.setText(text)

    def _on_signal(self):
        """Qt 信号回调（X11 首选路径）。"""
        if not self.is_enabled:
            return
        self._check_and_emit()

    def _on_poll(self):
        """定时轮询回调（Wayland 回退路径）。"""
        if not self.is_enabled:
            return
        self._check_and_emit()

    def _check_and_emit(self):
        """统一的剪贴板检查逻辑。"""
        current_text = self.clipboard.text()
        if not current_text:
            return
        if current_text == self._last_clipboard_text:
            return
        self._last_clipboard_text = current_text

        if current_text == self.last_ai_reply:
            return

        self.new_message_received.emit(current_text)
