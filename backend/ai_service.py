"""AI 服务：纯 Python 调用 OpenAI 兼容 API，无 Qt 依赖。"""

import json
import re
from openai import OpenAI

from backend.config import ConfigManager
from backend.prompt_builder import PromptBuilder, PromptMode


class AIService:
    """封装 AI API 调用的同步方法，供 FastAPI 端点使用。"""

    @staticmethod
    def _build_debug(messages, model, request_type):
        """构建调试信息 payload（从原 AIWorker.emit_debug_info 提取）。"""
        debug_msgs = []
        for m in messages:
            if m["role"] == "system" and "预设方向库" in m["content"]:
                if request_type != "PRELOAD_PING":
                    continue
            debug_msgs.append(m)

        return {
            "request_type": request_type,
            "model": model,
            "messages": debug_msgs,
        }

    @staticmethod
    def preload(cfg: ConfigManager, preset_directions_str: str) -> dict:
        """预热连接：发 max_tokens=1 的请求，不解析返回内容。"""
        api_key = cfg.get("api_key")
        base_url = cfg.get("base_url")
        model = cfg.get("model")

        if not api_key:
            raise ValueError("请先在设置中配置 API Key")

        client = OpenAI(api_key=api_key, base_url=base_url)
        builder = PromptBuilder(cfg)

        messages, request_type = builder.build(
            mode=PromptMode.PRELOAD,
            preset_directions_str=preset_directions_str,
        )

        debug = AIService._build_debug(messages, model, request_type)

        client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=1,
        )

        return {"status": "ok", "debug": debug}

    @staticmethod
    def direct_chat(cfg: ConfigManager, prompt: str, context: list = None) -> dict:
        """直接聊天模式：发送 prompt，返回完整回复。"""
        api_key = cfg.get("api_key")
        base_url = cfg.get("base_url")
        model = cfg.get("model")

        if not api_key:
            raise ValueError("请先在设置中配置 API Key")

        client = OpenAI(api_key=api_key, base_url=base_url)
        builder = PromptBuilder(cfg)

        messages, request_type = builder.build(
            mode=PromptMode.DIRECT_CHAT,
            prompt=prompt,
            context=context or [],
        )

        debug = AIService._build_debug(messages, model, request_type)

        response = client.chat.completions.create(model=model, messages=messages)
        reply = response.choices[0].message.content

        return {"reply": reply, "debug": debug}

    @staticmethod
    def generate_options(
        cfg: ConfigManager,
        prompt: str,
        context: list = None,
        preset_directions_str: str = "",
    ) -> dict:
        """生成 3 个回复选项和对应内容。"""
        api_key = cfg.get("api_key")
        base_url = cfg.get("base_url")
        model = cfg.get("model")

        if not api_key:
            raise ValueError("请先在设置中配置 API Key")

        client = OpenAI(api_key=api_key, base_url=base_url)
        builder = PromptBuilder(cfg)

        messages, request_type = builder.build(
            mode=PromptMode.GENERATE_OPTIONS,
            prompt=prompt,
            context=context or [],
            preset_directions_str=preset_directions_str,
        )

        debug = AIService._build_debug(messages, model, request_type)

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.8,
        )

        raw_content = (response.choices[0].message.content or "").strip()
        lines = [line.strip() for line in raw_content.split("\n") if line.strip()]

        parsed_options = []
        pattern = re.compile(r"^\[(.*?)\]\s*(.*)$")

        for line in lines[:3]:
            match = pattern.match(line)
            if match:
                label = match.group(1)
                content = match.group(2)
                parsed_options.append({"label": label, "content": content})
            else:
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    parsed_options.append({"label": parts[0], "content": parts[1]})
                else:
                    parsed_options.append({"label": line[:5] + "..", "content": line})

        while len(parsed_options) < 3:
            parsed_options.append({"label": "继续", "content": "..."})

        return {"options": parsed_options, "debug": debug}
