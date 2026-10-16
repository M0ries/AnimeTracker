#!/bin/bash
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin${PATH:+:$PATH}"
case "${BASH_SOURCE[0]}" in */*) cd -- "${BASH_SOURCE[0]%/*}" || exit 1;; esac
finish() { read -r -p "按回车关闭。" _answer; exit "$1"; }
if [ "$(/usr/bin/uname)" != "Darwin" ]; then echo "此脚本用于 macOS。"; finish 1; fi
for tool in npm cargo xcodebuild; do
 if ! command -v "$tool" >/dev/null 2>&1; then echo "缺少 $tool，请按 README 安装构建环境，或下载 GitHub Actions 的安装包。"; finish 1; fi
done
npm ci || finish 1
npm run app:build || finish 1
/usr/bin/open -R "$PWD/src-tauri/target/release/bundle/macos/AnimeTracker.app"
echo "构建完成。把 AnimeTracker.app 放入应用程序文件夹，以后直接打开，无需终端。"
finish 0
