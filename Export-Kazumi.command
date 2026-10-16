#!/bin/bash
set -e
# Restore standard command locations before any external command runs.
# Keep the user's existing Python/Dart paths; do not modify shell profiles.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin${PATH:+:$PATH}"
# Bash parameter expansion works even when dirname cannot be found.
case "${BASH_SOURCE[0]}" in
  */*) cd -- "${BASH_SOURCE[0]%/*}" || exit 1 ;;
  *)   cd -- . || exit 1 ;;
esac
if ! command -v dart >/dev/null 2>&1; then
  export PATH="/opt/homebrew/bin:$PATH"
fi
if ! command -v dart >/dev/null 2>&1; then
  echo "未找到 Dart。请使用你之前安装 Dart 的终端运行。"
  read -r -p "按回车关闭。" _answer
  exit 1
fi
echo "请先完全退出 Kazumi，再继续。这里只读取临时副本，不会写入原始 Hive。"
read -r -p "已经退出 Kazumi？输入 yes 继续：" _answer
if [ "$_answer" != "yes" ]; then exit 0; fi
read -r -p "Hive 文件完整路径（直接回车使用 Kazumi 默认位置）：" input_path
if [ -z "$input_path" ]; then
  input_path="$HOME/Library/Containers/com.example.kazumi/Data/Library/Application Support/com.example.kazumi/hive/histories.hive"
fi
output_path="$(pwd)/kazumi-history-$(date +%Y%m%d-%H%M%S).json"
cd hive_exporter
dart pub get
dart run bin/export.dart "$input_path" "$output_path"
echo "导出完成。在 AnimeTracker 的『导入与备份』中选择刚生成的 JSON。"
read -r -p "按回车关闭。" _answer
