"""语言识别与一键运行：把 VS Code 版 dsh-window 的 detectLanguage / buildRunCommand
原样移植成 Python（shutil.which 找解释器，dev.cmd 兜底编译 C/C++）。"""
import os
import re
import shutil
import subprocess
import sys
import webbrowser

EXT_BY_LANG = {
    "python": ".py", "javascript": ".js", "java": ".java", "c": ".c",
    "cpp": ".cpp", "go": ".go", "rust": ".rs", "php": ".php", "ruby": ".rb",
    "html": ".html", "css": ".css", "sql": ".sql", "shellscript": ".sh",
}

LANG_BY_EXT = {
    ".py": "python", ".pyw": "python", ".js": "javascript", ".mjs": "javascript",
    ".cjs": "javascript", ".ts": "typescript", ".tsx": "typescriptreact",
    ".jsx": "javascriptreact", ".java": "java", ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".cs": "csharp",
    ".go": "go", ".rs": "rust", ".php": "php", ".rb": "ruby", ".html": "html",
    ".htm": "html", ".css": "css", ".scss": "scss", ".sql": "sql",
    ".sh": "shellscript", ".vue": "vue", ".json": "json", ".md": "markdown",
}

SKIP_LANGS = {"log", "output", "search-result", "settings", "debug", "git", "scminput", "notebook", "jsonc"}


def detect_language(text):
    """从代码内容猜语言。只认最有辨识度的写法，宁可不猜也不要猜错。"""
    t = text or ""
    if not t.strip():
        return ""
    if re.search(r"^#!.*\bpython[0-9.]*", t, re.M):
        return "python"
    if re.search(r"^#!.*\bnode\b", t, re.M):
        return "javascript"
    if re.search(r"^#!.*\b(ba)?sh\b", t, re.M):
        return "shellscript"
    if re.search(r"<\?php", t):
        return "php"
    if re.search(r"#include\s*[<\"]", t):
        if re.search(r"\bstd::|using\s+namespace|cout\s*<<|cin\s*>>|#include\s*<iostream>", t):
            return "cpp"
        return "c"
    if re.search(r"\bpublic\s+(final\s+)?(class|interface|enum)\s+\w+|\bpublic\s+static\s+void\s+main\b|System\.out\.print", t):
        return "java"
    if re.search(r"<!DOCTYPE\s+html|<html[\s>]|<body[\s>]", t, re.I):
        return "html"
    if re.search(r"\bfunc\s+main\s*\(|\bpackage\s+main\b|fmt\.(Print|Println|Sprintf)", t):
        return "go"
    if re.search(r"\bfn\s+main\s*\(|println!\(|\blet\s+mut\s+", t):
        return "rust"
    if re.search(r"\bdef\s+\w+\s*\(|\bif\s+__name__\s*==|^\s*(from\s+\w+\s+import|import\s+\w+)", t, re.M):
        return "python"
    if re.search(r"\bprint\s*\(", t) and not re.search(r"\bconsole\.(log|error|warn)\b|\bfunction\b|=>", t):
        return "python"
    if re.search(r"\bconsole\.(log|error|warn)\b|\brequire\s*\(|\bmodule\.exports\b|\bconst\s+\w+\s*=|\blet\s+\w+\s*=|=>\s*\{", t):
        return "javascript"
    if re.search(r"^\s*(\.|#)?[\w-]+\s*\{[^}]*:[^}]*\}", t, re.M) or re.search(r":\s*(color|margin|padding|display|flex|background)\b", t):
        return "css"
    if re.search(r"\bSELECT\b[\s\S]+\bFROM\b", t, re.I):
        return "sql"
    if re.search(r"\bputs\s+|\bdef\s+\w+[\s\S]*\bend\b", t):
        return "ruby"
    return ""


def lang_for_file(path, text=""):
    ext = os.path.splitext(path or "")[1].lower()
    if ext in LANG_BY_EXT:
        return LANG_BY_EXT[ext]
    if not text:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except Exception:
            text = ""
    return detect_language(text) or "text"


def which(prog):
    try:
        return shutil.which(prog) or ""
    except Exception:
        return ""


def dev_chain_cmd():
    d = which("dev")
    if d:
        return d
    fixed = r"C:\Users\33848\.deepseekharness\tools\devchain\dev.cmd"
    if os.path.isfile(fixed):
        return fixed
    return ""


def build_run_stages(lang, path):
    """返回阶段列表：每段 {cmd: [..], cwd: str, note: str}；识别不出返回 {error: str}。

    cmd 里的可执行程序一律绝对路径（QProcess 不靠 shell，找不到会在第一条报错）。
    """
    lang = (lang or "").lower()
    fdir = os.path.dirname(os.path.abspath(path)) or os.getcwd()
    base = os.path.basename(path)
    stem = os.path.splitext(base)[0]

    def stage(cmd, cwd=fdir, note=""):
        return {"cmd": cmd, "cwd": cwd, "note": note}

    if lang == "python":
        t = which("python") or which("python3") or which("py")
        if not t:
            return {"error": "没找到 Python，请先安装 Python 并重启 Spyder。"}
        return [stage([t, "-u", path], note="python -u")]
    if lang in ("javascript", "javascriptreact", "typescript", "typescriptreact"):
        t = which("node")
        if not t:
            return {"error": "没找到 Node.js，请先安装 Node.js。"}
        return [stage([t, path], note="node")]
    if lang == "java":
        jc = which("javac")
        jr = which("java")
        if not jc or not jr:
            return {"error": "没找到 JDK（javac/java），请安装 JDK 17+。"}
        return [
            stage([jc, "-encoding", "UTF-8", base], note="javac 编译"),
            stage([jr, stem], note="java 运行"),
        ]
    if lang == "c":
        t = which("gcc") or which("clang")
        if t:
            exe = os.path.join(fdir, stem + ".exe")
            return [stage([t, base, "-o", exe], note="编译 C"), stage([exe], note="运行")]
        dev = dev_chain_cmd()
        if dev:
            return [stage([dev, path], note="dev.cmd 编译并运行 C")]
        return {"error": "没找到 C 编译器（gcc / clang / MSVC），请安装编译工具。"}
    if lang in ("cpp", "c++"):
        t = which("g++") or which("clang++")
        if t:
            exe = os.path.join(fdir, stem + ".exe")
            return [stage([t, base, "-o", exe], note="编译 C++"), stage([exe], note="运行")]
        dev = dev_chain_cmd()
        if dev:
            return [stage([dev, path], note="dev.cmd 编译并运行 C++")]
        return {"error": "没找到 C++ 编译器（g++ / clang++ / MSVC），请安装编译工具。"}
    if lang == "go":
        t = which("go")
        if not t:
            return {"error": "没找到 Go，请安装 Go。"}
        return [stage([t, "run", base], note="go run")]
    if lang == "rust":
        t = which("rustc")
        if not t:
            return {"error": "没找到 rustc，请安装 Rust。"}
        exe = os.path.join(fdir, stem + ".exe")
        return [stage([t, base, "-o", exe], note="rustc 编译"), stage([exe], note="运行")]
    if lang == "php":
        t = which("php")
        if not t:
            return {"error": "没找到 PHP。"}
        return [stage([t, path], note="php")]
    if lang == "ruby":
        t = which("ruby")
        if not t:
            return {"error": "没找到 Ruby。"}
        return [stage([t, path], note="ruby")]
    if lang == "html":
        return {"webbrowser": path}
    return {"error": ""}
