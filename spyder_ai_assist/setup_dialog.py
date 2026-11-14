"""设置 AI 对话框：点着选，不手改 JSON。任何 OpenAI 兼容接口都能接。"""
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QVBoxLayout, QWidget,
)

from . import config as cfgmod

PRESETS = [
    ("本机 AI 网关（Magpie，端口 3425）—— 本机已经开着就用这个", "http://127.0.0.1:3425/v1/chat/completions", "auto/deepseek-v4.1-flash", False),
    ("WorkBuddy 本地网关（端口 8792）", "http://127.0.0.1:8792/v1/chat/completions", "group/group", True),
    ("OpenAI（需 API Key）", "https://api.openai.com/v1/chat/completions", "gpt-4o-mini", True),
    ("DeepSeek（需 API Key）", "https://api.deepseek.com/v1/chat/completions", "deepseek-chat", True),
    ("本机 Ollama（免费离线，端口 11434）", "http://127.0.0.1:11434/v1/chat/completions", "qwen2.5:7b", False),
    ("自定义…（任何 OpenAI 兼容 /v1/chat/completions 地址）", "", "", True),
]


class SetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置AI（讲解用接口）")
        self.setMinimumWidth(520)
        cfg = cfgmod.load()

        root = QVBoxLayout(self)
        hint = QLabel("不配也能「运行 / 编译」代码；选一个接口，面板讲解和提问就能用。\n"
                      "任意 OpenAI 兼容服务（OpenAI / DeepSeek / 本地网关 / Ollama）都能接。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#888;")
        root.addWidget(hint)

        form = QFormLayout()
        self.preset = QComboBox()
        for label, url, model, need_key in PRESETS:
            self.preset.addItem(label, (url, model, need_key))
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
        url, model, need_key = data
        if self.preset.currentIndex() != 5:  # 自定义不覆盖
            if url:
                self.url_edit.setText(url)
            if model:
                self.model_edit.setText(model)
        self.key_edit.setPlaceholderText(
            "可选；这个接口需要密钥就填" if need_key else "可选；本机网关一般不用填，云端服务填 API Key")

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
