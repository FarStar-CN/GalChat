"""NapCatQQ WebSocket 消息接收。

连接 NapCatQQ WebSocket 服务器，实时接收 OneBot 11 消息推送，
格式化后输出到控制台并写入日志文件。

使用方法：
    python -m backend.napcat_client          # 运行测试
    python -m backend.napcat_client --once   # 接收一条后退出
"""

import json
import sys
import os
import time
import threading
from datetime import datetime

import websocket

# ── 配置 ──
WS_HOST = "127.0.0.1"
WS_PORT = 3001
ACCESS_TOKEN = "8yMAr8rGvHJSKkte"
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "napcat_messages.log")

# ── 中文标签映射 ──

MESSAGE_SUBTYPE_ZH = {
    "friend": "好友消息",
    "group": "群临时会话",
    "group_self": "群内自身消息",
    "normal": "普通消息",
    "anonymous": "匿名消息",
    "notice": "系统提示",
}

NOTICE_TYPE_ZH = {
    "friend_add": "好友添加",
    "friend_recall": "私聊消息撤回",
    "group_upload": "群文件上传",
    "group_admin": "群管理员变动",
    "group_ban": "群禁言变动",
    "group_card": "群名片变更",
    "group_decrease": "群成员减少",
    "group_increase": "群成员增加",
    "group_recall": "群消息撤回",
    "essence": "群精华消息",
    "notify": "群内通知",
    "gray_tip": "群灰条提示",
    "bot_offline": "机器人离线",
    "group_name": "群名称变更",
    "group_msg_emoji_like": "群表情回应",
}

NOTIFY_SUBTYPE_ZH = {
    "poke": "戳一戳",
    "title": "群头衔变更",
    "profile_like": "个人资料点赞",
    "input_status": "输入状态",
    "honor": "群荣誉变更",
    "lucky_king": "群红包运气王",
}

GROUP_ADMIN_ZH = {"set": "设为管理员", "unset": "取消管理员"}
GROUP_BAN_ZH = {"ban": "禁言", "lift_ban": "解除禁言"}
GROUP_DECREASE_ZH = {"leave": "主动退群", "kick": "被踢出", "kick_me": "我被踢出"}
GROUP_INCREASE_ZH = {"approve": "管理员通过", "invite": "邀请入群"}
ESSENCE_ZH = {"add": "设为精华", "delete": "取消精华"}
REQUEST_TYPE_ZH = {"friend": "好友请求", "group": "群请求"}

SEGMENT_TYPE_ZH = {
    "text": "文本",
    "image": "图片",
    "at": "@",
    "reply": "回复",
    "face": "表情",
    "record": "语音",
    "video": "视频",
    "file": "文件",
    "share": "分享",
    "location": "位置",
    "music": "音乐",
    "forward": "合并转发",
    "node": "转发节点",
    "json": "JSON消息",
    "xml": "XML消息",
    "poke": "戳一戳",
    "dice": "骰子",
    "rps": "猜拳",
    "markdown": "Markdown",
    "mention": "提及",
    "contact": "推荐好友/群",
    "redbag": "红包",
    "longmsg": "长消息",
}


