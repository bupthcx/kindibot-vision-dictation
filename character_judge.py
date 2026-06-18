# character_judge.py
import base64
import json
import requests
import time
import os
import subprocess
import cv2
import numpy as np

API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
MODEL   = "qwen-vl-plus"

# =====================
# 字形特征库
# =====================
CHAR_FEATURES = {
    '一': '只有一横，要写平，不能倾斜',
    '二': '两横，上短下长，两横要平行',
    '三': '三横，上下两横短，中间一横最短，三横间距要均匀',
    '十': '一横一竖，竖在横的正中间，成十字形',
    '人': '一撇一捺，两笔在顶端交叉，撇向左下，捺向右下',
    '口': '四条边围成方形，四个角要封闭，不能留缺口',
    '八': '左撇右捺，两笔分开不相交，撇短捺长',
    '工': '上横短，下横长，中间竖连接两横中间',
    '山': '三竖，左右两竖短，中间竖最高，底部三竖连在一起',
    '水': '中间竖钩，左边一撇，右边两点，共四笔',
    '火': '下面两点，上面一撇一捺，像火苗形状，没有竖',
    '土': '上面短横，中间竖，下面长横，竖在两横中间',
    '木': '一横一竖，左撇右捺，横在竖上方，撇捺在竖下方',
    '日': '像长方形，里面有一横分成两格，共五笔',
    '月': '左边一撇，右边折钩，里面两横，像月亮形状',
    '大': '一横一竖，左撇右捺，撇捺在横的下方要舒展',
    '上': '下面长横，中间短横，上面一竖',
    '下': '上面长横，中间一竖，下面一点',
    '手': '三横一竖一撇，三横要平行，竖穿过三横',
    '耳': '横折加三横，最后一横最长要超出左边',
    '目': '像长方形，里面两横，共六笔',
    '田': '大方框里加一横一竖，形成四个小格子',
    '左': '上面一横一撇，下面工字',
    '右': '上面一横一撇，下面口字',
    '头': '上面两横，中间一撇一捺，下面两点',
    '足': '上面口字，下面竖加横折钩再加一捺',
}

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
# 汉字教学内容库
# =====================
TEACHING_SCRIPTS = {
    "山": "山字，三竖，先写左边短竖，再写中间长竖，最后写右边短竖，中间竖最高",
    "日": "日字，先写左竖，再写上横，然后右竖，中间横，最后下横，像一个小方格",
    "口": "口字，先写左竖，再写上横，然后右竖，最后下横，是一个正方形",
    "木": "木字，先写一横，再写竖，然后左撇，最后右捺，撇和捺要对称",
    "人": "人字，只有两笔，先写一撇，再写一捺，两笔要在顶端交叉",
    "大": "大字，先写横，再写竖，然后左撇，最后右捺，撇捺要舒展",
    "一": "一字，就是一横，从左到右，写平就好",
    "二": "二字，两横，上面一横短，下面一横长",
    "三": "三字，三横，上下两横短，中间一横最短",
    "火": "火字，先写两点，再写人字，撇捺要舒展",
    "水": "水字，先写竖钩，再写左撇，然后右边两点",
    "土": "土字，先写横，再写竖，最后写下面长横",
    "十": "十字，先写一横，再写一竖，竖在横中间",
    "八": "八字，先写左撇，再写右捺，两笔分开",
    "工": "工字，先写上横，再写竖，最后写下横",
    "月": "月字，先撇，再折，然后两横在里面",
    "上": "上字，先写短横，再写竖，最后写长横",
    "下": "下字，先写长横，再写竖，最后写一点",
    "手": "手字，三横一竖再加一撇，三横要平行",
    "耳": "耳字，先写横折，再写三横，最后一横最长",
    "目": "目字，先写竖折，再写三横，中间两横短",
    "田": "田字，先写大方框，再在里面加一横一竖",
    "左": "左字，先写一横一撇，再写工字",
    "右": "右字，先写一横一撇，再写口字",
    "头": "头字，先写两横，再写一撇一捺，最后两点",
    "足": "足字，先写口字，再写下面的捺折和竖弯",
}

def get_teaching_script(char):
    return TEACHING_SCRIPTS.get(char, f"请认真写{char}这个字，注意笔画顺序")

# =====================
# 图像编码
# =====================
def encode_image(image_path):
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')

# =====================
# 图像增强（弱光处理）
# =====================
def enhance_image(image_path):
    img = cv2.imread(image_path)
    if img is None:
        return image_path
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    avg_brightness = gray.mean()
    print(f"[图像] 平均亮度：{avg_brightness:.1f}")
    if avg_brightness > 100:
        return image_path
    print("[图像] 亮度不足，进行增强...")
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    enhanced = cv2.merge([l, a, b])
    enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
    kernel = np.array([[0, -0.5, 0],
                       [-0.5, 3, -0.5],
                       [0, -0.5, 0]])
    enhanced = cv2.filter2D(enhanced, -1, kernel)
    enhanced_path = image_path.replace('.jpg', '_enhanced.jpg')
    cv2.imwrite(enhanced_path, enhanced)
    return enhanced_path

