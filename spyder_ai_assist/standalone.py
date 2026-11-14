"""独立运行模式（不需要 Spyder）：把「洄·讲解」面板开成一个普通窗口。

用法：
    python -m spyder_ai_assist.standalone          # 空窗口，可提问
    python -m spyder_ai_assist.standalone <文件>    # 打开并自动讲解该文件
用于：在没装 Spyder 的机器上先验证面板 + AI 接口，或把面板当独立小工具用。
"""
import os
import sys


def _make_app():
    from qtpy.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    return app


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    target = argv[0] if argv else ""
    app = _make_app()

    from .panel import AiAssistPanel
    from . import detect as detectmod

    if target and os.path.isfile(target):
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        lang = detectmod.lang_for_file(target, text)

        def get_doc():
            return text, lang, os.path.basename(target), 0

        panel = AiAssistPanel(get_doc=get_doc)
        panel.explain(text, lang, os.path.basename(target), "当前文件")
    else:
        panel = AiAssistPanel(get_doc=lambda: None)
        if target:
            print("文件不存在：", target, file=sys.stderr)

    from qtpy.QtWidgets import QMainWindow
    win = QMainWindow()
    win.setWindowTitle("洄·讲解（独立模式）")
    win.resize(560, 720)
    win.setCentralWidget(panel)
    win.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
