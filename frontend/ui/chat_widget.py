"""主聊天页面。"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QTextEdit, QLineEdit,
                             QMessageBox, QGridLayout)
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
        self._conv_id = None
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
        self.options_btn.setVisible(is_idle)

        if is_idle:
            self.send_btn.setText("发送")
            self.send_btn.setProperty("send", True)
            self.send_btn.setProperty("cancel", False)
        else:
            self.send_btn.setText("取消")
            self.send_btn.setProperty("send", False)
            self.send_btn.setProperty("cancel", True)

        self.send_btn.style().unpolish(self.send_btn)
        self.send_btn.style().polish(self.send_btn)

    def on_send_clicked(self):
        """纯文本输入：追加到聊天显示和 history，不触发 AI。"""
        if self.state != ConversationState.IDLE:
            self.handle_cancel()
            return
        text = self.input_field.text().strip()
        if not text:
            return
        user_name = self.config_cache.get("user_name", "我")
        self.append_chat(user_name, text, align_right=False)
        self.history.append({"role": "user", "content": text})
        self.current_user_input = text
        if self._conv_id:
            self.api.save_message(self._conv_id, "user", text)
        self.input_field.clear()

    def on_options_clicked(self):
        """触发 AI 选项请求，以当前累积的 history 作为上下文。"""
        if self.state != ConversationState.IDLE:
            return
        text = self.input_field.text().strip()
        if text:
            self.on_send_clicked()
        if not self.history:
            return
        self.start_chat_flow()

    def handle_cancel(self):
        self._disconnect_options()
        self.log("用户取消了当前操作")
        self.options_overlay.hide()
        self.current_options_data = []
        self.input_field.setText(self.current_user_input)
        self.input_field.setFocus()
        self.set_state(ConversationState.IDLE)

    def _disconnect_options(self):
        try:
            self.api.finished_options.disconnect(self.show_options)
        except TypeError:
            pass
        try:
            self.api.error_occurred.disconnect(self.handle_error)
        except TypeError:
            pass
        try:
            self.api.debug_payload.disconnect(self._on_debug_payload)
        except TypeError:
            pass

    def _on_debug_payload(self, payload: str):
        self.payload_captured.emit(payload)

    def start_chat_flow(self):
        if self.state != ConversationState.IDLE:
            return

        # 取最后一条用户输入作为 prompt，之前的历史作为 context（避免重复）
        user_msgs = [m for m in self.history if m["role"] == "user"]
        if not user_msgs:
            return
        prompt = user_msgs[-1]["content"]
        context = self.history[:-1] if len(self.history) > 1 else []

        self.set_state(ConversationState.WAIT_OPTIONS)
        self.current_options_data = []

        self.api.finished_options.connect(self.show_options)
        self.api.error_occurred.connect(self.handle_error)
        self.api.debug_payload.connect(self._on_debug_payload)
        self.api.get_options(
            prompt=prompt,
            context=context,
            preset_str=self._preset_directions_str,
            conversation_id=self._conv_id,
        )

    def show_options(self, options_data: list):
        if self.state != ConversationState.WAIT_OPTIONS:
            return

        self.current_options_data = options_data
        self.log(f"生成数据包: {len(options_data)} 条方案")
        self.options_generated.emit(options_data)

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
        self.display_final_reply(content)

    def on_regenerate_clicked(self):
        self.log("用户请求重新生成选项...")
        self.options_overlay.hide()
        self._disconnect_options()
        self.state = ConversationState.IDLE
        self.start_chat_flow()

    def display_final_reply(self, reply):
        self._disconnect_options()

        ai_name = self.config_cache.get("ai_name", "AI")
        self.append_chat(ai_name, reply, align_right=True)

        self.history.append({"role": "assistant", "content": reply})

        if self._conv_id:
            self.api.save_message(self._conv_id, "assistant", reply)

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
        self.stack_layout.addWidget(self.chat_display, 0, 0)

        self.options_overlay = QWidget()
        self.options_overlay.hide()
        self.options_overlay.setStyleSheet(
            "background-color: rgba(0,0,0,0.35); border-radius: 10px;")
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
        self.input_field.returnPressed.connect(self.on_send_clicked)

        self.send_btn = QPushButton("发送")
        self.send_btn.setProperty("send", True)
        self.send_btn.setFixedSize(60, 40)
        self.send_btn.clicked.connect(self.on_send_clicked)

        self.options_btn = QPushButton("AI选项")
        self.options_btn.setProperty("option_trigger", True)
        self.options_btn.setFixedSize(70, 40)
        self.options_btn.clicked.connect(self.on_options_clicked)

        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_btn)
        input_layout.addWidget(self.options_btn)
        main_layout.addLayout(input_layout)

    def on_external_message(self, text):
        if self.state == ConversationState.IDLE:
            self.input_field.setText(text)

    def run_preload(self):
        self.api.preload_done.connect(self._on_preload_done)
        self.api.error_occurred.connect(self._on_preload_error)
        self.api.debug_payload.connect(self._on_preload_debug)
        self.api.preload(self._preset_directions_str)

    def _on_preload_done(self):
        self.log("连接预热成功，上下文环境已建立。")
        self._disconnect_preload()

    def _on_preload_error(self, msg):
        self.log(f"预热失败: {msg}")
        self._disconnect_preload()

    def _on_preload_debug(self, payload: str):
        self.payload_captured.emit(payload)

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
            self.api.debug_payload.disconnect(self._on_preload_debug)
        except TypeError:
            pass

    def append_chat(self, role, text, align_right=False):
        self._displayed_messages.append((role, text, align_right))
        self._render_message(role, text, align_right)

    def _render_message(self, role, text, align_right):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        block_format = QTextBlockFormat()
        block_format.setAlignment(
            Qt.AlignmentFlag.AlignRight if align_right else Qt.AlignmentFlag.AlignLeft
        )
        cursor.insertBlock(block_format)

        name_color = get_color("accent_strong") if align_right else get_color("accent")
        if align_right:
            bubble_bg = get_color("ai_bubble")
            bubble_text_color = get_color("ai_bubble_text")
        else:
            bubble_bg = get_color("user_bubble")
            bubble_text_color = get_color("text")

        safe_text = text.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")

        html = f"""
        <div style="margin: 5px;">
            <span style="font-weight:bold; color:{name_color}; font-size:12px;">{role}</span><br>
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

    def load_conversation(self, conv: dict):
        self._conv_id = conv["id"]
        self.history = []
        self._displayed_messages = []
        self.chat_display.clear()

        user_name = self.config_cache.get("user_name", "我")
        ai_name = self.config_cache.get("ai_name", "AI")

        for msg in conv.get("messages", []):
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                self.append_chat(user_name, content, align_right=False)
                self.history.append({"role": "user", "content": content})
            elif role == "assistant":
                self.append_chat(ai_name, content, align_right=True)
                self.history.append({"role": "assistant", "content": content})

    def clear_conversation(self):
        self._conv_id = None
        self.history = []
        self._displayed_messages = []
        self.chat_display.clear()

    def refresh_theme(self):
        """主题切换后重绘所有聊天记录，颜色从当前主题重新解析。"""
        self.chat_display.clear()
        for role, text, align_right in self._displayed_messages:
            self._render_message(role, text, align_right)
