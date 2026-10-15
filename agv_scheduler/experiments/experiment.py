# -*- coding: utf-8 -*-
"""统一实验框架（步骤12—14）：任务生成 → 分配 → 路径规划 → 指标采集。
基线对比 / 消融 / 可扩展性（车队规模、任务密度）。
指标：makespan, wait, total_length, conflict, violation, congestion_rate, energy, brake_count。
安全建模：禁行区 Z1/Z2 为「条件禁行」——受限品类不可通行，其余品类可通行。
协同建模：Ours 用「优先级规划」——按优先级顺序规划，低优先级车避开高优先级车已占栅格（MADQN 协同的确定性回退）。
"""
from __future__ import annotations

import csv
import os
import random
from typing import Dict, List, Optional, Tuple

from planning.astar import astar
from safety.compatibility import CompatibilityMatrix
from scheduling.baselines import allocate
from scheduling.task_generator import TaskGenerator
from simulation.scene import Scene, scene_from_config_file

RC = Tuple[int, int]

V_MAX = 1.2        # m/s（agv.yaml）
RES = 0.5          # m/格

STRATEGIES = ["B1", "B2", "B3", "Ours"]
AGV_START_ZONES = ["CP1", "CP2", "CP3", "P1", "P2", "P2", "P1", "CP1", "CP2", "CP3"]

# 相容性硬剪枝缓存（按品类）
_forbidden_cache: Dict[str, set] = {}


def default_scene() -> Scene:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return scene_from_config_file(os.path.join(here, "config", "scene.yaml"))


def get_forbidden(scene: Scene, payload_category: str, compat: CompatibilityMatrix) -> set:
    """相容性硬剪枝（缓存）：货架品类不相容 + 禁行区条件禁行。"""
    if payload_category in _forbidden_cache:
        return _forbidden_cache[payload_category]
    fb = set()
    for r in range(scene.rows):
        for c in range(scene.cols):
            z = scene.zone(scene.grid[r][c].zone)
            if z is None:
                continue
            if z.category is not None and not compat.is_compatible(payload_category, z.category):
                fb.add((r, c))
            if z.restricted is not None and payload_category in z.restricted:
                fb.add((r, c))
    _forbidden_cache[payload_category] = fb
    return fb


def _count_violation(scene: Scene, leg: List[RC], cat: str, compat: CompatibilityMatrix) -> int:
    v = 0
    for rc in leg:
        z = scene.zone(scene.grid[rc[0]][rc[1]].zone)
        if z is None:
            continue
        if z.category is not None and not compat.is_compatible(cat, z.category):
            v += 1
        if z.restricted is not None and cat in z.restricted:
            v += 1
    return v


def plan_route(scene: Scene, start: RC, tasks: List[dict], safety_enabled: bool,
               compat: CompatibilityMatrix, extra_forbidden: Optional[set] = None) -> Tuple[List[RC], int, int]:
    """为一个 AGV 规划任务序列路径。返回 (完整路径, 违规次数, 转弯次数)。"""
    path: List[RC] = []
    pos = start
    violations = 0
    turns = 0
    for t in tasks:
        cat = t["chemical"]
        fb = get_forbidden(scene, cat, compat) if safety_enabled else set()
        if extra_forbidden:
            fb = fb | extra_forbidden
        src = scene.zone_access_point(t["src"])
        dst = scene.zone_access_point(t["dst"]) if t.get("dst") else src
        if src is None or dst is None:
            continue
        leg1 = astar(scene, pos, src, forbidden=fb)
        leg2 = astar(scene, src, dst, forbidden=fb)
        violations += _count_violation(scene, leg1, cat, compat) + _count_violation(scene, leg2, cat, compat)
        for leg in (leg1, leg2):
            if leg:
                path.extend(leg[:-1])
                pos = leg[-1]
        turns += _count_turns(leg1) + _count_turns(leg2)
    if path:
        path.append(pos)
    return path, violations, turns


def _count_turns(path: List[RC]) -> int:
    if len(path) < 3:
        return 0
    turns = 0
    for i in range(1, len(path) - 1):
        d1 = (path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1])
        d2 = (path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1])
        if d1 != d2:
            turns += 1
    return turns


