#!/usr/bin/env python3
# quantitative_test.py - 系统性量化测试
import sys
import rospy
import cv2
import time
import json
import os
import numpy as np
sys.path.append('/opt/ros/noetic/lib/python3/dist-packages')
sys.path.insert(0, '/home/lemon/robot_ws/dictation')
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
from character_judge import judge_character
import subprocess

def speak(text):
    try:
        tmp_file = '/tmp/tts_output.mp3'
        subprocess.run(
            ['edge-tts', '--voice', 'zh-CN-XiaoxiaoNeural',
             '--text', text, '--write-media', tmp_file],
            check=True, capture_output=True
        )
        subprocess.run(['play', '-q', tmp_file], check=True)
    except Exception as e:
        print(f"[TTS] {e}")
        try:
            subprocess.run(['espeak-ng', '-v', 'zh', '-s', '130', text])
        except:
            pass

bridge = CvBridge()
latest_frame = [None]
SAVE_PATH = '/home/lemon/robot_ws/dictation/test_capture.jpg'
RESULT_PATH = '/home/lemon/robot_ws/dictation/test_results.json'
PAPER_THRESHOLD = 0.15

# 所有测试字符
TEST_CHARS = {
    '简单': ['一', '二', '三', '十', '人', '口', '八', '工'],
    '中等': ['山', '水', '火', '土', '木', '日', '月', '大', '上', '下'],
    '难':   ['手', '耳', '目', '田', '左', '右', '头', '足']
}

def image_callback(msg):
    latest_frame[0] = bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

def detect_paper(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    contours = cv2.findContours(binary, cv2.RETR_EXTERNAL,
                                cv2.CHAIN_APPROX_SIMPLE)[-2]
    if not contours:
        return False
    largest = max(contours, key=cv2.contourArea)
    ratio = cv2.contourArea(largest) / (frame.shape[0] * frame.shape[1])
    return ratio > PAPER_THRESHOLD

def capture_when_ready():
    print("  [等待] 请把写好的纸举到摄像头前...")
    while True:
        if latest_frame[0] is not None:
            frame = latest_frame[0].copy()
            if detect_paper(frame):
                cv2.imwrite(SAVE_PATH, frame)
                print("  [拍照] 检测到纸张，已拍照")
                return SAVE_PATH
        time.sleep(0.1)

def run_test():
    results = []
    total = 0
    correct_count = 0

    print("\n" + "="*50)
    print("量化测试开始")
    print("每个字写好后举到摄像头前，自动拍照判断")
    print("="*50)

    for level, chars in TEST_CHARS.items():
        print(f"\n【{level}难度】")
        for char in chars:
            print(f"\n第{total+1}题：请写「{char}」")
            speak(f"请写{char}")

            # 等待拍照
            image_path = capture_when_ready()
            time.sleep(0.5)

            # VLM判断 + 计时
            t_start = time.time()
            result = judge_character(image_path, char)
            t_end = time.time()
            response_time = round(t_end - t_start, 2)

            is_correct = result['correct']
            total += 1
            if is_correct:
                correct_count += 1

            status = '✅' if is_correct else '❌'
            print(f"  结果：{status} | 反馈：{result['feedback']} | 耗时：{response_time}s")
            speak(result['feedback'])

            results.append({
                'char': char,
                'level': level,
                'correct': is_correct,
                'feedback': result['feedback'],
                'response_time': response_time
            })

            time.sleep(1)

    # 保存结果
    with open(RESULT_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 打印汇总
    print("\n" + "="*50)
    print("测试汇总")
    print("="*50)
    print(f"总题数：{total}")
    print(f"答对：{correct_count}")
    print(f"总准确率：{correct_count/total:.1%}")
    print()

    for level in ['简单', '中等', '难']:
        level_results = [r for r in results if r['level'] == level]
        level_correct = sum(1 for r in level_results if r['correct'])
        avg_time = sum(r['response_time'] for r in level_results) / len(level_results)
        print(f"{level}：{level_correct}/{len(level_results)} "
              f"准确率={level_correct/len(level_results):.1%} "
              f"平均响应={avg_time:.2f}s")

    avg_total_time = sum(r['response_time'] for r in results) / len(results)
    print(f"\n平均VLM响应时间：{avg_total_time:.2f}s")
    print(f"结果已保存至：{RESULT_PATH}")

    return results

if __name__ == '__main__':
    rospy.init_node('quantitative_test', anonymous=True)
    rospy.Subscriber('/camera/color/image_raw', Image, image_callback)
    rospy.sleep(1)

    print("准备好了吗？准备好按回车开始")
    input()
    run_test()