# -*- coding: utf-8 -*-
"""
仿真空间演示脚本（P1 交付物联调）：
  1. 加载并栅格化化工仓库场景（40×28 栅格）
  2. 生成任务流（非齐次泊松过程）
  3. A* 基础导航：从装卸点 P1 → 货架 → 工位
  4. 安全相容性校验（硬剪枝 + 禁行区）
  5. 渲染仿真空间 PNG（含路径与 AGV 标记）
对应《项目落地实施方案 V1.42》4.1 步骤 1—4。
"""
from __future__ import annotations

import os
import sys

# 确保包根目录在 sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scheduling.task_generator import TaskGenerator
from safety.engine import SafetyEngine
from safety.compatibility import CompatibilityMatrix
from planning.astar import astar, path_length
from simulation.scene import scene_from_config_file, CATEGORY_HAZARD
from viz.render_grid import render_scene


def main():
    here = ROOT
    cfg = os.path.join(here, "config", "scene.yaml")
    scene = scene_from_config_file(cfg)
    print("=" * 60)
    print("化工仓储 AGV 协同调度仿真平台 —— 仿真空间构建")
    print("=" * 60)
    print(f"场景: {scene.cols}×{scene.rows} 栅格, 分辨率 {scene.resolution} m/格")
    n_pass = sum(1 for r in range(scene.rows) for c in range(scene.cols) if scene.is_passable(r, c))
    print(f"可通行栅格: {n_pass}/{scene.cols * scene.rows}")

    # 1) 任务生成
    gen = TaskGenerator(seed=42)
    tasks = gen.generate()  # 默认 3 班 (1440 min)，约 500 任务
    print(f"\n[任务生成] 生成任务 {len(tasks)} 个，品类分布:")
    for k, v in sorted(gen.distribution(tasks).items()):
        print(f"   {k:16s}: {v}")

    # 2) 安全相容性矩阵
    cm = CompatibilityMatrix()
    print("\n[安全] 相容性矩阵（0=不可共用路径）:")
    cats = list(CATEGORY_HAZARD.keys())
    print("        " + "".join(f"{c[:6]:>7s}" for c in cats))
    mat = cm.matrix()
    for i in cats:
        print(f"{i:8s}" + "".join(f"{mat[i][j]:>7d}" for j in cats))

    # 3) 基础导航：P1 → 碱类货架前沿 → 工位 WS1
    # 取装卸点 P1、货架 alkali、工位 WS1 的中心栅格
    def zone_center(zone_id):
        cells = scene.cells_of_zone(zone_id)
        r = sum(x[0] for x in cells) // len(cells)
        c = sum(x[1] for x in cells) // len(cells)
        return (r, c)

    def nearest_passable(rc):
        """若给定栅格不可通行（如货架内部），BFS 找最近的可行走栅格。"""
        from collections import deque
        if scene.is_passable(*rc):
            return rc
        seen = {rc}
        q = deque([rc])
        while q:
            r, c = q.popleft()
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if (nr, nc) in seen or not (0 <= nr < scene.rows and 0 <= nc < scene.cols):
                    continue
                if scene.is_passable(nr, nc):
                    return (nr, nc)
                seen.add((nr, nc))
                q.append((nr, nc))
        return rc

    start = nearest_passable(zone_center("P1"))
    rack_front = nearest_passable(zone_center("rack_alkali"))
    ws = nearest_passable(zone_center("WS1"))

    # 禁行区 + 非通行栅格作为 A* 障碍
    forbidden = set()
    for r in range(scene.rows):
        for c in range(scene.cols):
            if not scene.is_passable(r, c):
                forbidden.add((r, c))

    print("\n[导航] 起点 P1 -> 碱类货架前沿 -> 工位 WS1")
    leg1 = astar(scene, start, rack_front, forbidden=forbidden)
    leg2 = astar(scene, rack_front, ws, forbidden=forbidden)
    full_path = leg1 + (leg2 if leg2 else [])
    print(f"   路径长度: {len(full_path)} 栅格 ≈ {path_length(full_path, scene.resolution):.1f} m")
    print(f"   导航成功: {len(leg1) > 0 and len(leg2) > 0}")

    # 4) 安全校验：载运碱类（腐蚀性）能否通行于各区域
    eng = SafetyEngine()
    print("\n[安全校验] 载运 'alkali(碱类/腐蚀性)':")
    for z in ["main_aisle", "cross_aisle", "no_go_Z1", "no_go_Z2", "rack_acid"]:
        zcat = scene.category_of_zone(z)
        ok = eng.compatible("alkali", zcat)
        print(f"   通行 {z:14s} (品类={zcat or 'None'}) -> {'允许' if ok else '禁止'}")

    # 5) 渲染仿真空间
    out_png = os.path.join(here, "viz", "warehouse_scene_demo.png")
    agvs = {"agv1": start, "agv2": zone_center("CP1"), "agv3": zone_center("CP2")}
    render_scene(scene, path=full_path, agvs=agvs, out_path=out_png)
    print(f"\n[渲染] 仿真空间图: {out_png}")

    print("\n" + "=" * 60)
    print("仿真空间构建完成 [OK]  (P1 步骤 1—4 核心交付物)")
    print("=" * 60)


if __name__ == "__main__":
    main()
