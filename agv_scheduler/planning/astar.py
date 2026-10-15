# -*- coding: utf-8 -*-
"""改进 A* 路径规划（步骤4/6：单车快速规划，动态权重地图 + 转弯惩罚 + 禁行区硬剪枝）。
对应《项目落地实施方案 V1.42》4.1 步骤 4、4.2 步骤 6。
"""
from __future__ import annotations

import heapq
from typing import Dict, Iterable, List, Optional, Set, Tuple

from simulation.scene import Scene

RC = Tuple[int, int]


def neighbors(rc: RC, rows: int, cols: int) -> List[Tuple[RC, float]]:
    """8 邻域 + 移动代价（直 1，斜 √2）。禁止对角线穿墙（角落剪枝）。"""
    r, c = rc
    out = []
    for dr, dc, cost in [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
                         (-1, -1, 1.41421356), (-1, 1, 1.41421356),
                         (1, -1, 1.41421356), (1, 1, 1.41421356)]:
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            out.append(((nr, nc), cost))
    return out


def astar(scene: Scene,
          start: RC,
          goal: RC,
          forbidden: Optional[Set[RC]] = None,
          edge_cost: Optional[Dict[RC, float]] = None,
          turn_penalty: float = 0.1) -> List[RC]:
    """在 scene 栅格上做 A*。

    forbidden : 不可通行栅格（硬剪枝：禁行区 + 相容性剪枝 + 障碍）
    edge_cost : 节点进入代价（动态权重地图）cost(node)，缺省为 1.0
    turn_penalty : 转弯惩罚（方向变化附加代价）

    返回栅格路径（含 start、goal）；无解返回空列表。
    """
    forbidden = forbidden or set()
    if start in forbidden or goal in forbidden:
        return []
    if not scene.is_passable(*start) or not scene.is_passable(*goal):
        return []

    rows, cols = scene.rows, scene.cols
    edge = edge_cost or {}

    g: Dict[RC, float] = {start: 0.0}
    parent: Dict[RC, RC] = {}
    # 记录进入方向，用于转弯惩罚
    come_from: Dict[RC, RC] = {}
    open_heap: List[Tuple[float, RC]] = [(heuristic(start, goal), start)]
    closed: Set[RC] = set()

    while open_heap:
        f, cur = heapq.heappop(open_heap)
        if cur in closed:
            continue
        if cur == goal:
            return reconstruct(parent, start, goal)
        closed.add(cur)

        for nb, base_cost in neighbors(cur, rows, cols):
            if nb in closed or nb in forbidden:
                continue
            if not scene.is_passable(*nb):
                continue
            # 对角线穿墙剪枝
            if abs(nb[0] - cur[0]) == 1 and abs(nb[1] - cur[1]) == 1:
                if not scene.is_passable(cur[0], nb[1]) or not scene.is_passable(nb[0], cur[1]):
                    continue
            move_cost = base_cost * edge.get(nb, 1.0)
            # 转弯惩罚：与上一段方向比较
            pen = 0.0
            if cur in come_from:
                prev = come_from[cur]
                d1 = (cur[0] - prev[0], cur[1] - prev[1])
                d2 = (nb[0] - cur[0], nb[1] - cur[1])
                if d1 != d2:
                    pen = turn_penalty
            ng = g[cur] + move_cost + pen
            if nb not in g or ng < g[nb]:
                g[nb] = ng
                parent[nb] = cur
                come_from[nb] = cur
                heapq.heappush(open_heap, (ng + heuristic(nb, goal), nb))
    return []


def heuristic(a: RC, b: RC) -> float:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def reconstruct(parent: Dict[RC, RC], start: RC, goal: RC) -> List[RC]:
    path = [goal]
    cur = goal
    while cur != start:
        cur = parent[cur]
        path.append(cur)
    path.reverse()
    return path


def path_length(path: List[RC], resolution: float) -> float:
    """近似路径长度（米）。"""
    if len(path) < 2:
        return 0.0
    total = 0.0
    for a, b in zip(path, path[1:]):
        total += (abs(a[0] - b[0]) ** 2 + abs(a[1] - b[1]) ** 2) ** 0.5 * resolution
    return total
