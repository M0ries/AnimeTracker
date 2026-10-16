#!/bin/bash
# Restore standard command locations before any external command runs.
# Keep the user's existing Python/Dart paths; do not modify shell profiles.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin${PATH:+:$PATH}"
# Bash parameter expansion works even when dirname cannot be found.
case "${BASH_SOURCE[0]}" in
  */*) cd -- "${BASH_SOURCE[0]%/*}" || exit 1 ;;
  *)   cd -- . || exit 1 ;;
esac
if ! command -v python3 >/dev/null 2>&1; then
  echo "未找到 Python 3。请安装 Python 3.9 或更高版本后重试。"
  read -r -p "按回车关闭。" _answer
  exit 1
fi
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
  echo "需要可用的 Python 3.9 或更高版本；当前 python3 不可用或版本过低。"
  read -r -p "按回车关闭。" _answer
  exit 1
fi
python3 local_app/app.py "$@"
result=$?
if [ "$result" -ne 0 ]; then
  echo "启动没有完成。上方是具体原因；你的数据库没有被启动脚本清空。"
  read -r -p "按回车关闭。" _answer
fi
exit "$result"
