"""Spyder 插件入口：把「洄·讲解」注册成可停靠面板（View → Panes → 洄·讲解）。

基于 SpyderDockablePlugin + PluginMainWidget（Spyder 5/6 通用）：
- 面板自带工具栏（讲当前文件 / 讲选中 / 我卡住了 / 运行 / 设置AI / 自动讲解开关）；
- 与编辑器联动：保存自动讲解、边写边讲（默认关）；
- 快捷键：Ctrl+Alt+E 讲文件、Ctrl+Alt+Shift+E 讲选中、Ctrl+Alt+H 卡住了、Ctrl+Alt+R 运行、Ctrl+Alt+Q 提问。
"""
import os

from spyder.api.plugins import Plugins, SpyderDockablePlugin
from spyder.api.translations import get_translation
from spyder.api.widgets.main_widget import PluginMainWidget
from qtpy.QtCore import Qt, QTimer
from qtpy.QtWidgets import QApplication, QMessageBox

# 兼容不同 Spyder 版本：装饰器模块路径在历史上出现过变动，逐级回退，
# 全部缺失时退化为空装饰器（插件仍能加载，只是少了生命周期钩子）。
try:
    from spyder.api.plugin_registration.decorators import (
        on_plugin_available, on_plugin_teardown)
except Exception:  # pragma: no cover - 旧版本回退
    try:
        from spyder.api.plugins import (  # type: ignore
            on_plugin_available, on_plugin_teardown)
    except Exception:
        def on_plugin_available(*args, **kwargs):
            def _deco(func):
                return func
            return _deco

        def on_plugin_teardown(*args, **kwargs):
            def _deco(func):
                return func
            return _deco

from . import config as cfgmod
from . import detect as detectmod
from .panel import AiAssistPanel
from .setup_dialog import run_setup

_ = get_translation("spyder_ai_assist")


