#!/usr/bin/env bash
# Spyder AI Assist —— macOS / Linux 一键安装
# 用法： bash install.sh   （或双击在部分桌面环境里运行）
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "============================================"
echo "  Spyder AI Assist  一键安装 (macOS/Linux)"
echo "============================================"

find_py_with_spyder() {
  local cands=() c
  if command -v spyder >/dev/null 2>&1; then
    cands+=("$(dirname "$(command -v spyder)")/python")
  fi
  for n in python3 python; do
    if command -v "$n" >/dev/null 2>&1; then cands+=("$(command -v "$n")"); fi
  done
  for c in "${cands[@]}"; do
    if "$c" -c "import spyder" >/dev/null 2>&1; then echo "$c"; return 0; fi
  done
  return 1
}

PY="$(find_py_with_spyder)" || {
  echo "[未找到] 本机没有能 import spyder 的 Python。"
  echo "请先安装 Spyder（https://www.spyder-ide.org/ 或 pip install spyder），再运行本安装。"
  exit 2
}
echo "[找到] Python: $PY"
"$PY" -c "import spyder;print('[找到] Spyder 版本:', getattr(spyder,'__version__','?'))"

echo "[安装] pip install ..."
"$PY" -m pip install --upgrade --no-deps --no-build-isolation "$HERE" \
  || "$PY" -m pip install --upgrade --no-deps "$HERE"

echo "[验证] ..."
"$PY" "$HERE/verify_install.py"
echo ""
echo "=== 安装完成 ==="
echo "重启 Spyder，在「视图(View) -> 窗格(Panes)」勾选「洄·讲解」。"
echo "首次使用点工具栏「设置AI」选接口并填 Key。"
