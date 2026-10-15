# -*- coding: utf-8 -*-
"""多车 Gym 环境封装（步骤8/11：MADQN 多车协同 + 多车联调）。
每台 AGV 为一个智能体，局部观测含 3×3 邻域占用 + 自身状态 + 邻居意图。
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

from envs.warehouse_env import MOVES, Discrete
from planning.astar import astar
from safety.collision import detect_conflicts, TimeWindow
from simulation.scene import Scene, scene_from_config_file


class MultiWarehouseEnv:
    """多 AGV 协同调度环境（CTDE：集中训练、分散执行）。"""

    def __init__(self, scene: Optional[Scene] = None, n_agvs: int = 5,
                 seed: Optional[int] = None, max_steps: int = 600,
                 conflict_radius: float = 0.5):
        import random
        self.scene = scene or self._default_scene()
        self.n_agvs = n_agvs
        self.max_steps = max_steps
        self.conflict_radius = conflict_radius
        self.rng = random.Random(seed)
        self.action_space = Discrete(9)
        self.observation_space = Discrete(6 + 9)  # 6 状态 + 3×3 邻域
        self.reset()

    @staticmethod
    def _default_scene() -> Scene:
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return scene_from_config_file(os.path.join(here, "config", "scene.yaml"))

    def _random_free_cell(self):
        while True:
            r = self.rng.randrange(self.scene.rows)
            c = self.rng.randrange(self.scene.cols)
            if self.scene.is_passable(r, c):
                return (r, c)

    def reset(self):
        self.poses: List[Tuple[int, int]] = []
        self.goals: List[Tuple[int, int]] = []
        self.batteries = [100.0] * self.n_agvs
        for _ in range(self.n_agvs):
            p = self._random_free_cell()
            g = self._random_free_cell()
            while g == p:
                g = self._random_free_cell()
            self.poses.append(p)
            self.goals.append(g)
        self.steps = 0
        self.conflicts = 0
        self.done = [False] * self.n_agvs
        return self._obs_all()

    def _obs(self, i: int) -> List[float]:
        r, c = self.poses[i]
        gr, gc = self.goals[i]
        local = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                nr, nc = r + dr, c + dc
                occupied = any((nr, nc) == p for p in self.poses) or not self.scene.is_passable(nr, nc)
                local.append(1.0 if occupied else 0.0)
        return [r / self.scene.rows, c / self.scene.cols,
                gr / self.scene.rows, gc / self.scene.cols,
                self.batteries[i] / 100.0, 0.0] + local

    def _obs_all(self):
        return [self._obs(i) for i in range(self.n_agvs)]

    def step(self, actions: List[int]):
        for i, a in enumerate(actions):
            if self.done[i]:
                continue
            dr, dc = MOVES[a]
            nr, nc = self.poses[i][0] + dr, self.poses[i][1] + dc
            if self.scene.is_passable(nr, nc):
                # 避免两车进入同一格（简单占位冲突避免）
                if not any((nr, nc) == p for j, p in enumerate(self.poses) if j != i):
                    self.poses[i] = (nr, nc)
            self.batteries[i] = max(0.0, self.batteries[i] - 0.05)
        self.steps += 1

        # 冲突计数：两车中心距 < 0.5m
        self._count_conflicts()

        rewards = []
        for i in range(self.n_agvs):
            r = -0.01
            if self.poses[i] == self.goals[i]:
                r += 10.0
                self.done[i] = True
            if self.batteries[i] <= 20.0:
                r -= 0.1
            rewards.append(r)
        if self.steps >= self.max_steps:
            self.done = [True] * self.n_agvs
        infos = [{"pos": p, "goal": g} for p, g in zip(self.poses, self.goals)]
        return self._obs_all(), rewards, list(self.done), infos

    def _count_conflicts(self):
        res = self.scene.resolution
        for i in range(self.n_agvs):
            for j in range(i + 1, self.n_agvs):
                a, b = self.poses[i], self.poses[j]
                dist = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 * res
                if dist < self.conflict_radius:
                    self.conflicts += 1

    def plan_all(self, forbidden: Optional[set] = None) -> Dict[int, List[Tuple[int, int]]]:
        """为每车用 A* 计算路径（无协同基准）。"""
        return {i: astar(self.scene, self.poses[i], self.goals[i], forbidden=forbidden)
                for i in range(self.n_agvs)}
