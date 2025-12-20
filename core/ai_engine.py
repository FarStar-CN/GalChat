# ----------------------------
# ai回复接口
# ----------------------------
import json
import re
from PyQt6.QtCore import QThread, pyqtSignal
from openai import OpenAI
from core.prompt_builder import PromptBuilder, PromptMode


class AIWorker(QThread):
    finished_options = pyqtSignal(list)
    finished_reply = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    log_message = pyqtSignal(str)
    debug_payload = pyqtSignal(str)

    def __init__(self, config_manager, mode, prompt=None, context=None,
                 preset_directions_str=None):
        super().__init__()
        self.cfg = config_manager
        self.mode = mode
        self.prompt = prompt
        self.context = context
        self.preset_directions_str = preset_directions_str

    def run(self):
        api_key = self.cfg.get("api_key")
        base_url = self.cfg.get("base_url")
        model = self.cfg.get("model")

        if not api_key:
            self.error_occurred.emit("请先在设置中配置 API Key")
            return

        try:
            client = OpenAI(api_key=api_key, base_url=base_url)
            builder = PromptBuilder(self.cfg)

            messages, request_type = builder.build(
                mode=PromptMode(self.mode),
                prompt=self.prompt,
                context=self.context,
                preset_directions_str=self.preset_directions_str
            )
            def emit_debug_info(msgs, req_type):
                debug_msgs = []

                for m in msgs:
                    if m["role"] == "system" and "预设方向库" in m["content"]:
                        if req_type == "PRELOAD_PING":
                            debug_msgs.append(m)
                        # 非预热阶段：直接省略 system
                    else:
                        debug_msgs.append(m)

                payload = json.dumps(
                    {
                        "request_type": req_type,
                        "model": model,
                        "messages": debug_msgs
                    },
                    indent=2,
                    ensure_ascii=False
                )

                self.debug_payload.emit(payload)


            # -------- 预热模式  --------
            if self.mode == "preload":
                use_preset = self.cfg.get("use_preset_directions")
                self.log_message.emit(
                    f"正在预热 AI 连接 (携带词库: {'是' if use_preset else '否'})..."
                )

                emit_debug_info(messages, request_type)


                client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=1
                )

                self.log_message.emit("连接预热成功，上下文环境已建立。")
                return

            # -------- 调试模式 --------
            elif self.mode == "direct_chat":
                response = client.chat.completions.create(model=model, messages=messages)
                reply = response.choices[0].message.content
                self.finished_reply.emit(reply)
                return

            # --------  生成选项 + 内容 --------
            elif self.mode == "generate_options":
                self.log_message.emit("正在生成回复方案...")

                emit_debug_info(messages, request_type)

                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.8
                )

                raw_content = response.choices[0].message.content.strip()
                lines = [line.strip() for line in raw_content.split("\n") if line.strip()]

                parsed_options = []

                # 正则解析：匹配 [标签] 内容
                # ^\[(.*?)\]\s*(.*)$ 
                # Group 1 是标签，Group 2 是内容
                pattern = re.compile(r'^\[(.*?)\]\s*(.*)$')

                for line in lines[:3]:  # 只取前3行
                    match = pattern.match(line)
                    if match:
                        label = match.group(1)
                        content = match.group(2)
                        parsed_options.append({"label": label, "content": content})
                    else:
                        # 容错处理：如果AI没按格式输出，把前几个字当标签
                        # 比如: "热情：你好" -> label="热情", content="你好"
                        parts = line.split(" ", 1)
                        if len(parts) == 2:
                            parsed_options.append({"label": parts[0], "content": parts[1]})
                        else:
                            # 极度甚至情况，直接把整句当标签，内容为空（需前端处理）
                            parsed_options.append({"label": line[:5] + "..", "content": line})

                # 不足3个的情况
                while len(parsed_options) < 3:
                    parsed_options.append({"label": "继续", "content": "..."})

                self.finished_options.emit(parsed_options)
                return

        except Exception as e:
            self.error_occurred.emit(str(e))
            self.log_message.emit(f"连接错误: {str(e)}")