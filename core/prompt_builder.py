# ----------------------------
# Prompt构建
# ----------------------------
from enum import Enum
from typing import List, Dict, Optional


class PromptMode(Enum):
    PRELOAD = "preload"
    DIRECT_CHAT = "direct_chat"
    GENERATE_OPTIONS = "generate_options"


class PromptBuilder:
    PRESET_MARK = "### 核心指令：预设方向库###"

    def __init__(self, config_manager):
        self.cfg = config_manager

    def build(self, mode: PromptMode, prompt: Optional[str] = None, context: Optional[List[Dict]] = None, preset_directions_str: Optional[str] = None):
        messages: List[Dict] = []
        request_type: str = ""

        # 1. System Prompt
        messages.append(self._build_system_message(preset_directions_str))

        # 2. 预热模式
        if mode == PromptMode.PRELOAD:
            messages.append({"role": "user", "content": "Ping (System Check)"})
            request_type = "PRELOAD_PING"
            return messages, request_type

        # 3. 直接聊天模式
        if mode == PromptMode.DIRECT_CHAT:
            messages.append({"role": "user", "content": prompt})
            request_type = "DIRECT_CHAT"
            return messages, request_type

        # 4. 上下文
        if context:
            messages.extend(context)

        # -------- 生成选项 + 内容 --------
        if mode == PromptMode.GENERATE_OPTIONS:
            messages.append({
                "role": "user",
                "content": self._build_generate_options_prompt(prompt)
            })
            request_type = "GENERATE_OPTIONS_WITH_CONTENT"  # 更新类型标识
            return messages, request_type


        return messages, request_type

    def _build_system_message(self, preset_directions_str: Optional[str]) -> Dict:
        raw_system_msg = self.cfg.get("system_prompt")
        use_preset = self.cfg.get("use_preset_directions")


        if use_preset and preset_directions_str:
            content = (
                f"{raw_system_msg}\n\n"
                f"{self.PRESET_MARK}\n"
                f"参考预设方向库: {preset_directions_str}\n"
                f"################################"
            )
        else:
            content = raw_system_msg

        return {"role": "system", "content": content}

    def _build_generate_options_prompt(self, user_input: str) -> str:

        use_preset = self.cfg.get("use_preset_directions")

        base_req = f"用户输入: '{user_input}'。\n"

        if use_preset:
            instruction = (
                f"请根据【预设方向库】挑选3个合适的方向，并直接生成对应的回复内容。\n"
            )
        else:
            instruction = (
                f"请构思3个有差异的回复方向，并生成对应的回复内容。同时，你应当同时概括该回复，但不要太过于精简，作为下文提到的[方向词]，要求方向词要达到类似galgame选项的效果，介于5到7个字\n"
            )

        format_req = (
            "严苛格式要求：\n"
            "1. 仅输出3行，每行对应一个选项。\n"
            "2. 必须严格遵守格式：[方向词] 回复正文\n"
            "3. 不要输出任何序号或额外说明。"
        )

        return base_req + instruction + format_req
