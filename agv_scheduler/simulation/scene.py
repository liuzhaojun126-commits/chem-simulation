# -*- coding: utf-8 -*-
"""
化工仓储仿真空间 —— 场景模型与栅格化（步骤1）

将 20m × 14m 的化工原料仓库离散为 40 × 28 栅格（0.5 m/格），
每个栅格带属性 (可通行, 安全等级, 所属区域)，作为路径搜索与 RL 环境的共用底图。

对应《项目落地实施方案 V1.42》4.1 步骤 1。
坐标约定：x 向右 (0~20 m)，y 向上 (0~14 m)；栅格 (row, col)：
    row = int(y / resolution)，col = int(x / resolution)
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:  # 若无 PyYAML，仅 JSON 导出仍然可用
    yaml = None


# ---------------------------------------------------------------
# 语义层：化学品等级与品类
# ---------------------------------------------------------------
HAZARD_CLASSES = {
    "corrosive": "腐蚀性",
    "flammable": "易燃",
    "toxic": "有毒",
    "oxidizing": "氧化性",
    "non_hazardous": "非危化",
}

# 品类 → 危化品等级
CATEGORY_HAZARD = {
    "alkali": "corrosive",
    "acid": "corrosive",
    "organic_solvent": "flammable",
    "catalyst": "non_hazardous",
    "oxidizer": "oxidizing",
    "general": "non_hazardous",
    "toxic": "toxic",
    "consumable": "non_hazardous",
}

# 相容性矩阵（品类级）0 = 不可共用路径区域
INCOMPATIBLE_PAIRS = [
    ("acid", "alkali"),                 # Z1 中和反应
    ("oxidizer", "organic_solvent"),    # Z2 燃爆风险
]

# 危化品等级级相容性（氧化性 × 易燃不可共用）
HAZARD_INCOMPATIBLE = [("oxidizing", "flammable")]


@dataclass
class Zone:
    """场景中的一块矩形区域。"""
    id: str
    name: str
    x0: float
    y0: float
    x1: float
    y1: float
    kind: str            # wall / rack / no_go / loading / ws / cp / passing / main_aisle / cross_aisle
    passable: bool = True
    safety: int = 0      # 0 一般 / 1 储区 / 3 禁行
    category: Optional[str] = None   # 语义层：区域所属品类（货架/禁行区）
    hazard: Optional[str] = None     # 语义层：区域危化品等级标签
    restricted: Optional[list] = None  # 禁行区 Z1/Z2 的受限品类对（条件禁行）


@dataclass
class Cell:
    """栅格单元。"""
    rc: Tuple[int, int]  # (row, col)
    passable: bool
    safety: int
    zone: str


@dataclass
class Scene:
    """仿真空间：几何 + 栅格底图 + 语义。"""
    name: str
    resolution: float
    cols: int
    rows: int
    zones: List[Zone] = field(default_factory=list)
    grid: List[List[Cell]] = field(default_factory=list)  # grid[row][col]

    # -- 便捷访问 -------------------------------------------------
    def cell(self, row: int, col: int) -> Optional[Cell]:
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return self.grid[row][col]
        return None

    def is_passable(self, row: int, col: int) -> bool:
        c = self.cell(row, col)
        return bool(c and c.passable)

    def to_xy(self, row: int, col: int) -> Tuple[float, float]:
        """栅格中心 → 米坐标。"""
        return ((col + 0.5) * self.resolution, (row + 0.5) * self.resolution)

    def to_rc(self, x: float, y: float) -> Tuple[int, int]:
        """米坐标 → 栅格索引。"""
        return (int(y / self.resolution), int(x / self.resolution))

    def cells_of_zone(self, zone_id: str) -> List[Tuple[int, int]]:
        out = []
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c].zone == zone_id:
                    out.append((r, c))
        return out

    def zone_access_point(self, zone_id: str) -> Optional[Tuple[int, int]]:
        """返回区域附近最近的可行走栅格（货架/禁行区等不可通行区域的"前沿"接入点）。"""
        from collections import deque
        cells = self.cells_of_zone(zone_id)
        if not cells:
            return None
        center = (sum(r for r, _ in cells) // len(cells),
                  sum(c for _, c in cells) // len(cells))
        if self.is_passable(*center):
            return center
        seen = {center}
        q = deque([center])
        while q:
            r, c = q.popleft()
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if (nr, nc) in seen or not (0 <= nr < self.rows and 0 <= nc < self.cols):
                    continue
                if self.is_passable(nr, nc):
                    return (nr, nc)
                seen.add((nr, nc))
                q.append((nr, nc))
        return center

    def zone(self, zone_id: str) -> Optional[Zone]:
        for z in self.zones:
            if z.id == zone_id:
                return z
        return None

    def category_of_zone(self, zone_id: str) -> Optional[str]:
        z = self.zone(zone_id)
        return z.category if z else None

    # -- 序列化 ---------------------------------------------------
    def grid_as_dict(self) -> dict:
        """导出栅格底图（与实施方案 step1 的 YAML 示例同构）。"""
        cells = []
        for r in range(self.rows):
            for c in range(self.cols):
                cell = self.grid[r][c]
                cells.append({
                    "rc": [r, c],
                    "passable": cell.passable,
                    "safety": cell.safety,
                    "zone": cell.zone,
                })
        return {
            "resolution": self.resolution,
            "size": [self.cols, self.rows],
            "cells": cells,
        }


# ---------------------------------------------------------------
# 场景构建
# ---------------------------------------------------------------
def build_scene(config: dict) -> Scene:
    """由 scene.yaml 的配置字典构建 Scene（含栅格化）。"""
    sc = config["scene"]
    bounds = sc["bounds"]
    res = config["grid"]["resolution"]
    cols, rows = config["grid"]["size"]
    wall = sc["wall_thickness"]

    x_min, x_max = bounds["x"]
    y_min, y_max = bounds["y"]

    zones: List[Zone] = []

    def add(z: Zone):
        zones.append(z)

    # 1) 外墙（四边）
    add(Zone("wall_bottom", "外墙-底", x_min, y_min, x_max, y_min + wall, "wall", False, 0))
    add(Zone("wall_top", "外墙-顶", x_min, y_max - wall, x_max, y_max, "wall", False, 0))
    add(Zone("wall_left", "外墙-左", x_min, y_min, x_min + wall, y_max, "wall", False, 0))
    add(Zone("wall_right", "外墙-右", x_max - wall, y_min, x_max, y_max, "wall", False, 0))

    # 2) 8 个储区货架
    for rk in config["racks"]:
        cat = rk["category"]
        add(Zone(
            rk["id"], "货架-" + cat, rk["x"][0], rk["y"][0], rk["x"][1], rk["y"][1],
            "rack", False, 1, category=cat, hazard=CATEGORY_HAZARD[cat],
        ))

    # 3) 禁行区 Z1/Z2（条件禁行：对受限品类不可通行，其余品类可通行）
    for nz in config["no_go_zones"]:
        pair = nz["pair"]
        add(Zone(
            nz["id"], f"禁行区({pair[0]}×{pair[1]})",
            nz["x"][0], nz["y"][0], nz["x"][1], nz["y"][1],
            "no_go", True, nz["safety"], restricted=list(pair),
        ))

    # 4) 装卸点 P1/P2
    for lp in config["loading_points"]:
        add(Zone(lp["id"], "装卸点" + lp["id"], lp["x"][0], lp["y"][0], lp["x"][1], lp["y"][1], "loading"))

    # 5) 工位 WS1—WS6
    for ws in config["workstations"]:
        add(Zone(ws["id"], "工位" + ws["id"], ws["x"][0], ws["y"][0], ws["x"][1], ws["y"][1], "ws"))

    # 6) 充电桩 CP1—CP3
    for cp in config["charging_piles"]:
        add(Zone(cp["id"], "充电桩" + cp["id"], cp["x"][0], cp["y"][0], cp["x"][1], cp["y"][1], "cp"))

    # 7) 会车避让点
    for pp in config["passing_points"]:
        add(Zone(pp["id"], "避让点" + pp["id"], pp["x"][0], pp["y"][0], pp["x"][1], pp["y"][1], "passing"))

    # 主通道
    my = config["main_aisle"]["y_range"]
    add(Zone("main_aisle", "主通道", x_min + wall, my[0], x_max - wall, my[1], "main_aisle"))

    scene = Scene(config["scene"]["name"], res, cols, rows, zones)

    # 栅格化：按优先级从低到高覆盖（后写的覆盖先写的）。
    # 主通道先铺底，装卸点/工位/充电桩/避让点等特征再覆盖，
    # 货架/禁行区/外墙等不可通行要素最后覆盖。
    grid = [[None] * cols for _ in range(rows)]

    priority = ["main_aisle", "passing", "loading", "ws", "cp", "rack", "no_go", "wall"]

    for kind in priority:
        for z in zones:
            if z.kind != kind:
                continue
            r0, c0 = scene.to_rc(z.x0, z.y0)
            r1, c1 = scene.to_rc(z.x1, z.y1)
            for r in range(r0, r1):
                for c in range(c0, c1):
                    if 0 <= r < rows and 0 <= c < cols:
                        grid[r][c] = Cell((r, c), z.passable, z.safety, z.id)

    # 其余空白 → 交叉通道（可通行地面）
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] is None:
                grid[r][c] = Cell((r, c), True, 0, "cross_aisle")

    scene.grid = grid
    return scene


def load_scene_config(path: str) -> dict:
    if yaml is not None:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    # 回退：无 PyYAML 时使用内置极简解析器
    import _mini_yaml
    return _mini_yaml.load(path)


def scene_from_config_file(path: str) -> Scene:
    return build_scene(load_scene_config(path))


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    cfg = os.path.join(here, "..", "config", "scene.yaml")
    s = scene_from_config_file(cfg)
    d = s.grid_as_dict()
    out = os.path.join(here, "warehouse_grid.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    print(f"[scene] 栅格底图已生成: {out}  ({s.cols}×{s.rows}, res={s.resolution}m)")
