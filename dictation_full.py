#!/usr/bin/env python3
# dictation_full.py - ROS节点版本（含动态麦克风、错题本过滤、稳定版）
import sys
import rospy
import rospkg
import cv2
import numpy as np
import time
import json
import random
import os
import subprocess
import threading
import vosk
import pyaudio
sys.path.append(rospkg.RosPack().get_path('leju_lib_pkg'))
from sensor_msgs.msg import Image
from std_msgs.msg import String
from cv_bridge import CvBridge
from bodyhub.msg import JointControlPoint
from bodyhub.srv import SrvTLSstring
import motion.bodyhub_client as bodycli
sys.path.insert(0, '/home/lemon/robot_ws/dictation')
from character_judge import judge_character

bridge = CvBridge()
latest_frame = [None]
is_busy = [False]

PAPER_THRESHOLD = 0.06
SAVE_PATH = '/home/lemon/robot_ws/dictation/live_capture.jpg'
WRONG_BOOK_PATH = '/home/lemon/robot_ws/dictation/wrong_book.json'
VOSK_MODEL_PATH = '/home/lemon/robot_ws/dictation/vosk-model-small-cn-0.22'
TRIGGER_KEYWORDS = ['写好了', '好了', '开始', '写完了', '完成', '好']

VOSK_MODEL = None
VOSK_REC = None
result_pub = None
pub = None
control_id = 2
MIC_INDEX = 16
MIC_CHANNELS = 1
MIC_RATE = 44100

# =====================
# 动态查找麦克风
# =====================
def find_mic():
    p = pyaudio.PyAudio()
    priority = ['pulse', 'Bothlent', 'USB PnP']
    found = {name: None for name in priority}

    for i in range(p.get_device_count()):
        try:
            d = p.get_device_info_by_index(i)
            if d['maxInputChannels'] > 0:
                for name in priority:
                    if name in d['name'] and found[name] is None:
                        found[name] = {
                            'index': i,
                            'channels': min(int(d['maxInputChannels']), 8),
                            'rate': 16000 if 'Bothlent' in name else 44100
                        }
        except:
            continue
    p.terminate()

    for name in priority:
        if found[name]:
            info = found[name]
            print(f"[麦克风] 使用：{name}，索引={info['index']}，"
                  f"声道={info['channels']}，采样率={info['rate']}")
            return info['index'], info['channels'], info['rate']

    print("[麦克风] 未找到合适设备，使用默认")
    return 16, 1, 44100

# =====================
# 语音播报
# =====================
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
        print(f"[TTS错误] {e}")
        try:
            subprocess.run(['espeak-ng', '-v', 'zh', '-s', '130', text])
        except:
            pass

