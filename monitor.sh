#!/bin/bash
echo "时间,CPU%,内存MB,内存%" > ~/robot_ws/dictation/performance_log.csv
echo "开始监控，Ctrl+C停止..."
while true; do
    TIME=$(date +"%H:%M:%S")
    STATS=$(ps aux | grep dictation_full | grep -v grep | \
            awk '{printf "%s,%.1f,%.1f", $3, $6/1024, $4}')
    if [ ! -z "$STATS" ]; then
        echo "$TIME,$STATS" | tee -a ~/robot_ws/dictation/performance_log.csv
    fi
    sleep 3
done
