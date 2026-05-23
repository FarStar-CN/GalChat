"""主聊天页面。"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QTextEdit, QLineEdit,
                             QMessageBox, QGridLayout, QGraphicsBlurEffect)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextCursor, QTextBlockFormat
from enum import Enum, auto

from frontend.api_client import APIClient
from frontend.input_handler import InputHandler
from frontend.theme import get_color


class ConversationState(Enum):
    IDLE = auto()
    WAIT_OPTIONS = auto()


class ChatWidget(QWidget):
    payload_captured = pyqtSignal(str)
    reply_received = pyqtSignal(str)
    options_generated = pyqtSignal(list)

    def __init__(self, api_client: APIClient, log_callback):
        super().__init__()
        self.api = api_client
        self.log = log_callback
        self.history = []
        self.current_user_input = ""
        self.current_options_data = []
        self.config_cache = {}
        self._preset_directions_str = ""
        self._displayed_messages = []  # (role, text, align_right)

        self.state = ConversationState.IDLE

        self.input_handler = InputHandler()
        self.input_handler.new_message_received.connect(self.on_external_message)

        self.init_ui()
        self.update_ui_by_state()

        self.api.directions_ready.connect(self._on_directions_loaded)
        self.api.fetch_directions()

    def _on_directions_loaded(self, directions: list):
        self._preset_directions_str = "、".join(directions) if directions else ""

    def apply_config_from_cache(self, config: dict):
        self.config_cache = config
        is_monitor_on = config.get("enable_clipboard_monitor", True)
        self.input_handler.set_enabled(is_monitor_on)
        state_text = "开启" if is_monitor_on else "关闭"
        self.log(f"剪贴板监听已{state_text}")

    def set_state(self, new_state: ConversationState):
        self.log(f"[状态切换] {self.state.name} -> {new_state.name}")
        self.state = new_state
        self.update_ui_by_state()

    def update_ui_by_state(self):
        is_idle = (self.state == ConversationState.IDLE)
        self.input_field.setEnabled(is_idle)

        if is_idle:
            self.send_btn.setText("发送")
            self.send_btn.setProperty("send", True)
            self.send_btn.setProperty("cancel", False)
        else:
            self.send_btn.setText("取消")
            self.send_btn.setProperty("send", False)
            self.send_btn.setProperty("cancel", True)

        # 刷新样式以应用属性变更
        self.send_btn.style().unpolish(self.send_btn)
        self.send_btn.style().polish(self.send_btn)
        self.input_field.setFocus()

    def on_send_or_cancel_clicked(self):
        if self.state == ConversationState.IDLE:
            self.start_chat_flow()
        else:
            self.handle_cancel()

    def handle_cancel(self):
        try:
            self.api.finished_options.disconnect(self.show_options)
        except TypeError:
            pass
        try:
            self.api.error_occurred.disconnect(self.handle_error)
        except TypeError:
            pass
        try:
            self.api.debug_payload.disconnect()
        except TypeError:
            pass

        self.log("用户取消了当前操作")
        self.options_overlay.hide()
        self.blur_effect.setBlurRadius(0)
        self.current_options_data = []
        self.set_state(ConversationState.IDLE)

    def start_chat_flow(self, is_regenerate=False):
        if self.state != ConversationState.IDLE and not is_regenerate:
            return

        text = self.input_field.text().strip() if not is_regenerate else self.current_user_input
        if not text:
            return

        self.blur_effect.setBlurRadius(0)
        self.set_state(ConversationState.WAIT_OPTIONS)

        if not is_regenerate:
            self.current_user_input = text
            user_name = self.config_cache.get("user_name", "我")
            self.append_chat(user_name, text, get_color("accent"), align_right=False)
            self.input_field.clear()

        self.current_options_data = []

        self.api.finished_options.connect(self.show_options)
        self.api.error_occurred.connect(self.handle_error)
        self.api.debug_payload.connect(self.payload_captured.emit)
        self.api.get_options(
            prompt=text,
            context=self.history,
            preset_str=self._preset_directions_str,
        )

    def show_options(self, options_data: list):
        if self.state != ConversationState.WAIT_OPTIONS:
            return

        self.current_options_data = options_data
        self.log(f"生成数据包: {len(options_data)} 条方案")
        self.options_generated.emit(options_data)

        self.blur_effect.setBlurRadius(15)

        for i, btn in enumerate(self.option_btns):
            if i < len(options_data):
                data = options_data[i]
                label_text = data.get("label", "选项")
                display_text = label_text[:10] + ".." if len(label_text) > 10 else label_text
                btn.setText(display_text)
                btn.setToolTip(f"预览：{data.get('content', '')[:50]}...")
                btn.show()
            else:
                btn.hide()

        self.options_overlay.show()

    def on_option_clicked(self, index):
        if self.state != ConversationState.WAIT_OPTIONS:
            return

        if index >= len(self.current_options_data):
            self.log("错误：选中的索引超出数据范围")
            return

        selected_data = self.current_options_data[index]
        label = selected_data.get("label", "Unknown")
        content = selected_data.get("content", "")

        self.log(f"用户选择了方向: [{label}]")
        self.options_overlay.hide()
        self.blur_effect.setBlurRadius(0)
        self.display_final_reply(content)

    def on_regenerate_clicked(self):
        self.log("用户请求重新生成选项...")
        self.options_overlay.hide()
        self.blur_effect.setBlurRadius(0)
        self.state = ConversationState.IDLE
        self.start_chat_flow(is_regenerate=True)

    def display_final_reply(self, reply):
        ai_name = self.config_cache.get("ai_name", "AI")
        self.append_chat(ai_name, reply, get_color("accent_strong"), align_right=True)

        self.history.append({"role": "user", "content": self.current_user_input})
        self.history.append({"role": "assistant", "content": reply})

        self.input_handler.update_ai_reply(reply)
        self.set_state(ConversationState.IDLE)
        self.reply_received.emit(reply)

    def handle_error(self, error_msg):
        QMessageBox.critical(self, "AI 错误", error_msg)
        self.handle_cancel()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        self.display_container = QWidget()
        self.stack_layout = QGridLayout(self.display_container)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.blur_effect = QGraphicsBlurEffect()
        self.chat_display.setGraphicsEffect(self.blur_effect)
        self.stack_layout.addWidget(self.chat_display, 0, 0)

        self.options_overlay = QWidget()
        self.options_overlay.hide()
        overlay_layout = QVBoxLayout(self.options_overlay)
        overlay_layout.addStretch(1)

        self.option_btns = []
        for i in range(3):
            btn = QPushButton(f"选项 {i + 1}")
            btn.setProperty("option", True)
            btn.setFixedHeight(60)
            btn.clicked.connect(lambda checked, idx=i: self.on_option_clicked(idx))
            overlay_layout.addWidget(btn)
            overlay_layout.addSpacing(10)
            self.option_btns.append(btn)

        aux_layout = QHBoxLayout()
        self.regen_btn = QPushButton("重新生成")
        self.regen_btn.setProperty("aux", True)
        self.regen_btn.setFixedHeight(45)
        self.regen_btn.clicked.connect(self.on_regenerate_clicked)

        self.back_btn = QPushButton("返回修改")
        self.back_btn.setProperty("aux", True)
        self.back_btn.setFixedHeight(45)
        self.back_btn.clicked.connect(self.handle_cancel)

        aux_layout.addWidget(self.regen_btn)
        aux_layout.addWidget(self.back_btn)
        overlay_layout.addLayout(aux_layout)
        overlay_layout.addStretch(1)
        self.stack_layout.addWidget(self.options_overlay, 0, 0)
        main_layout.addWidget(self.display_container)

        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setFixedHeight(40)
        self.input_field.setPlaceholderText("在此输入对话内容...")
        self.input_field.returnPressed.connect(self.on_send_or_cancel_clicked)

        self.send_btn = QPushButton("发送")
        self.send_btn.setProperty("send", True)
        self.send_btn.setFixedSize(80, 40)
        self.send_btn.clicked.connect(self.on_send_or_cancel_clicked)

        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_btn)
        main_layout.addLayout(input_layout)

    def on_external_message(self, text):
        if self.state == ConversationState.IDLE:
            self.input_field.setText(text)

    def run_preload(self):
        self.api.preload_done.connect(self._on_preload_done)
        self.api.error_occurred.connect(self._on_preload_error)
        self.api.debug_payload.connect(self.payload_captured.emit)
        self.api.preload(self._preset_directions_str)

    def _on_preload_done(self):
        self.log("连接预热成功，上下文环境已建立。")
        self._disconnect_preload()

    def _on_preload_error(self, msg):
        self.log(f"预热失败: {msg}")
        self._disconnect_preload()

    def _disconnect_preload(self):
        try:
            self.api.preload_done.disconnect(self._on_preload_done)
        except TypeError:
            pass
        try:
            self.api.error_occurred.disconnect(self._on_preload_error)
        except TypeError:
            pass
        try:
            self.api.debug_payload.disconnect()
        except TypeError:
            pass

    def append_chat(self, role, text, color, align_right=False):
        self._displayed_messages.append((role, text, color, align_right))
        self._render_message(role, text, color, align_right)

    def _render_message(self, role, text, color, align_right):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        block_format = QTextBlockFormat()
        block_format.setAlignment(
            Qt.AlignmentFlag.AlignRight if align_right else Qt.AlignmentFlag.AlignLeft
        )
        cursor.insertBlock(block_format)

        if align_right:
            bubble_bg = get_color("ai_bubble")
            bubble_text_color = get_color("ai_bubble_text")
        else:
            bubble_bg = get_color("user_bubble")
            bubble_text_color = get_color("text")

        safe_text = text.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")

        html = f"""
        <div style="margin: 5px;">
            <span style="font-weight:bold; color:{color}; font-size:12px;">{role}</span><br>
            <span style="
                background-color: {bubble_bg};
                color: {bubble_text_color};
                padding: 8px;
                border-radius: 8px;
                display: inline-block;
            ">{safe_text}</span>
        </div>
        """
        cursor.insertHtml(html)
        self.chat_display.ensureCursorVisible()

    def refresh_theme(self):
        """主题切换后重绘所有聊天记录。"""
        self.chat_display.clear()
        for role, text, color, align_right in self._displayed_messages:
            self._render_message(role, text, color, align_right)
