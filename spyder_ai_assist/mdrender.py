"""极简 Markdown → HTML：与 VS Code 面板 mdToHtml 同构，只支持讲解用到的语法。"""
import html
import re

_CSS = """
body{font-family:'Segoe UI','Microsoft YaHei',system-ui,sans-serif;color:#e6e6e6;background:#1e1e1e;line-height:1.75;font-size:14px;}
h1,h2,h3,h4{color:#ffffff;line-height:1.3;margin:1.1em 0 .5em;}
h2{font-size:1.2em;border-bottom:1px solid #3a3a3a;padding-bottom:.25em;}
h3{font-size:1.05em;}
p{margin:.5em 0;}
ul,ol{margin:.4em 0 .4em 1.4em;padding:0;}
li{margin:.28em 0;}
code{background:#2a2a2a;padding:1px 5px;border-radius:4px;font-family:Consolas,'Courier New',monospace;font-size:.92em;color:#dcdcaa;}
pre{background:#161616;padding:12px 14px;border-radius:8px;overflow:auto;}
pre code{background:none;padding:0;color:#ce9178;}
strong{color:#4ea1ff;}
blockquote{border-left:3px solid #4ea1ff;margin:.6em 0;padding:.2em .9em;color:#aaa;}
a{color:#4ea1ff;}
"""


def esc(s):
    return html.escape(s, quote=False)


def inline(s):
    s = esc(s)
    s = re.sub(r"`([^`]+)`", lambda m: "<code>" + m.group(1) + "</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    return s


def md_to_html(md):
    lines = (md or "").splitlines()
    out = []
    in_code = False
    code_buf = []
    list_type = None

    def close_list():
        nonlocal list_type
        if list_type:
            out.append("</%s>" % list_type)
            list_type = None

    for ln in lines:
        if ln.startswith("```"):
            if not in_code:
                in_code = True
                code_buf = []
            else:
                in_code = False
                out.append("<pre><code>" + esc("\n".join(code_buf)) + "</code></pre>")
            continue
        if in_code:
            code_buf.append(ln)
            continue
        if not ln.strip():
            close_list()
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            close_list()
            lvl = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (lvl, inline(m.group(2)), lvl))
            continue
        m = re.match(r"^\s*[-*]\s+(.*)$", ln)
        if m:
            if list_type != "ul":
                close_list()
                out.append("<ul>")
                list_type = "ul"
            out.append("<li>" + inline(m.group(1)) + "</li>")
            continue
        m = re.match(r"^\s*\d+\.\s+(.*)$", ln)
        if m:
            if list_type != "ol":
                close_list()
                out.append("<ol>")
                list_type = "ol"
            out.append("<li>" + inline(m.group(1)) + "</li>")
            continue
        m = re.match(r"^>\s?(.*)$", ln)
        if m:
            close_list()
            out.append("<blockquote>" + inline(m.group(1)) + "</blockquote>")
            continue
        close_list()
        out.append("<p>" + inline(ln) + "</p>")

    if in_code:
        out.append("<pre><code>" + esc("\n".join(code_buf)) + "</code></pre>")
    close_list()
    return "<style>%s</style>" % _CSS + "".join(out)
