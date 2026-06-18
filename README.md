# KindiBot K宝视觉听写模块

面向 Roban 人形机器人的 ROS 视觉模块，完成儿童听写场景中的出题播报、语音触发、相机拍照、Qwen-VL 书写判断、错题记录和情绪反馈。

## 目录

- [功能亮点](#功能亮点)
- [部署路径](#部署路径)
- [运行环境](#运行环境)
- [环境变量](#环境变量)
- [启动流程](#启动流程)
- [演示前检查](#演示前检查)
- [ROS 接口](#ros-接口)
- [文件说明](#文件说明)
- [量化测试结果](#量化测试结果)
- [系统性能](#系统性能)
- [注意事项](#注意事项)

## 功能亮点

- **完整听写闭环:** 订阅听写任务后自动播报题目和笔顺，等待孩子说“写好了”，再低头扫描纸张并拍照判断。
- **视觉语言模型判断:** 使用 DashScope/Qwen-VL 对汉字和数字书写进行宽松、鼓励式评价，返回结构化 JSON 结果。
- **情绪感知反馈:** 答错后调用人脸扫描和表情识别，按 `happy`、`confused`、`neutral` 给出不同反馈。
- **ROS 模块解耦:** 通过 `/dictation/start` 接收任务，通过 `/vision/result` 发布判断结果，便于语音模块和动作模块接入。
- **演示脚本齐全:** `demo_runner.py` 控制课堂展示节奏，`monitor.sh` 和测试结果文件用于说明准确率与资源占用。

## 部署路径

机器人部署目录：

```bash
/home/lemon/robot_ws/dictation/
```

本地备份目录：

```text
E:\python data\pythonProject\ROBOT\robot_dictation_remote\
```

## 运行环境

- Ubuntu 20.04
- ROS Noetic
- Python 3.8
- Roban 机器人 bodyhub 控制环境
- RealSense 彩色相机话题：`/camera/color/image_raw`
- Python 依赖：`opencv-python`、`numpy`、`requests`、`vosk`、`pyaudio`
- 系统命令：`edge-tts`、`play`

Vosk 中文模型 `vosk-model-small-cn-0.22` 不包含在仓库中，需要放在机器人部署目录下。

## 环境变量

视觉判断和情绪识别需要 DashScope API Key。不要把真实 Key 写入代码或提交到 GitHub。

```bash
export DASHSCOPE_API_KEY="你的DashScope API Key"
```

仓库提供 `.env.example` 作为变量名参考。

## 启动流程

终端 1：启动机器人底层控制，保持运行。

```bash
startrobot
```

等待看到：

```text
bodyhubState: ready
```

终端 2：启动听写视觉节点，保持运行。

```bash
cd ~/robot_ws/dictation
sss
bash start_dictation.sh
```

等待看到：

```text
听写节点已启动
```

终端 3：启动演示控制脚本。

```bash
cd ~/robot_ws/dictation
sss
python3 demo_runner.py
```

每道题准备好后按回车触发，机器人会自动完成播报、监听、拍照、判断和反馈。

## 演示前检查

确认相机帧率接近 30fps 后再开始录制：

```bash
rostopic hz /camera/color/image_raw
```

也可以手动触发单道题：

```bash
rostopic pub /dictation/start std_msgs/String "data: 'char:山'" --once
```

查看视觉模块输出：

```bash
rostopic echo /vision/result
```

## ROS 接口

| 方向 | 话题 | 类型 | 说明 |
|------|------|------|------|
| 订阅 | `/dictation/start` | `std_msgs/String` | 接收听写任务 |
| 发布 | `/vision/result` | `std_msgs/String` | 发布判断结果 JSON |
| 订阅 | `/camera/color/image_raw` | `sensor_msgs/Image` | 获取 RealSense 彩色图像 |
| 发布 | `MediumSize/BodyHub/HeadPosition` | `bodyhub/JointControlPoint` | 控制头部低头扫描和复位 |

`/dictation/start` 支持格式：

```text
char:山
digit:3
char
digit
```

`/vision/result` 输出格式：

```json
{"target":"山","correct":true,"feedback":"写得很好，三竖很清楚。"}
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `dictation_full.py` | 听写主节点，负责 ROS 订阅发布、TTS、语音监听、拍照、判断和反馈 |
| `character_judge.py` | Qwen-VL 书写判断模块，含图像增强和鼓励式反馈提示词 |
| `emotion_detector.py` | 情绪感知模块，负责扫描人脸并识别 `happy`、`confused`、`neutral` |
| `demo_runner.py` | 演示用题目序列控制脚本 |
| `digit_recognizer.py` | MNIST 数字识别备用模块，当前主流程统一使用 VLM 判断 |
| `head_control.py` | 头部控制测试脚本 |
| `start_dictation.sh` | 一键启动脚本，加载 ROS 环境并运行主节点 |
| `dictation.launch` | ROS launch 文件 |
| `quantitative_test.py` | 26 字量化测试脚本 |
| `monitor.sh` | CPU/内存性能监控脚本 |
| `test_results.json` | 量化测试结果 |
| `performance_log.csv` | 性能监控数据 |
| `wrong_book.json` | 错题本数据，运行时持续更新 |
| `mnist.onnx` | MNIST 模型，数字识别备用 |

## 量化测试结果

| 指标 | 结果 |
|------|------|
| 总准确率 | 25/26 = 96.2% |
| 简单字 | 8/8 = 100% |
| 中等字 | 10/10 = 100% |
| 难字 | 7/8 = 87.5% |
| 平均 VLM 响应时间 | 1.11 秒 |

## 系统性能

| 指标 | 实测结果 |
|------|----------|
| 空载 CPU | ~10% |
| 空载内存 | ~255MB |
| 峰值 CPU | 15.7% |
| 峰值内存 | ~357MB |
| 内存占总 RAM（7.5GB）比例 | 4.7% |

## 注意事项

- 真实 DashScope API Key 通过环境变量配置，不要写入源码。
- `vosk-model-small-cn-0.22` 模型目录未纳入 GitHub，可按需重新下载后放入部署目录。
- 演示时优先使用汉字题目，如 `char:山`、`char:一`、`char:手`；数字题目可作为扩展能力展示。
- `wrong_book.json` 是运行数据，演示前可以保留历史记录，也可以按需要清空后重新生成。

## License

Course project code. Add a license file before public reuse or redistribution.
