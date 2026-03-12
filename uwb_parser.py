# uwb_parser.py
# 负责解析 UWB 二进制数据文件，提取每一帧的基站距离信息

import struct
import os

class UWBData:
    def __init__(self, frame_id, anchor_ids, distances):
        self.frame_id = frame_id
        self.anchor_ids = anchor_ids
        self.distances = distances  # Dictionary: {id: dist}

class UWBParser:
    def __init__(self, filepath):
        self.filepath = filepath

    def parse(self):
        """
        生成器函数，每次返回一帧解析好的 UWBData
        """
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"File not found: {self.filepath}")

        with open(self.filepath, 'rb') as f:
            content = f.read()

        i = 0
        valid_frames = 0
        
        # 遍历文件内容
        while i < len(content) - 40:
            # 1. 寻找包头 55 AA 12
            if content[i] == 0x55 and content[i+1] == 0xAA and content[i+2] == 0x12:
                try:
                    # 2. 自适应判断 offset (处理固件差异)
                    # 基站数量字节通常是 3，位置在 i+16 或 i+17
                    offset_count = 0
                    if content[i + 16] == 3: 
                        offset_count = 16
                    elif content[i + 17] == 3: 
                        offset_count = 17
                    else:
                        # 没找到基站数量，说明这是虚假的包头，跳过
                        i += 1
                        continue

                    id_start = i + offset_count + 1
                    id_list = []
                    
                    # 3. 解析基站 ID (3个，每个2字节，小端序)
                    for k in range(3):
                        uid = struct.unpack('<H', content[id_start + k*2 : id_start + k*2 + 2])[0]
                        id_list.append(uid)

                    # 4. 解析距离 (3个，每个2字节，小端序，单位 cm)
                    dists = {}
                    dist_start = id_start + 6
                    has_error = False
                    
                    for k in range(3):
                        d_val = struct.unpack('<H', content[dist_start + k*2 : dist_start + k*2 + 2])[0]
                        
                        # 过滤 0xFFFF (无效测量)
                        if d_val == 0xFFFF: 
                            has_error = True
                            break
                        dists[id_list[k]] = d_val
                    
                    if has_error:
                        # 如果这一帧数据有损坏的，跳过整帧
                        i += 30 
                        continue

                    # 5. 返回有效数据
                    yield UWBData(valid_frames, id_list, dists)
                    valid_frames += 1
                    
                    # 成功解析一帧后，跳过这一帧的数据长度
                    i += 30 
                    continue

                except Exception:
                    # 解析出错，继续寻找下一个包头
                    pass
            i += 1
