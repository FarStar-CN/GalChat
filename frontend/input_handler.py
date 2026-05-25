# ----------------------------
# 输入处理
# ----------------------------

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication


class InputHandler(QObject):
    """
    输入处理器：负责监听外部输入源，并处理向外部输出（复制）的逻辑。
    目前实现方式：系统剪贴板 (Clipboard)。
    未来如果要改为其他方式，只需修改这个类，保持信号接口不变即可。
    """

    # 对外信号：当检测到新的有效用户消息时发出
    new_message_received = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.clipboard = QApplication.clipboard()

        # 监听剪贴板变化
        self.clipboard.dataChanged.connect(self._on_source_changed)

        # 记录最后一次 AI 生成的回复，用于过滤掉自己发出的内容
        self.last_ai_reply = ""
        self.is_enabled = True

    def set_enabled(self, enabled: bool):
        """设置是否启用监听"""
        self.is_enabled = enabled

    def update_ai_reply(self, text):
        """
        主程序调用此方法：通知处理器 AI 生成了新回复。
        处理器需要：
        1. 记录它（防止自循环读取）。
        2. 将其输出到外部（目前是写入剪贴板）。
        """
        if not text:
            return

        self.last_ai_reply = text

        # 写入剪贴板 (这是目前的输出方式)
        # 注意：这一步会触发 dataChanged，但在 _on_source_changed 中会被过滤
        self.clipboard.setText(text)

    def _on_source_changed(self):

        if not self.is_enabled:
            return

        # 获取内容
        current_text = self.clipboard.text()

        # 过滤空内容
        if not current_text:
            return

        # 核心过滤逻辑：
        # 如果当前获取的内容 == AI 刚刚回复的内容，说明这是我们自己写的，忽略
        if current_text == self.last_ai_reply:
            return

        # 只有内容确实不同，才通知主程序
        self.new_message_received.emit(current_text)