class AiAssistWidget(PluginMainWidget):
    """可停靠面板。"""

    def get_title(self):
        return _("洄·讲解")

    def get_focus_widget(self):
        return self.panel.ask_input

    def setup(self):
        self.editor_plugin = None
        self.panel = AiAssistPanel(self, get_doc=self._get_doc)
        self._layout = None
        from qtpy.QtWidgets import QVBoxLayout
        lay = QVBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.panel)
        self.setLayout(lay)

        # 首次使用（还没有配置文件）给一句明确引导：教师机默认网关通常不存在
        try:
            if not os.path.isfile(cfgmod.CONFIG_PATH):
                self.panel.set_status(
                    "首次使用：点工具栏「设置AI」选接口（OpenAI / DeepSeek / Ollama）；运行代码不需要 AI")
        except Exception:
            pass

        # 保存 / 边写边讲 的防抖计时器
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(900)
        self._save_timer.timeout.connect(self._on_save_debounce)
        self._typing_timer = QTimer(self)
        self._typing_timer.setSingleShot(True)
        self._typing_timer.setInterval(2500)
        self._typing_timer.timeout.connect(self._on_typing_debounce)
        self._last_hash = {}
        self._pending_save_file = None
        self._pending_type_file = None

        self._create_actions()
        self._add_toolbar()
        self._add_shortcuts()

    # ---------- 动作 ----------
    def _icon(self, name):
        """图标名在个别 Spyder 版本可能不存在；取不到就返回 None（不阻断插件加载）。"""
        try:
            return self.create_icon(name)
        except Exception:
            return None

    def _create_actions(self):
        self.action_explain_file = self.create_action(
            "explain_file", text="讲当前文件", icon=self._icon("comment"),
            tip="从最基础讲解当前文件（Ctrl+Alt+E）", triggered=self.explain_file)
        self.action_explain_sel = self.create_action(
            "explain_selection", text="讲选中", icon=self._icon("comment"),
            tip="讲解选中的代码（Ctrl+Alt+Shift+E）", triggered=self.explain_selection)
        self.action_stuck = self.create_action(
            "stuck", text="我卡住了", icon=self._icon("debug"),
            tip="看看卡在哪、下一步写什么（Ctrl+Alt+H）", triggered=self.stuck)
        self.action_run = self.create_action(
            "run", text="运行", icon=self._icon("run"),
            tip="运行当前文件，自动挑解释器/编译器（Ctrl+Alt+R）", triggered=self.run_current)
        self.action_ask = self.create_action(
            "ask", text="提问", icon=self._icon("find"),
            tip="聚焦到面板下方的提问框（Ctrl+Alt+Q）", triggered=self.focus_ask)
        self.action_setup = self.create_action(
            "setup_ai", text="设置AI", icon=self._icon("settings"),
            tip="选择讲解用的 AI 接口（任意 OpenAI 兼容服务都可接）", triggered=self.setup_ai)
        self.action_toggle = self.create_action(
            "toggle_auto_explain", text="保存时自动讲解", icon=self._icon("book"),
            tip="开关：保存文件后自动从最基础讲解", toggled=self._on_toggle_auto,
            initial=bool(cfgmod.load().get("explainOnSave", True)))
        self.action_toggle.setChecked(bool(cfgmod.load().get("explainOnSave", True)))

    def _add_toolbar(self):
        try:
            self.main_toolbar = self.create_toolbar("ai_assist_main_toolbar")
            for action in (self.action_explain_file, self.action_explain_sel,
                           self.action_stuck, self.action_run, self.action_ask,
                           self.action_setup, self.action_toggle):
                self.add_item_to_toolbar(action, self.main_toolbar, "ai_assist_main_toolbar")
        except Exception as e:
            cfgmod.log("toolbar add failed: %r" % (e,))

    def _add_shortcuts(self):
        for action, key in ((self.action_explain_file, "Ctrl+Alt+E"),
                            (self.action_explain_sel, "Ctrl+Alt+Shift+E"),
                            (self.action_stuck, "Ctrl+Alt+H"),
                            (self.action_run, "Ctrl+Alt+R"),
                            (self.action_ask, "Ctrl+Alt+Q")):
            try:
                action.setShortcut(key)
            except Exception:
                pass

    def update_actions(self):
        pass

    # ---------- 文档读取 ----------
    def _get_doc(self):
        ed = self._current_editor()
        if ed is None:
            return None
        try:
            text = ed.toPlainText()
        except Exception:
            text = ""
        try:
            fname = getattr(ed, "filename", "") or "untitled"
        except Exception:
            fname = "untitled"
        lang = getattr(ed, "language", "") or ""
        if not lang:
            lang = detectmod.lang_for_file(fname, text)
        if lang in ("", "text"):
            guessed = detectmod.detect_language(text)
            if guessed:
                lang = guessed
        try:
            cursor = ed.textCursor().blockNumber() + 1
        except Exception:
            cursor = 0
        return text, lang or "text", os.path.basename(fname), cursor

    def _current_editor(self):
        if not self.editor_plugin:
            return None
        try:
            return self.editor_plugin.get_current_editor()
        except Exception:
            return None

    def _current_file(self):
        ed = self._current_editor()
        if ed is None:
            return None
        try:
            return getattr(ed, "filename", "") or ""
        except Exception:
            return ""

    # ---------- 讲解动作 ----------
    def explain_file(self):
        doc = self._get_doc()
        if not doc:
            self._notify("请先打开一个代码文件，再让我讲解。")
            return
        text, lang, fname, _c = doc
        if len(text.strip()) < 6:
            self._notify("这个文件内容太少，先不讲解。")
            return
        self.panel.explain(text, lang, fname, "当前文件")

    def explain_selection(self):
        ed = self._current_editor()
        if ed is None:
            self._notify("请先打开一个代码文件。")
            return
        try:
            text = ed.get_selected_text()
        except Exception:
            text = ""
        if not text or not text.strip():
            # 不同 Spyder 版本/封装可能没有 get_selected_text，用光标选区兜底
            try:
                text = ed.textCursor().selectedText().replace("\u2029", "\n")
            except Exception:
                text = text or ""
        if not text or not text.strip():
            self._notify("没有选中的代码：先选中一段，再点「讲选中」。")
            return
        doc = self._get_doc()
        lang = doc[1] if doc else detectmod.detect_language(text) or "text"
        fname = doc[2] if doc else "选中代码"
        self.panel.explain(text, lang, fname, "选中代码")

    def stuck(self):
        doc = self._get_doc()
        if not doc:
            self._notify("请先打开一个代码文件。")
            return
        text, lang, fname, cursor = doc
        if not text.strip():
            self._notify("文件里还没有内容。")
            return
        self.panel.explain(text, lang, fname, "卡住了", "stuck", cursor)

    def focus_ask(self):
        self.panel.tabs.setCurrentIndex(0)
        self.panel.focus_ask()

    def setup_ai(self):
        run_setup(self, on_saved=lambda cfg: self._notify(
            "已保存 AI 设置：%s @ %s" % (cfg.get("model"), cfg.get("gatewayUrl"))))

    def _on_toggle_auto(self, checked):
        cfg = cfgmod.load()
        cfg["explainOnSave"] = bool(checked)
        cfgmod.save(cfg)
        self._notify("保存时自动讲解：%s" % ("已开启" if checked else "已关闭"))

    # ---------- 运行 ----------
    def run_current(self):
        f = self._current_file()
        if not f:
            self._notify("请先保存一次（保存成 .py/.c/.cpp/.java/.js 之类），再点运行。")
            return
        self.panel.run_file(f)

    # ---------- 保存自动讲解 / 边写边讲 ----------
    def set_editor_plugin(self, editor_plugin):
        self.editor_plugin = editor_plugin
        # 焦点切换信号挂在 Editor 插件对象上（Spyder 5/6 都有 sig_editor_focus_changed）
        try:
            sig_focus = getattr(editor_plugin, "sig_editor_focus_changed", None)
            if sig_focus is not None and not getattr(self, "_focus_connected", False):
                sig_focus.connect(self._on_editor_focus_changed)
                self._focus_connected = True
        except Exception as e:
            cfgmod.log("editor focus hook failed: %r" % (e,))
        self._on_editor_focus_changed()

    def _hook_editorstack_save(self):
        # 保存信号在 EditorStack 上：file_saved(editor_id, filename, filename)，换文件/换栈时重连
        try:
            stack = self.editor_plugin.get_current_editorstack()
        except Exception:
            stack = None
        if stack is None or stack is getattr(self, "_hooked_stack", None):
            return
        try:
            stack.file_saved.connect(self._on_file_saved)
            self._hooked_stack = stack
        except Exception as e:
            cfgmod.log("file_saved hook failed: %r" % (e,))

    def _on_file_saved(self, *args):
        filename = str(args[-1]) if args else (self._current_file() or "")
        cfg = cfgmod.load()
        if not cfg.get("explainOnSave", True):
            return
        f = self._current_file()
        if not f or os.path.normpath(f) != os.path.normpath(str(filename)):
            return
        self._pending_save_file = str(filename)
        self._save_timer.start()

    def _on_save_debounce(self):
        f = self._pending_save_file
        self._pending_save_file = None
        doc = self._get_doc()
        if not doc:
            return
        text, lang, fname, _c = doc
        if len(text) < 6 or len(text) > 300000:
            return
        key = "save:" + (self._current_file() or f or "")
        import hashlib
        h = hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()
        if self._last_hash.get(key) == h:
            return
        self._last_hash[key] = h
        self.panel.explain(text, lang, fname, "当前文件")

    def _on_editor_focus_changed(self):
        ed = self._current_editor()
        if ed is None:
            return
        try:
            try:
                self._prev_editor.textChanged.disconnect(self._on_text_changed)
            except Exception:
                pass
        except Exception:
            pass
        try:
            ed.textChanged.connect(self._on_text_changed)
            self._prev_editor = ed
        except Exception:
            pass
        self._hook_editorstack_save()

    def _on_text_changed(self):
        cfg = cfgmod.load()
        if not cfg.get("explainWhileTyping", False):
            return
        if not cfg.get("useGateway", True):
            return
        f = self._current_file()
        if not f:
            return
        self._pending_type_file = f
        self._typing_timer.start()

    def _on_typing_debounce(self):
        f = self._pending_type_file
        self._pending_type_file = None
        doc = self._get_doc()
        if not doc:
            return
        text, lang, fname, cursor = doc
        if len(text) < 6 or len(text) > 20000:
            return
        key = "type:" + (self._current_file() or f or "")
        import hashlib
        h = hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()
        if self._last_hash.get(key) == h:
            return
        self._last_hash[key] = h
        self.panel.explain(text, lang, fname, "边写边讲", "coach", cursor)

    # ---------- 收尾 ----------
    def _notify(self, msg):
        try:
            self.panel.set_status(msg)
        except Exception:
            pass


