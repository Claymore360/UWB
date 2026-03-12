# -*- coding: utf-8 -*-
"""
圆形鱼眼全景图片转换工具
Circular Fisheye Image Converter

功能描述：
    本脚本专门用于处理圆形鱼眼（Circular Fisheye）全景相机拍摄的照片。
    它可以将原本畸变的圆形鱼眼图像，展开为多张正常的透视投影（Perspective Projection）图像。
    生成的图像（如前、后、左、右视角）可以直接用于大模型识别或人眼观察。

关于参数的说明：
    用户提问：是否只需要圆心坐标、半径 R、视场角 FOV，而不需要复杂的相机内参（如畸变系数 D, 内参矩阵 K）？
    
    回答：
    是的，对于视觉识别和大模型理解任务，使用【圆心、半径、视场角】的简化几何模型通常已经足够。
    
    原因如下：
    1. 近似模型有效性：圆形鱼眼镜头的设计通常遵循特定的投影模型（最常见的是等距投影 r = f * theta）。
       只要我们知道图像的成像圆半径 R 对应多少视场角 FOV，就可以反推出焦距 f。
       圆心 (cx, cy) 对应光轴中心。这三个参数本质上构成了相机的简化内参。
    2. 容错率：大模型（如 GPT-4V, YOLO 等）对图像的轻微几何形变具有很强的鲁棒性。
       即使没有通过棋盘格标定获得亚像素级的精确内参，仅通过几何参数展开的图像，
       其物体形状已经恢复正常（直线变直），完全满足识别需求。
    3. 实际操作：相比于拍摄几十张棋盘格进行标定，直接测量图像中的圆心和半径要快得多，且效果差异在识别任务中可忽略。

使用方法：
    1. 在 main 函数中修改 input_path 为你的图片路径。
    2. 运行脚本：python fisheye_converter.py
"""

import cv2
import numpy as np
import os
import math

