#!/usr/bin/env bash
# 定时任务入口：脱离会话后台启动每周全流程（约 2 小时），本脚本立即返回。
# 直接前台跑 weekly_job.py 会被调用方的超时/会话结束杀掉。
cd "$(dirname "$0")" || exit 1
mkdir -p logs

if pgrep -f "python3 -u weekly_job.py weekly" >/dev/null; then
    echo "已有每周任务在运行，跳过本次启动"
    exit 0
fi

LOG="logs/weekly_$(date +%Y%m%d_%H%M).log"
nohup setsid python3 -u weekly_job.py weekly > "$LOG" 2>&1 < /dev/null &
echo "已在后台启动 (pid $!)，日志: $LOG"
