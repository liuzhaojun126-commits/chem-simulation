# -*- coding: utf-8 -*-
"""L1 战略级 DQN 任务分配（步骤5）。
状态 s：任务队列特征（队首 K=10 品类 one-hot、危化品等级、剩余时间窗、起讫点栅格坐标）
      + 各 AGV 状态（位置、负载、电量、序列长度、故障）。
动作 a：将队首任务分配给某台 AGV（离散 m 维）。
网络：全连接 3 层（256-256-128，ReLU）+ 经验回放(10⁵) + 目标网络(τ=0.005)。
超参：γ=0.95, lr=1e-4, batch=128, ε 1.0→0.05（前 2 万步）。
对应《项目落地实施方案 V1.42》4.2 步骤 5。

说明：完整 DQN 训练需 PyTorch（见 requirements.txt）。本模块提供
「接口 + 规则回退」实现，保证在无 PyTorch 环境下整个仿真空间仍可运行；
安装 PyTorch 后可在 train() 中启用真实网络。
"""
from __future__ import annotations

from typing import Dict, List, Optional


class DQNAllocator:
    """任务分配策略。默认使用「最近空闲车」规则作为可运行回退基线。"""

    def __init__(self, gamma: float = 0.95, lr: float = 1e-4,
                 hidden: List[int] = (256, 256, 128), seed: Optional[int] = None):
        self.gamma = gamma
        self.lr = lr
        self.hidden = list(hidden)
        self._torch = None
        self._net = None
        try:
            import torch  # 可选依赖
            self._torch = torch
        except ImportError:
            self._torch = None

    @property
    def uses_torch(self) -> bool:
        return self._torch is not None

    def allocate(self, task_queue: List[dict], fleet: List[dict],
                 safety_feasible: Optional[Dict[str, List[bool]]] = None) -> dict:
        """返回 {task_id: agv_id}。
        规则回退：把队首任务分配给「可行且距离最近」的空闲车。
        safety_feasible: {agv_id: [任务级可行性掩码]}，用于动作屏蔽。
        """
        assignment = {}
        busy = {a["id"]: len(a.get("seq", [])) for a in fleet}
        for t in task_queue:
            best, best_score = None, float("inf")
            for a in fleet:
                if a.get("fault", False) or a.get("battery", 100) < 20:
                    continue
                if safety_feasible and not safety_feasible.get(a["id"], [True])[0]:
                    continue
                # 简化代价：距离 + 当前负载
                dist = _manhattan(a.get("pos", (0, 0)), t.get("src_rc", (0, 0)))
                score = dist + 0.1 * busy[a["id"]]
                if score < best_score:
                    best, best_score = a["id"], score
            if best is not None:
                assignment[t["task_id"]] = best
                busy[best] += 1
        return assignment

    def train(self, env, episodes: int = 1000):
        """训练 DQN（需 PyTorch；无则跳过并提示）。"""
        if self._torch is None:
            print("[DQN] 未安装 PyTorch，跳过训练（当前使用规则回退基线）。")
            return None
        # 真实训练在此展开：三层 MLP + 经验回放 + 目标网络 + ε-greedy
        raise NotImplementedError("安装 PyTorch 后可在此接入完整 DQN 训练循环。")


def _manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


if __name__ == "__main__":
    alloc = DQNAllocator()
    print("torch 可用:", alloc.uses_torch)
    tasks = [{"task_id": i, "src_rc": (i, i)} for i in range(3)]
    fleet = [{"id": "agv1", "pos": (5, 5), "battery": 90, "seq": []},
             {"id": "agv2", "pos": (30, 20), "battery": 80, "seq": []}]
    print("分配:", alloc.allocate(tasks, fleet))
