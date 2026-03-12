#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ROS 图像订阅节点（Python）
用途：订阅 C++ FLIR 发布的话题 /camera/fisheye/image_raw，并保存图片用于后处理。
"""

import os
import sys
import time
import atexit
import socket
import subprocess

# 使用系统 Python 运行，避免与 Conda 中 ROS 依赖冲突。
sys_python_path = "/usr/bin/python3"
if os.path.exists(sys_python_path) and os.path.realpath(sys.executable) != os.path.realpath(sys_python_path):
    print(f"[env-fix] switch {sys.executable} -> {sys_python_path}")
    os.execv(sys_python_path, [sys_python_path] + sys.argv)

import rospy
import cv2
from sensor_msgs.msg import Image
from cv_bridge import CvBridge, CvBridgeError


_managed_processes = []


def _is_ros_master_up(host="127.0.0.1", port=11311, timeout=0.4):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except Exception:
        return False
    finally:
        s.close()


def _start_cmd_in_bash(cmd):
    proc = subprocess.Popen(["/bin/bash", "-lc", cmd])
    _managed_processes.append(proc)
    return proc


def _cleanup_processes():
    for proc in _managed_processes:
        if proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass


atexit.register(_cleanup_processes)


def ensure_runtime_started():
    """自动拉起 roscore + FLIR 发布节点，省去手动开多个终端。"""
    auto_start = os.getenv("UWB_AUTO_START", "1") == "1"
    if not auto_start:
        return

    ros_setup = "source /opt/ros/noetic/setup.bash"
    ws_setup = "source /home/unitree/go2_3D_nav/nav/devel/setup.bash"

    if not _is_ros_master_up():
        print("[runtime] roscore 未运行，自动启动中...")
        _start_cmd_in_bash(f"{ros_setup} && roscore")
        for _ in range(30):
            if _is_ros_master_up():
                break
            time.sleep(0.3)

    if not _is_ros_master_up():
        raise RuntimeError("无法自动启动 roscore")

    print("[runtime] 自动启动 FLIR C++ 发布节点...")
    _start_cmd_in_bash(
        f"{ros_setup} && {ws_setup} && "
        "export LD_LIBRARY_PATH=/opt/spinnaker/lib:$LD_LIBRARY_PATH && "
        "roslaunch flir_gige_driver flir_gige_publisher.launch"
    )
    time.sleep(1.0)


class ImageSubscriberNode:
    def __init__(self):
        self.topic_name = rospy.get_param("~topic_name", "/camera/fisheye/image_raw")
        self.save_path = rospy.get_param("~save_path", "camera_test_snapshot.jpg")
        self.save_every_sec = float(rospy.get_param("~save_every_sec", 1.0))

        self.bridge = CvBridge()
        self.last_save_time = 0.0
        self.frame_count = 0

        self.sub = rospy.Subscriber(self.topic_name, Image, self._cb, queue_size=1)
        rospy.loginfo(f"[subscriber] topic={self.topic_name}")
        rospy.loginfo(f"[subscriber] save_path={self.save_path}")

    def _cb(self, msg):
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except CvBridgeError as e:
            rospy.logwarn_throttle(2.0, f"CvBridgeError: {e}")
            return

        self.frame_count += 1
        now = time.time()
        if now - self.last_save_time >= self.save_every_sec:
            cv2.imwrite(self.save_path, frame)
            self.last_save_time = now
            h, w = frame.shape[:2]
            rospy.loginfo(f"[subscriber] saved {self.save_path} ({w}x{h}), frame={self.frame_count}")


def main():
    ensure_runtime_started()
    rospy.init_node("fisheye_image_subscriber", anonymous=True)
    ImageSubscriberNode()
    rospy.spin()


if __name__ == "__main__":
    main()
