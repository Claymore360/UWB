"""简易 UWB 最小二乘解算示例。

步骤：
1) 用 UWBParser 读取二进制文件，提取每帧三基站距离。
2) 用线性化最小二乘求解 (x, y)（可处理 >=3 个基站）。
3) 可选：与真值点比对定位误差。

用法：
	python UWB_test.py /path/to/data.bin --limit 5 --truth-name Test_Pt1

保持模块化，便于在其他流程中复用求解器。
"""

import argparse
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from uwb_parser import UWBParser, UWBData

# 锚点坐标（cm），来自 坐标.txt
ANCHOR_COORDS: Dict[int, Tuple[float, float]] = {
	0x9524: (0.0, 0.0),
	0x9246: (560.1, 0.0),
	0x9532: (-166.4, 285.4),
}

# 可选真值点（cm），方便快速误差对比
TRUTH_POINTS: Dict[str, Tuple[float, float]] = {
	"Test_Pt1": (159.8, 169.3),
	"Test_Pt2": (752.9, 68.6),
}


def solve_position_ls(
	anchor_coords: Dict[int, Tuple[float, float]],
	distances_cm: Dict[int, float],
) -> Tuple[float, float, float]:
	"""用线性化最小二乘求 2D 位置。

	推导：以第 0 个锚点为参考，(xi^2 + yi^2 - ri^2) - (x0^2 + y0^2 - r0^2)
	= 2(xi - x0)x + 2(yi - y0)y，可用于 3 个及以上锚点。

	返回 (x, y, rms_residual_cm)。
	"""

	common_ids = [aid for aid in distances_cm.keys() if aid in anchor_coords]
	if len(common_ids) < 3:
		raise ValueError("Need at least 3 anchors with known coordinates")

	ref_id = common_ids[0]
	x0, y0 = anchor_coords[ref_id]
	r0 = distances_cm[ref_id]

	A_rows: List[List[float]] = []
	b_vals: List[float] = []

	for aid in common_ids[1:]:
		xi, yi = anchor_coords[aid]
		ri = distances_cm[aid]
		A_rows.append([2 * (xi - x0), 2 * (yi - y0)])
		b_vals.append(r0**2 - ri**2 + xi**2 - x0**2 + yi**2 - y0**2)

	A = np.asarray(A_rows, dtype=float)
	b = np.asarray(b_vals, dtype=float)

	# lstsq 同时支持方阵和超定方程。
	sol, residuals, _, _ = np.linalg.lstsq(A, b, rcond=None)
	x_est, y_est = sol.tolist()

	if residuals.size:
		rms = float(np.sqrt(residuals[0] / A.shape[0]))
	else:
		# 当恰好定解时，手动计算残差。
		rms = float(np.sqrt(np.mean((A @ sol - b) ** 2)))

	return x_est, y_est, rms


def solve_frames(
	bin_path: str,
	anchor_coords: Dict[int, Tuple[float, float]],
	limit: Optional[int] = None,
) -> Iterable[Tuple[UWBData, Tuple[float, float, float]]]:
	"""从二进制文件解析帧并逐帧求解。"""

	parser = UWBParser(bin_path)
	for frame in parser.parse():
		try:
			solution = solve_position_ls(anchor_coords, frame.distances)
		except ValueError:
			continue
		yield frame, solution
		if limit is not None and frame.frame_id + 1 >= limit:
			break


def main() -> None:
	parser = argparse.ArgumentParser(description="UWB least-squares positioning")
	parser.add_argument("bin_file", help="Path to the UWB binary log")
	parser.add_argument("--limit", type=int, default=None, help="Max frames to solve")
	parser.add_argument(
		"--truth-name",
		choices=list(TRUTH_POINTS.keys()),
		help="Compare against a named truth point",
	)
	parser.add_argument(
		"--truth",
		type=str,
		help="Manual truth as 'x,y' in cm (overrides truth-name)",
	)
	args = parser.parse_args()

	truth: Optional[Tuple[float, float]] = None
	if args.truth:
		x_str, y_str = args.truth.split(",")
		truth = (float(x_str), float(y_str))
	elif args.truth_name:
		truth = TRUTH_POINTS[args.truth_name]

	for frame, (x_est, y_est, rms) in solve_frames(
		args.bin_file, ANCHOR_COORDS, limit=args.limit
	):
		msg = (
			f"frame={frame.frame_id:04d} "
			f"est=({x_est:.2f}, {y_est:.2f}) cm "
			f"rms={rms:.2f} cm"
		)
		if truth:
			err = float(np.hypot(x_est - truth[0], y_est - truth[1]))
			msg += f" err_to_truth={err:.2f} cm"
		print(msg)


if __name__ == "__main__":
	main()