# =====================
# 错题本
# =====================
def load_wrong_book():
    if os.path.exists(WRONG_BOOK_PATH):
        with open(WRONG_BOOK_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_wrong_book(book):
    with open(WRONG_BOOK_PATH, 'w', encoding='utf-8') as f:
        json.dump(book, f, ensure_ascii=False, indent=2)

def update_wrong_book(target, is_correct):
    book = load_wrong_book()
    if target not in book:
        book[target] = {'wrong': 0, 'correct': 0}
    if is_correct:
        book[target]['correct'] += 1
    else:
        book[target]['wrong'] += 1
    save_wrong_book(book)

def get_wrong_chars(mode='char'):
    book = load_wrong_book()
    if mode == 'char':
        valid = set()
        for level in WORD_BANK.values():
            valid.update(level.keys())
    else:
        valid = None
    wrongs = {}
    for k, v in book.items():
        if v['wrong'] > 0:
            if valid is None or k in valid:
                wrongs[k] = v
    return sorted(wrongs.keys(), key=lambda x: wrongs[x]['wrong'], reverse=True)

# =====================
# 汉字词库（三级）
# =====================
WORD_BANK = {
    1: {
        '一': '一字，一横，从左写到右，写平就好',
        '二': '二字，两横，上面一横短，下面一横长',
        '三': '三字，三横，上下两横短，中间最短',
        '十': '十字，先写一横，再写一竖，竖在横中间',
        '人': '人字，先写一撇，再写一捺，顶端交叉',
        '口': '口字，先左竖，再上横，然后右竖，最后下横',
        '八': '八字，先写左撇，再写右捺，两笔分开',
        '工': '工字，先写上横，再写竖，最后写下横',
    },
    2: {
        '山': '山字，三竖，先写左边短竖，再写中间长竖，最后右边短竖',
        '水': '水字，先写竖钩，再写左撇，然后右边两点',
        '火': '火字，先写两点，再写人字，撇捺要舒展',
        '土': '土字，先写短横，再写竖，最后写下面长横',
        '木': '木字，先写横，再写竖，然后左撇右捺',
        '日': '日字，先左竖，上横，右竖，中横，下横，像小方格',
        '月': '月字，先撇，再折，然后两横在里面',
        '大': '大字，先写横，再写竖，然后左撇右捺，要舒展',
        '上': '上字，先写短横，再写竖，最后写长横',
        '下': '下字，先写长横，再写竖，最后写一点',
    },
    3: {
        '手': '手字，三横一竖再加一撇，三横要平行',
        '耳': '耳字，先写横折，再写三横，最后一横最长',
        '目': '目字，先写竖折，再写三横，中间两横短',
        '田': '田字，先写大方框，再在里面加一横一竖',
        '左': '左字，先写一横一撇，再写工字',
        '右': '右字，先写一横一撇，再写口字',
        '头': '头字，先写两横，再写一撇一捺，最后两点',
        '足': '足字，先写口字，再写下面的捺折和竖弯',
    }
}

def get_teaching(char):
    for level in [1, 2, 3]:
        if char in WORD_BANK[level]:
            return WORD_BANK[level][char]
    return f"请认真写{char}这个字"

# =====================
# 图像回调
# =====================
def image_callback(msg):
    latest_frame[0] = bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

# =====================
# 头部控制
# =====================
def set_head(horizontal=0, vertical=0):
    vertical = max(-25, min(25, vertical))
    horizontal = max(-75, min(75, horizontal))
    pub.publish(positions=[horizontal, vertical], mainControlID=control_id)
    rospy.sleep(0.5)

# =====================
# 语音模型初始化
# =====================
def init_vosk():
    global VOSK_MODEL, VOSK_REC
    print("[初始化] 加载语音识别模型...")
    VOSK_MODEL = vosk.Model(VOSK_MODEL_PATH)
    VOSK_REC = vosk.KaldiRecognizer(VOSK_MODEL, MIC_RATE)
    print("[初始化] 语音模型加载完成")

# =====================
# 语音关键词监听
# =====================
def listen_for_keyword(timeout=30):
    VOSK_REC.Reset()
    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=MIC_CHANNELS,
        rate=MIC_RATE,
        input=True,
        input_device_index=MIC_INDEX,
        frames_per_buffer=8000
    )
    print(f"[监听] 等待关键词（{timeout}秒内）...")
    start_time = time.time()
    try:
        while time.time() - start_time < timeout:
            data = stream.read(4000, exception_on_overflow=False)
            if MIC_CHANNELS > 1:
                audio_array = np.frombuffer(data, dtype=np.int16)
                mono = audio_array[::MIC_CHANNELS].tobytes()
            else:
                mono = data
            if VOSK_REC.AcceptWaveform(mono):
                result = json.loads(VOSK_REC.Result())
                text = result.get('text', '').replace(' ', '')
                if text:
                    print(f"[识别] {text}")
                    for keyword in TRIGGER_KEYWORDS:
                        if keyword in text:
                            print(f"✅ 检测到关键词：{keyword}")
                            return True
            else:
                partial = json.loads(VOSK_REC.PartialResult()).get(
                    'partial', '').replace(' ', '')
                if partial:
                    print(f"[识别中] {partial}", end='\r')
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
    print("\n[超时] 未检测到关键词")
    return False

