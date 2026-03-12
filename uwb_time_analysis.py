"""UWB 时序误差分析工具。

功能：分析一段连续数据中，测距误差随时间的变化。
用途：用于观察 LOS (视距) 和 NLOS (遮挡) 的切换过程，生成 uwb_analysis_plot.png。
"""

import argparse
import math
import matplotlib.pyplot as plt
import numpy as np

from uwb_parser import UWBParser
from uwb_eval import parse_truth_coord

# 锚点坐标 (cm)，与 main.py 保持一致
ANCHOR_COORDS = {
    0x9524: (0.0, 0.0, 80),
    0x9246: (349.7, 0.0, 80),
    0x9532: (121.6, 263.4, 80),
}

SUBPLOT_COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c']  # 蓝、橙、绿


def calculate_true_distances(truth_xyz):
    """计算真值点到所有基站的理论直线距离。"""
    dists = {}
    for aid, a_xyz in ANCHOR_COORDS.items():
        dx = a_xyz[0] - truth_xyz[0]
        dy = a_xyz[1] - truth_xyz[1]
        dz = a_xyz[2] - truth_xyz[2]
        dists[aid] = math.sqrt(dx * dx + dy * dy + dz * dz)
    return dists


def analyze_timeseries(bin_file, truth_xyz, limit=None):
    print(f"正在分析文件: {bin_file} ...")
    parser = UWBParser(bin_file)
    true_dists = calculate_true_distances(truth_xyz)
    
    # 数据存储结构: {anchor_id: {'frame': [], 'error': []}}
    data = {aid: {'frame': [], 'error': []} for aid in ANCHOR_COORDS}
    
    frame_idx = 0
    for frame in parser.parse():
        if limit and frame_idx >= limit:
            break
            
        for aid, measured_dist in frame.distances.items():
            if aid in ANCHOR_COORDS:
                # 误差 = 测量值 - 真值
                error = measured_dist - true_dists[aid]
                
                # 过滤掉极端的错误数据（例如解析错误的0值或超大值）
                if -1000 < error < 1000: 
                    data[aid]['frame'].append(frame_idx)
                    data[aid]['error'].append(error)
        
        frame_idx += 1

    plot_results(data, frame_idx)


def plot_results(data, total_frames):
    """绘制每个基站的误差波形图。"""
    fig, axes = plt.subplots(3, 1, figsize=(10, 12), sharex=True)
    fig.suptitle('UWB Ranging Error Over Time (LOS vs NLOS Cycles)', fontsize=16)
    
    anchors = list(ANCHOR_COORDS.keys())
    
    for i, ax in enumerate(axes):
        aid = anchors[i]
        
        # 兼容性处理：如果锚点数少于子图数
        if aid not in data:
            continue
            
        frames = data[aid]['frame']
        errors = data[aid]['error']
        
        if not frames:
            ax.text(0.5, 0.5, "No Data", ha='center', transform=ax.transAxes)
            continue
            
        # 绘制折线图
        ax.plot(frames, errors, label=f'Anchor {hex(aid)}', color=SUBPLOT_COLORS[i % len(SUBPLOT_COLORS)], linewidth=1, alpha=0.8)
        
        # 绘制 0 误差参考线
        ax.axhline(0, color='red', linestyle='--', linewidth=1, alpha=0.5)
        
        # 简单的统计
        if errors:
            avg = np.mean(errors)
            std = np.std(errors)
            info_text = f"Mean Bias: {avg:.1f}cm | Std: {std:.1f}cm"
            ax.text(0.02, 0.9, info_text, transform=ax.transAxes, bbox=dict(facecolor='white', alpha=0.8))

        ax.set_ylabel('Error (measured - truth) [cm]')
        ax.set_ylim(-50, 150)  # 设置Y轴范围，方便观察比如 +100cm 的跳变
        ax.legend(loc='upper right')
        ax.grid(True, linestyle=':', alpha=0.6)

    if axes.size > 0:
        axes[-1].set_xlabel('Frame Index (Time)')
    plt.tight_layout()
    
    # 保存图片而不是直接显示
    output_img = 'uwb_analysis_plot.png'
    plt.savefig(output_img)
    print(f"图表已保存至: {output_img} (请在编辑器中打开查看)")


def main():
    ap = argparse.ArgumentParser(description="UWB 时序误差分析工具")
    ap.add_argument("bin_file", help="UWB 二进制数据文件")
    ap.add_argument("--truth", required=True, help="真值坐标 x,y,z (例如 159.8,169.3,2.9)")
    ap.add_argument("--limit", type=int, default=3000, help="限制分析的帧数")
    
    args = ap.parse_args()
    truth = parse_truth_coord(args.truth)
    
    if len(truth) < 3:
        print("错误: 需要三维真值计算准确误差")
    else:
        analyze_timeseries(args.bin_file, truth, args.limit)


if __name__ == "__main__":
    main()
