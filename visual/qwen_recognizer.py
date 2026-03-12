# -*- coding: utf-8 -*-
"""
千问大模型视觉识别工具
Qwen VL Image Recognizer

功能描述：
    封装了阿里云百炼 (DashScope) 的兼容 OpenAI 接口。
    支持发送本地图片或网络图片给 Qwen-VL 大模型进行视觉识别。

依赖：
    pip install openai

注意：
    1. 需要设置环境变量 DASHSCOPE_API_KEY，或在初始化时传入 api_key。
    2. 视觉任务必须使用 qwen-vl 系列模型 (如 qwen-vl-max, qwen-vl-plus)，不能使用 qwen-plus (纯文本)。
"""

import os
import base64
from openai import OpenAI
import mimetypes

class QwenVisionClient:
    def __init__(self, api_key="sk-a89da5daaf414d15a54c843300f91ff3", base_url="https://dashscope.aliyuncs.com/compatible-mode/v1", model="qwen-vl-max"):
        """
        初始化视觉模型客户端
        :param api_key: 阿里云 API Key。如果不传，尝试从环境变量 DASHSCOPE_API_KEY 读取。
        :param base_url: API 基础 URL。
        :param model: 模型名称，默认使用的是 qwen-vl-max (视觉能力最强)。
        """
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("未找到 API Key。请在代码中传入 api_key 或设置环境变量 DASHSCOPE_API_KEY。")
            
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=base_url
        )
        self.model = model

    def _encode_image(self, image_path):
        """
        将本地图片转换为 Base64 格式
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"找不到文件: {image_path}")
            
        # 自动推断 mime type (e.g., image/jpeg, image/png)
        mime_type, _ = mimetypes.guess_type(image_path)
        if mime_type is None:
            mime_type = "image/jpeg" # 默认

        with open(image_path, "rb") as image_file:
            base64_data = base64.b64encode(image_file.read()).decode('utf-8')
            
        return f"data:{mime_type};base64,{base64_data}"

    def analyze_image(self, image_source, prompt="图中描绘的是什么景象?", is_local_file=True):
        """
        识别图片内容
        :param image_source: 图片路径 (本地) 或 URL (网络)
        :param prompt: 提示词 (即你想问大模型什么)
        :param is_local_file: True 表示 image_source 是本地路径，False 表示是 URL
        :return: 大模型的回答文本
        """
        
        # 构造图片 URL 对象
        if is_local_file:
            print(f"正在编码本地图片: {image_source} ...")
            img_url = self._encode_image(image_source)
        else:
            img_url = image_source

        # 构造消息体
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": img_url
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        try:
            print(f"正在请求大模型 ({self.model})...")
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages
            )
            return completion.choices[0].message.content
            
        except Exception as e:
            return f"识别请求失败: {str(e)}"

    def recognize_image(self, image_source, prompt="请描述给的图片"):
        """
        兼容 README 示例的别名方法
        """
        return self.analyze_image(image_source, prompt=prompt, is_local_file=True)


# --- 使用示例 ---
if __name__ == "__main__":
    # 请确保您已设置环境变量，或在此处填入您的 Key
    # os.environ["DASHSCOPE_API_KEY"] = "sk-..."
    
    # 实例化客户端
    # 建议使用 qwen-vl-max 或 qwen-vl-plus 进行图片识别
    try:
        recognizer = QwenVisionClient(model="qwen-vl-max") 
        
        # 示例：假设我们想识别刚才转换出来的 鱼眼-前方 视角图
        # 这里使用一个假路径作为演示，请修改为真实路径
        local_img = "visual/output_views/view_front.jpg" 
        
        # 如果文件不存在，创建一个假的测试文件以便代码能跑通 (仅供演示)
        if not os.path.exists(local_img):
            import cv2
            import numpy as np
            os.makedirs(os.path.dirname(local_img), exist_ok=True)
            dummy = np.zeros((100,100,3), dtype=np.uint8)
            cv2.createText = "Test"
            cv2.imwrite(local_img, dummy)
            print(f"生成了测试图片: {local_img}")

        # 发起识别
        prompt = "这张图片里是否有白色的 UWB 基站？如果有，请描述它的位置。"
        result = recognizer.analyze_image(local_img, prompt=prompt, is_local_file=True)
        
        print("-" * 30)
        print("大模型识别结果:")
        print(result)
        print("-" * 30)
        
    except ValueError as e:
        print(e)
