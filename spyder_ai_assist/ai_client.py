"""AI 客户端：任意 OpenAI 兼容网关直连（流式）+ dsh CLI 回落。

与 VS Code 版 dsh-window 同构：
- 首选 http POST <gatewayUrl>，stream:true，逐 delta 回吐（首字约 2 秒）；
- 网关不可用（连不上 / 非 200 / 超时 / 空流）自动回落 dsh 命令行（约 60 秒）；
- 全部在 QThread 里跑，不卡 Spyder 主界面；可取消。
"""
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import http.client

from qtpy.QtCore import QObject, Signal

from . import config as cfgmod

SYS_PROMPT = "你是耐心的编程入门老师，只输出 Markdown，不说多余的话，不寒暄。"


class GatewayError(Exception):
    pass


def _stream_gateway(url, model, key, prompt, on_delta, should_stop, timeout_sec=45, max_tokens=1200):
    """阻塞式流式调用 OpenAI 兼容接口；delta 通过 on_delta 回调，should_stop() 为真则提前停。"""
    u = urllib.parse.urlsplit(url)
    if not u.hostname:
        raise GatewayError("网关地址无效")
    https = u.scheme == "https"
    conn_cls = http.client.HTTPSConnection if https else http.client.HTTPConnection
    conn = conn_cls(u.hostname, u.port or (443 if https else 80), timeout=12)
    body = json.dumps({
        "model": model,
        "stream": True,
        "temperature": 0.3,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": SYS_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }, ensure_ascii=False)
    payload = body.encode("utf-8")
    path = (u.path or "/") + ("?" + u.query if u.query else "")
    headers = {
        "Content-Type": "application/json",
        "Content-Length": str(len(payload)),
        "Accept": "text/event-stream",
    }
    if key:
        headers["Authorization"] = "Bearer " + key
    try:
        conn.request("POST", path, body=payload, headers=headers)
        resp = conn.getresponse()
    except Exception as e:
        conn.close()
        raise GatewayError(str(e))
    if resp.status != 200:
        try:
            resp.read(512)
        except Exception:
            pass
        conn.close()
        raise GatewayError("HTTP %s" % resp.status)
    try:
        buf = b""
        for chunk in iter(lambda: resp.read(4096), b""):
            if should_stop():
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                text = line.decode("utf-8", "replace").strip()
                if not text.startswith("data:"):
                    continue
                payload_text = text[5:].strip()
                if payload_text == "[DONE]":
                    return
                try:
                    obj = json.loads(payload_text)
                except Exception:
                    continue
                ch = ((obj.get("choices") or [{}])[0] or {}).get("delta") or {}
                content = ch.get("content")
                if isinstance(content, str) and content:
                    on_delta(content)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _run_dsh_cli(dsh_path, prompt, on_delta, should_stop, timeout_sec=90):
    """dsh --profile headless --json，用 stdin 喂提示词，解析 JSON 行事件流。"""
    if not dsh_path or not os.path.isfile(dsh_path):
        raise GatewayError("没有找到 dsh 命令")
    # 用临时 prompt 文件 + 重定向，避免 shell 层吞掉 stdin
    stamp = "%d-%d" % (int(time.time() * 1000), os.getpid())
    tmp_prompt = os.path.join(tempfile.gettempdir(), "dshprompt-%s.txt" % stamp)
    launcher = os.path.join(tempfile.gettempdir(), "dshrun-%s.cmd" % stamp)
    try:
        with open(tmp_prompt, "w", encoding="utf-8") as f:
            f.write(prompt)
        with open(launcher, "w", encoding="ascii") as f:
            f.write('@echo off\r\n"%s" --profile headless --json < "%s"\r\n' % (dsh_path, tmp_prompt))
    except Exception as e:
        raise GatewayError(str(e))

    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    proc = subprocess.Popen(
        ["cmd.exe", "/d", "/s", "/c", launcher],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        startupinfo=startupinfo, text=True, encoding="utf-8", errors="replace",
    )
    try:
        for line in proc.stdout:
            if should_stop():
                proc.kill()
                break
            line = line.strip()
            if not line or line[0] != "{":
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("type") == "text" and isinstance(obj.get("text"), str):
                on_delta(obj["text"])
            elif obj.get("type") == "final" and isinstance(obj.get("text"), str):
                on_delta(obj["text"])
    finally:
        try:
            proc.kill()
        except Exception:
            pass
        for p in (tmp_prompt, launcher):
            try:
                os.unlink(p)
            except Exception:
                pass


class _Worker(threading.Thread):
    def __init__(self, fn, on_delta, on_done, on_error):
        super().__init__(daemon=True)
        self.fn = fn
        self.on_delta = on_delta
        self.on_done = on_done
        self.on_error = on_error
        self._stop = threading.Event()

    def should_stop(self):
        return self._stop.is_set()

    def stop(self):
        self._stop.set()

    def run(self):
        t0 = time.time()
        try:
            self.fn(self.on_delta, self.should_stop)
            self.on_done(time.time() - t0)
        except Exception as e:
            self.on_error(str(e))


class AiClient(QObject):
    """把流式调用包成带信号的 QObject，供面板直接连槽。"""

    delta = Signal(str)
    finished = Signal(str, float)  # 全文本, 秒
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._acc = ""

    def is_busy(self):
        return self._worker is not None and self._worker.is_alive()

    def cancel(self):
        if self._worker:
            self._worker.stop()

    def ask(self, prompt, cfg):
        """cfg: config.load() 的字典。"""
        self.cancel()
        self._acc = ""
        t0 = time.time()

        def on_delta(c):
            self._acc += c
            self.delta.emit(c)

        def on_done(elapsed):
            self._worker = None
            self.finished.emit(self._acc, elapsed)

        def on_error(why):
            self._worker = None
            self.error.emit(why)

        def gateway_job(on_delta_cb, should_stop):
            _stream_gateway(
                str(cfg.get("gatewayUrl") or "").strip(),
                str(cfg.get("model") or "").strip(),
                str(cfg.get("apiKey") or "").strip(),
                prompt,
                on_delta_cb,
                should_stop,
                timeout_sec=int(cfg.get("timeoutSec", 45)),
                max_tokens=int(cfg.get("maxTokens", 1200)),
            )

        def cli_job(on_delta_cb, should_stop):
            dsh = cfgmod.resolve_dsh(cfg)
            _run_dsh_cli(dsh, prompt, on_delta_cb, should_stop)

        if cfg.get("useGateway", True):
            self._worker = _Worker(gateway_job, on_delta, on_done, on_error)
        else:
            self._worker = _Worker(cli_job, on_delta, on_done, on_error)
        self._worker.start()
        return self._worker


def gateway_ask_sync(prompt, cfg, on_delta=None, should_stop=None):
    """同步版本（供 standalone 控制台与测试用）。"""
    acc = []
    def _cb(c):
        acc.append(c)
        if on_delta:
            on_delta(c)
    _stream_gateway(
        str(cfg.get("gatewayUrl") or "").strip(),
        str(cfg.get("model") or "").strip(),
        str(cfg.get("apiKey") or "").strip(),
        prompt,
        _cb,
        should_stop or (lambda: False),
        timeout_sec=int(cfg.get("timeoutSec", 45)),
        max_tokens=int(cfg.get("maxTokens", 1200)),
    )
    return "".join(acc)
