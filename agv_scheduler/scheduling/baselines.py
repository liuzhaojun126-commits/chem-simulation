# -*- coding: utf-8 -*-
"""基线调度策略（步骤12：表4 基线/实验组定义）。
B1 固定路径调度 / B2 最近任务优先 / B3 最短距离优先 / Ours 完整方案。
所有策略在分配时跟踪车辆当前位置（上一任务送达点），模拟顺序执行。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from simulation.scene import Scene

RC = Tuple[int, int]


def _manhattan(a: RC, b: RC) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _task_src(t: dict, scene: Scene) -> Optional[RC]:
    return scene.zone_access_point(t["src"])


def _task_dst(t: dict, scene: Scene) -> Optional[RC]:
    return scene.zone_access_point(t["dst"]) if t.get("dst") else _task_src(t, scene)


def round_robin(n_tasks: int, n_agvs: int) -> Dict[int, List[int]]:
    """B1 固定路径调度：任务按到达顺序轮询分配。"""
    assign = {i: [] for i in range(n_agvs)}
    for t in range(n_tasks):
        assign[t % n_agvs].append(t)
    return assign


def nearest_task_first(tasks: List[dict], agv_positions: List[RC],
                       scene: Scene) -> Dict[int, List[int]]:
    """B2 最近任务优先：每个任务分配给「当前代价最小」的车（贪心 + 负载均衡）。"""
    n = len(agv_positions)
    pos = list(agv_positions)
    load = {i: 0 for i in range(n)}
    assign = {i: [] for i in range(n)}
    for t_idx, t in enumerate(tasks):
        src = _task_src(t, scene)
        best, best_score = -1, float("inf")
        for i in range(n):
            d = _manhattan(pos[i], src) if src else 0
            score = d + 0.3 * load[i]
            if score < best_score:
                best, best_score = i, score
        assign[best].append(t_idx)
        load[best] += 1
        dst = _task_dst(t, scene)
        if dst:
            pos[best] = dst
    return assign


def shortest_distance_first(tasks: List[dict], agv_positions: List[RC],
                            scene: Scene) -> Dict[int, List[int]]:
    """B3 最短距离优先：全局贪心，每次取最短的 (车,任务) 对（仅优化距离）。"""
    n = len(agv_positions)
    pos = list(agv_positions)
    remaining = set(range(len(tasks)))
    assign = {i: [] for i in range(n)}
    while remaining:
        best = None
        best_d = float("inf")
        for t_idx in remaining:
            src = _task_src(tasks[t_idx], scene)
            if src is None:
                continue
            for i in range(n):
                d = _manhattan(pos[i], src)
                if d < best_d:
                    best_d = d
                    best = (t_idx, i)
        if best is None:
            break
        t_idx, i = best
        assign[i].append(t_idx)
        remaining.discard(t_idx)
        dst = _task_dst(tasks[t_idx], scene)
        if dst:
            pos[i] = dst
    return assign


def ours(tasks: List[dict], agv_positions: List[RC], scene: Scene,
         safety_feasible: Optional[Dict[int, List[bool]]] = None) -> Dict[int, List[int]]:
    """Ours：DQN 规则回退 —— 优先级加权 + 负载均衡 + 安全可行性掩码。"""
    n = len(agv_positions)
    pos = list(agv_positions)
    load = {i: 0 for i in range(n)}
    assign = {i: [] for i in range(n)}
    order = sorted(range(len(tasks)), key=lambda j: -tasks[j].get("priority", 0))
    for t_idx in order:
        t = tasks[t_idx]
        src = _task_src(t, scene)
        best, best_score = -1, float("inf")
        for i in range(n):
            if safety_feasible and not safety_feasible.get(i, [True])[0]:
                continue
            d = _manhattan(pos[i], src) if src else 0
            score = d + 0.4 * load[i]   # 负载均衡（优先级已通过排序体现）
            if score < best_score:
                best, best_score = i, score
        if best >= 0:
            assign[best].append(t_idx)
            load[best] += 1
            dst = _task_dst(t, scene)
            if dst:
                pos[best] = dst
    return assign


def allocate(strategy: str, tasks: List[dict], agv_positions: List[RC],
             scene: Scene, **kw) -> Dict[int, List[int]]:
    """统一入口。strategy ∈ {B1, B2, B3, Ours}。"""
    if strategy == "B1":
        return round_robin(len(tasks), len(agv_positions))
    if strategy == "B2":
        return nearest_task_first(tasks, agv_positions, scene)
    if strategy == "B3":
        return shortest_distance_first(tasks, agv_positions, scene)
    if strategy == "Ours":
        return ours(tasks, agv_positions, scene, kw.get("safety_feasible"))
    raise ValueError("未知策略: " + strategy)
