"""对话持久化管理：JSON 文件读写，单文件单对话。"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional


class ConversationManager:
    """管理 conversations/ 目录下的 JSON 对话文件。"""

    def __init__(self, project_root: str):
        self._dir = os.path.join(project_root, "conversations")
        self._index_path = os.path.join(self._dir, "index.json")
        os.makedirs(self._dir, exist_ok=True)

    # ── Internal helpers ──

    def _conv_path(self, conv_id: str) -> str:
        return os.path.join(self._dir, f"{conv_id}.json")

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _read_conv(self, conv_id: str) -> Optional[dict]:
        path = self._conv_path(conv_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            conv = json.load(f)
        return self._migrate_if_needed(conv)

    def _write_conv(self, conv: dict) -> None:
        path = self._conv_path(conv["id"])
        with open(path, "w", encoding="utf-8") as f:
            json.dump(conv, f, indent=2, ensure_ascii=False)

    def _migrate_if_needed(self, conv: dict) -> dict:
        """将旧格式 {history: [...]} 迁移为新格式 {messages: [...]}。"""
        if "history" in conv and "messages" not in conv:
            migrated = []
            for h in conv.pop("history", []):
                migrated.append({
                    "role": h.get("role", "user"),
                    "content": h.get("content", ""),
                    "timestamp": h.get("timestamp", conv.get("updated_at", self._now())),
                })
            conv["messages"] = migrated
            conv.setdefault("source", "manual")
            conv.setdefault("source_id", None)
            if "updated_at" not in conv:
                conv["updated_at"] = conv.get("created_at", self._now())
            self._write_conv(conv)
        return conv

    # ── Index helpers ──

    def _read_index(self) -> list[dict]:
        if not os.path.exists(self._index_path):
            return []
        with open(self._index_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_index(self, entries: list[dict]) -> None:
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)

    def _sync_index_entry(self, conv: dict) -> None:
        idx = self._read_index()
        last_msg = conv["messages"][-1]["content"] if conv["messages"] else None
        if last_msg and len(last_msg) > 50:
            last_msg = last_msg[:50] + "..."
        entry = {
            "id": conv["id"],
            "title": conv["title"],
            "source": conv["source"],
            "source_id": conv.get("source_id"),
            "updated_at": conv["updated_at"],
            "last_message": last_msg,
            "message_count": len(conv["messages"]),
        }
        replaced = False
        for i, row in enumerate(idx):
            if row["id"] == conv["id"]:
                idx[i] = entry
                replaced = True
                break
        if not replaced:
            idx.append(entry)
        self._write_index(idx)

    def _remove_index_entry(self, conv_id: str) -> None:
        idx = self._read_index()
        idx = [row for row in idx if row["id"] != conv_id]
        self._write_index(idx)

    # ── Public API ──

    def list_conversations(self) -> list[dict]:
        """返回所有对话的元信息（不含消息体），新到旧排序。"""
        if os.path.exists(self._index_path):
            idx = self._read_index()
            idx.sort(key=lambda r: r.get("updated_at", ""), reverse=True)
            return idx

        result = []
        for fname in os.listdir(self._dir):
            if not fname.endswith(".json") or fname == "index.json":
                continue
            conv = self._read_conv(fname.replace(".json", ""))
            if conv is None:
                continue
            last_msg = conv["messages"][-1]["content"] if conv["messages"] else None
            if last_msg and len(last_msg) > 50:
                last_msg = last_msg[:50] + "..."
            result.append({
                "id": conv["id"],
                "title": conv["title"],
                "source": conv["source"],
                "source_id": conv.get("source_id"),
                "updated_at": conv["updated_at"],
                "last_message": last_msg,
                "message_count": len(conv["messages"]),
            })
        result.sort(key=lambda r: r["updated_at"], reverse=True)
        return result

    def get_conversation(self, conv_id: str) -> Optional[dict]:
        return self._read_conv(conv_id)

    def create_conversation(self, title: str = "新对话",
                            source: str = "manual",
                            source_id: Optional[str] = None,
                            conv_id: Optional[str] = None) -> dict:
        conv = {
            "id": conv_id or uuid.uuid4().hex,
            "title": title,
            "source": source,
            "source_id": source_id,
            "created_at": self._now(),
            "updated_at": self._now(),
            "messages": [],
        }
        self._write_conv(conv)
        self._sync_index_entry(conv)
        return conv

    def update_title(self, conv_id: str, title: str) -> None:
        conv = self._read_conv(conv_id)
        if conv is None:
            raise ValueError(f"对话不存在: {conv_id}")
        conv["title"] = title
        conv["updated_at"] = self._now()
        self._write_conv(conv)
        self._sync_index_entry(conv)

    def delete_conversation(self, conv_id: str) -> None:
        path = self._conv_path(conv_id)
        if not os.path.exists(path):
            raise ValueError(f"对话不存在: {conv_id}")
        os.remove(path)
        self._remove_index_entry(conv_id)

    def add_message(self, conv_id: str, role: str, content: str) -> None:
        conv = self._read_conv(conv_id)
        if conv is None:
            raise ValueError(f"对话不存在: {conv_id}")
        msg = {"role": role, "content": content, "timestamp": self._now()}
        conv["messages"].append(msg)
        conv["updated_at"] = self._now()
        self._write_conv(conv)
        self._sync_index_entry(conv)