def log_message(msg: str, level: str = "INFO"):
    """同时输出到控制台和日志文件。"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ═══════════════════════════════════════════════════════════════
# 消息段解析
# ═══════════════════════════════════════════════════════════════

def _format_segment(seg: dict) -> str:
    """将单个消息段格式化为可读文本。"""
    seg_type = seg.get("type", "unknown")
    seg_data = seg.get("data", {})

    if seg_type == "text":
        return seg_data.get("text", "")
    elif seg_type == "image":
        url = seg_data.get("url", "")
        file = seg_data.get("file", "")
        sub = seg_data.get("sub_type", "0")
        summary = seg_data.get("summary", "")
        if summary:
            return f"[图片: {summary}]"
        return f"[图片: {url or file}]"
    elif seg_type == "at":
        qq = seg_data.get("qq", "all")
        return "@全体成员" if qq == "all" else f"@{qq}"
    elif seg_type == "reply":
        return f"[回复消息: {seg_data.get('id', '?')}]"
    elif seg_type == "face":
        return f"[表情: {seg_data.get('id', '?')}]"
    elif seg_type == "record":
        return f"[语音]"
    elif seg_type == "video":
        return f"[视频: {seg_data.get('file', '')}]"
    elif seg_type == "file":
        return f"[文件: {seg_data.get('file', '').split('/')[-1]}]"
    elif seg_type == "share":
        return f"[分享: {seg_data.get('title', seg_data.get('url', ''))}]"
    elif seg_type == "location":
        return f"[位置: {seg_data.get('content', seg_data.get('title', ''))}]"
    elif seg_type == "music":
        return f"[音乐: {seg_data.get('title', '')}]"
    elif seg_type == "poke":
        return f"[戳一戳: {seg_data.get('type', '')}]"
    elif seg_type == "dice":
        return f"[骰子: {seg_data.get('id', '?')}]"
    elif seg_type == "rps":
        return f"[猜拳: {seg_data.get('id', '?')}]"
    elif seg_type == "contact":
        return f"[推荐联系人: {seg_data.get('id', '')}]"
    elif seg_type == "forward":
        return f"[合并转发: {seg_data.get('id', '')}]"
    elif seg_type == "json":
        return f"[JSON消息: {seg_data.get('data', '')}]"
    elif seg_type == "markdown":
        return f"[Markdown]"
    elif seg_type == "longmsg":
        return f"[长消息: {seg_data.get('id', '')}]"
    elif seg_type == "redbag":
        return f"[红包: {seg_data.get('title', '')}]"
    else:
        return f"[{SEGMENT_TYPE_ZH.get(seg_type, seg_type)}]"


def _format_message_content(data: dict) -> str:
    """从 message 数组或 raw_message 中提取并格式化消息内容。"""
    segments = data.get("message")
    if isinstance(segments, list) and len(segments) > 0:
        parts = []
        for seg in segments:
            formatted = _format_segment(seg)
            if formatted:
                parts.append(formatted)
        # 将连续的文本段合并，非文本段单独显示
        result = []
        for part in parts:
            if result and not part.startswith("[") and not result[-1].startswith("["):
                result[-1] += part
            else:
                result.append(part)
        return " ".join(result) if len(result) == 1 and not result[0].startswith("[") else "".join(result)

    # fallback to raw_message
    return data.get("raw_message", "")


# ═══════════════════════════════════════════════════════════════
# 事件分发与格式化
# ═══════════════════════════════════════════════════════════════

def format_onebot_message(data: dict) -> str:
    """将 OneBot 11 / NapCat 事件格式化为可读文本。"""
    post_type = data.get("post_type", "unknown")

    handlers = {
        "message": _format_message_event,
        "message_sent": _format_message_sent_event,
        "notice": _format_notice_event,
        "request": _format_request_event,
        "meta_event": _format_meta_event,
    }
    handler = handlers.get(post_type)
    if handler:
        return handler(data)
    return f"未知事件 [{post_type}]: {json.dumps(data, ensure_ascii=False, indent=2)}"


def extract_message_data(data: dict) -> dict | None:
    """从 OneBot 消息事件中提取结构化数据，仅处理私聊消息。

    群聊、通知、请求等非私聊消息返回 None。
    message_sent（自己发出的消息）一并提取，作为"用户"消息写入对话。
    """
    post_type = data.get("post_type", "")
    if post_type not in ("message", "message_sent"):
        return None

    msg_type = data.get("message_type", "")
    if msg_type != "private":
        return None

    sender = data.get("sender", {})
    content = _format_message_content(data)

    # message_sent 的 target_id 才是对方 QQ，用于定位对话
    if post_type == "message_sent":
        peer_id = data.get("target_id", data.get("user_id", 0))
    else:
        peer_id = data.get("user_id", sender.get("user_id", 0))

    nickname = sender.get("nickname", str(peer_id))
    if post_type == "message_sent" and not sender.get("nickname"):
        # 自己发出的消息，用 self_id 对应账号的昵称
        nickname = "我"

    ts = data.get("time")
    timestamp = datetime.fromtimestamp(ts).isoformat() if ts else datetime.now().isoformat()

    return {
        "post_type": post_type,
        "message_type": msg_type,
        "user_id": peer_id,
        "nickname": nickname,
        "content": content,
        "timestamp": timestamp,
    }


# ── Message 事件 ──

def _format_message_event(data: dict) -> str:
    msg_type = data.get("message_type", "unknown")
    sub_type = data.get("sub_type", "")
    sender = data.get("sender", {})
    nickname = sender.get("nickname", sender.get("user_id", "?"))

    lines = []
    type_label = "私聊" if msg_type == "private" else ("群聊" if msg_type == "group" else msg_type)
    lines.append(f":: [{type_label}] {nickname}")

    # 基本信息
    lines.append(f"   消息ID : {data.get('message_id', '?')}")
    if msg_type == "group":
        lines.append(f"   群号   : {data.get('group_id', '?')}")
        card = sender.get("card", "")
        if card and card != nickname:
            lines.append(f"   群名片 : {card}")

    lines.append(f"   发送者 : {nickname} (QQ: {sender.get('user_id', '?')})")
    lines.append(f"   时间   : {datetime.fromtimestamp(data.get('time', 0)).strftime('%Y-%m-%d %H:%M:%S')}")

    if sub_type:
        sub_label = MESSAGE_SUBTYPE_ZH.get(sub_type, sub_type)
        lines.append(f"   子类型 : {sub_label}")

    # 消息内容
    content = _format_message_content(data)
    lines.append(f"   内容   :")
    if "\n" in content:
        for sub in content.split("\n"):
            lines.append(f"     {sub}")
    else:
        lines.append(f"     {content}")

    # 回复引用
    reply_to = _extract_reply_info(data)
    if reply_to:
        lines.append(f"   回复   : {reply_to}")

    return "\n".join(lines)


def _extract_reply_info(data: dict) -> str | None:
    """从消息段中提取回复引用信息。"""
    segments = data.get("message")
    if not isinstance(segments, list):
        return None
    for seg in segments:
        if seg.get("type") == "reply":
            reply_id = seg.get("data", {}).get("id", "")
            return f"回复消息 {reply_id}"
    return None


# ── message_sent 事件（NapCat 扩展） ──

def _format_message_sent_event(data: dict) -> str:
    msg_type = data.get("message_type", "private")
    target_id = data.get("target_id", "?")
    sender = data.get("sender", {})
    self_nickname = sender.get("nickname", data.get("self_id", "?"))

    type_label = "私聊" if msg_type == "private" else ("群聊" if msg_type == "group" else msg_type)
    lines = []
    lines.append(f">> [已发送 · {type_label}] {self_nickname}")

    lines.append(f"   消息ID : {data.get('message_id', '?')}")
    lines.append(f"   目标   : {target_id}")
    lines.append(f"   时间   : {datetime.fromtimestamp(data.get('time', 0)).strftime('%Y-%m-%d %H:%M:%S')}")

    content = _format_message_content(data)
    lines.append(f"   内容   :")
    if "\n" in content:
        for sub in content.split("\n"):
            lines.append(f"     {sub}")
    else:
        lines.append(f"     {content}")

    return "\n".join(lines)


# ── Notice 事件 ──

def _format_notice_event(data: dict) -> str:
    notice_type = data.get("notice_type", "unknown")
    sub_type = data.get("sub_type", "")

    icon = "::"
    type_label = NOTICE_TYPE_ZH.get(notice_type, notice_type)

    lines = []
    lines.append(f"{icon} [通知] {type_label}")

    if notice_type == "group_increase":
        lines.append(f"   群号   : {data.get('group_id', '?')}")
        add_label = GROUP_INCREASE_ZH.get(sub_type, sub_type)
        lines.append(f"   加入者 : {data.get('user_id', '?')}")
        lines.append(f"   方式   : {add_label}")
        if data.get("operator_id"):
            lines.append(f"   操作者 : {data.get('operator_id')}")

    elif notice_type == "group_decrease":
        lines.append(f"   群号   : {data.get('group_id', '?')}")
        dec_label = GROUP_DECREASE_ZH.get(sub_type, sub_type)
        lines.append(f"   离开者 : {data.get('user_id', '?')}")
        lines.append(f"   原因   : {dec_label}")
        if data.get("operator_id"):
            lines.append(f"   操作者 : {data.get('operator_id')}")

    elif notice_type == "group_admin":
        lines.append(f"   群号   : {data.get('group_id', '?')}")
        admin_label = GROUP_ADMIN_ZH.get(sub_type, sub_type)
        lines.append(f"   成员   : {data.get('user_id', '?')}")
        lines.append(f"   操作   : {admin_label}")

    elif notice_type == "group_ban":
        lines.append(f"   群号   : {data.get('group_id', '?')}")
        ban_label = GROUP_BAN_ZH.get(sub_type, sub_type)
        lines.append(f"   成员   : {data.get('user_id', '?')}")
        lines.append(f"   操作   : {ban_label}")
        duration = data.get("duration", 0)
        if duration > 0:
            lines.append(f"   时长   : {duration} 秒")
        elif sub_type == "ban":
            lines.append(f"   时长   : 永久")
        if data.get("operator_id"):
            lines.append(f"   操作者 : {data.get('operator_id')}")

    elif notice_type == "group_card":
        lines.append(f"   群号   : {data.get('group_id', '?')}")
        lines.append(f"   成员   : {data.get('user_id', '?')}")
        lines.append(f"   新名片 : {data.get('card_new', '')}")
        lines.append(f"   旧名片 : {data.get('card_old', '')}")

    elif notice_type == "group_recall":
        lines.append(f"   群号   : {data.get('group_id', '?')}")
        lines.append(f"   撤回者 : {data.get('user_id', '?')}")
        lines.append(f"   消息ID : {data.get('message_id', '?')}")
        if data.get("operator_id"):
            lines.append(f"   操作者 : {data.get('operator_id')}")

    elif notice_type == "friend_recall":
        lines.append(f"   撤回者 : {data.get('user_id', '?')}")
        lines.append(f"   消息ID : {data.get('message_id', '?')}")

    elif notice_type == "friend_add":
        lines.append(f"   新好友 : {data.get('user_id', '?')}")

    elif notice_type == "group_upload":
        lines.append(f"   群号   : {data.get('group_id', '?')}")
        lines.append(f"   上传者 : {data.get('user_id', '?')}")
        file_info = data.get("file", {})
        if file_info:
            lines.append(f"   文件名 : {file_info.get('name', '?')}")
            lines.append(f"   大小   : {file_info.get('size', 0)} bytes")
            lines.append(f"   标识   : {file_info.get('id', '?')}")

    elif notice_type == "essence":
        lines.append(f"   群号   : {data.get('group_id', '?')}")
        ess_label = ESSENCE_ZH.get(sub_type, sub_type)
        lines.append(f"   操作   : {ess_label}")
        lines.append(f"   消息ID : {data.get('message_id', '?')}")
        lines.append(f"   操作者 : {data.get('operator_id', '?')}")

    elif notice_type == "notify":
        notify_label = NOTIFY_SUBTYPE_ZH.get(sub_type, sub_type)
        lines.append(f"   子类型 : {notify_label}")
        if sub_type == "poke":
            lines.append(f"   群号   : {data.get('group_id', '?')}")
            lines.append(f"   发起者 : {data.get('user_id', '?')}")
            lines.append(f"   目标   : {data.get('target_id', '?')}")
        elif sub_type == "title":
            lines.append(f"   群号   : {data.get('group_id', '?')}")
            lines.append(f"   成员   : {data.get('user_id', '?')}")
            lines.append(f"   新头衔 : {data.get('title', '')}")
        elif sub_type == "honor":
            lines.append(f"   群号   : {data.get('group_id', '?')}")
            lines.append(f"   成员   : {data.get('user_id', '?')}")
            lines.append(f"   荣誉   : {data.get('honor_type', '')}")
        elif sub_type == "lucky_king":
            lines.append(f"   群号   : {data.get('group_id', '?')}")
            lines.append(f"   运气王 : {data.get('user_id', '?')}")
        elif sub_type == "input_status":
            lines.append(f"   群号   : {data.get('group_id', '?')}")
            lines.append(f"   用户   : {data.get('user_id', '?')}")
            lines.append(f"   状态   : {data.get('status_type', '?')}")
        else:
            lines.append(f"   群号   : {data.get('group_id', '?')}")
            lines.append(f"   用户   : {data.get('user_id', '?')}")

    elif notice_type == "group_msg_emoji_like":
        lines.append(f"   群号   : {data.get('group_id', '?')}")
        lines.append(f"   消息ID : {data.get('message_id', '?')}")
        lines.append(f"   点赞者 : {data.get('user_id', '?')}")
        lines.append(f"   表情   : {data.get('emoji_id', '?')}")

    elif notice_type == "group_name":
        lines.append(f"   群号   : {data.get('group_id', '?')}")
        lines.append(f"   新群名 : {data.get('group_name', '')}")

    elif notice_type == "gray_tip":
        lines.append(f"   群号   : {data.get('group_id', '?')}")
        tip = data.get("tip", "")
        if tip:
            lines.append(f"   提示   : {tip[:100]}")
        else:
            lines.append(f"   数据   : {json.dumps(data, ensure_ascii=False, indent=4)[:200]}")

    elif notice_type == "bot_offline":
        lines.append(f"   机器人 : {data.get('self_id', '?')}")
        lines.append(f"   原因   : {data.get('reason', '?')}")

    else:
        lines.append(f"   {json.dumps(data, ensure_ascii=False, indent=4)[:200]}")

    return "\n".join(lines)


# ── Request 事件 ──

def _format_request_event(data: dict) -> str:
    req_type = data.get("request_type", "unknown")
    sub_type = data.get("sub_type", "")

    icon = "::"
    type_label = REQUEST_TYPE_ZH.get(req_type, req_type)
    lines = [f"{icon} [请求] {type_label}"]

    lines.append(f"   请求者 : {data.get('user_id', '?')}")
    if req_type == "group":
        lines.append(f"   群号   : {data.get('group_id', '?')}")
        if sub_type == "invite":
            lines.append(f"   邀请人 : {data.get('user_id', '?')}")
            lines.append(f"   方式   : 被邀请入群")
        elif sub_type == "add":
            lines.append(f"   方式   : 主动加群")
    lines.append(f"   附言   : {data.get('comment', '(无)')}")
    lines.append(f"   flag   : {data.get('flag', '?')}")

    return "\n".join(lines)


# ── Meta 事件 ──

def _format_meta_event(data: dict) -> str:
    meta_type = data.get("meta_event_type", "unknown")

    if meta_type == "heartbeat":
        interval = data.get("interval", "?")
        status = data.get("status", {})
        online = status.get("online", False)
        good = status.get("good", False)
        status_str = f"online={online}, good={good}"
        return f"-- 心跳 (间隔: {interval}ms, {status_str})"

    elif meta_type == "lifecycle":
        sub_type = data.get("sub_type", "?")
        icon_map = {"enable": "[+]", "disable": "[-]", "connect": "[o]"}
        icon = icon_map.get(sub_type, "[i]")
        label_map = {"enable": "已启用", "disable": "已停用", "connect": "已连接"}
        label = label_map.get(sub_type, sub_type)
        return f"{icon} 生命周期: {label}"

    return f"元事件 [{meta_type}]"


# ═══════════════════════════════════════════════════════════════
# WebSocket 客户端
# ═══════════════════════════════════════════════════════════════

class NapCatClient:
    """NapCatQQ WebSocket 客户端。"""

    def __init__(self, host: str = WS_HOST, port: int = WS_PORT,
                 token: str = ACCESS_TOKEN,
                 config_manager=None,
                 on_message_callback=None):
        # 优先从 ConfigManager 读取
        if config_manager is not None:
            cfg_host = config_manager.get("napcat_ws_host")
            if cfg_host is not None:
                host = cfg_host
            cfg_port = config_manager.get("napcat_ws_port")
            if cfg_port is not None:
                port = cfg_port
            cfg_token = config_manager.get("napcat_access_token")
            if cfg_token is not None:
                token = cfg_token
        self.url = f"ws://{host}:{port}?access_token={token}"
        self.ws: websocket.WebSocketApp | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._on_message_callback = on_message_callback

    @property
    def is_running(self) -> bool:
        return self._running

    def _on_open(self, ws):
        log_message(f"已连接到 NapCatQQ: {self.url}", "OK")
        self._running = True

    def _on_message(self, ws, raw: str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            log_message(f"非 JSON 消息: {raw}", "WARN")
            return

        formatted = format_onebot_message(data)
        log_message(f"\n{formatted}", "MSG")

        # 提取结构化数据并触发回调
        if self._on_message_callback:
            extracted = extract_message_data(data)
            if extracted:
                self._on_message_callback(extracted)

    def _on_error(self, ws, error):
        log_message(f"WebSocket 错误: {error}", "ERROR")

    def _on_close(self, ws, close_status_code, close_msg):
        self._running = False
        log_message(f"连接关闭 (code={close_status_code}): {close_msg}", "WARN")

    def _run_forever(self):
        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        self.ws.run_forever(ping_interval=30, ping_timeout=10)

    def start(self, block: bool = False):
        """启动 WebSocket 监听。"""
        log_message(f"正在连接 NapCatQQ WebSocket: {self.url}")
        log_message(f"日志文件: {LOG_FILE}")

        if block:
            self._run_forever()
        else:
            self._thread = threading.Thread(target=self._run_forever, daemon=True)
            self._thread.start()
            deadline = time.time() + 5
            while time.time() < deadline:
                if self._running:
                    log_message("NapCatClient 已就绪，等待消息...")
                    break
                time.sleep(0.2)
            else:
                log_message("连接超时 - NapCatQQ 可能未启动或配置不正确", "ERROR")

    def stop(self):
        """关闭连接。"""
        self._running = False
        if self.ws:
            self.ws.close()
        log_message("NapCatClient 已停止")


def main():
    once = "--once" in sys.argv

    client = NapCatClient()
    try:
        client.start(block=once)
        if not once:
            log_message("按 Ctrl+C 退出")
            while client._running:
                time.sleep(1)
    except KeyboardInterrupt:
        log_message("收到中断信号，正在退出...")
    finally:
        client.stop()


if __name__ == "__main__":
    main()
