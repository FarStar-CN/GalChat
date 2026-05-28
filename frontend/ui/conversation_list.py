"""对话列表侧边栏。"""

from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QScrollArea, QWidget, QMenu, QInputDialog,
                             QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from frontend.theme import get_color


class ConversationList(QFrame):
    """对话列表面板：左侧会话列表，支持新建/切换/重命名/删除。"""

    conversation_selected = pyqtSignal(str)
    new_conversation_requested = pyqtSignal()
    rename_requested = pyqtSignal(str, str)
    delete_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        self.setProperty("conv_list", True)
        self._items = {}
        self._active_id = None
        self._data = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(10, 10, 10, 5)
        title_lbl = QLabel("会话列表")
        title_lbl.setProperty("conv_header", True)
        title_font = QFont()
        title_font.setBold(True)
        title_lbl.setFont(title_font)
        header.addWidget(title_lbl)

        self.new_btn = QPushButton("+")
        self.new_btn.setFixedSize(30, 30)
        self.new_btn.setProperty("conv_new", True)
        self.new_btn.setToolTip("新建对话")
        self.new_btn.clicked.connect(self.new_conversation_requested.emit)
        header.addWidget(self.new_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(header)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setProperty("conv_scroll", True)
        self.scroll_widget = QWidget()
        self.items_layout = QVBoxLayout(self.scroll_widget)
        self.items_layout.setSpacing(2)
        self.items_layout.setContentsMargins(5, 5, 5, 5)
        self.items_layout.addStretch()
        self.scroll_area.setWidget(self.scroll_widget)
        layout.addWidget(self.scroll_area)

        self._empty_label = QLabel("暂无对话\n点击 + 新建")
        self._empty_label.setProperty("conv_empty", True)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        layout.addWidget(self._empty_label)

    def set_conversations(self, data: list[dict]):
        self._data = data
        for w in list(self._items.values()):
            self.items_layout.removeWidget(w)
            w.deleteLater()
        self._items.clear()

        has_items = len(data) > 0
        self._empty_label.setVisible(not has_items)
        self.scroll_area.setVisible(has_items)

        for conv in data:
            self._add_item(conv)

    @staticmethod
    def _format_item_text(title: str, source: str, last_msg: str) -> str:
        preview = last_msg or ""
        if len(preview) > 20:
            preview = preview[:20] + "..."
        return f"{title}\n<span style='font-size:11px; color:{get_color('text_dim')};'>{preview}</span>"

    def _add_item(self, conv: dict):
        btn = QPushButton()
        btn.setProperty("conv_item", True)
        btn.setMinimumHeight(55)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        title = conv.get("title", "未命名")
        source = conv.get("source", "manual")
        last_msg = conv.get("last_message") or ""
        btn.setText(self._format_item_text(title, source, last_msg))
        btn.setToolTip(title)

        conv_id = conv["id"]
        btn.clicked.connect(lambda checked, cid=conv_id: self.select_conversation(cid))
        btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        btn.customContextMenuRequested.connect(lambda pos, cid=conv_id: self._show_context_menu(pos, cid))

        self.items_layout.insertWidget(self.items_layout.count() - 1, btn)
        self._items[conv_id] = btn

    def select_conversation(self, conv_id: str):
        self._active_id = conv_id
        for cid, btn in self._items.items():
            btn.setProperty("conv_item_active", cid == conv_id)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.conversation_selected.emit(conv_id)

    def _show_context_menu(self, pos, conv_id: str):
        menu = QMenu(self)
        rename_action = menu.addAction("重命名")
        delete_action = menu.addAction("删除")
        action = menu.exec(self._items[conv_id].mapToGlobal(pos))
        if action == rename_action:
            title, ok = QInputDialog.getText(self, "重命名对话", "新标题:", text="")
            if ok and title.strip():
                self.rename_requested.emit(conv_id, title.strip())
        elif action == delete_action:
            reply = QMessageBox.question(
                self, "删除对话",
                "确定要删除这个对话吗？所有消息将被永久删除。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.delete_requested.emit(conv_id)

    def refresh_theme(self):
        for conv_id, btn in self._items.items():
            for d in self._data:
                if d["id"] == conv_id:
                    source = d.get("source", "manual")
                    title = d.get("title", "未命名")
                    last_msg = d.get("last_message") or ""
                    btn.setText(self._format_item_text(title, source, last_msg))
                    btn.setToolTip(title)
                    break