# =====================
# 纸张检测
# =====================
def detect_paper(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    contours = cv2.findContours(binary, cv2.RETR_EXTERNAL,
                                cv2.CHAIN_APPROX_SIMPLE)[-2]
    if not contours:
        return False, 0
    largest = max(contours, key=cv2.contourArea)
    ratio = cv2.contourArea(largest) / (frame.shape[0] * frame.shape[1])
    return ratio > PAPER_THRESHOLD, ratio

# =====================
# 自动扫描找纸张
# =====================
def auto_scan_and_capture():
    speak("好的，让我看看你写的")
    for angle in [0, 5, 10, 15, 20, 25]:
        set_head(horizontal=0, vertical=angle)
        rospy.sleep(0.3)
        if latest_frame[0] is None:
            continue
        frame = latest_frame[0].copy()
        found, ratio = detect_paper(frame)
        print(f"[扫描] 角度={angle}度，占比={ratio:.2%}，找到={found}")
        if found:
            cv2.imwrite(SAVE_PATH, frame)
            speak("我看到了，稍等一下")
            return SAVE_PATH
    speak("我没有看到，请把纸举高一点")
    set_head(0, 0)
    return None

# =====================
# 情绪感知
# =====================
def check_emotion_and_respond(qtype, teaching, answer):
    try:
        from emotion_detector import scan_and_detect_emotion
        print("\n[情绪] 扫描孩子表情...")
        emotion = scan_and_detect_emotion(pub, control_id, latest_frame)
        print(f"[情绪] 结果：{emotion}")
        if emotion == 'confused':
            speak("看起来你有点困惑，我再给你讲一遍")
            if qtype == 'char':
                speak(teaching)
            else:
                speak(f"正确答案是{answer}，我们再想想")
        elif emotion == 'happy':
            speak("看到你笑得这么开心，你真棒！")
    except Exception as e:
        print(f"[情绪] 跳过：{e}")
        set_head(0, 0)

# =====================
# 发布结果
# =====================
def publish_result(target, is_correct, feedback):
    result = json.dumps({
        "target": target,
        "correct": is_correct,
        "feedback": feedback
    }, ensure_ascii=False)
    result_pub.publish(result)
    print(f"[发布] /vision/result: {result}")

# =====================
# 核心听写流程
# =====================
def run_dictation(qtype, target):
    if qtype == 'char':
        teaching = get_teaching(target)
        speak(f"请写这个字：{target}")
        speak(teaching)
    else:
        speak(f"请写数字或答案：{target}")
        teaching = ''

    speak("写好了告诉我")

    triggered = listen_for_keyword(timeout=30)
    if not triggered:
        speak("我来帮你拍一张")

    image_path = auto_scan_and_capture()
    if image_path is None:
        publish_result(target, False, "未能拍到照片")
        return

    print("\n[判断中...]")
    result = judge_character(image_path, target)
    is_correct = result['correct']
    feedback = result['feedback']

    print(f"是否正确：{'✅' if is_correct else '❌'}")
    print(f"反馈：{feedback}")
    speak(feedback)

    update_wrong_book(target, is_correct)
    publish_result(target, is_correct, feedback)

    if not is_correct:
        check_emotion_and_respond(qtype, teaching, target)

    set_head(0, 0)

# =====================
# /dictation/start 话题回调
# =====================
def start_callback(msg):
    if is_busy[0]:
        print("[警告] 当前正在执行听写，忽略新请求")
        return

    def execute():
        is_busy[0] = True
        try:
            data = msg.data.strip()
            print(f"\n[收到任务] {data}")

            if ':' in data:
                qtype, target = data.split(':', 1)
            else:
                qtype = data
                target = None

            if qtype == 'char':
                if target is None:
                    bank = WORD_BANK[1]
                    target = random.choice(list(bank.keys()))
                run_dictation('char', target)
            elif qtype == 'digit':
                if target is None:
                    target = str(random.randint(0, 9))
                run_dictation('digit', target)
            else:
                print(f"[错误] 未知任务类型：{qtype}")
        except Exception as e:
            print(f"[错误] 执行失败：{e}")
        finally:
            is_busy[0] = False

    threading.Thread(target=execute, daemon=True).start()

# =====================
# 主入口
# =====================
if __name__ == '__main__':
    rospy.init_node('dictation_node', anonymous=False)
    bodycli.BodyhubClient(2).ready()

    rospy.Subscriber('/camera/color/image_raw', Image, image_callback)
    rospy.sleep(1)

    pub = rospy.Publisher('MediumSize/BodyHub/HeadPosition',
                          JointControlPoint, queue_size=10)
    rospy.sleep(0.5)
    try:
        rospy.wait_for_service('MediumSize/BodyHub/GetMasterID', 1)
        client = rospy.ServiceProxy('MediumSize/BodyHub/GetMasterID', SrvTLSstring)
        control_id = client('get').data
    except:
        control_id = 2
    print(f"[初始化] 头部控制就绪，controlID={control_id}")

    result_pub = rospy.Publisher('/vision/result', String, queue_size=10)
    rospy.Subscriber('/dictation/start', String, start_callback)

    # 动态查找麦克风
    MIC_INDEX, MIC_CHANNELS, MIC_RATE = find_mic()
    init_vosk()

    print("\n=== 听写节点已启动 ===")
    print("订阅：/dictation/start")
    print("发布：/vision/result")
    speak("听写系统已就绪，等待指令")

    rospy.spin()