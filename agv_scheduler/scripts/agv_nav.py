#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单 AGV 自主导航节点（步骤4/11：A* 全局规划 + 纯追踪控制 → cmd_vel）。

在 /agv{i} 命名空间下运行：
  订阅  odom  (nav_msgs/Odometry)      —— 自身位姿
  订阅  goal  (geometry_msgs/PoseStamped) —— 目标点（世界坐标）
  发布  cmd_vel (geometry_msgs/Twist)   —— 速度指令
  发布  global_path (nav_msgs/Path)     —— 规划路径（RViz 显示）
  发布  status (std_msgs/String)        —— IDLE / MOVING / ARRIVED

用法（roslaunch 会自动带命名空间）：
  rosrun agv_scheduler agv_nav.py _grid_file:=<仓库grid.json路径>
"""
import math
import os

import rospy
import rospkg
from nav_msgs.msg import Odometry, Path
from geometry_msgs.msg import Twist, PoseStamped
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String

import agv_common as common


class AGVNav:
    def __init__(self):
        rospy.init_node("agv_nav", anonymous=False)

        # 参数
        self.v_max = rospy.get_param("~v_max", 1.0)
        self.omega_max = rospy.get_param("~omega_max", 1.5)
        self.lookahead = rospy.get_param("~lookahead", 0.5)
        self.goal_tol = rospy.get_param("~goal_tol", 0.25)
        grid_file = rospy.get_param("~grid_file", "")
        if not grid_file:
            try:
                grid_file = os.path.join(rospkg.RosPack().get_path("agv_scheduler"),
                                         "simulation", "warehouse_grid.json")
            except Exception:
                grid_file = "warehouse_grid.json"

        # 加载栅格地图
        self.grid = common.load_grid(grid_file)
        self.res = self.grid["resolution"]
        rospy.loginfo("已加载栅格地图 %s (%dx%d)", grid_file,
                      self.grid["cols"], self.grid["rows"])

        # 状态
        self.pose = None
        self.path = []        # 世界坐标路径 [(x,y), ...]
        self.status = "IDLE"
        self.min_scan = 1e9   # 前方最近障碍距离（激光雷达）

        # 订阅 / 发布（相对话题名，由命名空间自动前缀 /agv{i}/）
        rospy.Subscriber("odom", Odometry, self.odom_cb)
        rospy.Subscriber("scan", LaserScan, self.scan_cb)
        rospy.Subscriber("goal", PoseStamped, self.goal_cb)
        self.cmd_pub = rospy.Publisher("cmd_vel", Twist, queue_size=1)
        self.path_pub = rospy.Publisher("global_path", Path, queue_size=1)
        self.status_pub = rospy.Publisher("status", String, queue_size=1)

        rospy.loginfo("AGV 导航节点就绪，等待 goal ...")

    # ---- 回调 ----
    def odom_cb(self, msg):
        self.pose = msg.pose.pose

    def scan_cb(self, msg):
        """记录前方 ±60° 扇形内最近障碍距离，用于应急制动。"""
        if not msg.ranges:
            return
        n = len(msg.ranges)
        # 前方扇区（机器人 +x 方向，角度 0 附近，含 ±60°）
        half = max(1, int(n / 6))
        idxs = list(range(0, half + 1)) + list(range(n - half, n))
        vals = [msg.ranges[i] for i in idxs if msg.ranges[i] > msg.range_min]
        self.min_scan = min(vals) if vals else 1e9

    def goal_cb(self, msg):
        gx = msg.pose.position.x
        gy = msg.pose.position.y
        if self.pose is None:
            rospy.logwarn("尚未收到 odom，无法规划")
            return
        start = common.world_to_grid(self.pose.position.x, self.pose.position.y, self.res)
        goal = common.world_to_grid(gx, gy, self.res)
        grid_path = common.astar(self.grid["passable"], start, goal)
        if not grid_path:
            rospy.logerr("A* 无解：%s -> %s", start, goal)
            return
        self.path = [common.grid_to_world(r, c, self.res) for (r, c) in grid_path]
        self.status = "MOVING"
        self._publish_path()
        rospy.loginfo("规划完成，路径 %d 个点，目标 (%.2f, %.2f)", len(self.path), gx, gy)

    # ---- 控制主循环 ----
    def run(self):
        rate = rospy.Rate(20)
        while not rospy.is_shutdown():
            self._control_step()
            rate.sleep()

    def _control_step(self):
        if not self.path or self.pose is None:
            self._publish_cmd(0.0, 0.0)
            return
        x = self.pose.position.x
        y = self.pose.position.y
        yaw = self._yaw(self.pose.orientation)

        goal = self.path[-1]
        if math.hypot(goal[0] - x, goal[1] - y) < self.goal_tol:
            self._publish_cmd(0.0, 0.0)
            if self.status != "ARRIVED":
                self.status = "ARRIVED"
                self.status_pub.publish(String("ARRIVED"))
                rospy.loginfo("到达目标 (%.2f, %.2f)", goal[0], goal[1])
            return

        tx, ty = self._lookahead_point(x, y)
        dx, dy = tx - x, ty - y
        dist = math.hypot(dx, dy)
        desired = math.atan2(dy, dx)
        err = common.normalize_angle(desired - yaw)

        v = self.v_max * max(0.0, 1.0 - abs(err) / 1.2)   # 转角大时减速
        v = max(v, 0.12) if dist > 0.1 else 0.0
        omega = 2.5 * err
        omega = max(-self.omega_max, min(self.omega_max, omega))

        # 应急制动：前方 0.4m 内有障碍则停车（安全约束兜底）
        if self.min_scan < 0.4:
            v = 0.0
        self._publish_cmd(v, omega)

    def _lookahead_point(self, x, y):
        # 找最近路径点，再向前取前视距离点
        min_i, min_d = 0, 1e9
        for i, p in enumerate(self.path):
            d = math.hypot(p[0] - x, p[1] - y)
            if d < min_d:
                min_d, min_i = d, i
        for i in range(min_i, len(self.path)):
            p = self.path[i]
            if math.hypot(p[0] - x, p[1] - y) >= self.lookahead:
                return p
        return self.path[-1]

    # ---- 辅助 ----
    @staticmethod
    def _yaw(q):
        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        return math.atan2(siny, cosy)

    def _publish_cmd(self, v, omega):
        t = Twist()
        t.linear.x = v
        t.angular.z = omega
        self.cmd_pub.publish(t)

    def _publish_path(self):
        p = Path()
        p.header.frame_id = "odom"
        p.header.stamp = rospy.Time.now()
        for (px, py) in self.path:
            ps = PoseStamped()
            ps.header = p.header
            ps.pose.position.x = px
            ps.pose.position.y = py
            ps.pose.orientation.w = 1.0
            p.poses.append(ps)
        self.path_pub.publish(p)


if __name__ == "__main__":
    try:
        AGVNav().run()
    except rospy.ROSInterruptException:
        pass
