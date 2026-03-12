# -*- coding: utf-8 -*-
import os
import sys

#为了能够从 visual 目录导入同一目录下的模块，通常可以直接 import
#如果在根目录运行 python visual/test_ai_recognition.py，可能需要根据 pythonpath
try:
    from qwen_recognizer import QwenVisionClient
except ImportError:
    # 如果在 visual 目录下运行
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from qwen_recognizer import QwenVisionClient

import traceback

def main():
    print("初始化 QwenVisionClient...")
    try:
        # 使用默认配置（会尝试读取环境变量 DASHSCOPE_API_KEY，或使用默认 Key）
        client = QwenVisionClient()
    except Exception:
        print(f"初始化失败: {traceback.format_exc()}")
        return

    # 寻找测试图片
    # 优先寻找上级目录的 OIP-wr (4).webp (疑似实景图)
    # 其次寻找 uwb_analysis_plot.png (图表)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_images = [
        os.path.join(base_dir, "OIP-wr (4).webp"),
        os.path.join(base_dir, "uwb_analysis_plot.png"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_image.jpg") # 本地假想图
    ]
    
    target_image = None
    for img_path in test_images:
        if os.path.exists(img_path):
            target_image = img_path
            break
    
    if not target_image:
        print("错误: 未找到可用的测试图片。")
        print(f"请确保以下路径之一存在文件: {test_images}")
        return

    print(f"找到测试图片: {target_image}")
    
    prompt = "请描述给的图片"
    print(f"发送提示词: '{prompt}'")
    
    try:
        # 调用 recognize_image (我们在 qwen_recognizer.py 中新增的别名/封装)
        result = client.recognize_image(target_image, prompt=prompt)
        
        print("\n" + "="*20 + " AI 识别结果 " + "="*20)
        print(result)
        print("="*55 + "\n")
        
    except Exception as e:
        print(f"识别过程中发生错误: {e}")

if __name__ == "__main__":
    main()
