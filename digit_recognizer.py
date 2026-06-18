# digit_recognizer.py
import cv2
import numpy as np
import urllib.request
import os

# =====================
# 模型下载
# =====================
MODEL_PATH = "mnist.onnx"
MODEL_URL = "https://github.com/onnx/models/raw/main/validated/vision/classification/mnist/model/mnist-12.onnx"

def download_model():
    if not os.path.exists(MODEL_PATH):
        print("正在下载模型...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("下载完成")

# =====================
# 图像预处理（MNIST标准化）
# =====================
def preprocess_image(image_path):
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"找不到图片：{image_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    largest = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest)
    digit_roi = binary[y:y+h, x:x+w]

    # 保持长宽比缩放到20x20以内，放到28x28中央
    scale = 20.0 / max(w, h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    resized = cv2.resize(digit_roi, (new_w, new_h), interpolation=cv2.INTER_AREA)

    canvas = np.zeros((28, 28), dtype=np.uint8)
    x_offset = (28 - new_w) // 2
    y_offset = (28 - new_h) // 2
    canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized

    img_array = canvas.astype(np.float32) / 255.0
    img_array = img_array.reshape(1, 1, 28, 28)
    return img_array

def correct_five_six(image_path, predicted):
    """
    检测图中是否有封闭圆圈
    有封闭圆圈 → 可能是6，没有 → 保持5
    """
    try:
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        _, binary = cv2.threshold(img, 128, 255,
                                  cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # RETR_CCOMP可以检测内外层轮廓
        contours, hierarchy = cv2.findContours(
            binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
        )

        if hierarchy is None:
            return predicted

        # 如果存在内层轮廓（子轮廓），说明有封闭圆圈
        has_inner_loop = any(h[3] != -1 for h in hierarchy[0])

        if has_inner_loop:
            print("[补救] 检测到封闭圆圈，5修正为6")
            return 6

        return predicted

    except Exception:
        return predicted
    

# =====================
# 数字识别
# =====================
def recognize_digit(image_path):
    try:
        download_model()
        net = cv2.dnn.readNetFromONNX(MODEL_PATH)

        input_data = preprocess_image(image_path)
        if input_data is None:
            return ""

        net.setInput(input_data)
        output = net.forward()

        digit = int(np.argmax(output))
        confidence = float(output[0][digit])
        print(f"[识别] 数字={digit}, 置信度={confidence:.2f}")

        if confidence < 0.5:
            return ""
        if digit == 5:
            digit = correct_five_six(image_path, digit)
        
        return str(digit)

    except Exception as e:
        print(f"[OCR错误] {e}")
        return ""

# =====================
# 对错判断
# =====================
ERROR_HINTS = {
    ("1", "7"): "1不需要上面那一横，那是7的写法",
    ("7", "1"): "7需要在上面加一横，你写的更像1",
    ("6", "9"): "6的开口朝下，9的开口朝上，注意方向",
    ("9", "6"): "9的开口朝上，6的开口朝下，注意方向",
    ("3", "8"): "3是开口的，8是封闭的两个圆",
    ("8", "3"): "8需要把两个圆封闭，你写的像3",
}

def judge_digit(image_path, target):
    recognized = recognize_digit(image_path)

    if recognized == "":
        return {
            "correct": False,
            "recognized": "",
            "feedback": "没有识别到数字，请写大一点，检查光线是否充足"
        }

    if recognized == str(target):
        return {
            "correct": True,
            "recognized": recognized,
            "feedback": f"正确！{target}写得很好！"
        }
    else:
        hint = ERROR_HINTS.get((recognized, str(target)), "")
        feedback = f"写错了，你写的像{recognized}。{hint}" if hint else \
                   f"写错了，你写的是{recognized}，应该是{target}，再试一次吧"
        return {
            "correct": False,
            "recognized": recognized,
            "feedback": feedback
        }

# =====================
# 摄像头拍照
# =====================
def capture_from_camera(save_path='capture.jpg', camera_index=0):
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError("无法打开摄像头")

    print("摄像头已开启，按【空格键】拍照，按【q】退出")
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        key = cv2.waitKey(1) & 0xFF
        if key == ord(' '):
            cv2.imwrite(save_path, frame)
            print(f"已拍照：{save_path}")
            break
        elif key == ord('q'):
            save_path = None
            break

    cap.release()
    return save_path

# =====================
# 批量测试
# =====================
def batch_test():
    print("\n=== 批量测试 0-9 ===")
    correct = 0
    for i in range(10):
        path = f"test_{i}.png"
        if os.path.exists(path):
            result = judge_digit(path, str(i))
            status = "✅" if result['correct'] else f"❌(识别为{result['recognized']})"
            print(f"数字{i}：{status}")
            if result['correct']:
                correct += 1
    print(f"\n准确率：{correct}/10")

# =====================
# 测试入口
# =====================
if __name__ == '__main__':
    print("=== 数字识别测试 ===")
    print("1. 使用摄像头拍照")
    print("2. 使用本地图片")
    print("3. 批量测试0-9")
    choice = input("请输入1/2/3：").strip()

    if choice == '3':
        batch_test()
    elif choice == '1':
        image_path = capture_from_camera()
        if image_path is None:
            exit()
        target = input("目标数字是什么？").strip()
        result = judge_digit(image_path, target)
        print(f"\n识别结果：{result['recognized']}")
        print(f"是否正确：{'✅' if result['correct'] else '❌'}")
        print(f"反馈：{result['feedback']}")
    else:
        image_path = input("请输入图片路径：").strip()
        target = input("目标数字是什么？").strip()
        result = judge_digit(image_path, target)
        print(f"\n识别结果：{result['recognized']}")
        print(f"是否正确：{'✅' if result['correct'] else '❌'}")
        print(f"反馈：{result['feedback']}")