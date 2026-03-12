import math

# ==========================================
# 1. 基站原始数据 (定义坐标系基准)
# ==========================================
# 昨天的数据，用于确定原点和旋转角度
anchor_data = {
    0x9524: [3355936.826, 504314.106, 24.939],  # 基站2 (原点)
    0x9246: [3355940.024, 504312.691, 24.957],  # 基站3 (X轴方向)
    0x9532: [3355936.872, 504311.205, 24.955],  # 基站1
}

# ==========================================
# 2. 接收器测试点数据 (真值)
# ==========================================
# 从你刚才发的图片中提取的数据 [N, E, Z]
test_points = {
    "Test_Pt1_29": [3355937.890, 504312.955, 24.979],
    "Test_Pt2_30": [3355937.822, 504312.974, 24.981],
}

# 配置角色
ORIGIN_ID = 0x9524  # 原点ID
X_AXIS_ID = 0x9246  # X轴ID

# ==========================================
# 3. 转换核心逻辑
# ==========================================
def transform_coordinate(n, e, z, n_origin, e_origin, z_origin, theta_rad):
    """
    输入: 全站仪坐标 (N, E)
    输出: 局部平面坐标 (x_cm, y_cm)
    """
    # 1. 平移
    dx = e - e_origin
    dy = n - n_origin
    
    # 2. 旋转 (顺时针旋转 theta，将 X 轴对齐)
    # x_new = dx * cos(theta) + dy * sin(theta)
    # y_new = -dx * sin(theta) + dy * cos(theta)
    x_new = dx * math.cos(theta_rad) + dy * math.sin(theta_rad)
    y_new = -dx * math.sin(theta_rad) + dy * math.cos(theta_rad)
    
    # 3. 换算单位
    return x_new * 100, y_new * 100, (z - z_origin) * 100

def calculate_all():
    print("=== 坐标转换工具 (基站 + 真值点) ===")
    
    if ORIGIN_ID not in anchor_data or X_AXIS_ID not in anchor_data:
        print("错误：基站数据中找不到原点或X轴参考点")
        return

    # --- 第一步：计算坐标系参数 (基于基站) ---
    n_origin, e_origin, z_origin = anchor_data[ORIGIN_ID]
    n_xaxis,  e_xaxis,  _        = anchor_data[X_AXIS_ID]

    # 计算相对于原点的偏移
    dx_axis = e_xaxis - e_origin
    dy_axis = n_xaxis - n_origin

    # 计算旋转角度 (相对于正东方向)
    theta = math.atan2(dy_axis, dx_axis)
    
    print(f"原点基站: {hex(ORIGIN_ID)}")
    print(f"旋转角度: {math.degrees(theta):.3f} 度")
    print("-" * 60)

    # --- 第二步：转换基站坐标 (用于 main.py) ---
    print("【基站坐标 (请复制到 main.py)】")
    print("ANCHOR_COORDS = {")
    for uid, (n, e, z) in anchor_data.items():
        x, y, h = transform_coordinate(n, e, z, n_origin, e_origin, z_origin, theta)
        if abs(x) < 0.1: x = 0.0
        if abs(y) < 0.1: y = 0.0
        print(f"    {hex(uid)}: [{x:>8.1f}, {y:>8.1f}],  # Z: {h:.1f}")
    print("}")
    print("-" * 60)

    # --- 第三步：转换测试点坐标 (用于误差分析) ---
    print("【接收器真值坐标 (单位: cm)】")
    print(f"{'点名称':<18} | {'X (cm)':<10} | {'Y (cm)':<10} | {'Z相对(cm)'}")
    print("-" * 55)
    
    for name, (n, e, z) in test_points.items():
        x, y, h = transform_coordinate(n, e, z, n_origin, e_origin, z_origin, theta)
        print(f"{name:<18} | {x:<10.1f} | {y:<10.1f} | {h:.1f}")

if __name__ == "__main__":
    calculate_all()