#!/bin/sh
set -eu

if [ "$(uname -s)" != Darwin ]; then
  echo 'IPA 必须在装有 Xcode 的 Mac 上构建。' >&2
  exit 1
fi
if ! command -v xcodebuild >/dev/null 2>&1 || ! command -v rustup >/dev/null 2>&1; then
  echo '请先安装 Xcode、Xcode 命令行工具和 Rust。' >&2
  exit 1
fi

cd "$(dirname "$0")/.."
npm ci
rustup target add aarch64-apple-ios
if [ ! -d src-tauri/gen/apple ]; then
  npm run tauri -- ios init
fi

echo '请确认 Xcode 已登录 Apple ID，iOS 工程已设置 Signing Team 和唯一 Bundle ID。'
echo '隐私清单 src-tauri/PrivacyInfo.xcprivacy 需要加入 Xcode 应用 target。'
npm run tauri -- ios build --export-method "${IOS_EXPORT_METHOD:-debugging}"

find src-tauri/gen/apple/build -type f -name '*.ipa' -print
echo '以上为生成的 IPA；安装到 iPhone 仍需要有效签名和描述文件。'
