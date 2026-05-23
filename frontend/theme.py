"""主题管理器：深色/浅色/跟随系统。"""

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# ── 配色常量 ──

DARK_COLORS = {
    "bg": "#1e1e2e",
    "bg_alt": "#181825",
    "surface": "#313244",
    "surface_hover": "#45475a",
    "overlay": "#11111b",
    "text": "#cdd6f4",
    "text_dim": "#6c7086",
    "accent": "#89b4fa",
    "accent_strong": "#1e66f5",
    "user_bubble": "#313244",
    "ai_bubble": "#1e66f5",
    "ai_bubble_text": "#ffffff",
    "input_bg": "#313244",
    "input_border": "#45475a",
    "terminal_bg": "#11111b",
    "terminal_text": "#a6e3a1",
    "log_bg": "#181825",
    "log_text": "#6c7086",
    "danger": "#f38ba8",
    "option_hover": "#5a8de0",
    "tooltip_bg": "#2d2d2d",
    "tooltip_text": "#f0f0f0",
}

LIGHT_COLORS = {
    "bg": "#eff1f5",
    "bg_alt": "#e6e9ef",
    "surface": "#dce0e8",
    "surface_hover": "#ccd0da",
    "overlay": "#f9f9fb",
    "text": "#4c4f69",
    "text_dim": "#9ca0b0",
    "accent": "#1e66f5",
    "accent_strong": "#8839ef",
    "user_bubble": "#e6e9ef",
    "ai_bubble": "#1e66f5",
    "ai_bubble_text": "#ffffff",
    "input_bg": "#dce0e8",
    "input_border": "#bcc0cc",
    "terminal_bg": "#f4f4f4",
    "terminal_text": "#40a02b",
    "log_bg": "#e6e9ef",
    "log_text": "#9ca0b0",
    "danger": "#d20f39",
    "option_hover": "#6c3fd4",
    "tooltip_bg": "#f0f2f6",
    "tooltip_text": "#ffffff",
}

_current_mode = "dark"
_colors = DARK_COLORS


def detect_system_theme():
    """检测系统主题，返回 'dark' 或 'light'。"""
    try:
        scheme = QApplication.styleHints().colorScheme()
        return "dark" if scheme == Qt.ColorScheme.Dark else "light"
    except AttributeError:
        return "dark"


def apply_theme(app: QApplication, theme_mode: str = "auto"):
    """将主题应用到整个 QApplication。"""
    global _current_mode, _colors

    if theme_mode == "auto":
        detected = detect_system_theme()
    else:
        detected = theme_mode

    _current_mode = detected
    _colors = DARK_COLORS if detected == "dark" else LIGHT_COLORS

    app.setStyleSheet(_build_qss(_colors))


def get_color(key: str) -> str:
    """获取当前主题配色中的颜色值（供 Widget 动态样式使用）。"""
    return _colors.get(key, "#000000")


def current_mode() -> str:
    return _current_mode


def _build_qss(c):
    """构建完整的全局 Qt 样式表。"""
    return f"""
    /* ── 全局 ── */
    QMainWindow, QWidget {{
        background-color: {c["bg"]};
        color: {c["text"]};
        font-size: 14px;
    }}

    QLabel {{
        background: transparent;
    }}

    /* ── 侧边栏 ── */
    QFrame[sidebar="true"] {{
        background-color: {c["bg_alt"]};
    }}

    /* ── 导航按钮 ── */
    QPushButton[nav="true"] {{
        background-color: transparent;
        color: {c["text_dim"]};
        border: none;
        font-size: 14px;
        border-radius: 5px;
        text-align: left;
        padding-left: 15px;
    }}
    QPushButton[nav="true"]:hover {{
        background-color: {c["surface_hover"]};
        color: {c["text"]};
    }}
    QPushButton[nav="true"]:checked {{
        background-color: {c["accent_strong"]};
        color: white;
        border-left: 4px solid {c["accent"]};
    }}

    /* ── 发送按钮 ── */
    QPushButton[send="true"] {{
        background-color: {c["accent_strong"]};
        color: white;
        border-radius: 5px;
        font-size: 14px;
    }}
    QPushButton[send="true"]:hover {{
        background-color: {c["accent"]};
    }}

    /* ── 取消按钮 ── */
    QPushButton[cancel="true"] {{
        background-color: {c["danger"]};
        color: white;
        border-radius: 5px;
        font-size: 14px;
    }}

    /* ── 选项覆盖层按钮 ── */
    QPushButton[option="true"] {{
        background-color: {c["accent_strong"]};
        color: white;
        border-radius: 8px;
        font-size: 16px;
        font-weight: bold;
        border: 2px solid {c["accent"]};
    }}
    QPushButton[option="true"]:hover {{
        background-color: {c["option_hover"]};
        color: white;
        border: 2px solid white;
    }}

    /* ── 辅助按钮（重新生成/返回修改） ── */
    QPushButton[aux="true"] {{
        background-color: {c["surface"]};
        color: {c["text"]};
        border-radius: 8px;
        font-weight: bold;
        font-size: 14px;
    }}
    QPushButton[aux="true"]:hover {{
        background-color: {c["surface_hover"]};
    }}

    /* ── 保存按钮 ── */
    QPushButton[save="true"] {{
        background-color: {c["accent_strong"]};
        color: white;
        border-radius: 5px;
        font-size: 14px;
        font-weight: bold;
    }}

    /* ── 输入框 ── */
    QLineEdit {{
        background-color: {c["input_bg"]};
        color: {c["text"]};
        border: 1px solid {c["input_border"]};
        border-radius: 5px;
        padding: 5px 10px;
    }}

    /* ── 文本编辑 ── */
    QTextEdit {{
        background-color: {c["bg"]};
        color: {c["text"]};
        border: 1px solid {c["input_border"]};
        border-radius: 5px;
        padding: 10px;
    }}

    /* ── 下拉框 ── */
    QComboBox {{
        background-color: {c["input_bg"]};
        color: {c["text"]};
        border: 1px solid {c["input_border"]};
        border-radius: 5px;
        padding: 5px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {c["surface"]};
        color: {c["text"]};
        selection-background-color: {c["accent_strong"]};
    }}

    /* ── 复选框 ── */
    QCheckBox {{
        color: {c["text"]};
    }}

    /* ── 工具提示 ── */
    QToolTip {{
        background-color: {c["tooltip_bg"]};
        color: {c["tooltip_text"]};
        border: 1px solid {c["accent"]};
        border-radius: 6px;
        padding: 8px 12px;
        font-size: 13px;
    }}

    /* ── 表单布局 ── */
    QFormLayout {{
        background-color: transparent;
    }}

    /* ── 滚动条 ── */
    QScrollBar:vertical {{
        background: {c["bg_alt"]};
        width: 8px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: {c["surface_hover"]};
        border-radius: 4px;
        min-height: 20px;
    }}
    """
