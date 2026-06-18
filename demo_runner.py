#!/usr/bin/env python3
# demo_runner.py - 演示专用题目序列脚本
import rospy
import time
from std_msgs.msg import String

# 演示题目序列（按脚本顺序）
DEMO_SEQUENCE = [
    ("char:一", "第1题：一字（简单）"),
    ("char:二", "第2题：二字（应触发难度升级）"),
    ("char:手", "第3题：手字（故意写错，触发情绪感知）"),
    ("char", "第4题：随机出题（可能触发错题复习）"),
    ("digit:7", "第5题：数字7"),
]

if __name__ == '__main__':
    rospy.init_node('demo_runner', anonymous=True)
    pub = rospy.Publisher('/dictation/start', String, queue_size=10)
    rospy.sleep(1)

    print("=== 演示序列 ===")
    for i, (cmd, desc) in enumerate(DEMO_SEQUENCE):
        input(f"\n按回车开始 {desc}（指令：{cmd}）...")
        pub.publish(cmd)
        print(f"已发送：{cmd}")
        print("等待本题完成后再按回车进入下一题")