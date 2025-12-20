# ----------------------------
# 词库加载
# ----------------------------
import json
import os

class DirectionManager:
    def __init__(self, filename="lexicon.json"):
        self.filename = filename
        self.directions = []
        self.load_directions()

    def load_directions(self):
        """加载词库文件"""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.directions = data
                    else:
                        print("词库格式错误：应为字符串列表")
            except Exception as e:
                print(f"加载词库失败: {e}")
        else:
            # 如果文件不存在，创建一个默认的
            self.create_default_file()

    def create_default_file(self):
        default_data = ["热情同意", "委婉拒绝", "幽默调侃", "冷漠回应"]
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, indent=4, ensure_ascii=False)
            self.directions = default_data
        except Exception as e:
            print(f"创建默认词库失败: {e}")

    def get_all_directions_string(self):
        """将所有选项拼接成一个字符串，供 Prompt 使用"""
        if not self.directions:
            return ""
        return "、".join(self.directions)