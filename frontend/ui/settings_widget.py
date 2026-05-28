"""设置页面。"""

from PyQt6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit,
    QTextEdit, QPushButton, QMessageBox,
    QLabel, QComboBox, QCheckBox
)

from frontend.api_client import APIClient


def _safe_int(s: str, default: int) -> int:
    try:
        return int(s)
    except ValueError:
        return default


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

        theme = config.get("theme", "auto")
        theme_map = {"auto": "跟随系统", "dark": "深色", "light": "浅色"}
        self.theme_combo.setCurrentText(theme_map.get(theme, "跟随系统"))

        # QQ 监听设置
        qq_enabled = config.get("enable_qq_monitor", False)
        self.qq_monitor_check.setChecked(qq_enabled)
        self.qq_host_input.setText(config.get("napcat_ws_host", "127.0.0.1"))
        self.qq_port_input.setText(str(config.get("napcat_ws_port", 3001)))
        self.qq_token_input.setText(config.get("napcat_access_token", ""))
        self._toggle_qq_fields()

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

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["跟随系统", "深色", "浅色"])
        layout.addRow("主题:", self.theme_combo)

        layout.addRow(QLabel("<b>--- QQ 消息监听 ---</b>"))

        self.qq_monitor_check = QCheckBox("启用 QQ 消息监听（需 NapCatQQ 运行）")
        self.qq_monitor_check.toggled.connect(self._toggle_qq_fields)
        layout.addRow("QQ 监听:", self.qq_monitor_check)

        self.qq_host_input = QLineEdit()
        self.qq_host_input.setPlaceholderText("127.0.0.1")
        layout.addRow("WS 地址:", self.qq_host_input)

        self.qq_port_input = QLineEdit()
        self.qq_port_input.setPlaceholderText("3001")
        layout.addRow("WS 端口:", self.qq_port_input)

        self.qq_token_input = QLineEdit()
        self.qq_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.qq_token_input.setPlaceholderText("NapCat access token")
        layout.addRow("Access Token:", self.qq_token_input)

        self.sys_prompt_edit = QTextEdit()
        self.sys_prompt_edit.setMaximumHeight(100)
        layout.addRow("系统人设:", self.sys_prompt_edit)

        self.save_btn = QPushButton("保存并应用")
        self.save_btn.setProperty("save", True)
        self.save_btn.setFixedHeight(40)
        self.save_btn.clicked.connect(self.save_settings)
        layout.addRow(self.save_btn)
        self.setLayout(layout)

    def _toggle_qq_fields(self):
        enabled = self.qq_monitor_check.isChecked()
        self.qq_host_input.setEnabled(enabled)
        self.qq_port_input.setEnabled(enabled)
        self.qq_token_input.setEnabled(enabled)

    def save_settings(self):
        config = {
            "base_url": self.url_input.text().strip(),
            "model": self.model_combo.currentText().strip(),
            "system_prompt": self.sys_prompt_edit.toPlainText().strip(),
            "user_name": self.user_name_input.text().strip(),
            "ai_name": self.ai_name_input.text().strip(),
            "use_preset_directions": self.preset_checkbox.isChecked(),
            "enable_clipboard_monitor": self.clipboard_check.isChecked(),
            "theme": {"跟随系统": "auto", "深色": "dark", "浅色": "light"}.get(
                self.theme_combo.currentText(), "auto"),
            "custom_models": [self.model_combo.itemText(i)
                              for i in range(self.model_combo.count())],
            "enable_qq_monitor": self.qq_monitor_check.isChecked(),
            "napcat_ws_host": self.qq_host_input.text().strip(),
            "napcat_ws_port": _safe_int(self.qq_port_input.text().strip(), 3001),
            "napcat_access_token": self.qq_token_input.text().strip(),
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