class SpyderAiAssist(SpyderDockablePlugin):
    NAME = "spyder_ai_assist"
    REQUIRES = [Plugins.Editor]
    OPTIONAL = []
    TABIFY = [Plugins.IPythonConsole]
    WIDGET_CLASS = AiAssistWidget
    CONF_FILE = False

    @staticmethod
    def get_name():
        return _("洄·讲解")

    @staticmethod
    def get_description():
        return _("通用 AI 辅助窗口：从最基础讲解代码、面板内提问、一键运行；任意 OpenAI 兼容接口可接入（默认本机 Magpie 3425，回落 dsh CLI）。")

    @classmethod
    def get_icon(cls):
        try:
            return cls.create_icon("comment")
        except Exception:
            return None

    def on_initialize(self):
        cfgmod.log("plugin on_initialize")
        # 面板由 SpyderDockablePlugin 自动创建；这里只做编辑器接线
        self._wire_editor()

    @on_plugin_available(plugin=Plugins.Editor)
    def on_editor_available(self):
        cfgmod.log("editor plugin available")
        self._wire_editor()

    def _wire_editor(self):
        """把编辑器接进面板；Editor 未就绪时静默跳过（保存/边写功能暂不可用，不影响其他功能）。"""
        try:
            editor = self.get_plugin(Plugins.Editor)
        except Exception as e:
            cfgmod.log("get_plugin(Editor) failed: %r" % (e,))
            return
        if editor is None:
            return
        widget = self.get_widget()
        if widget is not None:
            widget.set_editor_plugin(editor)

    @on_plugin_teardown(plugin=Plugins.Editor)
    def on_editor_teardown(self):
        pass
