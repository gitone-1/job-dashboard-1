#!/bin/bash
# ═══════════════════════════════════════════════════════════
# 求职工作台 - 每日执行脚本
# 用法: bash pipeline/run_daily.sh
# ═══════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "========================================="
echo "求职工作台 - 每日岗位更新"
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================="

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装"
    exit 1
fi

# 运行流水线
echo "🚀 启动数据抓取流水线..."
python3 pipeline/pipeline.py "$@"

# 检查结果
if [ -f "jobs.json" ]; then
    COUNT=$(python3 -c "import json; print(len(json.load(open('jobs.json'))))")
    echo "✅ 更新完成: ${COUNT} 个岗位"
else
    echo "⚠️ jobs.json 未生成"
fi

# 更新最后执行时间
echo "$(date '+%Y-%m-%d %H:%M:%S')" > data/last_run.txt

echo "========================================="
echo "完成时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================="
