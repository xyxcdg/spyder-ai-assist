"""配置层：独立于 Spyder 的 JSON 配置（跨版本稳定，改完即生效）。

优先级：磁盘 JSON > 环境变量 > 默认值。
刻意不用 Spyder 的 CONF 系统：外部插件 CONF 依赖版本 API，且每个 Spyder 小版本
行为略有差异；自己读 JSON 则任何 Spyder 5/6 都能跑。
"""
import json
import os
import sys

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".spyder-ai-assist")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
LOG_PATH = os.path.join(CONFIG_DIR, "plugin.log")

DEFAULTS = {
    "gatewayUrl": "http://127.0.0.1:3425/v1/chat/completions",
    "model": "auto/deepseek-v4.1-flash",
    "apiKey": "",
    "useGateway": True,
    "dshPath": "",
    "explainOnSave": True,
    "autoOpenPanel": True,
    "explainWhileTyping": False,
    "maxTokens": 1200,
    "timeoutSec": 45,
}


def log(msg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (__import__("datetime").datetime.now().isoformat(timespec="seconds"), msg))
    except Exception:
        pass


def load():
    cfg = dict(DEFAULTS)
    try:
        if os.path.isfile(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for k in DEFAULTS:
                    if k in data:
                        cfg[k] = data[k]
    except Exception as e:
        log("config load failed: %r" % (e,))
    # 环境变量覆盖（便携场景）
    env_map = {
        "SPYDER_AI_URL": "gatewayUrl",
        "SPYDER_AI_MODEL": "model",
        "SPYDER_AI_KEY": "apiKey",
        "SPYDER_AI_DSH": "dshPath",
    }
    for env, key in env_map.items():
        v = os.environ.get(env, "").strip()
        if v:
            cfg[key] = v
    cfg["useGateway"] = bool(cfg.get("useGateway", True))
    return cfg


def save(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        clean = {k: cfg.get(k, DEFAULTS[k]) for k in DEFAULTS}
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log("config save failed: %r" % (e,))
        return False


def resolve_dsh(cfg=None):
    """找本机 dsh.cmd：设置里的 dshPath 优先，其次默认安装位置，最后 PATH。"""
    cfg = cfg or load()
    p = (cfg.get("dshPath") or "").strip().strip('"')
    if p and os.path.isfile(p):
        return p
    candidates = []
    local = os.environ.get("LOCALAPPDATA", "")
    pf = os.environ.get("ProgramFiles", "")
    if local:
        candidates.append(os.path.join(local, "Programs", "DeepSeek Harness", "resources", "runtime", "cli", "bin", "dsh.cmd"))
    if pf:
        candidates.append(os.path.join(pf, "DeepSeek Harness", "resources", "runtime", "cli", "bin", "dsh.cmd"))
    candidates.append(os.path.join(os.path.expanduser("~"), ".deepseekharness", "dsh.cmd"))
    for c in candidates:
        if os.path.isfile(c):
            return c
    for d in (os.environ.get("PATH") or "").split(os.pathsep):
        if d:
            c = os.path.join(d, "dsh.cmd")
            if os.path.isfile(c):
                return c
    return ""