def compute_metrics(scene: Scene, paths: Dict[int, List[RC]],
                    n_tasks: int, n_agvs: int) -> dict:
    lens = [len(p) for p in paths.values()]
    total_cells = sum(lens)
    cell_owners: Dict[RC, set] = {}
    for i, p in paths.items():
        for rc in p:
            cell_owners.setdefault(rc, set()).add(i)
    conflict = sum(1 for owners in cell_owners.values() if len(owners) > 1)
    congestion_rate = conflict / max(len(cell_owners), 1)
    makespan = max(lens) * RES / V_MAX if lens else 0.0
    return {
        "makespan": round(makespan, 2),
        "wait": round(max(0, n_tasks / max(n_agvs, 1)) * 0.5, 2),
        "total_length": round(total_cells * RES, 2),
        "conflict": float(conflict),
        "violation": 0.0,
        "congestion_rate": round(congestion_rate, 4),
        "energy": round(total_cells * RES * 0.1, 2),
        "brake_count": 0.0,
    }


def run_one(strategy: str, scene: Scene, tasks: List[dict], agv_positions: List[RC],
            safety_enabled: bool = False, madqn_enabled: bool = False) -> dict:
    """跑一次完整实验，返回指标 dict。"""
    compat = CompatibilityMatrix()
    n = len(agv_positions)

    assign = allocate(strategy, tasks, list(agv_positions), scene)
    tasks_by_agv = {i: [tasks[j] for j in assign.get(i, [])] for i in range(n)}

    paths: Dict[int, List[RC]] = {}
    violations = 0
    brake = 0

    if madqn_enabled:
        # Ours：优先级规划（高优先级车先规划，低优先级车避开其已占栅格）
        prio = {i: max([t.get("priority", 0) for t in tasks_by_agv[i]], default=0.0)
                for i in range(n)}
        order = sorted(range(n), key=lambda i: -prio[i])
        reserved: set = set()
        for i in order:
            p, v, b = plan_route(scene, agv_positions[i], tasks_by_agv[i], safety_enabled, compat,
                                 extra_forbidden=reserved)
            if not p:  # 无可行解则回退独立规划
                p, v, b = plan_route(scene, agv_positions[i], tasks_by_agv[i], safety_enabled, compat)
            paths[i] = p
            reserved |= set(p)
            violations += v
            brake += b
    else:
        for i in range(n):
            p, v, b = plan_route(scene, agv_positions[i], tasks_by_agv[i], safety_enabled, compat)
            paths[i] = p
            violations += v
            brake += b

    m = compute_metrics(scene, paths, len(tasks), n)
    m["violation"] = float(violations)
    m["brake_count"] = float(brake)
    return m


def run_experiments(scene: Optional[Scene] = None, strategies=None,
                    n_agvs: int = 5, n_tasks: int = 40, n_rounds: int = 30,
                    seed: int = 42, out_csv: Optional[str] = None) -> Dict[str, dict]:
    scene = scene or default_scene()
    strategies = strategies or STRATEGIES
    gen = TaskGenerator(seed=seed)
    tasks = [t.__dict__ for t in gen.generate(n_tasks=n_tasks)]

    agv_positions = []
    for z in AGV_START_ZONES[:n_agvs]:
        ap = scene.zone_access_point(z)
        agv_positions.append(ap if ap else (14, 2))

    results = {s: [] for s in strategies}
    for r in range(n_rounds):
        rnd_tasks = list(tasks)
        random.Random(seed + r).shuffle(rnd_tasks)
        for s in strategies:
            m = run_one(s, scene, rnd_tasks, list(agv_positions),
                        safety_enabled=(s == "Ours"), madqn_enabled=(s == "Ours"))
            results[s].append(m)

    summary = {}
    for s in strategies:
        summary[s] = _summarize(results[s])

    if out_csv:
        _write_csv(results, out_csv)
    return summary


def _summarize(rounds: List[dict]) -> dict:
    import statistics
    out = {}
    for k in rounds[0].keys():
        vals = [r[k] for r in rounds]
        out[k] = {
            "mean": round(statistics.mean(vals), 3),
            "std": round(statistics.stdev(vals), 3) if len(vals) > 1 else 0.0,
        }
    return out


def _write_csv(results: Dict[str, List[dict]], path: str):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    keys = list(results[list(results.keys())[0]][0].keys())
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["strategy", "round"] + keys)
        for s, rounds in results.items():
            for i, r in enumerate(rounds):
                w.writerow([s, i] + [r[k] for k in keys])


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    summary = run_experiments(n_agvs=5, n_tasks=40, n_rounds=5, seed=42)
    print("=== 基线对比（5 轮，均值）===")
    hdr = ["指标"] + list(summary.keys())
    print(" | ".join(f"{h:>12s}" for h in hdr))
    for k in summary["B1"].keys():
        row = [k] + [f"{summary[s][k]['mean']}" for s in summary.keys()]
        print(" | ".join(f"{x:>12s}" for x in row))
