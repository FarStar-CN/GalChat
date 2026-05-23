"""API 客户端：在 QThread 中通过 HTTP 与后端通信，通过信号返回结果。"""

import json
import httpx
from PyQt6.QtCore import QObject, QThread, pyqtSignal


class _HttpWorker(QThread):
    """内部 HTTP 工作线程：同步请求，完成后 emit 结果。"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, method: str, url: str, body: dict = None, parent: QObject = None):
        super().__init__(parent)
        self.method = method
        self.url = url
        self.body = body

    def run(self):
        try:
            with httpx.Client(timeout=httpx.Timeout(60.0)) as client:
                if self.method == "GET":
                    resp = client.get(self.url)
                elif self.method == "PUT":
                    resp = client.put(self.url, json=self.body)
                else:
                    resp = client.post(self.url, json=self.body)
                resp.raise_for_status()
                data = resp.json() if resp.text else {}
                self.finished.emit(data)
        except httpx.HTTPStatusError as e:
            try:
                detail = e.response.json().get("detail", str(e))
            except Exception:
                detail = str(e)
            self.error.emit(f"HTTP {e.response.status_code}: {detail}" if e.response.status_code else str(e))
        except Exception as e:
            self.error.emit(str(e))


class APIClient(QObject):
    """后端 API 客户端。每个方法启动一个 QThread 执行 HTTP 请求。"""

    finished_options = pyqtSignal(list)
    finished_reply = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    debug_payload = pyqtSignal(str)

    config_ready = pyqtSignal(dict)
    directions_ready = pyqtSignal(list)
    config_saved = pyqtSignal()
    preload_done = pyqtSignal()

    def __init__(self, base_url: str = "http://localhost:8000"):
        super().__init__()
        self.base_url = base_url
        self._workers = []

    def _start_worker(self, method: str, path: str, body: dict = None,
                      on_finished=None, on_error=None):
        """创建并启动一个 HTTP 工作线程。"""
        worker = _HttpWorker(method, f"{self.base_url}{path}", body, parent=self)
        self._workers.append(worker)

        def handle_finished(data):
            if on_finished:
                on_finished(data)
            self._cleanup_worker(worker)

        def handle_error(msg):
            if on_error:
                on_error(msg)
            self._cleanup_worker(worker)

        worker.finished.connect(handle_finished)
        worker.error.connect(handle_error)
        worker.start()
        return worker

    def _cleanup_worker(self, worker):
        """在工作线程完成后安全清理。"""
        if worker in self._workers:
            self._workers.remove(worker)
        worker.wait(1000)
        worker.deleteLater()

    # ── AI 端点 ──

    def get_options(self, prompt: str, context: list = None, preset_str: str = ""):
        body = {"prompt": prompt, "context": context or [], "preset_directions_str": preset_str}
        self._start_worker("POST", "/api/chat/options", body,
                           on_finished=self._on_options,
                           on_error=lambda e: self.error_occurred.emit(e))

    def _on_options(self, data: dict):
        options = data.get("options", [])
        debug = data.get("debug", {})
        if debug:
            self.debug_payload.emit(json.dumps(debug, indent=2, ensure_ascii=False))
        self.finished_options.emit(options)

    def direct_chat(self, prompt: str, context: list = None):
        body = {"prompt": prompt, "context": context or []}
        self._start_worker("POST", "/api/chat/direct", body,
                           on_finished=self._on_reply,
                           on_error=lambda e: self.error_occurred.emit(e))

    def _on_reply(self, data: dict):
        reply = data.get("reply", "")
        debug = data.get("debug", {})
        if debug:
            self.debug_payload.emit(json.dumps(debug, indent=2, ensure_ascii=False))
        self.finished_reply.emit(reply)

    def preload(self, preset_str: str = ""):
        body = {"preset_directions_str": preset_str}
        self._start_worker("POST", "/api/preload", body,
                           on_finished=self._on_preload,
                           on_error=lambda e: self.error_occurred.emit(e))

    def _on_preload(self, data: dict):
        debug = data.get("debug", {})
        if debug:
            self.debug_payload.emit(json.dumps(debug, indent=2, ensure_ascii=False))
        self.preload_done.emit()

    # ── 配置端点 ──

    def fetch_config(self):
        self._start_worker("GET", "/api/config",
                           on_finished=lambda data: self.config_ready.emit(data),
                           on_error=lambda e: self.error_occurred.emit(e))

    def save_config(self, config_dict: dict):
        self._start_worker("PUT", "/api/config", config_dict,
                           on_finished=lambda data: self.config_saved.emit(),
                           on_error=lambda e: self.error_occurred.emit(e))

    # ── 方向库端点 ──

    def fetch_directions(self):
        self._start_worker("GET", "/api/directions",
                           on_finished=lambda data: self.directions_ready.emit(data.get("directions", [])),
                           on_error=lambda e: self.error_occurred.emit(e))
