#!/bin/bash
echo "=== 启动听写节点 ==="
source /home/lemon/robot_ros_application/catkin_ws/devel/setup.sh

echo "[确认] 检查相机话题..."
timeout 5 rostopic hz /camera/color/image_raw --window=3 2>/dev/null | head -1

echo "[启动] 听写节点..."
python3 /home/lemon/robot_ws/dictation/dictation_full.py
