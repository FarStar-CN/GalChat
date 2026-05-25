"""QQ-nt 集成：窗口定位、弹出选项、文本注入（跨平台）。"""

import sys
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                              QPushButton, QLabel, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal

# 平台后端选择
if sys.platform == "win32":
    from frontend._qq_platform_win32 import (
        find_qq_windows, get_main_window_geometry, inject_text,
    )
elif sys.platform == "linux":
    from frontend._qq_platform_linux import (
        find_qq_windows, get_main_window_geometry, inject_text,
    )
else:
    import warnings
    warnings.warn(f"QQ-nt 集成不支持当前平台 ({sys.platform})，功能将不可用")

    def find_qq_windows() -> list:
        return []

    def get_main_window_geometry() -> dict | None:
        return None

    def inject_text(text: str) -> bool:
        return False


class QQWindowFinder:
    """跨平台 QQ 窗口查找器（委托给平台后端）。"""

    @staticmethod
    def find_qq_windows() -> list[dict]:
        return find_qq_windows()

    @classmethod
    def get_main_window_geometry(cls) -> dict | None:
        return get_main_window_geometry()


class QQTextInjector:
    """跨平台文本注入器（委托给平台后端）。"""

    @staticmethod
    def inject_via_paste(text: str) -> bool:
        return inject_text(text)


class QQPopupOverlay(QWidget):
    """在 QQ 窗口附近显示的浮动选项弹窗。"""

    option_selected = pyqtSignal(int)
    regenerate_requested = pyqtSignal()
    cancel_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        flags = (Qt.WindowType.FramelessWindowHint |
                 Qt.WindowType.WindowStaysOnTopHint |
                 Qt.WindowType.Popup)
        self.setWindowFlags(flags)
        # Windows: 提示无任务栏图标；Linux/X11: 标记为 dialog 类型
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        if sys.platform == "linux":
            self.setAttribute(Qt.WidgetAttribute.WA_X11NetWmWindowTypeDialog, True)
        elif sys.platform == "win32":
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self._options_data = []
        self._option_btns = []

        self._init_ui()
        self.hide()

    def _init_ui(self):
        self.setFixedSize(380, 360)
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e2e;
                border: 2px solid #89b4fa;
                border-radius: 12px;
            }
            QLabel#title {
                color: #cdd6f4;
                font-size: 14px;
                font-weight: bold;
                padding: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 15)
        layout.setSpacing(8)

        title = QLabel("回复选项")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        for i in range(3):
            btn = QPushButton(f"选项 {i + 1}")
            btn.setFixedHeight(55)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e66f5;
                    color: white;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: bold;
                    border: 2px solid #89b4fa;
                }
                QPushButton:hover {
                    background-color: #5a8de0;
                    border: 2px solid white;
                }
            """)
            btn.clicked.connect(lambda checked, idx=i: self.option_selected.emit(idx))
            layout.addWidget(btn)
            self._option_btns.append(btn)

        aux_layout = QHBoxLayout()
        regen_btn = QPushButton("重新生成")
        regen_btn.setFixedHeight(40)
        regen_btn.setStyleSheet("""
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #45475a; }
        """)
        regen_btn.clicked.connect(self.regenerate_requested.emit)

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedHeight(40)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f38ba8;
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #e06c88; }
        """)
        cancel_btn.clicked.connect(self.cancel_requested.emit)

        aux_layout.addWidget(regen_btn)
        aux_layout.addWidget(cancel_btn)
        layout.addLayout(aux_layout)

    def show_options(self, options_data: list):
        self._options_data = options_data
        for i, btn in enumerate(self._option_btns):
            if i < len(options_data):
                data = options_data[i]
                label_text = data.get("label", "选项")
                content_preview = data.get("content", "")[:30]
                btn.setText(f"[{label_text}] {content_preview}...")
                btn.setToolTip(data.get("content", ""))
                btn.show()
            else:
                btn.hide()
        self.show()
        self.raise_()

    def position_near_qq(self):
        geom = get_main_window_geometry()
        if geom is None:
            return
        popup_w = self.width()
        popup_h = self.height()
        x = geom["x"] + (geom["width"] - popup_w) // 2
        y = geom["y"] + (geom["height"] - popup_h) // 2
        self.move(max(0, x), max(0, y))

    def get_selected_content(self, index: int) -> str:
        if 0 <= index < len(self._options_data):
            return self._options_data[index].get("content", "")
        return ""


class QQIntegration(QWidget):
    """QQ 集成控制器：串联窗口检测、弹窗和文本注入。"""

    reply_injected = pyqtSignal(str)

    def __init__(self, api_client, log_callback):
        super().__init__()
        self.api = api_client
        self.log = log_callback
        self._enabled = False
        self._current_prompt = ""
        self._preset_directions_str = ""
        self._options_data = []

        self.popup = QQPopupOverlay()
        self.popup.option_selected.connect(self._on_option_selected)
        self.popup.regenerate_requested.connect(self._on_regenerate)
        self.popup.cancel_requested.connect(self._on_cancel)
        self.hide()

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
        state = "开启" if value else "关闭"
        self.log(f"QQ-nt 集成已{state}")

    def handle_incoming_message(self, text: str, preset_directions_str: str = ""):
        if not self._enabled:
            return

        self._current_prompt = text
        self._preset_directions_str = preset_directions_str

        geom = get_main_window_geometry()
        if geom is None:
            self.log("QQ 集成：未找到 QQ-nt 窗口，请先打开 QQ")
            return

        self.log(f"QQ 集成：收到消息，生成选项中...")

        # 先断开旧连接再重连，防止重复连接导致首次响应后全部被移除
        self._disconnect_api()
        self.api.finished_options.connect(self._on_options_ready)
        self.api.error_occurred.connect(self._on_api_error)

        self.api.get_options(
            prompt=text,
            context=[],
            preset_str=preset_directions_str,
        )

    def _on_options_ready(self, options_data: list):
        self._disconnect_api()
        self._options_data = options_data
        self.popup.position_near_qq()
        self.popup.show_options(options_data)

    def _on_api_error(self, error_msg: str):
        self._disconnect_api()
        self.log(f"QQ 集成 API 错误: {error_msg}")

    def _disconnect_api(self):
        try:
            self.api.finished_options.disconnect(self._on_options_ready)
        except TypeError:
            pass
        try:
            self.api.error_occurred.disconnect(self._on_api_error)
        except TypeError:
            pass

    def _on_option_selected(self, index: int):
        if index >= len(self._options_data):
            return
        content = self.popup.get_selected_content(index)
        self.popup.hide()
        label = self._options_data[index].get("label", "?")
        self.log(f"QQ 集成：用户选择了选项 [{label}]")

        # 先更新 InputHandler 防循环标记，再操作剪贴板
        self.reply_injected.emit(content)
        success = QQTextInjector.inject_via_paste(content)
        if success:
            self.log("QQ 集成：回复已注入到 QQ (Ctrl+V)")
        else:
            self.log("QQ 集成：注入失败，回复内容已放入剪贴板")

    def _on_regenerate(self):
        self.popup.hide()
        self.log("QQ 集成：重新生成选项...")
        self.handle_incoming_message(self._current_prompt, self._preset_directions_str)

    def _on_cancel(self):
        self.popup.hide()
        self._options_data = []
        self._disconnect_api()
        self.log("QQ 集成：用户取消了操作")
