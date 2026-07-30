#!/usr/bin/env bash
# 统一发布入口：先校验，后推送。杜绝「改完直接 push 导致语法错误上线」。
# 用法： ./publish.sh "提交说明"
set -e
cd "$(dirname "$0")"

echo "▶ [1/2] 发布前校验 ..."
python3 verify_before_push.py

MSG="${1:-更新岗位仪表板}"
echo "▶ [2/2] 校验通过，提交并推送到 GitHub Pages ..."
git add -A
git commit -m "$MSG"
git push
echo "✅ 发布完成。"