# =====================
# VLM汉字判断
# =====================
def judge_character(image_path, target_char, max_retries=2):
    image_path = enhance_image(image_path)
    image_data = encode_image(image_path)
    char_feature = CHAR_FEATURES.get(target_char, f"这个字是{target_char}")

    prompt = f"""你是一位鼓励型幼儿写字辅导老师。
图中是一个5-8岁孩子手写的内容，目标是写"{target_char}"。

判断标准（请宽松判断）：
- correct=true：整体上能认出是"{target_char}"这个字，即使笔画不够规范
- correct=false：完全写成别的字，或缺少主要笔画导致完全不像

反馈要求：
- 如果写对了：给一句鼓励，可以指出一个可以更好的地方
- 如果写错了：针对"{target_char}"的特征（{char_feature}），用一句话说明主要问题
- 语言要简单温柔，适合5-8岁孩子

只返回JSON：
{{"correct": true或false, "feedback": "一句话反馈"}}"""

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ],
        "max_tokens": 200
    }

    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                API_URL, 
                headers = {
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json; charset=utf-8"
                },
                data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                timeout=15,
                proxies={"http": None, "https": None}
            )
            response.raise_for_status()
            content = response.json()['choices'][0]['message']['content'].strip()
            content = content.replace('```json', '').replace('```', '').strip()
            result = json.loads(content)
            if 'correct' not in result or 'feedback' not in result:
                raise ValueError("返回格式不完整")
            return result

        except json.JSONDecodeError:
            print(f"[第{attempt+1}次] JSON解析失败：{content}")
        except requests.exceptions.Timeout:
            print(f"[第{attempt+1}次] 请求超时")
        except Exception as e:
            print(f"[第{attempt+1}次] 错误：{e}")

        if attempt < max_retries:
            print("重试中...")
            time.sleep(1)

    return {
        "correct": False,
        "feedback": "我现在看不太清楚，请把字写大一点让我再看看"
    }

# =====================
# ROS摄像头拍照
# =====================
def capture_from_ros(save_path='/home/lemon/robot_ws/dictation/live_capture.jpg',
                     topic='/camera/color/image_raw', timeout=5):
    try:
        import rospy
        from sensor_msgs.msg import Image
        from cv_bridge import CvBridge
        bridge = CvBridge()
        captured = [False]

        def callback(msg):
            if not captured[0]:
                try:
                    frame = bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
                    cv2.imwrite(save_path, frame)
                    print(f"已拍照：{save_path}")
                    captured[0] = True
                except Exception as e:
                    print(f"图像转换失败：{e}")

        rospy.init_node('dictation_capture', anonymous=True)
        sub = rospy.Subscriber(topic, Image, callback)
        start = time.time()
        while not captured[0]:
            if time.time() - start > timeout:
                print("拍照超时")
                return None
            time.sleep(0.1)
        sub.unregister()
        return save_path
    except Exception as e:
        print(f"[ROS拍照错误] {e}")
        return None

# =====================
# 完整教学流程
# =====================
def teaching_session(target_char, image_path=None):
    print(f"\n{'='*40}")
    print(f"目标汉字：【{target_char}】")
    print(f"{'='*40}")

    teaching_text = get_teaching_script(target_char)
    print(f"\n[教学] {teaching_text}")
    speak(teaching_text)

    if image_path is None:
        input("\n孩子写完后按回车键拍照...")
        image_path = capture_from_ros()
        if image_path is None:
            speak("拍照失败，请重试")
            return

    print("\n[判断中，请稍候...]")
    result = judge_character(image_path, target_char)

    print(f"\n--- 判断结果 ---")
    print(f"是否正确：{'✅ 正确' if result['correct'] else '❌ 错误'}")
    print(f"反馈内容：{result['feedback']}")
    speak(result['feedback'])
    return result

# =====================
# 测试入口
# =====================
if __name__ == '__main__':
    print("=== 汉字判断测试 ===")
    print(f"支持的汉字：{list(TEACHING_SCRIPTS.keys())}")
    print("\n1. 完整教学流程（ROS摄像头）")
    print("2. 使用本地图片测试")
    choice = input("请输入1或2：").strip()

    char = input("请输入目标汉字：").strip()

    if choice == '2':
        path = input("请输入图片路径：").strip()
        if not os.path.exists(path):
            print(f"找不到图片：{path}")
            exit()
        teaching_session(char, image_path=path)
    else:
        teaching_session(char)