class CircularFisheyeConverter:
    def __init__(self, image_path):
        """
        初始化转换器
        :param image_path: 输入的鱼眼图片路径
        """
        self.img = cv2.imread(image_path)
        if self.img is None:
            raise ValueError(f"无法读取图片: {image_path}")
        
        self.h, self.w = self.img.shape[:2]
        
        # 默认参数初始化（由于不知道具体参数，先根据图像尺寸自动估算）
        # 用户后续可以通过 set_params 方法手动覆盖
        self.center_x = self.w / 2.0
        self.center_y = self.h / 2.0
        # 此时假设圆形成像区域撑满了较短边
        self.radius = min(self.w, self.h) / 2.0
        # 大多数圆形鱼眼相机的FOV是180度或略大
        self.fov = 180.0 

    def set_params(self, center_x=None, center_y=None, radius=None, fov=None):
        """
        手动设置鱼眼参数。如果不设置，将使用初始化时的自动估算值。
        
        :param center_x: 圆心 X 坐标 (像素)
        :param center_y: 圆心 Y 坐标 (像素)
        :param radius: 成像圆的半径 R (像素)
        :param fov: 鱼眼镜头的视场角 (度)，通常为 180-220
        """
        if center_x is not None: self.center_x = center_x
        if center_y is not None: self.center_y = center_y
        if radius is not None: self.radius = radius
        if fov is not None: self.fov = fov
        
        print(f"参数已更新: Center=({self.center_x:.1f}, {self.center_y:.1f}), Radius={self.radius:.1f}, FOV={self.fov:.1f}")

    def _get_focal_length(self):
        """
        根据半径和FOV计算焦距。
        假设鱼眼模型为等距投影 (Equidistant Projection): r = f * theta
        其中 theta 是入射角（弧度）。
        最大半径 R 对应最大入射角 FOV/2。
        因此: R = f * (FOV_rad / 2)  =>  f = R / (FOV_rad / 2)
        """
        fov_rad = np.deg2rad(self.fov)
        return self.radius / (fov_rad / 2.0)

    def dewarp_to_perspective(self, output_width=640, output_height=640, output_fov=90, yaw=0, pitch=0, roll=0):
        """
        将鱼眼图像转换为特定视角的透视投影图像。
        
        :param output_width: 输出图像宽度
        :param output_height: 输出图像高度
        :param output_fov: 输出图像的视场角 (度)，建议 80-100 度以模拟人眼或普通相机
        :param yaw: 水平偏航角 (度): 0=前, 90=右, 180=后, -90=左
        :param pitch: 垂直俯仰角 (度): 正值向上看，负值向下看
        :param roll: 滚转角 (度)
        :return: 去畸变后的图像 (numpy array)
        """
        # 1. 准备输出图像的像素网格 (u, v)
        # 归一化坐标: x, y in [-1, 1]
        cols = np.arange(output_width)
        rows = np.arange(output_height)
        map_x, map_y = np.meshgrid(cols, rows)
        
        # 将像素坐标 (u, v) 转换为归一化平面坐标 (x, y)
        # (2*u - w) / w, (2*v - h) / h
        # 注意: 在计算机图形学中，y通常向下，但在3D相机坐标系中 y 通常也是向下或者向上，需保持一致
        # 这里我们假设图像中心为原点 (0,0)
        norm_x = (2.0 * map_x - output_width) / output_width
        norm_y = (2.0 * map_y - output_height) / output_height # y 向下增加
        
        # 2. 计算透视投影相机的焦距 (Scale Factor)
        # tan(fov/2) = (sensor_width/2) / focal_length
        # 在归一化平面上，sensor_width/2 = 1.0
        persp_f = 1.0 / np.tan(np.deg2rad(output_fov) / 2.0)
        
        # 3. 构建 3D 向量 (x, y, z)
        # 假设相机坐标系：X向右，Y向下，Z向前
        z = np.ones_like(norm_x) * persp_f
        # 初始向量
        vecs = np.stack([norm_x, norm_y, z], axis=-1)
        
        # 归一化向量
        # vecs = vecs / np.linalg.norm(vecs, axis=-1, keepdims=True)
        
        # 4. 应用旋转 (Yaw, Pitch, Roll)
        # 为了模拟相机旋转，我们需要旋转这个向量
        
        # 转换角度为弧度
        y_rad = np.deg2rad(yaw)
        p_rad = np.deg2rad(pitch)
        r_rad = np.deg2rad(roll)
        
        # 定义旋转矩阵
        # 绕Y轴 (Yaw)
        R_yaw = np.array([
            [np.cos(y_rad), 0, np.sin(y_rad)],
            [0, 1, 0],
            [-np.sin(y_rad), 0, np.cos(y_rad)]
        ])
        
        # 绕X轴 (Pitch)
        R_pitch = np.array([
            [1, 0, 0],
            [0, np.cos(p_rad), -np.sin(p_rad)],
            [0, np.sin(p_rad), np.cos(p_rad)]
        ])
        
        # 绕Z轴 (Roll)
        R_roll = np.array([
            [np.cos(r_rad), -np.sin(r_rad), 0],
            [np.sin(r_rad), np.cos(r_rad), 0],
            [0, 0, 1]
        ])
        
        # 组合旋转矩阵 R = R_yaw * R_pitch * R_roll
        # 注意矩阵乘法顺序，根据想先转哪个轴定
        R = R_yaw @ R_pitch @ R_roll
        
        # 应用旋转: v_rot = R * v
        # 使用 einsum 进行批量矩阵乘法: 'ij, h w j -> h w i'
        vecs_rot = np.einsum('ij,hwj->hwi', R, vecs)
        
        # 提取旋转后的分量
        X = vecs_rot[..., 0]
        Y = vecs_rot[..., 1]
        Z = vecs_rot[..., 2]
        
        # 5. 将 3D 向量映射回鱼眼图像平面 (Fisheye Projection)
        
        # 计算入射角 theta (相对于光轴 Z)
        # r3d = sqrt(X^2 + Y^2 + Z^2)
        r3d = np.sqrt(X**2 + Y**2 + Z**2)
        theta = np.arccos(Z / (r3d + 1e-6)) # 防止除零
        
        # 计算方位角 phi (在成像平面上的角度)
        phi = np.arctan2(Y, X)
        
        # 根据鱼眼模型计算半径 r_fish
        # 等距投影: r = f * theta
        f_fish = self._get_focal_length()
        r_fish = f_fish * theta
        
        # 6. 计算在原图中的像素坐标 (u_src, v_src)
        u_src = self.center_x + r_fish * np.cos(phi)
        v_src = self.center_y + r_fish * np.sin(phi)
        
        # 7. 重映射 (Remap)
        # cv2.remap 需要 float32 类型的映射表
        map_x_float = u_src.astype(np.float32)
        map_y_float = v_src.astype(np.float32)
        
        # 使用双线性插值，边界填充为黑色
        dewarped_img = cv2.remap(self.img, map_x_float, map_y_float, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        
        return dewarped_img

    def convert_all_directions(self, output_dir, out_size=640):
        """
        自动生成前、后、左、右四张视角的图片
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        directions = {
            "front": 0,
            "right": 90,
            "back": 180,
            "left": -90
        }
        
        print(f"开始转换... 输出目录: {output_dir}")
        for name, yaw in directions.items():
            print(f"处理视角: {name} (Yaw={yaw}°)")
            img = self.dewarp_to_perspective(output_width=out_size, output_height=out_size, output_fov=100, yaw=yaw)
            
            save_path = os.path.join(output_dir, f"view_{name}.jpg")
            cv2.imwrite(save_path, img)
            print(f"已保存: {save_path}")

# --- 测试代码 ---
if __name__ == "__main__":
    # 创建一个虚拟的测试图像（如果当前目录下没有真实图片）
    # 在实际使用中，请将 image_path 替换为真实的鱼眼图片路径
    
    # 简单的测试逻辑
    print("--- 圆形鱼眼转换工具 ---")
    
    # 这里为了演示，我们假设用户会修改下面的路径
    # 如果您有真实图片，请修改这里的路径
    input_image_path = "test_fisheye.jpg" 
    
    if not os.path.exists(input_image_path):
        print(f"提示: 未找到测试图片 '{input_image_path}'.")
        print("请在代码中修改 'input_image_path' 为您的实际图片路径，或确保存放了该图片。")
        
        # 生成一个模拟的鱼眼图用于演示（画几个同心圆）
        print("正在生成模拟测试图片...")
        fake_img = np.zeros((1000, 1000, 3), dtype=np.uint8)
        cv2.circle(fake_img, (500, 500), 480, (255, 255, 255), 2) # 边缘
        cv2.circle(fake_img, (500, 500), 100, (0, 0, 255), -1)    # 中心红点
        cv2.putText(fake_img, "Fisheye", (400, 300), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 2)
        cv2.imwrite(input_image_path, fake_img)
        print(f"模拟图片已保存至 {input_image_path}")
    
    try:
        # 1. 初始化转换器
        converter = CircularFisheyeConverter(input_image_path)
        
        # 2. (可选) 手动设置参数。如果不设置，会自动估算。
        # 假设我们知道这确实是一个完美的圆形鱼眼
        converter.set_params(radius=500, fov=180) 
        
        # 3. 批量生成四个方向的图
        output_folder = "output_views"
        converter.convert_all_directions(output_folder)
        
        print("所有转换完成！")
        
    except Exception as e:
        print(f"发生错误: {e}")
