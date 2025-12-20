# ----------------------------
# 设置界面
# ----------------------------
from PyQt6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit,
    QTextEdit, QPushButton, QMessageBox,
    QLabel, QComboBox, QCheckBox
)

class SettingsWidget(QWidget):
    def __init__(self, config_manager, log_callback, on_save_callback=None):
        super().__init__()
        self.cfg = config_manager
        self.log = log_callback
        self.on_save_callback = on_save_callback
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        self.api_input = QLineEdit(self.cfg.get("api_key"))
        self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("OpenAI API Key:", self.api_input)

        self.url_input = QLineEdit(self.cfg.get("base_url"))
        layout.addRow("Base URL:", self.url_input)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItems(self.cfg.get("custom_models"))
        self.model_combo.setCurrentText(self.cfg.get("model"))
        layout.addRow("聊天模型:", self.model_combo)

        layout.addRow(QLabel("<b>--- 个性化设置 ---</b>"))

        self.user_name_input = QLineEdit(self.cfg.get("user_name"))
        layout.addRow("用户称呼 (左):", self.user_name_input)

        self.ai_name_input = QLineEdit(self.cfg.get("ai_name"))
        layout.addRow("AI 称呼 (右):", self.ai_name_input)

        self.clipboard_check = QCheckBox("启用剪贴板监听")
        self.clipboard_check.setChecked(self.cfg.get("enable_clipboard_monitor"))
        layout.addRow("输入源:", self.clipboard_check)

        self.preset_checkbox = QCheckBox("启用预设回复库")
        self.preset_checkbox.setChecked(self.cfg.get("use_preset_directions"))
        layout.addRow("回复策略:", self.preset_checkbox)

        self.sys_prompt_edit = QTextEdit(self.cfg.get("system_prompt"))
        self.sys_prompt_edit.setMaximumHeight(100)
        layout.addRow("系统人设:", self.sys_prompt_edit)

        self.save_btn = QPushButton("保存并应用")
        self.save_btn.setFixedHeight(40)
        self.save_btn.clicked.connect(self.save_settings)
        layout.addRow(self.save_btn)
        self.setLayout(layout)

    def save_settings(self):
        self.cfg.set("api_key", self.api_input.text().strip())
        self.cfg.set("base_url", self.url_input.text().strip())
        self.cfg.set("model", self.model_combo.currentText().strip())
        self.cfg.set("system_prompt", self.sys_prompt_edit.toPlainText().strip())
        self.cfg.set("user_name", self.user_name_input.text().strip())
        self.cfg.set("ai_name", self.ai_name_input.text().strip())
        self.cfg.set("use_preset_directions", self.preset_checkbox.isChecked())
        self.cfg.set("enable_clipboard_monitor", self.clipboard_check.isChecked())

        QMessageBox.information(self, "成功", "设置已保存")
        if self.on_save_callback:
            self.on_save_callback()