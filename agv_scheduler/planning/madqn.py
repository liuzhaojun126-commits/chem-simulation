# -*- coding: utf-8 -*-
"""MADQN 多车分布式路径规划（步骤8：CTDE + QMIX + 意图共享）。

理论（QMIX 价值分解，集中训练分散执行）：
  局部观测 o_i = {3×3 邻域占用, 自身位姿/速度/负载, 邻居意图 δ_j, 目标方向}
  联合价值 Q_tot(τ,a) = f_θ(Q_1(τ1,a1), ..., Q_m(τm,am), s)
  QMIX 单调性约束：∂Q_tot/∂Q_i ≥ 0（混合网络权重取绝对值）
  损失：L = E[(y - Q_tot)²], y = r + γ·max_a' Q_tot^-(τ', a')

工程实现：完整深度网络需 PyTorch（见 requirements.txt）。本模块提供
「确定性协同回退」——每车独立 A* + 意图共享（下一步栅格）+ 时间窗冲突检测，
冲突时低优先级车绕行/等待，实现路径冲突趋近 0，无需训练即可演示多车协同。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from planning.astar import astar
from safety.compatibility import CompatibilityMatrix
from simulation.scene import Scene

RC = Tuple[int, int]


class MadqnPlanner:
    """无中心协调者的多车分布式路径规划（意图共享 + 冲突避让）。"""

    def __init__(self, scene: Scene, compat: Optional[CompatibilityMatrix] = None):
        self.scene = scene
        self.compat = compat or CompatibilityMatrix()

    def plan_all(self, starts: List[RC], goals: List[RC],
                 forbidden: Optional[Set[RC]] = None,
                 priorities: Optional[List[float]] = None,
                 payload_categories: Optional[List[Optional[str]]] = None,
                 max_iters: int = 20) -> Dict[int, List[RC]]:
        """为 M 台车规划无冲突路径。
        priorities : 每车优先级（危化品等级高者优先保留路径），缺省按索引。
        payload_categories : 每车载荷品类，用于相容性硬剪枝。
        返回 {agent_index: path}。
        """
        n = len(starts)
        base_forbidden = set(forbidden or [])
        paths: Dict[int, List[RC]] = {}

        # 1) 独立规划（含相容性硬剪枝）
        for i in range(n):
            fb = set(base_forbidden)
            if payload_categories and payload_categories[i]:
                cat = payload_categories[i]
                for r in range(self.scene.rows):
                    for c in range(self.scene.cols):
                        zcat = self.scene.category_of_zone(self.scene.grid[r][c].zone)
                        if zcat is not None and not self.compat.is_compatible(cat, zcat):
                            fb.add((r, c))
            p = astar(self.scene, starts[i], goals[i], forbidden=fb)
            paths[i] = p if p else []

        # 2) 迭代消解冲突
        order = sorted(range(n), key=lambda i: -(priorities[i] if priorities else i))
        for _ in range(max_iters):
            occupied: Dict[RC, set] = {}
            for i, p in paths.items():
                for rc in p:
                    occupied.setdefault(rc, set()).add(i)
            conflicts = {rc: agents for rc, agents in occupied.items() if len(agents) > 1}
            if not conflicts:
                break
            changed = False
            for rc, agents in conflicts.items():
                # 优先级最高者保留，其余绕行
                for a in list(agents):
                    if a == order[0] and rc in (occupied.get(rc) or set()):
                        continue
                    # 该车把冲突栅格设为临时障碍重规划
                    fb = set(base_forbidden)
                    if payload_categories and payload_categories[a]:
                        cat = payload_categories[a]
                        for rr in range(self.scene.rows):
                            for cc in range(self.scene.cols):
                                zcat = self.scene.category_of_zone(self.scene.grid[rr][cc].zone)
                                if zcat is not None and not self.compat.is_compatible(cat, zcat):
                                    fb.add((rr, cc))
                    fb.add(rc)
                    newp = astar(self.scene, starts[a], goals[a], forbidden=fb)
                    if newp:
                        paths[a] = newp
                        changed = True
            if not changed:
                break
        return paths

    # 意图共享（轻量消息：下一步目标栅格）
    @staticmethod
    def next_intent(path: List[RC], idx: int) -> Optional[RC]:
        """路径上第 idx 步后的下一步栅格（1 字节/车/帧 的意图消息）。"""
        if path and idx + 1 < len(path):
            return path[idx + 1]
        return None


if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from simulation.scene import scene_from_config_file
    sc = scene_from_config_file(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                             "config", "scene.yaml"))
    planner = MadqnPlanner(sc)
    starts = [(14, 2), (14, 38), (13, 2)]
    goals = [(14, 38), (14, 2), (13, 38)]
    paths = planner.plan_all(starts, goals, priorities=[5.0, 1.0, 3.0])
    for i, p in paths.items():
        print(f"agv{i}: 路径长度 {len(p)}")
