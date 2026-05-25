"""GalChat 后端 API 服务器。"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

from backend.config import ConfigManager
from backend.direction_manager import DirectionManager
from backend.ai_service import AIService

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


# ── Pydantic schemas ──

class OptionsRequest(BaseModel):
    prompt: str
    context: Optional[List[dict]] = None
    preset_directions_str: str = ""


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
    enable_qq_integration: Optional[bool] = None
    theme: Optional[str] = None


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
