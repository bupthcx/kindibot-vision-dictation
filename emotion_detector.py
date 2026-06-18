#!/usr/bin/env python3
# emotion_detector.py
import base64
import json
import urllib.request
import cv2
import time
import sys
import threading
import re
import datetime
import os
import rospy
import rospkg
sys.path.append(rospkg.RosPack().get_path('leju_lib_pkg'))
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
from bodyhub.msg import JointControlPoint
from bodyhub.srv import SrvTLSstring
import motion.bodyhub_client as bodycli

API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
MODEL   = "qwen-vl-plus"

bridge = CvBridge()
latest_frame = [None]
FACE_DIR = '/home/lemon/robot_ws/dictation/'

FACE_CASCADE = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
)

def image_callback(msg):
    latest_frame[0] = bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

def encode_image(image_path):
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')

def call_api(payload, timeout=15):
    request_data = json.dumps(payload, ensure_ascii=True).encode('ascii')
    req = urllib.request.Request(
        API_URL, data=request_data,
        headers={
            'Authorization': f'Bearer {API_KEY}',
            'Content-Type': 'application/json; charset=utf-8'
        },
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result_data = json.loads(resp.read().decode('utf-8'))
    content = result_data['choices'][0]['message']['content'].strip()
    content = content.replace('```json', '').replace('```', '').strip()
    match = re.search(r'\{[^}]+\}', content)
    if match:
        return json.loads(match.group())
    return json.loads(content)

def confirm_is_face(image_path):
    try:
        image_data = encode_image(image_path)
        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
                {"type": "text",
                 "text": "Is there a human face in this image? Reply only JSON: {\"has_face\": true or false}"}
            ]}],
            "max_tokens": 50
        }
        result = call_api(payload, timeout=10)
        has_face = result.get('has_face', False)
        print(f"[人脸确认] {'是人脸' if has_face else '不是人脸'}")
        return has_face
    except Exception as e:
        print(f"[人脸确认] 失败：{e}")
        return False

def detect_face_in_frame(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = FACE_CASCADE.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=8, minSize=(100, 100)
    )
    return len(faces) > 0, faces

def scan_for_face(pub, control_id, frame_ref=None,
                  start_angle=20, end_angle=-20):
    """扫描找人脸，frame_ref为外部帧引用（list），None则用内部的"""
    source = frame_ref if frame_ref is not None else latest_frame
    print("[扫描] 开始寻找人脸...")
    scan_angles = list(range(start_angle, end_angle - 1, -5))

    for angle in scan_angles:
        pub.publish(positions=[0, angle], mainControlID=control_id)
        time.sleep(0.6)

        if source[0] is None:
            print(f"[扫描] 垂直={angle}度，等待图像...")
            continue

        frame = source[0].copy()
        found, faces = detect_face_in_frame(frame)
        print(f"[扫描] 垂直={angle}度，检测到人脸：{found}")

        if found:
            x, y, w, h = faces[0]
            pad = 40
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(frame.shape[1], x + w + pad)
            y2 = min(frame.shape[0], y + h + pad)
            face_img = frame[y1:y2, x1:x2]
            ts = datetime.datetime.now().strftime("%H%M%S")
            face_path = f'{FACE_DIR}face_{ts}.jpg'
            cv2.imwrite(face_path, face_img)

            if confirm_is_face(face_path):
                print(f"✅ 确认找到人脸，角度={angle}度")
                return face_path, angle
            else:
                print("[扫描] 误识别，继续...")

    print("❌ 未找到人脸")
    return None, 0

def detect_emotion(image_path):
    try:
        image_data = encode_image(image_path)
        prompt_text = ("请仔细观察图中人物的面部表情，特别注意眉毛是否皱起、嘴角是否上扬。"
                       "从以下三种中选一个：happy（嘴角上扬开心）、"
                       "confused（眉头紧皱困惑）、neutral（表情平静）。"
                       "只返回JSON，不要其他文字："
                       "{\"emotion\": \"happy或confused或neutral\", "
                       "\"confidence\": \"high或low\"}")
        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
                {"type": "text", "text": prompt_text}
            ]}],
            "max_tokens": 100
        }
        result = call_api(payload, timeout=20)
        emotion = result.get('emotion', 'neutral')
        confidence = result.get('confidence', 'low')
        print(f"[情绪] 检测结果：{emotion}（置信度：{confidence}）")
        return emotion
    except Exception as e:
        print(f"[情绪] 检测失败：{e}")
        return 'neutral'

def scan_and_detect_emotion(pub, control_id, frame_ref=None):
    """完整流程：扫描找脸 → 情绪检测 → 复位"""
    face_path, angle = scan_for_face(pub, control_id, frame_ref)
    if face_path is None:
        pub.publish(positions=[0, 0], mainControlID=control_id)
        return 'neutral'
    emotion = detect_emotion(face_path)
    pub.publish(positions=[0, 0], mainControlID=control_id)
    time.sleep(0.5)
    return emotion

# =====================
# 测试入口
# =====================
if __name__ == '__main__':
    rospy.init_node('emotion_test', anonymous=True)
    bodycli.BodyhubClient(2).ready()

    pub = rospy.Publisher('MediumSize/BodyHub/HeadPosition',
                          JointControlPoint, queue_size=10)
    rospy.sleep(0.5)

    try:
        rospy.wait_for_service('MediumSize/BodyHub/GetMasterID', 1)
        from rospy import ServiceProxy
        cid = ServiceProxy('MediumSize/BodyHub/GetMasterID',
                           SrvTLSstring)('get').data
    except:
        cid = 2

    rospy.Subscriber('/camera/color/image_raw', Image, image_callback)

    print("等待摄像头...")
    spin_thread = threading.Thread(target=rospy.spin, daemon=True)
    spin_thread.start()

    start = time.time()
    while latest_frame[0] is None and time.time() - start < 5:
        time.sleep(0.1)

    if latest_frame[0] is None:
        print("摄像头未就绪")
        exit()
    print("摄像头就绪")

    print("\n=== 情绪感知测试 ===")
    input("按回车开始...")
    emotion = scan_and_detect_emotion(pub, cid)
    print(f"\n最终情绪：{emotion}")
