"""将 UWB 二进制数据解析后打印并可选保存为 CSV。

用法示例：
    python uwb_dump.py data.bin --limit 120 --csv output.csv

说明：
- 使用现有的 UWBParser 逐帧解析距离信息。
- 默认仅打印到终端；若提供 --csv 则写入文件。
- --limit 可限制处理的帧数，便于快速查看。
"""

import argparse
import csv
from typing import Iterable, List, Optional

from uwb_parser import UWBParser, UWBData


def collect_frames(bin_path: str, limit: Optional[int] = None) -> List[UWBData]:
    """解析二进制文件，返回若干帧数据。"""
    frames: List[UWBData] = []
    parser = UWBParser(bin_path)
    for frame in parser.parse():
        frames.append(frame)
        if limit is not None and len(frames) >= limit:
            break
    return frames


def print_frames(frames: Iterable[UWBData]) -> None:
    """打印帧的基站距离信息到终端。"""
    for frame in frames:
        anchor_str = ", ".join(
            f"{aid:04x}:{dist}cm" for aid, dist in frame.distances.items()
        )
        print(f"frame={frame.frame_id:04d} anchors=[{anchor_str}]")


def save_csv(frames: Iterable[UWBData], csv_path: str) -> None:
    """将帧数据保存为 CSV。列：frame_id, anchor_id, distance_cm。"""
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["frame_id", "anchor_id_hex", "distance_cm"])
        for frame in frames:
            for aid, dist in frame.distances.items():
                writer.writerow([frame.frame_id, f"0x{aid:04x}", dist])


def main() -> None:
    ap = argparse.ArgumentParser(description="解析并查看 UWB 距离数据")
    ap.add_argument("bin_file", help="UWB 二进制数据文件路径")
    ap.add_argument("--limit", type=int, default=None, help="限制解析的帧数")
    ap.add_argument("--csv", dest="csv_path", help="可选：保存为 CSV 的路径")
    args = ap.parse_args()

    frames = collect_frames(args.bin_file, limit=args.limit)
    print_frames(frames)

    if args.csv_path:
        save_csv(frames, args.csv_path)
        print(f"已保存 CSV: {args.csv_path}")


if __name__ == "__main__":
    main()
