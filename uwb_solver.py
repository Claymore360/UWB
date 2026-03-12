"""UWB 最小二乘定位函数集合。

提供基础函数，方便在脚本或服务中复用：
- solve_position_ls: 用线性化最小二乘求 (x, y)
- solve_position_nlls: 用非线性最小二乘（可鲁棒）精化解
- estimate_frames: 对多帧数据批量求解，返回估计结果
- error_to_truth: 计算估计与真值的平面误差

保持模块化，方便扩展（如换用非线性最小二乘、加入鲁棒估计等）。
"""

from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from uwb_parser import UWBData

AnchorCoord = Tuple[float, float, float]


def correct_slant_ranges(
    distances_cm: Dict[int, float],
    anchor_coords: Dict[int, AnchorCoord],
    receiver_z_cm: float,
    min_horizontal: float = 1e-3,
) -> Dict[int, float]:
    """根据已知的接收器高度对斜距进行改正，输出水平投影距离。

    如果距离短于高度差（数据异常）则跳过该锚点。
    """

    corrected: Dict[int, float] = {}
    for aid, dist in distances_cm.items():
        if aid not in anchor_coords:
            continue
        _, _, az = anchor_coords[aid]
        dz = receiver_z_cm - az
        squared = dist * dist - dz * dz
        if squared <= min_horizontal * min_horizontal:
            continue
        corrected[aid] = float(np.sqrt(squared))
    return corrected


def solve_position_ls(
    anchor_coords: Dict[int, AnchorCoord],
    distances_cm: Dict[int, float],
) -> Tuple[float, float, float]:
    """用线性化最小二乘求 2D 位置，返回 (x, y, rms_residual_cm)。

    推导：以第 0 个锚点为参考，(xi^2 + yi^2 - ri^2) - (x0^2 + y0^2 - r0^2)
    = 2(xi - x0)x + 2(yi - y0)y，可用于 3 个及以上锚点。
    """

    common_ids = [aid for aid in distances_cm.keys() if aid in anchor_coords]
    if len(common_ids) < 3:
        raise ValueError("需要至少 3 个已知坐标的锚点")

    ref_id = common_ids[0]
    x0, y0, _ = anchor_coords[ref_id]
    r0 = distances_cm[ref_id]

    A_rows: List[List[float]] = []
    b_vals: List[float] = []

    for aid in common_ids[1:]:
        xi, yi, _ = anchor_coords[aid]
        ri = distances_cm[aid]
        A_rows.append([2 * (xi - x0), 2 * (yi - y0)])
        b_vals.append(r0**2 - ri**2 + xi**2 - x0**2 + yi**2 - y0**2)

    A = np.asarray(A_rows, dtype=float)
    b = np.asarray(b_vals, dtype=float)

    sol, residuals, _, _ = np.linalg.lstsq(A, b, rcond=None)
    x_est, y_est = sol.tolist()

    if residuals.size:
        rms = float(np.sqrt(residuals[0] / A.shape[0]))
    else:
        rms = float(np.sqrt(np.mean((A @ sol - b) ** 2)))

    return x_est, y_est, rms


def _build_arrays(
    anchor_coords: Dict[int, AnchorCoord],
    distances_cm: Dict[int, float],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[int]]:
    """根据可用锚点构造 xi, yi, ri 数组和 id 列表。"""
    common_ids = [aid for aid in distances_cm.keys() if aid in anchor_coords]
    if len(common_ids) < 3:
        raise ValueError("需要至少 3 个已知坐标的锚点")
    xs, ys, rs = [], [], []
    for aid in common_ids:
        x, y, _ = anchor_coords[aid]
        xs.append(x)
        ys.append(y)
        rs.append(float(distances_cm[aid]))
    return np.asarray(xs, float), np.asarray(ys, float), np.asarray(rs, float), common_ids


def solve_position_nlls(
    anchor_coords: Dict[int, AnchorCoord],
    distances_cm: Dict[int, float],
    init_xy: Optional[Tuple[float, float]] = None,
    loss: str = "huber",
    f_scale: float = 10.0,
    max_nfev: int = 20,
) -> Tuple[float, float, float]:
    """用非线性最小二乘（scipy.optimize.least_squares）精化 (x, y)。

    - init_xy：初值；若未提供，则先用线性解作为初值。
    - loss：鲁棒损失（'linear'、'soft_l1'、'huber' 等）。
    - f_scale：鲁棒损失尺度，单位 cm。
    - max_nfev：最大函数评估次数，控制迭代步数（"一两步"可取 10~30）。
    返回 (x, y, rms_residual_cm)。
    """

    try:
        from scipy.optimize import least_squares  # type: ignore
    except Exception:
        # 无 SciPy 时直接回退到线性解（仍输出可用 RMS）
        x_lin, y_lin, rms_lin = solve_position_ls(anchor_coords, distances_cm)
        return x_lin, y_lin, rms_lin

    xi, yi, ri, ids = _build_arrays(anchor_coords, distances_cm)

    if init_xy is None:
        x_lin, y_lin, _ = solve_position_ls(anchor_coords, distances_cm)
        x0 = np.array([x_lin, y_lin], dtype=float)
    else:
        x0 = np.array([init_xy[0], init_xy[1]], dtype=float)

    def residuals(p: np.ndarray) -> np.ndarray:
        dx = p[0] - xi
        dy = p[1] - yi
        rng = np.sqrt(dx * dx + dy * dy)
        return rng - ri

    def jacobian(p: np.ndarray) -> np.ndarray:
        dx = p[0] - xi
        dy = p[1] - yi
        rng = np.sqrt(dx * dx + dy * dy)
        # 防止除零
        rng = np.where(rng < 1e-6, 1e-6, rng)
        Jx = dx / rng
        Jy = dy / rng
        return np.vstack([Jx, Jy]).T

    res = least_squares(
        residuals,
        x0,
        jac=jacobian,
        method="trf",
        loss=loss,
        f_scale=f_scale,
        max_nfev=max_nfev,
        xtol=1e-8,
        ftol=1e-8,
        gtol=1e-8,
    )

    x_est, y_est = res.x.tolist()
    # 以未加权残差计算 RMS（cm）
    res_vec = residuals(res.x)
    # 忽略非有限值，避免 NaN 传播
    res_vec = res_vec[np.isfinite(res_vec)]
    if res_vec.size == 0:
        rms = float("nan")
    else:
        rms = float(np.sqrt(np.mean(res_vec**2)))

    return x_est, y_est, rms


def estimate_frames(
    frames: Iterable[UWBData],
    anchor_coords: Dict[int, AnchorCoord],
    limit: Optional[int] = None,
) -> Iterable[Tuple[UWBData, Tuple[float, float, float]]]:
    """对多帧数据批量求解，逐帧返回 (frame, (x, y, rms))。"""

    for frame in frames:
        try:
            solution = solve_position_ls(anchor_coords, frame.distances)
        except ValueError:
            continue
        yield frame, solution
        if limit is not None and frame.frame_id + 1 >= limit:
            break


def error_to_truth(
    est_xy: Tuple[float, float], truth_xy: Tuple[float, float]
) -> float:
    """返回估计与真值的平面欧氏误差（cm）。"""

    dx = est_xy[0] - truth_xy[0]
    dy = est_xy[1] - truth_xy[1]
    return float(np.hypot(dx, dy))
