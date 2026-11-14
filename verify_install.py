# -*- coding: utf-8 -*-
"""安装后自检：确认 spyder-ai-assist 的插件入口点已被当前 Python 环境注册。

用法（用装有 Spyder 的那个 Python 运行）：
    python verify_install.py

退出码：0 = 通过；1 = 未通过（把输出发给作者即可定位）。
"""
import sys


def main():
    ok = True
    print("Python :", sys.executable)

    # 1) 能 import spyder
    try:
        import spyder
        ver = getattr(spyder, "__version__", "?")
        print("[ok] spyder 版本:", ver)
        try:
            major = int(str(ver).split(".")[0])
            if major < 5:
                print("[warn] 本插件按 Spyder 5/6 的稳定 API 编写，低于 5 可能不兼容")
        except Exception:
            pass
    except Exception as e:
        print("[FAIL] 无法 import spyder（说明这个 Python 不是装 Spyder 的那个）：", e)
        print("RESULT: FAIL")
        return 1

    # 2) 入口点是否注册（组名必须是 spyder.plugins，名字必须是 spyder_ai_assist）
    try:
        from importlib.metadata import entry_points
        eps = entry_points(group="spyder.plugins")
        names, found = [], None
        for ep in eps:
            names.append(ep.name)
            if ep.name == "spyder_ai_assist":
                found = ep
        print("[ok] 已注册的 spyder.plugins 入口点:", ", ".join(names) if names else "(空)")
        if not found:
            print("[FAIL] 没有找到入口点 spyder_ai_assist —— 安装没装进这个环境，或入口点名字被改过")
            ok = False
        else:
            print("[ok] 入口点 ->", "%s:%s" % (found.module, found.attr))
            # 3) 真正把插件类 import 出来
            try:
                import importlib
                m = importlib.import_module(found.module)
                cls = getattr(m, found.attr)
                print("[ok] 插件类:", cls.__name__, "NAME =", getattr(cls, "NAME", "?"))
            except Exception as e:
                print("[FAIL] 入口点能查到，但 import 插件类失败（多半是依赖/版本问题）：", repr(e))
                ok = False
    except Exception as e:
        print("[FAIL] 检查入口点出错:", repr(e))
        ok = False

    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
