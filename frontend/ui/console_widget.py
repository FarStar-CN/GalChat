"""自定义终端：调试面板 + 直接 AI 对话。"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor, QTextCharFormat, QColor
from datetime import datetime

from frontend.api_client import APIClient


class TerminalTextEdit(QTextEdit):
    command_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.prompt = "ADMIN>>>"
        self.setStyleSheet("""
            QTextEdit {
                background-color: #0d0d0d;
                border: none;
                padding: 10px;
            }
        """)
        self.insert_prompt()

    def keyPressEvent(self, event):
        cursor = self.textCursor()

        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self.moveCursor(QTextCursor.MoveOperation.End)
            cursor = self.textCursor()
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            line_text = cursor.selectedText()
            cursor.clearSelection()

            if self.prompt in line_text:
                cmd = line_text.split(self.prompt)[-1].strip()
            else:
                cmd = line_text.strip()

            if cmd:
                self.command_signal.emit(cmd)

            self.append("")
            self.insert_prompt()
            return

        if event.key() == Qt.Key.Key_Backspace:
            self.moveCursor(QTextCursor.MoveOperation.End)
            cursor = self.textCursor()
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            text = cursor.selectedText()
            if text == self.prompt:
                return
            if cursor.positionInBlock() <= len(self.prompt):
                return

        self.moveCursor(QTextCursor.MoveOperation.End)
        self.reset_format()
        super().keyPressEvent(event)

    def reset_format(self):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#00ff00"))
        fmt.setFontFamilies(["Consolas", "Courier New", "monospace"])
        fmt.setFontPointSize(10)
        fmt.setFontWeight(QFont.Weight.Normal)
        self.setCurrentCharFormat(fmt)

    def insert_prompt(self):
        self.moveCursor(QTextCursor.MoveOperation.End)
        self.reset_format()
        self.insertPlainText(self.prompt)
        self.moveCursor(QTextCursor.MoveOperation.End)

    def append_html_log(self, html):
        self.moveCursor(QTextCursor.MoveOperation.End)
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
        last_line_text = cursor.selectedText()

        if last_line_text == self.prompt:
            cursor.removeSelectedText()
            cursor.deletePreviousChar()
        else:
            self.append("")

        self.moveCursor(QTextCursor.MoveOperation.End)
        self.textCursor().insertHtml(html)

        self.append("")
        self.insert_prompt()


class ConsoleWidget(QWidget):
    def __init__(self, api_client: APIClient):
        super().__init__()
        self.api = api_client
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_label = QLabel(">_ SYSTEM_TERMINAL ")
        title_label.setStyleSheet(
            "background-color: #1e1e1e; color: #666; padding: 5px 10px; font-family: Consolas; font-weight: bold; font-size: 10px;")
        layout.addWidget(title_label)

        self.terminal = TerminalTextEdit()
        self.terminal.command_signal.connect(self.execute_command)

        layout.addWidget(self.terminal)
        self.setLayout(layout)

    def execute_command(self, cmd):
        if cmd == "/clear" or cmd == "/cls":
            self.terminal.clear()
            self.terminal.insert_prompt()
            return

        self.api.finished_reply.connect(self.on_worker_reply)
        self.api.error_occurred.connect(self.on_worker_error)
        self.api.direct_chat(prompt=cmd, context=[])

    def on_worker_reply(self, reply):
        try:
            self.api.finished_reply.disconnect(self.on_worker_reply)
        except TypeError:
            pass
        try:
            self.api.error_occurred.disconnect(self.on_worker_error)
        except TypeError:
            pass
        time_str = datetime.now().strftime("%H:%M:%S")
        html = f"""
        <div style="color: #ffffff; margin-bottom: 5px;">
           <span style="color: #444;">[{time_str}]</span>
           <span style="color: #00ff00; font-weight: bold;">AI &gt;&gt;</span>
           <span> {reply}</span>
        </div>
        """
        self.terminal.append_html_log(html)

    def on_worker_error(self, err):
        try:
            self.api.finished_reply.disconnect(self.on_worker_reply)
        except TypeError:
            pass
        try:
            self.api.error_occurred.disconnect(self.on_worker_error)
        except TypeError:
            pass
        html = f"""
        <div style="color: #ff0000;">
        [ERROR]
           {err}
        </div>
        """
        self.terminal.append_html_log(html)

    def append_outgoing_payload(self, json_str):
        time_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        html = f"""
        <div style="border-top: 1px dashed #444; margin-top:5px;">
          <span style="color: #666;">[{time_str}]</span>
          <span style="color: #ffff00; font-weight: bold;">[PAYLOAD] &gt;&gt;</span><br>
          <span style="color: #808080; font-size: 11px;">
            {json_str}
          </span>
        </div>
        """
        self.terminal.append_html_log(html)

    def append_generated_options(self, options):
        time_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        display_lines = []
        for opt in options:
            if isinstance(opt, dict):
                label = opt.get("label", "?")
                content = opt.get("content", "")
                display_lines.append(f"[{label}] {content}...")
            else:
                display_lines.append(str(opt))

        options_html = "<br>".join(display_lines)

        html = f"""
        <div>
          <span style="color: #666;">[{time_str}]</span>
          <span style="color: #ff79c6; font-weight: bold;">[OPTIONS]</span><br>
          <span style="color: #ddd; margin-left: 10px;">
            {options_html}
          </span>
        </div>
        """

        self.terminal.append_html_log(html)

    def append_incoming_reply(self, content):
        time_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        safe_content = content.replace("<", "&lt;").replace(">", "&gt;")
        html = f"""
        <div>
          <span style="color: #666;">[{time_str}]</span>
          <span style="color: #00ffff; font-weight: bold;">[REPLY] &lt;&lt;</span>
          <span style="color: #aaa;">
            {safe_content}
          </span>
        </div>
        """
        self.terminal.append_html_log(html)
