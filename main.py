"""主程序：读取 UWB 二进制数据，解析后用最小二乘计算接收器坐标。

用法示例：
    python main.py data.bin --limit 120 --truth 159.8,169.3,2.9

说明：
- 使用 uwb_parser.UWBParser 逐帧解析距离。
- 使用 uwb_solver.solve_position_ls 求 (x, y)。
- 如提供三维真值，则按高度差做斜距改正，并输出真值误差。
"""

import argparse
from typing import Dict, Tuple

from uwb_eval import Coord, error_to_truth, parse_truth_coord
from uwb_parser import UWBParser
from uwb_solver import (
    AnchorCoord,
    correct_slant_ranges,
    solve_position_ls,
    solve_position_nlls,
)

# 锚点坐标（cm），包含 (x, y, z)
ANCHOR_COORDS: Dict[int, AnchorCoord] = {
    0x9524: (0.0, 0.0, 80),
    0x9246: (349.7, 0.0, 80),
    0x9532: (121.6, 263.4, 80),
}


def run(
    bin_file: str,
    limit: int | None = None,
    truth_coord: Coord | None = None,
) -> None:
    parser = UWBParser(bin_file)
    receiver_z = truth_coord[2] if truth_coord and len(truth_coord) == 3 else None
    for frame in parser.parse():
        try:
            dists = frame.distances
            if receiver_z is not None:
                dists = correct_slant_ranges(dists, ANCHOR_COORDS, receiver_z)
            # 需要至少 3 个有效锚点
            if len([aid for aid in dists if aid in ANCHOR_COORDS]) < 3:
                continue
            # 1) 线性解作为初值
            x_lin, y_lin, _ = solve_position_ls(ANCHOR_COORDS, dists)
            # 2) 非线性最小二乘精化（迭代步数有限，快速收敛）
            x_est, y_est, rms = solve_position_nlls(
                ANCHOR_COORDS,
                dists,
                init_xy=(x_lin, y_lin),
                loss="huber",
                f_scale=10.0,
                max_nfev=20,
            )
        except ValueError:
            # 锚点数量不足，跳过该帧
            continue
        msg = (
            f"frame={frame.frame_id:04d} "
            f"est=({x_est:.2f}, {y_est:.2f}) cm "
            f"rms={rms:.2f} cm"
        )
        if truth_coord is not None:
            err = error_to_truth((x_est, y_est), truth_coord)
            msg += f" err_to_truth={err:.2f} cm"
        print(msg)
        if limit is not None and frame.frame_id + 1 >= limit:
            break


def main() -> None:
    ap = argparse.ArgumentParser(description="UWB 最小二乘定位主程序")
    ap.add_argument("bin_file", help="UWB 二进制数据文件路径")
    ap.add_argument("--limit", type=int, default=None, help="限制处理帧数")
    ap.add_argument(
        "--truth",
        type=str,
        default=None,
        help="可选真值，格式 'x,y' 或 'x,y,z'，例如 159.8,169.3,2.9",
    )
    args = ap.parse_args()

    truth_coord = parse_truth_coord(args.truth) if args.truth else None
    run(args.bin_file, limit=args.limit, truth_coord=truth_coord)


if __name__ == "__main__":
    main()
