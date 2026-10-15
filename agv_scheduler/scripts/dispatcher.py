#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""任务调度节点（步骤5/9 落地到 ROS）：把取送任务下发给各 AGV，驱动自主导航。

职责（本次演示用简化调度，DQN/拍卖在纯 Python 环境中验证）：
  1. 维护每台 AGV 的取送任务序列（货架取货 → 工位/装卸点送达）
  2. 订阅 /agv{i}/status，AGV 到达后推进到下一目标
  3. 发布 /agv{i}/goal 目标点（世界坐标），并在未确认时定时重发

用法： rosrun agv_scheduler dispatcher.py _n_agvs:=5
"""
import rospy
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String

# 演示任务：每台 AGV 的 (取货点, 送达点) 世界坐标序列
# 取货点 = 货架前沿；送达点 = 工位/装卸点（与 config/scene.yaml 布局一致）
TASKS = {
    1: [((3.0, 10.25), (1.75, 9.75)),    # 碱类货架 -> WS4
        ((16.5, 10.25), (18.75, 6.75))],  # 催化剂 -> P2
    2: [((7.5, 10.25), (3.75, 9.75)),    # 酸类 -> WS5
        ((7.5, 3.75), (15.75, 4.75))],    # 一般原料 -> WS3
    3: [((3.0, 3.75), (1.75, 4.75)),     # 氧化剂 -> WS1
        ((12.0, 3.75), (15.75, 9.75))],   # 毒性品 -> WS6
    4: [((12.0, 10.25), (1.25, 6.75)),   # 有机溶剂 -> P1
        ((16.5, 3.75), (18.75, 6.75))],   # 耗材 -> P2
    5: [((7.5, 3.75), (15.75, 4.75)),    # 一般原料 -> WS3
        ((3.0, 10.25), (1.25, 6.75))],    # 碱类 -> P1
    6: [((16.5, 10.25), (15.75, 9.75)),  # 催化剂 -> WS6
        ((7.5, 10.25), (1.25, 6.75))],    # 酸类 -> P1
    7: [((12.0, 3.75), (1.75, 4.75)),    # 毒性品 -> WS1
        ((16.5, 3.75), (15.75, 4.75))],   # 耗材 -> WS3
    8: [((3.0, 10.25), (3.75, 9.75)),    # 碱类 -> WS5
        ((12.0, 10.25), (15.75, 9.75))],  # 有机溶剂 -> WS6
    9: [((16.5, 10.25), (1.75, 9.75)),   # 催化剂 -> WS4
        ((3.0, 3.75), (1.25, 6.75))],     # 氧化剂 -> P1
    10: [((7.5, 3.75), (1.75, 4.75)),    # 一般原料 -> WS1
         ((16.5, 3.75), (18.75, 6.75))],  # 耗材 -> P2
}


class Dispatcher:
    def __init__(self):
        rospy.init_node("dispatcher", anonymous=False)
        self.n = int(rospy.get_param("~n_agvs", 5))
        self.n = min(self.n, 10)

        # 每台 AGV 的状态机
        self.state = {i: {"idx": 0, "phase": "pickup", "moving": False}
                      for i in range(1, self.n + 1)}

        self.goal_pubs = {}
        for i in range(1, self.n + 1):
            self.goal_pubs[i] = rospy.Publisher("/agv%d/goal" % i, PoseStamped, queue_size=1)
            rospy.Subscriber("/agv%d/status" % i, String, self.status_cb, callback_args=i)

        # 启动后先发第一目标
        for i in range(1, self.n + 1):
            t = self._current_target(i)
            if t:
                self._publish_goal(i, t)

        # 定时重发（处理启动竞态：nav 节点可能还没收到 odom）
        self.timer = rospy.Timer(rospy.Duration(2.0), self._resend_tick)
        rospy.loginfo("调度节点就绪，%d 台 AGV 任务已下发", self.n)

    # ---- 状态机 ----
    def _tasks(self, i):
        return TASKS.get(i, [])

    def _current_target(self, i):
        st = self.state[i]
        tasks = self._tasks(i)
        if st["idx"] >= len(tasks):
            return None
        task = tasks[st["idx"]]
        return task[0] if st["phase"] == "pickup" else task[1]

    def status_cb(self, msg, i):
        if msg.data != "ARRIVED":
            if msg.data == "MOVING":
                self.state[i]["moving"] = True
            return
        # 到达：推进状态机
        st = self.state[i]
        if st["phase"] == "pickup":
            st["phase"] = "deliver"
        else:
            st["phase"] = "pickup"
            st["idx"] += 1
        st["moving"] = False
        t = self._current_target(i)
        if t:
            self._publish_goal(i, t)
            rospy.loginfo("agv%d 到达，下发下一目标 (%.2f, %.2f)", i, t[0], t[1])
        else:
            rospy.loginfo("agv%d 完成全部任务", i)

    def _resend_tick(self, _event):
        for i in range(1, self.n + 1):
            if not self.state[i]["moving"]:
                t = self._current_target(i)
                if t:
                    self._publish_goal(i, t)

    # ---- 发布 ----
    def _publish_goal(self, i, xy):
        g = PoseStamped()
        g.header.frame_id = "odom"
        g.header.stamp = rospy.Time.now()
        g.pose.position.x = xy[0]
        g.pose.position.y = xy[1]
        g.pose.orientation.w = 1.0
        self.goal_pubs[i].publish(g)


if __name__ == "__main__":
    try:
        Dispatcher()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
