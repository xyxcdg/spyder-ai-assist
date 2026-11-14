"""主面板：Spyder 无关的 Qt 组件（讲解 / 提问 / 运行输出 / 状态栏）。

用 QTextBrowser 渲染 Markdown（无 WebEngine 依赖，任何 Spyder 5/6 都能跑）；
QPlainTextEdit 做提问输入，回车发送、Shift+回车换行。
"""
from qtpy.QtCore import Qt, QProcess, QTimer, Signal
from qtpy.QtGui import QTextCursor
from qtpy.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QTabWidget,
    QTextBrowser, QVBoxLayout, QWidget,
)

from . import config as cfgmod
from . import detect as detectmod
from . import prompts as promptmod
from .mdrender import md_to_html
from .ai_client import AiClient

WELCOME = (
    "*在编辑器里写代码，保存后这里会自动从最基础讲解；也可以点「讲当前文件」、"
    "选中代码点「讲选中」，卡住了点「我卡住了」。下方输入框可以直接提问。*"
)


class AskInput(QPlainTextEdit):
    """回车发送、Shift+回车换行的提问输入框。"""

    submitted = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("不懂就问我，比如：什么是变量？这段为什么要这么写？（回车发送，Shift+回车换行）")
        self.setFixedHeight(64)
        self.setTabChangesFocus(False)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            self.submitted.emit()
            return
        super().keyPressEvent(event)


