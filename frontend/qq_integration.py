"""QQ-nt 集成：窗口定位、弹出选项、文本注入。"""

import time
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                              QPushButton, QLabel, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal

import Xlib.display
from Xlib.ext import xtest
import Xlib.X
import Xlib.XK


class QQWindowFinder:
    """通过 Xlib 查找 QQ-nt 窗口的位置和尺寸。"""

    @staticmethod
    def find_qq_windows() -> list[dict]:
        """返回所有 QQ 窗口信息列表，按面积降序排列。"""
        display = Xlib.display.Display()
        root = display.screen().root
        results = []

        def _recurse(window, depth=0):
            if depth > 30:
                return
            try:
                klass = window.get_wm_class()
                if klass and 'qq' in str(klass[0]).lower():
                    geom = window.get_geometry()
                    w, h = geom.width, geom.height
                    if w > 150 and h > 150:
                        name = window.get_wm_name() or ""
                        results.append({
                            "window": window,
                            "name": name,
                            "x": geom.x, "y": geom.y,
                            "width": w, "height": h,
                            "area": w * h,
                        })
                for child in window.query_tree().children:
                    _recurse(child, depth + 1)
            except Exception:
                pass

        _recurse(root)
        results.sort(key=lambda r: r["area"], reverse=True)
        return results

    @classmethod
    def get_main_window_geometry(cls) -> dict | None:
        """获取主 QQ 窗口几何信息（面积最大的窗口）。"""
        windows = cls.find_qq_windows()
        if not windows:
            return None
        win = windows[0]
        return {"x": win["x"], "y": win["y"],
                "width": win["width"], "height": win["height"]}


class QQTextInjector:
    """通过 XTest 将文本注入到 QQ-nt 输入框。"""

    # Ctrl+V 方式：将文本放入剪贴板后发送粘贴组合键
    @staticmethod
    def inject_via_paste(text: str):
        """将文本复制到剪贴板，然后向 QQ 窗口发送 Ctrl+V。"""
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

        display = Xlib.display.Display()
        # 找到 QQ 窗口并聚焦
        windows = QQWindowFinder.find_qq_windows()
        if not windows:
            return False

        try:
            win = windows[0]["window"]
            # 尝试 raise 和 set input focus
            win.configure(stack_mode=Xlib.X.Above)
            win.set_input_focus(Xlib.X.RevertToParent, Xlib.X.CurrentTime)
            display.sync()
        except Exception:
            pass

        time.sleep(0.1)

        # 获取 Control_L 和 V 的 keycode
        keysym_v = Xlib.XK.string_to_keysym("v")
        keycode_v = display.keysym_to_keycode(keysym_v)

        # 查找 Control 键的 modifier 的 keycode
        keysym_ctrl = Xlib.XK.string_to_keysym("Control_L")
        keycode_ctrl = display.keysym_to_keycode(keysym_ctrl)

        if keycode_ctrl == 0 or keycode_v == 0:
            return False

        # 按下 Ctrl
        xtest.fake_input(display, Xlib.X.KeyPress, keycode_ctrl)
        display.sync()
        # 按下 V
        xtest.fake_input(display, Xlib.X.KeyPress, keycode_v)
        display.sync()
        # 释放 V
        xtest.fake_input(display, Xlib.X.KeyRelease, keycode_v)
        display.sync()
        # 释放 Ctrl
        xtest.fake_input(display, Xlib.X.KeyRelease, keycode_ctrl)
        display.sync()

        return True


class QQPopupOverlay(QWidget):
    """在 QQ 窗口附近显示的浮动选项弹窗。"""

    option_selected = pyqtSignal(int)     # index
    regenerate_requested = pyqtSignal()
    cancel_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Popup
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_X11NetWmWindowTypeDialog, True)
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
        """显示选项数据，position_relative_to_qq_window 需先调用。"""
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
        """将弹窗定位到 QQ 主窗口中央。"""
        geom = QQWindowFinder.get_main_window_geometry()
        if geom is None:
            return
        popup_w = self.width()
        popup_h = self.height()
        # 居中在 QQ 窗口内
        x = geom["x"] + (geom["width"] - popup_w) // 2
        y = geom["y"] + (geom["height"] - popup_h) // 2
        self.move(x, y)

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
        self._options_data = []
        self._popup_closed_by_selection = False

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
        """当检测到 QQ 消息时调用（目前通过剪贴板监听触发）。

        该方法会调用 API 生成选项，结果显示在 QQ 旁弹窗中。
        """
        if not self._enabled:
            return

        self._current_prompt = text
        self._popup_closed_by_selection = False

        # 确保 QQ 窗口存在
        geom = QQWindowFinder.get_main_window_geometry()
        if geom is None:
            self.log("QQ 集成：未找到 QQ-nt 窗口，请先打开 QQ")
            return

        self.log(f"QQ 集成：收到消息，生成选项中...")

        # 连接 API 信号
        try:
            self.api.finished_options.connect(self._on_options_ready)
        except TypeError:
            pass
        try:
            self.api.error_occurred.connect(self._on_api_error)
        except TypeError:
            pass

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
        self._popup_closed_by_selection = True
        self.popup.hide()
        self.log(f"QQ 集成：用户选择了选项 [{self._options_data[index].get('label', '?')}]")

        # 注入文本到 QQ
        success = QQTextInjector.inject_via_paste(content)
        if success:
            self.log(f"QQ 集成：回复已注入到 QQ (Ctrl+V)")
            self.reply_injected.emit(content)
        else:
            self.log(f"QQ 集成：注入失败，回复内容已放入剪贴板")
            self.reply_injected.emit(content)

    def _on_regenerate(self):
        self.popup.hide()
        self.log("QQ 集成：重新生成选项...")
        self.handle_incoming_message(self._current_prompt)

    def _on_cancel(self):
        self.popup.hide()
        self._options_data = []
        self._disconnect_api()
        self.log("QQ 集成：用户取消了操作")
