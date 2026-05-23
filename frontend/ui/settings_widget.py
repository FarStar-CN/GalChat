"""设置页面。"""

from PyQt6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit,
    QTextEdit, QPushButton, QMessageBox,
    QLabel, QComboBox, QCheckBox
)

from frontend.api_client import APIClient


class SettingsWidget(QWidget):
    def __init__(self, api_client: APIClient, log_callback, on_save_callback=None):
        super().__init__()
        self.api = api_client
        self.log = log_callback
        self.on_save_callback = on_save_callback
        self._original_api_key = ""
        self.init_ui()

        # 异步加载当前配置
        self.api.config_ready.connect(self._fill_ui)
        self.api.fetch_config()

    def _fill_ui(self, config: dict):
        masked_key = config.get("api_key", "")
        self.api_input.setText(masked_key)
        self._original_api_key = masked_key  # 记录脱敏后的值，用于判断用户是否修改
        self.url_input.setText(config.get("base_url", ""))
        self.model_combo.setCurrentText(config.get("model", ""))
        self.user_name_input.setText(config.get("user_name", ""))
        self.ai_name_input.setText(config.get("ai_name", ""))
        self.clipboard_check.setChecked(config.get("enable_clipboard_monitor", True))
        self.preset_checkbox.setChecked(config.get("use_preset_directions", True))
        self.sys_prompt_edit.setPlainText(config.get("system_prompt", ""))

        custom_models = config.get("custom_models", [])
        self.model_combo.clear()
        self.model_combo.addItems(custom_models)
        self.model_combo.setCurrentText(config.get("model", ""))

    def init_ui(self):
        layout = QFormLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        self.api_input = QLineEdit()
        self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("OpenAI API Key:", self.api_input)

        self.url_input = QLineEdit()
        layout.addRow("Base URL:", self.url_input)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        layout.addRow("聊天模型:", self.model_combo)

        layout.addRow(QLabel("<b>--- 个性化设置 ---</b>"))

        self.user_name_input = QLineEdit()
        layout.addRow("用户称呼 (左):", self.user_name_input)

        self.ai_name_input = QLineEdit()
        layout.addRow("AI 称呼 (右):", self.ai_name_input)

        self.clipboard_check = QCheckBox("启用剪贴板监听")
        layout.addRow("输入源:", self.clipboard_check)

        self.preset_checkbox = QCheckBox("启用预设回复库")
        layout.addRow("回复策略:", self.preset_checkbox)

        self.sys_prompt_edit = QTextEdit()
        self.sys_prompt_edit.setMaximumHeight(100)
        layout.addRow("系统人设:", self.sys_prompt_edit)

        self.save_btn = QPushButton("保存并应用")
        self.save_btn.setFixedHeight(40)
        self.save_btn.clicked.connect(self.save_settings)
        layout.addRow(self.save_btn)
        self.setLayout(layout)

    def save_settings(self):
        config = {
            "base_url": self.url_input.text().strip(),
            "model": self.model_combo.currentText().strip(),
            "system_prompt": self.sys_prompt_edit.toPlainText().strip(),
            "user_name": self.user_name_input.text().strip(),
            "ai_name": self.ai_name_input.text().strip(),
            "use_preset_directions": self.preset_checkbox.isChecked(),
            "enable_clipboard_monitor": self.clipboard_check.isChecked(),
        }
        # 只有当用户修改了 API Key 时才提交（避免将脱敏值写回覆盖真 key）
        new_key = self.api_input.text().strip()
        if new_key != self._original_api_key:
            config["api_key"] = new_key

        self.api.config_saved.connect(self._on_saved)
        self.api.error_occurred.connect(self._on_save_error)
        self.api.save_config(config)

    def _on_saved(self):
        self.api.config_saved.disconnect(self._on_saved)
        self.api.error_occurred.disconnect(self._on_save_error)
        QMessageBox.information(self, "成功", "设置已保存")
        if self.on_save_callback:
            self.on_save_callback()

    def _on_save_error(self, msg):
        self.api.config_saved.disconnect(self._on_saved)
        self.api.error_occurred.disconnect(self._on_save_error)
        QMessageBox.critical(self, "保存失败", msg)
