"""QQ-nt 集成：Linux 平台后端（Xlib + XTest）。"""

import time
import Xlib.display
from Xlib.ext import xtest
import Xlib.X
import Xlib.XK


# ── 窗口查找 ──

def find_qq_windows() -> list[dict]:
    """通过 Xlib 枚举所有 QQ-nt 窗口，按面积降序排列。"""
    display = Xlib.display.Display()
    root = display.screen().root
    results = []

    def _recurse(window, depth=0):
        if depth > 30:
            return
        try:
            klass = window.get_wm_class()
            if klass and "qq" in str(klass[0]).lower():
                geom = window.get_geometry()
                w, h = geom.width, geom.height
                if w > 150 and h > 150:
                    name = window.get_wm_name() or ""
                    results.append({
                        "title": name,
                        "x": geom.x, "y": geom.y,
                        "width": w, "height": h,
                        "area": w * h,
                        "window": window,
                    })
            for child in window.query_tree().children:
                _recurse(child, depth + 1)
        except Exception:
            pass

    _recurse(root)
    results.sort(key=lambda r: r["area"], reverse=True)
    return results


def get_main_window_geometry() -> dict | None:
    """获取主 QQ 窗口几何信息。"""
    windows = find_qq_windows()
    if not windows:
        return None
    win = windows[0]
    return {"x": win["x"], "y": win["y"],
            "width": win["width"], "height": win["height"]}


# ── 文本注入 ──

def inject_text(text: str) -> bool:
    """将文本写入剪贴板并模拟 Ctrl+V 粘贴到 QQ。"""
    from PyQt6.QtWidgets import QApplication
    QApplication.clipboard().setText(text)

    display = Xlib.display.Display()
    windows = find_qq_windows()
    if not windows:
        return False

    try:
        win = windows[0]["window"]
        win.configure(stack_mode=Xlib.X.Above)
        win.set_input_focus(Xlib.X.RevertToParent, Xlib.X.CurrentTime)
        display.sync()
    except Exception:
        pass

    time.sleep(0.1)

    keysym_v = Xlib.XK.string_to_keysym("v")
    keycode_v = display.keysym_to_keycode(keysym_v)
    keysym_ctrl = Xlib.XK.string_to_keysym("Control_L")
    keycode_ctrl = display.keysym_to_keycode(keysym_ctrl)

    if keycode_ctrl == 0 or keycode_v == 0:
        return False

    xtest.fake_input(display, Xlib.X.KeyPress, keycode_ctrl)
    display.sync()
    xtest.fake_input(display, Xlib.X.KeyPress, keycode_v)
    display.sync()
    xtest.fake_input(display, Xlib.X.KeyRelease, keycode_v)
    display.sync()
    xtest.fake_input(display, Xlib.X.KeyRelease, keycode_ctrl)
    display.sync()

    return True
