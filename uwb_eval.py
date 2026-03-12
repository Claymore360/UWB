"""结果评估工具。

提供与真值的误差计算函数，供主程序或其他模块调用。
"""

from __future__ import annotations

from typing import Tuple, Union

import numpy as np


Coord2D = Tuple[float, float]
Coord3D = Tuple[float, float, float]
Coord = Union[Coord2D, Coord3D]


def parse_truth_coord(text: str) -> Coord:
    """解析 'x,y' 或 'x,y,z' 形式的真值输入。"""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) not in (2, 3):
        raise ValueError("真值格式应为 'x,y' 或 'x,y,z'，例如 159.8,169.3,2.9")
    values = tuple(float(p) for p in parts)
    if len(values) == 2:
        return values  # type: ignore[return-value]
    return (values[0], values[1], values[2])  # type: ignore[return-value]


def error_to_truth(est_xy: Coord2D, truth_coord: Coord) -> float:
    """计算估计与真值的平面欧氏误差（cm）。"""

    dx = est_xy[0] - truth_coord[0]
    dy = est_xy[1] - truth_coord[1]
    return float(np.hypot(dx, dy))
