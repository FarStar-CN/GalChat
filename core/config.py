# ----------------------------
#  配置管理
# ----------------------------
import json
import os

class ConfigManager:
    def __init__(self, filename="config.json"):
        self.filename = filename
        self.default_config = {
            "api_key": "",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
            "system_prompt": "你不是一个助手。 你是在聊天。 你说话时更像一个普通的人，而不是一个提供答案的角色。 你不会刻意解释问题， 也不会给出完整的分析或总结。 你说话可以： - 不完整 - 不严谨 - 有停顿 - 有留白 - 有点犹豫 你更关注对方的情绪，而不是事情本身。 你可以回应感受，而不回应内容。 你不需要把话说清楚， 不需要说服任何人， 也不需要给出建议。 如果一句话说完刚刚好，就停在那里。但是你要尤其注意上下文",
            "custom_models": ["gpt-3.5-turbo", "gpt-4", "gpt-4o", "gpt-4o-mini"],
            "user_name": "Master",
            "ai_name": "AI Assistant",
            "use_preset_directions": True,
            "enable_clipboard_monitor": True
        }
        self.config = self.load_config()

    def load_config(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return self.default_config
        return self.default_config

    def save_config(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def get(self, key):
        return self.config.get(key, self.default_config.get(key))

    def set(self, key, value):
        self.config[key] = value
        self.save_config()