# -*- coding: utf-8 -*-
"""单车 Gym 环境封装（步骤：envs/ Gym 环境封装 单车版）。
统一 RL 训练接口；无 Gym 依赖，亦提供 gym 风格 reset/step/observation_space/action_space。
动作空间：9 维离散 —— 0~7 八方向移动，8 原地等待。
"""
from __future__ import annotations

import os
import random
from typing import Dict, List, Optional, Tuple

from planning.astar import astar
from simulation.scene import Scene, scene_from_config_file

MOVES = [(-1, 0), (1, 0), (0, -1), (0, 1),
         (-1, -1), (-1, 1), (1, -1), (1, 1), (0, 0)]


class WarehouseEnv:
    """单 AGV 在化工仓储栅格空间执行取送任务的强化学习环境。"""

    def __init__(self, scene: Optional[Scene] = None, seed: Optional[int] = None,
                 max_steps: int = 400, forbidden: Optional[set] = None):
        self.scene = scene or self._default_scene()
        self.max_steps = max_steps
        self.forbidden = forbidden or set()
        self.rng = random.Random(seed)
        self.action_space = Discrete(9)
        self.reset()

    @staticmethod
    def _default_scene() -> Scene:
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return scene_from_config_file(os.path.join(here, "config", "scene.yaml"))

    # -- 辅助 -------------------------------------------------
    def _random_free_cell(self) -> Tuple[int, int]:
        while True:
            r = self.rng.randrange(self.scene.rows)
            c = self.rng.randrange(self.scene.cols)
            if self.scene.is_passable(r, c) and (r, c) not in self.forbidden:
                return (r, c)

    def reset(self, start: Optional[Tuple[int, int]] = None,
              goal: Optional[Tuple[int, int]] = None):
        self.start = start or self._random_free_cell()
        self.goal = goal or self._random_free_cell()
        while self.goal == self.start:
            self.goal = self._random_free_cell()
        self.pos = self.start
        self.battery = 100.0
        self.load = 0
        self.steps = 0
        self.done = False
        self.violations = 0
        return self._obs()

    def _obs(self) -> List[float]:
        r, c = self.pos
        gr, gc = self.goal
        local = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                nr, nc = r + dr, c + dc
                local.append(0.0 if self.scene.is_passable(nr, nc) else 1.0)
        return [r / self.scene.rows, c / self.scene.cols,
                gr / self.scene.rows, gc / self.scene.cols,
                self.battery / 100.0, float(self.load)] + local

    def step(self, action: int):
        dr, dc = MOVES[action]
        nr, nc = self.pos[0] + dr, self.pos[1] + dc
        moved = False
        if self.scene.is_passable(nr, nc) and (nr, nc) not in self.forbidden:
            self.pos = (nr, nc)
            moved = True
            self.battery = max(0.0, self.battery - 0.05)
        self.steps += 1

        reward = -0.01  # 步进代价
        if self.pos == self.goal:
            reward += 10.0
            self.done = True
        if self.battery <= 20.0:
            reward -= 0.1
        if self.steps >= self.max_steps:
            self.done = True
        info = {"pos": self.pos, "goal": self.goal, "moved": moved}
        return self._obs(), reward, self.done, info

    def plan(self, forbidden: Optional[set] = None) -> List[Tuple[int, int]]:
        """用 A* 计算从当前点到目标的最短路径（基础导航闭环）。"""
        return astar(self.scene, self.pos, self.goal, forbidden=(forbidden or self.forbidden))


class Discrete:
    """轻量离散动作空间（Gym 兼容占位）。"""
    def __init__(self, n: int):
        self.n = n

    def sample(self):
        return random.randrange(self.n)

    def __contains__(self, x):
        return 0 <= x < self.n
