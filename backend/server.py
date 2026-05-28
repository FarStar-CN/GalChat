"""GalChat 后端 API 服务器。"""

import os
from collections import deque
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

from backend.config import ConfigManager
from backend.direction_manager import DirectionManager
from backend.ai_service import AIService
from backend.conversation_manager import ConversationManager
from backend.napcat_client import NapCatClient

app = FastAPI(title="GalChat API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 项目根目录（backend/ 的上级目录）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

cfg = ConfigManager(os.path.join(PROJECT_ROOT, "config.json"))
directions = DirectionManager(os.path.join(PROJECT_ROOT, "lexicon.json"))
conv_mgr = ConversationManager(PROJECT_ROOT)

# QQ 消息事件队列（最多 100 条）
_qq_events: deque[dict] = deque(maxlen=100)
_napcat_client: Optional[NapCatClient] = None
_qq_event_seq = 0


# ── NapCatQQ 消息处理 ──

def _on_qq_message(msg: dict):
    """收到 QQ 私聊消息时的回调：对话存在则存入，不存在则丢弃。"""
    global _qq_event_seq

    user_id = str(msg.get("user_id", ""))
    conv = conv_mgr.get_conversation(user_id)
    if conv is None:
        return

    # message = 远星发来的 → user; message_sent = 北辰发出的 → assistant
    role = "user" if msg.get("post_type") == "message" else "assistant"
    conv_mgr.add_message(user_id, role, msg.get("content", ""))

    _qq_event_seq += 1
    _qq_events.append({
        "seq": _qq_event_seq,
        "conv_id": user_id,
        "nickname": msg.get("nickname", ""),
        "content": msg.get("content", ""),
        "timestamp": msg.get("timestamp", ""),
    })


@app.on_event("startup")
def _startup():
    global _napcat_client
    if cfg.get("enable_qq_monitor"):
        _napcat_client = NapCatClient(
            config_manager=cfg,
            on_message_callback=_on_qq_message,
        )
        _napcat_client.start()


@app.on_event("shutdown")
def _shutdown():
    if _napcat_client:
        _napcat_client.stop()


# ── Pydantic schemas ──

class OptionsRequest(BaseModel):
    prompt: str
    context: Optional[List[dict]] = None
    preset_directions_str: str = ""
    conversation_id: Optional[str] = None


class DirectChatRequest(BaseModel):
    prompt: str
    context: Optional[List[dict]] = None


class ConfigUpdate(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    custom_models: Optional[List[str]] = None
    user_name: Optional[str] = None
    ai_name: Optional[str] = None
    use_preset_directions: Optional[bool] = None
    enable_clipboard_monitor: Optional[bool] = None
    theme: Optional[str] = None
    enable_qq_monitor: Optional[bool] = None
    napcat_ws_host: Optional[str] = None
    napcat_ws_port: Optional[int] = None
    napcat_access_token: Optional[str] = None


class MessageSchema(BaseModel):
    role: str
    content: str
    timestamp: str


class ConversationMeta(BaseModel):
    id: str
    title: str
    source: str
    source_id: Optional[str] = None
    updated_at: str
    last_message: Optional[str] = None
    message_count: int = 0


class ConversationFull(BaseModel):
    id: str
    title: str
    source: str
    source_id: Optional[str] = None
    created_at: str
    updated_at: str
    messages: list[MessageSchema]


class CreateConversationRequest(BaseModel):
    title: str = "新对话"
    source: str = "manual"
    conv_id: Optional[str] = None


class UpdateTitleRequest(BaseModel):
    title: str


class AddMessageRequest(BaseModel):
    role: str
    content: str


# ── Endpoints ──

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat/options")
def chat_options(req: OptionsRequest):
    try:
        result = AIService.generate_options(
            cfg=cfg,
            prompt=req.prompt,
            context=req.context,
            preset_directions_str=req.preset_directions_str,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/direct")
def chat_direct(req: DirectChatRequest):
    try:
        result = AIService.direct_chat(
            cfg=cfg,
            prompt=req.prompt,
            context=req.context,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class PreloadRequest(BaseModel):
    preset_directions_str: str = ""


@app.post("/api/preload")
def preload(req: PreloadRequest):
    try:
        result = AIService.preload(
            cfg=cfg,
            preset_directions_str=req.preset_directions_str,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 对话管理端点 ──

@app.get("/api/conversations")
def list_conversations():
    try:
        return {"conversations": conv_mgr.list_conversations()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/conversations")
def create_conversation(req: CreateConversationRequest):
    try:
        return conv_mgr.create_conversation(title=req.title, source=req.source, conv_id=req.conv_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/conversations/{conv_id}")
def get_conversation(conv_id: str):
    try:
        conv = conv_mgr.get_conversation(conv_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="对话不存在")
        return conv
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/conversations/{conv_id}")
def update_conversation(conv_id: str, req: UpdateTitleRequest):
    try:
        conv_mgr.update_title(conv_id, req.title)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: str):
    try:
        conv_mgr.delete_conversation(conv_id)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/conversations/{conv_id}/messages")
def add_message(conv_id: str, req: AddMessageRequest):
    try:
        conv_mgr.add_message(conv_id, req.role, req.content)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── QQ 消息端点 ──

@app.get("/api/qq/events")
def get_qq_events(since: int = 0):
    """返回 seq > since 的未消费 QQ 事件。"""
    events = [e for e in _qq_events if e["seq"] > since]
    return {"events": events, "connected": _napcat_client is not None and _napcat_client.is_running}


@app.get("/api/qq/status")
def get_qq_status():
    """返回 NapCat 连接状态。"""
    running = _napcat_client is not None and _napcat_client.is_running
    return {
        "connected": running,
        "enabled": cfg.get("enable_qq_monitor"),
        "host": cfg.get("napcat_ws_host"),
        "port": cfg.get("napcat_ws_port"),
    }


@app.get("/api/config")
def get_config():
    config = cfg.config.copy()
    # 脱敏 api_key
    key = config.get("api_key", "")
    if key and len(key) > 7:
        config["api_key"] = key[:3] + "..." + key[-4:]
    elif key:
        config["api_key"] = "***"
    return config


@app.put("/api/config")
def update_config(req: ConfigUpdate):
    updates = req.model_dump(exclude_none=True)
    for key, value in updates.items():
        cfg.set(key, value)
    return {"status": "ok"}


@app.get("/api/directions")
def get_directions():
    return {
        "directions": directions.directions,
        "directions_str": directions.get_all_directions_string(),
    }
