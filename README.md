# UWB Positioning & Visual Recognition System

本项目集成了 **UWB (Ultra-Wideband) 高精度定位解算** 与 **视觉图像处理/大模型识别** 两个主要模块。旨在通过 UWB 数据进行位置追踪，并利用鱼眼相机结合多模态大模型（Qwen-VL）进行环境感知与视觉识别。

## 📁 项目结构说明

### 1. UWB 定位核心模块 (Root Directory)
主要负责解析 UWB 硬件输出的原始二进制数据，并进行坐标解算与精度评估。

- **`main.py`**: 主程序入口。
  -读取 UWB 二进制数据文件。
  - 调用 `uwb_parser` 解析距离信息。
  - 调用 `uwb_solver` 使用最小二乘法 (Least Squares) 或非线性优化解算标签 (Tag) 的坐标 (x, y)。
- **`uwb_parser.py`**: 二进制数据解析器。负责将硬件传输的字节流解析为距离、锚点 ID 等结构化数据。
- **`uwb_solver.py`**: 定位算法实现。包含最小二乘法 (`solve_position_ls`) 和非线性最小二乘 (`solve_position_nlls`) 等解算逻辑，支持三维斜距改正。
- **`uwb_eval.py`**: 精度评估工具。计算解算坐标与真值 (Ground Truth) 之间的误差。
- **`coord_tool.py`**: 坐标转换与辅助工具。
- **`uwb_dump.py`**: 数据转储工具，用于调试或查看原始数据内容。

### 2. 视觉处理模块 (`visual/` 文件夹) 👁️
**这是移植时需要特别关注的部分。** 该模块处理全景相机图像，并接入大模型进行语义识别。

- **`fisheye_converter.py` (鱼眼图像展开)**:
  - **功能**: 专门处理**圆形鱼眼 (Circular Fisheye)** 全景图片。
  - **原理**: 将畸变的圆形鱼眼图像，通过几何投影（等距投影模型）展开为符合人眼视觉习惯的透视投影图像（如前、后、左、右四个视角的平面图）。
  - **目的**: 展开后的图像消除了鱼眼畸变，可以直接输入给视觉大模型 (如 Qwen-VL, GPT-4V) 进行更准确的物体识别和场景理解，同时也方便人工监视。
  - **特点**: 采用简化的几何模型（圆心、半径、视场角），无需复杂的棋盘格标定即可满足大模型识别需求。

- **`qwen_recognizer.py` (千问大模型识别)**:
  - **功能**: 封装了阿里云百炼 (DashScope) 的 API 接口，专门对接 **Qwen-VL** 系列视觉大模型。
  - **用法**: 支持将本地图像文件自动编码为 Base64 格式并发送给云端模型。
  - **配置**: 需要配置环境变量 `DASHSCOPE_API_KEY` 才能使用。
  - **用途**: 用于对 `fisheye_converter.py` 展开后的图像进行内容描述、物体检测或场景分析。

## 🚀 移植与环境配置

### 1. 安装依赖
在新服务器上，请使用项目根目录下的 `requirements.txt` 安装所需 Python 库：

```bash
conda create -n uwb_env python=3.13
conda activate uwb_env
pip install -r requirements.txt
```

**关键依赖包括：**
- `opencv-python`: 用于图像处理（鱼眼展开）。
- `openai`: 用于调用 Qwen-VL 大模型接口。
- `numpy`: 用于矩阵运算和坐标解算。
- `matplotlib`: 用于绘图分析。

### 2. 环境变量设置
为了使用视觉模块中的大模型功能，必须在新服务器上设置 API Key：

```bash
export DASHSCOPE_API_KEY="your_api_key_here"
```
*(请将 `your_api_key_here` 替换为实际的阿里云 DashScope API Key)*

## 🛠️ 使用示例

### UWB 定位解算
```bash
python main.py data.bin --limit 100 --truth 150.0,200.0,2.5
```

### 鱼眼图片转换
```bash
cd visual
python fisheye_converter.py
# (需在脚本内指定输入图片路径)
```

### 视觉识别调用 (Python)
```python
from visual.qwen_recognizer import QwenVisionClient

client = QwenVisionClient()
response = client.recognize_image("path/to/image.jpg", prompt="描述这张图片里的内容")
print(response)
```

## 🤖 机器狗实机新增内容（迁移重点）

以下内容为在 Unitree 机器狗（Ubuntu 20.04, aarch64）上新增/验证过的实机方案，用于 FLIR GigE 鱼眼相机采集。

### 1. FLIR GigE 相机接入方案

- 结论：在当前环境中，Spinnaker Debian 包可用 C/C++，未包含 `PySpin`，因此采用 **ROS C++ 发布 + Python 订阅** 方案。
- 相机 IP：当前实机配置为 `192.168.123.100`（与机器狗 `eth0` 同网段）。
- ROS 图像话题：`/camera/fisheye/image_raw`

### 2. 新增文件位置

- Python 订阅与一键启动脚本：`visual/ros_cam_driver.py`
  - 自动拉起 `roscore`
  - 自动拉起 FLIR C++ 发布节点
  - 订阅 `/camera/fisheye/image_raw` 并保存 `camera_test_snapshot.jpg`

- C++ 发布代码（为便于迁移，已复制到当前仓库）：
  - `flir_ros_cpp_driver/flir_gige_driver/src/flir_gige_publisher.cpp`
  - `flir_ros_cpp_driver/flir_gige_driver/launch/flir_gige_publisher.launch`
  - `flir_ros_cpp_driver/flir_gige_driver/CMakeLists.txt`
  - `flir_ros_cpp_driver/flir_gige_driver/package.xml`

说明：实机编译运行工作区仍在 `/home/unitree/go2_3D_nav/nav`，上述目录是为打包迁移保留的同步副本。

### 3. FLIR 发布节点增强点（已实机验证）

- 相机发现重试（缓解 GigE 枚举抖动）
- 初始化重试（缓解 `[-1010]`/`[-1015]`）
- GigE 传输参数调优：`GevSCPSPacketSize`、`GevSCPD`
- 强制采集模式：`TriggerMode=Off`、`AcquisitionMode=Continuous`
- 流缓冲模式：`StreamBufferHandlingMode=NewestOnly`
- `roslaunch` 自动 `respawn`（进程异常自动重启）

### 4. 实机运行（一条命令）

```bash
python3 /home/unitree/UWB/visual/ros_cam_driver.py
```

输出图片默认保存在当前执行目录：`camera_test_snapshot.jpg`。

### 5. 网络与稳定性建议

- 推荐 `eth0` 保持单一工作网段（避免多网段地址并存造成 GEV Interface 重复/误判）。
- 推荐 `MTU=1500` 先求稳：

```bash
sudo ip link set dev eth0 mtu 1500
```

- 若出现丢包或初始化偶发失败，优先检查：
  - `ping -I eth0 192.168.123.100`
  - `/opt/spinnaker/bin/Enumeration`

