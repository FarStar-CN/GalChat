"""QQ-nt 集成：Windows 平台后端（ctypes + Win32 API）。"""

import time
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


# ── 窗口查找 ──

def _get_process_name(pid: int) -> str:
    """从 PID 获取进程名（小写）。"""
    try:
        handle = kernel32.OpenProcess(0x0400 | 0x0010, False, pid)
        if not handle:
            return ""
        buf = ctypes.create_unicode_buffer(260)
        size = wintypes.DWORD(260)
        kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
        kernel32.CloseHandle(handle)
        return buf.value.split("\\")[-1].lower()
    except Exception:
        return ""


def find_qq_windows() -> list[dict]:
    """枚举所有 QQ-nt 窗口，按面积降序排列。"""
    results = []

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @WNDENUMPROC
    def enum_proc(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True

        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        if w <= 150 or h <= 150:
            return True

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        proc_name = _get_process_name(pid.value)

        if "qq" not in proc_name:
            return True

        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        title = buf.value

        results.append({
            "title": title,
            "x": rect.left, "y": rect.top,
            "width": w, "height": h,
            "area": w * h,
            "hwnd": hwnd,
        })
        return True

    user32.EnumWindows(enum_proc, 0)
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

def _try_focus_qq():
    """尝试将焦点切换到 QQ 窗口。"""
    windows = find_qq_windows()
    if not windows:
        return False
    hwnd = windows[0]["hwnd"]
    try:
        user32.ShowWindow(hwnd, 9)          # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.15)
        return True
    except Exception:
        return False


def inject_text(text: str) -> bool:
    """将文本写入剪贴板并模拟 Ctrl+V 粘贴到 QQ。"""
    from PyQt6.QtWidgets import QApplication
    QApplication.clipboard().setText(text)

    if not _try_focus_qq():
        return False  # QQ 窗口无法聚焦，不发送按键以免误粘贴到其他窗口

    VK_CONTROL = 0x11
    VK_V = 0x56
    KEYEVENTF_KEYUP = 0x0002

    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_V, 0, 0, 0)
    user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

    return True
