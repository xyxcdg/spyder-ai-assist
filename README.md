# spyder-ai-assist —— Spyder 通用 AI 辅助窗口「洄·讲解」

把 VS Code 里 dsh-window「洄·讲解」面板的能力搬进 **Spyder**：在编辑器旁边开一个停靠面板，
从最基础讲解你正在写的代码、面板内直接提问、一键运行，还能保存时自动讲解。

**智能体都能接**：任何 **OpenAI 兼容的 `/v1/chat/completions` 接口**都能用——
OpenAI / DeepSeek / 本机 Ollama / 各种本地网关 / 自定义地址。不绑定某一家服务。

> 默认指向本机 Magpie 网关 `http://127.0.0.1:3425`（模型 `auto/deepseek-v4.1-flash`，流式）。
> **在别人电脑上首次使用，务必点工具栏「设置AI」选一个自己能用的接口**（见下文「首次配置」）。
> 网关连不上时会自动回落 `dsh` 命令行；两条都不通时面板会直接提示你去配置，不会卡死。

---

## 支持的 Spyder 版本

- 目标：**Spyder 5.x / 6.x**（按 Spyder 5.5.6 源码逐项核实 API 编写，6.x 沿用同一套稳定 API）。
- 对版本差异做了回退，避免“换个版本就加载失败”：
  - 生命周期装饰器 import 路径多级回退（新版 `plugin_registration.decorators` → 旧版 `api.plugins` → 空装饰器）；
  - 图标名取不到时降级为无图标（不会因为某个图标名不存在导致插件加载失败）；
  - 编辑器焦点/保存信号用 `getattr + try` 挂载，取不到就跳过（不影响讲解/提问/运行）；
  - 配置走独立 JSON（不依赖版本相关的 CONF 系统），任何 5/6 版本行为一致。
- 面板用 `QTextBrowser` 渲染 Markdown，**不依赖 QtWebEngine**，装没装 WebEngine 都能跑。

---

## 一键安装

### Windows（推荐）

1. 双击 **`install.cmd`**。
2. 它会自动找到「装有 Spyder 的那个 Python」（`where spyder` 反查 + 常见安装路径扫描 +
   逐个 `import spyder` 验证），把插件 `pip install` 进去，然后自动做一次入口点自检。
3. 看到 `RESULT: PASS` 和「安装完成」后，**重启 Spyder**。
4. 打开：**视图(View) → 窗格(Panes) → 勾选「洄·讲解」**。

> 提示：脚本会打印它选中的 Python 和 Spyder 版本，请确认那就是你平时用的那个 Spyder。
> 如果你的 Spyder 在 conda 环境里，脚本也会扫到 `anaconda3 / miniconda3` 的 python。

### macOS / Linux

```bash
bash install.sh
```

同样会自动找装有 Spyder 的 Python 并安装、自检。

### 手动安装（进阶 / 排错用）

用**你运行 Spyder 的那个 Python**执行（不要在别的 Python 里装）：

```bash
/path/to/spyder-python -m pip install .
# 或者开发模式（改代码即时生效）：
/path/to/spyder-python -m pip install -e .
```

装完用同一 Python 跑自检：

```bash
/path/to/spyder-python verify_install.py     # 应输出 RESULT: PASS
```

> 为什么强调“同一个 Python”：插件靠 setuptools 入口点被发现，装错解释器就是“装了但 Spyder 看不见”。

---

## 首次配置（很重要）

面板默认接口是开发者本机网关。**在别人电脑上第一次用，先配接口：**

1. 点面板工具栏 **「设置AI」**。
2. 在「接口预设」里选一个（详见下节「老师怎么接入智能体」）。
3. 填「接口地址 / 模型 id / API Key」（本机 Ollama、Magpie 不用 Key），点确定。
4. 之后点「讲当前文件 / 提问」就能用了。

> 「运行 / 编译」功能**不需要任何 AI 接口**，没配也能用。

### 老师怎么接入智能体（WorkBuddy / Codex 中转 / 直接 API）

这个插件只认一种东西：**OpenAI 兼容的 `/v1/chat/completions` 地址**。
你手上有哪种智能体，就把它变成这种地址填进来：

| 老师手上的智能体 | 怎么填 | 填什么 |
| --- | --- | --- |
| **WorkBuddy（中转）** | 预设选「WorkBuddy 中转网关」 | 地址 = 你的中转网关地址（形如 `http://127.0.0.1:端口/v1/chat/completions`），模型 id 按网关实际暴露的填（如 `group/group`） |
| **Codex（中转）** | 预设选「Codex 中转网关」 | 地址 = 你的 Codex 中转地址，模型 id 以中转网关为准（常见如 `gpt-4o-mini` / `gpt-5-codex` 之类） |
| **直接给 API** | 预设选「OpenAI / DeepSeek / 自定义」 | 服务商给的 Base URL + 模型 id + API Key；任何 OpenAI 兼容服务都能用 |

- 预设里的 `8792` / `8787` 端口**只是示例**，点选后按你中转网关的实际端口改一下就行。
- 中转网关 / 本机网关一般**不用填 API Key**（网关自己解决鉴权）；云端官方服务才填 Key。
- 没有中转、也没有 API？在老师电脑装一个 **Ollama**（免费离线），预设选「本机 Ollama」就能用，无需任何账号。

---

## 功能（与 VS Code 版要求一致）

