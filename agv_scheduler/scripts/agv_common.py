#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ROS 导航共用模块：栅格地图加载 + A* + 坐标转换。
被 agv_nav.py / dispatcher.py 引用（安装后同目录，import 可用）。
"""
import json
import math
import heapq


def load_grid(json_path):
    """加载 warehouse_grid.json，返回 {passable(2D), cols, rows, resolution}。"""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    cols, rows = data["size"]
    res = data["resolution"]
    passable = [[True] * cols for _ in range(rows)]
    for cell in data["cells"]:
        r, c = cell["rc"]
        passable[r][c] = cell["passable"]
    return {"passable": passable, "cols": cols, "rows": rows, "resolution": res}


def world_to_grid(x, y, res):
    return (int(y / res), int(x / res))


def grid_to_world(row, col, res):
    return ((col + 0.5) * res, (row + 0.5) * res)


def normalize_angle(a):
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


def _neighbors(rc, rows, cols):
    r, c = rc
    out = []
    for dr, dc, cost in [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
                         (-1, -1, 1.414), (-1, 1, 1.414), (1, -1, 1.414), (1, 1, 1.414)]:
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            out.append(((nr, nc), cost))
    return out


def astar(passable, start, goal):
    """A* 在栅格上求最短路径，返回 [(row,col), ...]（含起终点）；无解返回 []。"""
    rows = len(passable)
    cols = len(passable[0]) if rows else 0
    if not passable[start[0]][start[1]] or not passable[goal[0]][goal[1]]:
        return []
    g = {start: 0.0}
    parent = {start: None}
    heap = [(abs(start[0] - goal[0]) + abs(start[1] - goal[1]), start)]
    closed = set()
    while heap:
        f, cur = heapq.heappop(heap)
        if cur in closed:
            continue
        if cur == goal:
            path = []
            while cur is not None:
                path.append(cur)
                cur = parent[cur]
            path.reverse()
            return path
        closed.add(cur)
        for nb, cost in _neighbors(cur, rows, cols):
            if nb in closed or not passable[nb[0]][nb[1]]:
                continue
            # 对角线穿墙剪枝
            if abs(nb[0] - cur[0]) == 1 and abs(nb[1] - cur[1]) == 1:
                if not passable[cur[0]][nb[1]] or not passable[nb[0]][cur[1]]:
                    continue
            ng = g[cur] + cost
            if nb not in g or ng < g[nb]:
                g[nb] = ng
                parent[nb] = cur
                heapq.heappush(heap, (ng + abs(nb[0] - goal[0]) + abs(nb[1] - goal[1]), nb))
    return []
