# ----------------------------
# 主聊天窗口
# ----------------------------
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QTextEdit, QLineEdit,
                             QMessageBox, QGridLayout, QGraphicsBlurEffect)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextCursor, QTextBlockFormat
from enum import Enum, auto

# --- 模块导入 ---
from core.input_handler import InputHandler
from core.direction_manager import DirectionManager
from core.ai_engine import AIWorker
from core.prompt_builder import PromptMode


class ConversationState(Enum):
    IDLE = auto()
    WAIT_OPTIONS = auto()
    # WAIT_REPLY 已移除，因为改为单阶段生成，点击即回复


class ChatWidget(QWidget):
    # 信号定义
    payload_captured = pyqtSignal(str)
    reply_received = pyqtSignal(str)
    options_generated = pyqtSignal(list)

    def __init__(self, config_manager, log_callback):
        super().__init__()
        self.cfg = config_manager
        self.log = log_callback
        self.history = []
        self.current_user_input = ""

        # [新增] 缓存当前生成的选项数据 [{"label":Str, "content":Str}, ...]
        self.current_options_data = []

        self.state = ConversationState.IDLE
        self.worker = None

        self.input_handler = InputHandler()
        self.input_handler.new_message_received.connect(self.on_external_message)
        self.dir_manager = DirectionManager()

        self.init_ui()
        self.update_ui_by_state()

    def set_state(self, new_state: ConversationState):
        self.log(f"[状态切换] {self.state.name} -> {new_state.name}")
        self.state = new_state
        self.update_ui_by_state()

    def update_ui_by_state(self):
        """根据状态切换按钮功能和样式"""
        is_idle = (self.state == ConversationState.IDLE)

        # 输入框控制
        self.input_field.setEnabled(is_idle)

        # 发送/取消按钮切换
        if is_idle:
            self.send_btn.setText("发送")
            self.send_btn.setStyleSheet("background-color: #0984e3; color: white; border-radius: 5px;")
            self.input_field.setFocus()
        else:
            self.send_btn.setText("取消")
            self.send_btn.setStyleSheet("background-color: #d63031; color: white; border-radius: 5px;")

    def on_send_or_cancel_clicked(self):
        """发送按钮的逻辑分发"""
        if self.state == ConversationState.IDLE:
            self.start_chat_flow()
        else:
            self.handle_cancel()

    def handle_cancel(self):
        """取消逻辑：中断线程监听并重置 UI"""
        if self.worker:
            try:
                # 断开所有信号，防止线程完成后继续触发 UI 逻辑
                self.worker.finished_options.disconnect()
                self.worker.finished_reply.disconnect()
                self.worker.error_occurred.disconnect()
            except:
                pass

        self.log("用户取消了当前操作")
        self.options_overlay.hide()
        self.blur_effect.setBlurRadius(0)
        self.current_options_data = []  # 清空缓存
        self.set_state(ConversationState.IDLE)

    def start_chat_flow(self, is_regenerate=False):
        """开始流程。is_regenerate 为 True 时不重复打印用户消息"""
        if self.state != ConversationState.IDLE and not is_regenerate:
            return

        text = self.input_field.text().strip() if not is_regenerate else self.current_user_input
        if not text: return

        self.blur_effect.setBlurRadius(0)
        self.set_state(ConversationState.WAIT_OPTIONS)

        # 记录用户输入并上屏
        if not is_regenerate:
            self.current_user_input = text
            user_name = self.cfg.get("user_name")
            self.append_chat(user_name, text, "#333333", align_right=False)
            self.input_field.clear()

        # 清空旧数据
        self.current_options_data = []

        preset_str = self.dir_manager.get_all_directions_string()

        # 启动 AI Worker
        self.worker = AIWorker(
            self.cfg,
            mode=PromptMode.GENERATE_OPTIONS.value,
            prompt=text,
            context=self.history,
            preset_directions_str=preset_str
        )
        self.worker.finished_options.connect(self.show_options)
        self.worker.error_occurred.connect(self.handle_error)
        self.worker.log_message.connect(self.log)
        self.worker.debug_payload.connect(self.payload_captured.emit)
        self.worker.start()

    def show_options(self, options_data: list):
        """
        [修改] 接收结构化数据 [{"label":Str, "content":Str}, ...]
        """
        if self.state != ConversationState.WAIT_OPTIONS: return

        self.current_options_data = options_data
        self.log(f"生成数据包: {len(options_data)} 条方案")

        # 提取 Label 用于 Console 显示和 UI 按钮
        self.options_generated.emit(options_data)  # 发送给 Console

        self.blur_effect.setBlurRadius(15)

        for i, btn in enumerate(self.option_btns):
            if i < len(options_data):
                data = options_data[i]
                label_text = data.get("label", "选项")

                # 设置按钮文本（截断过长文本）
                display_text = label_text[:10] + ".." if len(label_text) > 10 else label_text
                btn.setText(display_text)

                # 设置鼠标悬停提示显示完整回复预览
                btn.setToolTip(f"预览：{data.get('content', '')[:50]}...")
                btn.show()
            else:
                btn.hide()

        self.options_overlay.show()

    def on_option_clicked(self, index):
        """
        [修改] 用户点击后直接上屏，无需再次请求 AI
        """
        if self.state != ConversationState.WAIT_OPTIONS: return

        # 1. 安全检查
        if index >= len(self.current_options_data):
            self.log("错误：选中的索引超出数据范围")
            return

        selected_data = self.current_options_data[index]
        label = selected_data.get("label", "Unknown")
        content = selected_data.get("content", "")

        self.log(f"用户选择了方向: [{label}]")

        # 2. 隐藏 UI 并恢复清晰度
        self.options_overlay.hide()
        self.blur_effect.setBlurRadius(0)

        # 3. 直接上屏回复 (Skip Stage 2)
        self.display_final_reply(content)

    def on_regenerate_clicked(self):
        """重新生成选项逻辑"""
        self.log("用户请求重新生成选项...")
        self.options_overlay.hide()
        self.blur_effect.setBlurRadius(0)

        # 必须先回到 IDLE 状态，start_chat_flow 才会执行
        self.state = ConversationState.IDLE
        self.start_chat_flow(is_regenerate=True)

    def display_final_reply(self, reply):
        """上屏最终回复"""
        ai_name = self.cfg.get("ai_name")
        self.append_chat(ai_name, reply, "#0984e3", align_right=True)

        # 更新历史
        self.history.append({"role": "user", "content": self.current_user_input})
        self.history.append({"role": "assistant", "content": reply})

        # 输出到剪贴板
        self.input_handler.update_ai_reply(reply)

        # 状态回归
        self.set_state(ConversationState.IDLE)
        self.reply_received.emit(reply)

    def handle_error(self, error_msg):
        QMessageBox.critical(self, "AI 错误", error_msg)
        self.handle_cancel()

    # --- UI 构建逻辑 ---
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        self.display_container = QWidget()
        self.stack_layout = QGridLayout(self.display_container)

        # 聊天显示
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
        QTextEdit {
            background-color: #f8f9fa;
            color: #2d3436;
            border-radius: 10px;
            padding: 15px;
            font-size: 15px;
        }
        """)
        self.blur_effect = QGraphicsBlurEffect()
        self.chat_display.setGraphicsEffect(self.blur_effect)
        self.stack_layout.addWidget(self.chat_display, 0, 0)

        # 选项覆盖层
        self.options_overlay = QWidget()
        self.options_overlay.hide()
        overlay_layout = QVBoxLayout(self.options_overlay)
        overlay_layout.addStretch(1)

        # 3个主选项按钮
        self.option_btns = []
        for i in range(3):
            btn = QPushButton(f"选项 {i + 1}")
            btn.setFixedHeight(60)
            btn.clicked.connect(lambda checked, idx=i: self.on_option_clicked(idx))
            btn.setStyleSheet("""
                QPushButton { 
                    background-color: rgba(45, 52, 54, 0.95); 
                    color: white; 
                    border-radius: 8px; 
                    font-size: 16px; 
                    font-weight: bold; 
                    border: 1px solid #636e72;
                }
                QPushButton:hover { 
                    background-color: rgba(9, 132, 227, 0.95); 
                    border: 1px solid #74b9ff;
                }
            """)
            overlay_layout.addWidget(btn)
            overlay_layout.addSpacing(10)
            self.option_btns.append(btn)

        # 辅助操作栏
        aux_layout = QHBoxLayout()
        self.regen_btn = QPushButton("重新生成")
        self.regen_btn.setFixedHeight(45)
        self.regen_btn.setStyleSheet(
            "background-color: #2d3436; color: #fab1a0; border-radius: 8px; font-weight: bold;")
        self.regen_btn.clicked.connect(self.on_regenerate_clicked)

        self.back_btn = QPushButton("返回修改")
        self.back_btn.setFixedHeight(45)
        self.back_btn.setStyleSheet("background-color: #2d3436; color: #dfe6e9; border-radius: 8px; font-weight: bold;")
        self.back_btn.clicked.connect(self.handle_cancel)

        aux_layout.addWidget(self.regen_btn)
        aux_layout.addWidget(self.back_btn)
        overlay_layout.addLayout(aux_layout)

        overlay_layout.addStretch(1)
        self.stack_layout.addWidget(self.options_overlay, 0, 0)
        main_layout.addWidget(self.display_container)

        # 底部输入
        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setFixedHeight(40)
        self.input_field.setPlaceholderText("在此输入对话内容...")
        self.input_field.returnPressed.connect(self.on_send_or_cancel_clicked)

        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedSize(80, 40)
        self.send_btn.clicked.connect(self.on_send_or_cancel_clicked)

        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_btn)
        main_layout.addLayout(input_layout)

    def on_external_message(self, text):
        if self.state == ConversationState.IDLE:
            self.input_field.setText(text)

    def run_preload(self):
        preset_str = self.dir_manager.get_all_directions_string()
        self.preload_worker = AIWorker(self.cfg, mode=PromptMode.PRELOAD.value, preset_directions_str=preset_str)
        self.preload_worker.log_message.connect(self.log)
        self.preload_worker.debug_payload.connect(self.payload_captured.emit)
        self.preload_worker.start()

    def append_chat(self, role, text, color, align_right=False):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        block_format = QTextBlockFormat()
        block_format.setAlignment(
            Qt.AlignmentFlag.AlignRight if align_right else Qt.AlignmentFlag.AlignLeft
        )
        cursor.insertBlock(block_format)

        bubble_bg = "#dfefff" if align_right else "#ffffff"
        bubble_text_color = "#2d3436"

        # 简单的 HTML 转义防止显示异常
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