| 功能 | 说明 |
| --- | --- |
| 讲当前文件 | 四段式从最基础讲解（这段在做什么 / 关键几行 / 必须懂的概念 / 下一步你写这个），正文 ≤400 字 |
| 讲选中 | 选中一段代码直接讲解 |
| 我卡住了 | 指出你写到哪、有没有问题、下一步写什么 |
| 边写边讲 | 停手约 2.5 秒自动看写到哪（默认关，避免盖住基础讲解） |
| 面板内提问 | 底部输入框回车发送、Shift+回车换行；自动带上当前文件上下文；流式输出 |
| 保存自动讲解 | 保存文件后自动讲解（同一文件内容没变不重复讲） |
| 一键运行 | 自动识别语言，自动挑 python/node/javac/gcc/g++/go/rust 等，输出到「运行输出」页 |
| 设置AI | 对话框点选预设：WorkBuddy / Codex 中转、OpenAI / DeepSeek / Ollama、自定义任意 OpenAI 兼容地址 |

快捷键：`Ctrl+Alt+E` 讲文件、`Ctrl+Alt+Shift+E` 讲选中、`Ctrl+Alt+H` 卡住了、
`Ctrl+Alt+R` 运行、`Ctrl+Alt+Q` 提问。

---

## 配置文件

存在 `~/.spyder-ai-assist/config.json`（Windows 下即 `C:\Users\<你>\.spyder-ai-assist\config.json`），
面板「设置AI」按钮就是写它。字段：

```json
{
  "gatewayUrl": "http://127.0.0.1:3425/v1/chat/completions",
  "model": "auto/deepseek-v4.1-flash",
  "apiKey": "",
  "useGateway": true,
  "dshPath": "",
  "explainOnSave": true,
  "autoOpenPanel": true,
  "explainWhileTyping": false,
  "maxTokens": 1200,
  "timeoutSec": 45
}
```

环境变量可覆盖：`SPYDER_AI_URL` / `SPYDER_AI_MODEL` / `SPYDER_AI_KEY` / `SPYDER_AI_DSH`。
插件日志在 `~/.spyder-ai-assist/plugin.log`。

---

## 不用 Spyder 也能预览面板（只依赖 PyQt5）

```bash
python -m spyder_ai_assist.standalone D:\Learn\python\hello.py
```

会把这个面板开成独立窗口，并自动讲解你给的那个文件。用来验证界面/接口是否正常，不必启动整个 Spyder。

---

## 常见问题

- **重启后「视图 → 窗格」里找不到「洄·讲解」**
  → 多半是装错了 Python。用运行 Spyder 的那个 Python 跑 `verify_install.py`，看是否 `RESULT: PASS`；
  不是 PASS 就说明没装进 Spyder 环境，重跑 `install.cmd` 并按提示确认选中的 Python。
- **能打开面板，但点讲解没反应 / 提示“没有连上可用的 AI 接口”**
  → 还没配置接口或 Key 填错。点「设置AI」选接口重填；本机没有 3425 网关时就别选它。
- **讲解很慢**
  → 用的是「网关 → dsh CLI」回落里的 CLI 那条（慢）。正常直连网关首字约 2 秒；选一个响应快的模型即可。
- **装完想卸掉**
  → 双击 `uninstall.cmd`，或 `pip uninstall spyder-ai-assist`，然后重启 Spyder。

---

## 目录结构

```
spyder-ai-assist/
  install.cmd / install.ps1    Windows 一键安装（自动定位 Spyder 的 Python + 自检）
  install.sh                   macOS / Linux 一键安装
  uninstall.cmd                卸载
  verify_install.py            安装后自检（入口点是否注册、插件类能否导入）
  pyproject.toml               打包配置（入口点组 spyder.plugins，名字 spyder_ai_assist）
  spyder_ai_assist/
    plugin.py        SpyderDockablePlugin + PluginMainWidget（面板/动作/信号接线，含跨版本回退）
    panel.py         面板 UI（讲解页/运行输出页/提问框，流式渲染）
    ai_client.py     直连 OpenAI 兼容网关（SSE 流式）+ dsh CLI 回落
    detect.py        语言识别 / 一键运行命令拼装
    prompts.py       四段式讲解 / 卡住了 / 提问 的提示词
    mdrender.py      极简 Markdown→HTML（暗色）
    setup_dialog.py  「设置AI」对话框（预设 + 自定义）
    config.py        配置读写 / 环境变量覆盖 / dsh 定位
    standalone.py    不装 Spyder 时的独立预览入口
```

> 插件靠 setuptools 入口点被发现，组名必须是 `spyder.plugins`，且**入口点名字必须等于
> `SpyderAiAssist.NAME`（`spyder_ai_assist`）**——Spyder 的 `find_plugins.py` 对此有硬校验，
> 不匹配会直接抛错不加载。`pyproject.toml` 已按此配好，勿改名。

---

## 已做的验证

- 逐项对照 Spyder 5.5.6 wheel 源码核实 API：`create_action` 无 `checkable`（用 `toggled=`+`initial=`）、
  `PluginMainWidget.setLayout` 被重写（故用 `self.setLayout(lay)`）、`find_plugins.py` 入口点组与名字校验、
  编辑器焦点/保存信号挂载方式。
- 无头 Qt（offscreen）实测：纯逻辑 + 面板构建/两 tab/流式渲染 + **真连 3425 网关流式出字**（TTFB≈2.2s）通过。
- 回落逻辑实测：网关与 CLI 都不可用时**只回落一次即停并提示配置**，不再无限循环。
- 所有模块 `py_compile` 通过；`install.ps1` PowerShell 解析 0 错。

---

## 许可证

MIT，见 [LICENSE](LICENSE)。
