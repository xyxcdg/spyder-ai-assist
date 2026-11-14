"""设置 AI 对话框：点着选，不手改 JSON。

任何 OpenAI 兼容接口都能接：WorkBuddy / Codex 这类「中转网关」暴露出来的
/v1/chat/completions 地址、以及 OpenAI / DeepSeek / Ollama 等各家 API。
"""
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QVBoxLayout, QWidget,
)

from . import config as cfgmod

# url 里 8792 / 8787 只是示例端口：点选后按老师那边中转网关的实际地址改即可。
PRESETS = [
    {
        "label": "本机 Magpie 网关（开发者本机 3425，无需 Key）",
        "url": "http://127.0.0.1:3425/v1/chat/completions",
        "model": "auto/deepseek-v4.1-flash",
        "need_key": False,
    },
    {
        "label": "WorkBuddy 中转网关（把端口改成你的中转端口）",
        "url": "http://127.0.0.1:8792/v1/chat/completions",
        "model": "group/group",
        "need_key": True,
    },
    {
        "label": "Codex 中转网关（地址/模型以你的中转网关为准）",
        "url": "http://127.0.0.1:8787/v1/chat/completions",
        "model": "gpt-4o-mini",
        "need_key": True,
    },
    {
        "label": "OpenAI（官方，需 API Key）",
        "url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o-mini",
        "need_key": True,
    },
    {
        "label": "DeepSeek（官方，需 API Key）",
        "url": "https://api.deepseek.com/v1/chat/completions",
        "model": "deepseek-chat",
        "need_key": True,
    },
    {
        "label": "本机 Ollama（免费离线，端口 11434）",
        "url": "http://127.0.0.1:11434/v1/chat/completions",
        "model": "qwen2.5:7b",
        "need_key": False,
    },
    {
        "label": "自定义…（任何 OpenAI 兼容 /v1/chat/completions 地址）",
        "url": "",
        "model": "",
        "need_key": True,
        "is_custom": True,
    },
]


class SetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置AI（讲解用接口）")
        self.setMinimumWidth(560)
        cfg = cfgmod.load()

        root = QVBoxLayout(self)
        hint = QLabel(
            "不配也能「运行 / 编译」代码；选一个接口，面板讲解和提问就能用。\n"
            "三类都能接：① WorkBuddy / Codex 的「中转网关」地址（形如 "
            "http://127.0.0.1:端口/v1/chat/completions）；\n"
            "② 各家官方 API（OpenAI / DeepSeek …）；③ 本机 Ollama / Magpie 等本地网关。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#888;")
        root.addWidget(hint)

        form = QFormLayout()
        self.preset = QComboBox()
        for p in PRESETS:
            self.preset.addItem(p["label"], p)
        self.url_edit = QLineEdit(cfg.get("gatewayUrl", ""))
        self.model_edit = QLineEdit(cfg.get("model", ""))
        self.key_edit = QLineEdit(cfg.get("apiKey", ""))
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText("可选；本机 Magpie / Ollama 不用填，云端服务填 API Key")

        form.addRow("接口预设", self.preset)
        form.addRow("接口地址", self.url_edit)
        form.addRow("模型 id", self.model_edit)
        form.addRow("API Key", self.key_edit)
        root.addLayout(form)

        self.preset.currentIndexChanged.connect(self._apply_preset)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        # 默认不覆盖用户已存值
        if not self.url_edit.text().strip():
            self.preset.setCurrentIndex(0)
            self._apply_preset(0)

    def _apply_preset(self, idx):
        data = self.preset.itemData(idx)
        if not data:
            return
        if not data.get("is_custom"):
            if data.get("url"):
                self.url_edit.setText(data["url"])
            if data.get("model"):
                self.model_edit.setText(data["model"])
        # 自定义不动已填的 url/model，只更新 Key 提示
        if data.get("need_key"):
            self.key_edit.setPlaceholderText("需要就填；本机网关 / 中转网关一般可不填，云端服务必填")
        else:
            self.key_edit.setPlaceholderText("可选；本机网关一般不用填")

    def values(self):
        return {
            "gatewayUrl": self.url_edit.text().strip(),
            "model": self.model_edit.text().strip(),
            "apiKey": self.key_edit.text().strip(),
            "useGateway": True,
        }


def run_setup(parent=None, on_saved=None):
    dlg = SetupDialog(parent)
    if dlg.exec_() == QDialog.Accepted:
        cfg = cfgmod.load()
        cfg.update(dlg.values())
        cfgmod.save(cfg)
        if on_saved:
            on_saved(cfg)
        return cfg
    return None