class AiAssistPanel(QWidget):
    """面板本体。get_doc 回调由插件注入，返回 (text, lang, file_name) 或 None。"""

    def __init__(self, parent=None, get_doc=None):
        super().__init__(parent)
        self.get_doc = get_doc
        self.cfg = cfgmod.load()
        self.client = AiClient(self)
        self.client.delta.connect(self._on_delta)
        self.client.finished.connect(self._on_finished)
        self.client.error.connect(self._on_error)

        self._active_run = 0
        self._current_md = WELCOME
        self._header = ""
        self._pending = ""
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(150)
        self._flush_timer.timeout.connect(self._flush_pending)

        self._proc = None
        self._stages = []
        self._stage_idx = 0
        self._fallback_attempted = False

        self._build_ui()
        self.set_status("洄·讲解")
        self.set_md(WELCOME)

    # ---------- UI ----------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.status_label = QLabel("洄·讲解")
        self.status_label.setStyleSheet(
            "background:#1e1e1e;border-bottom:1px solid #3a3a3a;padding:6px 12px;color:#999;font-size:12px;")
        root.addWidget(self.status_label)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setStyleSheet("QTextBrowser{border:none;background:#1e1e1e;padding:8px 16px;}")

        self.run_view = QPlainTextEdit()
        self.run_view.setReadOnly(True)
        self.run_view.setStyleSheet("QPlainTextEdit{border:none;background:#161616;color:#d4d4d4;"
                                    "font-family:Consolas,'Courier New',monospace;font-size:13px;padding:8px 10px;}")
        self.run_view.setPlaceholderText("运行输出会显示在这里。")

        self.tabs.addTab(self.browser, "讲解")
        self.tabs.addTab(self.run_view, "运行输出")
        root.addWidget(self.tabs, 1)

        bar = QWidget()
        bar_lay = QHBoxLayout(bar)
        bar_lay.setContentsMargins(8, 8, 8, 8)
        bar_lay.setSpacing(8)
        self.ask_input = AskInput()
        self.ask_input.submitted.connect(self.submit_ask)
        self.send_btn = QPushButton("问 洄")
        self.send_btn.clicked.connect(self.submit_ask)
        self.send_btn.setStyleSheet(
            "QPushButton{background:#0e639c;color:#fff;border:none;border-radius:6px;padding:0 16px;}"
            "QPushButton:hover{background:#1177bb;}QPushButton:disabled{opacity:.5;}")
        bar_lay.addWidget(self.ask_input, 1)
        bar_lay.addWidget(self.send_btn, 0)
        root.addWidget(bar)
        self._bar = bar

    # ---------- 状态与内容 ----------
    def set_status(self, text):
        self.status_label.setText(text or "洄·讲解")

    def set_md(self, md):
        self._current_md = md
        self.browser.setHtml(md_to_html(md))

    def set_busy(self, on):
        self.send_btn.setEnabled(not on)
        self.ask_input.setEnabled(not on)

    def focus_ask(self):
        self.ask_input.setFocus()

    # ---------- AI 流式 ----------
    def _on_delta(self, chunk):
        self._pending += chunk

    def _flush_pending(self):
        if self._pending:
            md = self._header + self._pending
            self._current_md = md
            self.browser.setHtml(md_to_html(md))
            self._pending = ""

    def _on_finished(self, full, elapsed):
        self._flush_timer.stop()
        self._flush_pending()
        self.set_busy(False)
        if self._current_md.startswith(self._header):
            self._current_md = self._header + full
        self.set_md(self._current_md)
        self.set_status("讲解完成 · 用 %.1f 秒" % elapsed)

    def _on_error(self, why):
        self._flush_timer.stop()
        self._flush_pending()
        use_gw = self.cfg.get("useGateway", True)
        # 网关刚失败：只在“本次请求还没回落过”时回落一次 dsh CLI（绝不无限回落）
        if use_gw and not self._fallback_attempted:
            self._fallback_attempted = True
            self.set_status("网关不可用（%s），改用 dsh，会慢一些…" % why)
            self._run_cli_fallback()
            return
        # 两条路都不通：给一条说得清的提示，停在这里（不循环）
        self._fallback_attempted = False
        self.set_busy(False)
        self.set_status("AI 未连通：%s" % why)
        self.set_md(
            "*⚠️ 没有连上可用的 AI 接口。*\n\n"
            "请点工具栏的「**设置AI**」，选一个接口（OpenAI / DeepSeek / 本机 Ollama 等）"
            "并填好 API Key，再点「讲当前文件 / 提问」即可。\n\n"
            "*（「运行」和代码编译不依赖 AI，可照常使用。）*")

    def _run_cli_fallback(self):
        # 复用正在跑的那条提示词（存起来），把 useGateway 关掉重跑一次
        if not getattr(self, "_last_prompt", None):
            self.set_busy(False)
            self.set_status("还没配置 AI：设置里选一个接口即可（运行/编译照常可用）")
            return
        cfg = dict(self.cfg)
        cfg["useGateway"] = False
        self.cfg = cfg
        self._start_stream(self._last_prompt)

    def _start_stream(self, prompt, header=""):
        self._header = header
        self._pending = ""
        self._last_prompt = prompt
        self._flush_timer.start()
        self.set_busy(True)
        self.client.ask(prompt, self.cfg)

    def cancel_ai(self):
        self.client.cancel()
        self._flush_timer.stop()
        self.set_busy(False)

    # ---------- 讲解 ----------
    def explain(self, text, lang, file_name, label, mode="full", cursor_line=0):
        if not text or not text.strip():
            self.set_status("没有可讲解的内容。")
            return
        self.tabs.setCurrentIndex(0)
        self._active_run += 1
        coaching = mode in ("coach", "stuck")
        if coaching:
            prompt = promptmod.build_coach_prompt(text, lang, file_name, label, mode, cursor_line)
            self.set_status("洄在看你写到哪…（2~5 秒）")
            self.set_md("*⏳ 正在看你的代码，马上给建议…*")
        else:
            prompt = promptmod.build_prompt(text, lang, file_name, label)
            self.set_status("洄正在讲解…（通常 2~5 秒）")
            self.set_md("*⏳ 正在从最基础讲解，稍等几秒…*")
        self.cfg = cfgmod.load()
        self._fallback_attempted = False
        self._start_stream(prompt)

    def coach(self, mode="coach"):
        doc = self._current_doc()
        if not doc:
            self.set_status("请先打开一个代码文件。")
            return
        text, lang, file_name, cursor = doc
        if not text or not text.strip():
            self.set_status("文件里还没有内容。")
            return
        self.explain(text, lang, file_name, "卡住了" if mode == "stuck" else "边写边讲", mode, cursor)

    # ---------- 提问 ----------
    def submit_ask(self):
        q = self.ask_input.toPlainText().strip()
        if not q:
            return
        self.ask_input.clear()
        self.tabs.setCurrentIndex(0)
        header = "## ❓ " + q + "\n\n"
        ctx = self._context_for_ask()
        prompt = promptmod.build_ask_prompt(q, ctx)
        self.set_status("洄在想…（通常 2~5 秒）")
        self.set_md(header + "*⏳ 洄正在想…*")
        self.cfg = cfgmod.load()
        self._fallback_attempted = False
        self._start_stream(prompt, header)

    def _current_doc(self):
        if not self.get_doc:
            return None
        try:
            return self.get_doc()
        except Exception:
            return None

    def _context_for_ask(self):
        doc = self._current_doc()
        if not doc:
            return ""
        text, lang, file_name, _cursor = doc
        if not text or len(text) < 6:
            return ""
        clip = text[:6000] + ("\n...（已截断，只作参考）" if len(text) > 6000 else "")
        return {"file_name": file_name, "lang": lang or "text", "code": clip}

    # ---------- 运行 ----------
    def run_file(self, path):
        self.tabs.setCurrentIndex(1)
        self.run_view.clear()
        if not path:
            self.set_status("请先保存文件再运行。")
            return
        text = ""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except Exception as e:
            self._append_run("读文件失败：%s\n" % e)
            return
        lang = detectmod.lang_for_file(path, text)
        result = detectmod.build_run_stages(lang, path)
        self._append_run("## 运行 %s（语言：%s）\n\n" % (path, lang or "未知"))
        if isinstance(result, dict) and "error" in result:
            self._append_run(result["error"] + "\n")
            self.set_status(result["error"] or "没认出这是什么语言。")
            return
        if isinstance(result, dict) and "webbrowser" in result:
            import webbrowser
            webbrowser.open(result["webbrowser"])
            self._append_run("已用浏览器打开：%s\n" % result["webbrowser"])
            self.set_status("已用浏览器打开")
            return
        self._stages = result or []
        self._stage_idx = 0
        self._run_next_stage()

    def _run_next_stage(self):
        if self._stage_idx >= len(self._stages):
            self._append_run("\n---- 运行结束 ----\n")
            self.set_status("运行结束")
            return
        stage = self._stages[self._stage_idx]
        cmd = stage["cmd"]
        if not cmd:
            self._stage_idx += 1
            self._run_next_stage()
            return
        self._append_run("$ " + " ".join('"%s"' % c if " " in c else c for c in cmd) + "\n")
        proc = QProcess(self)
        proc.setWorkingDirectory(stage.get("cwd") or "")
        proc.setProcessChannelMode(QProcess.MergedChannels)
        proc.readyReadStandardOutput.connect(lambda p=proc: self._on_proc_output(p))
        proc.finished.connect(lambda code, status, p=proc: self._on_proc_done(p, code, status))
        self._proc = proc
        try:
            proc.start(cmd[0], cmd[1:])
        except Exception as e:
            self._append_run("启动失败：%s\n" % e)
            self._proc = None
            self._stage_idx += 1
            self._run_next_stage()

    def _on_proc_output(self, proc):
        try:
            data = bytes(proc.readAllStandardOutput())
            text = data.decode("utf-8", errors="replace")
            if text:
                self._append_run(text)
        except Exception:
            pass

    def _on_proc_done(self, proc, code, status):
        if self._proc is proc:
            self._proc = None
        self._stage_idx += 1
        self._run_next_stage()

    def _append_run(self, text):
        sb = self.run_view.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 4
        cursor = self.run_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.run_view.setTextCursor(cursor)
        self.run_view.insertPlainText(text)
        if at_bottom:
            sb.setValue(sb.maximum())

    def cancel_run(self):
        if self._proc:
            try:
                self._proc.kill()
            except Exception:
                pass
            self._proc = None
