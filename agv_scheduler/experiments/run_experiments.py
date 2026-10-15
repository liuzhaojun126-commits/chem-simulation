# -*- coding: utf-8 -*-
"""实验一键复跑脚本（步骤12—14）：基线对比 / 消融 / 可扩展性。
用法：
  python experiments/run_experiments.py --mode baseline    # 基线对比
  python experiments/run_experiments.py --mode ablation    # 消融实验
  python experiments/run_experiments.py --mode scalability # 可扩展性（3~10 车）
  python experiments/run_experiments.py --mode all         # 全部（默认）
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.experiment import (run_experiments, run_one, default_scene,
                                    STRATEGIES, AGV_START_ZONES)
from scheduling.task_generator import TaskGenerator


def _print_table(title, summary):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)
    hdr = ["指标"] + list(summary.keys())
    print(" | ".join(f"{h:>11s}" for h in hdr))
    for k in summary[list(summary.keys())[0]].keys():
        row = [k] + [f"{summary[s][k]['mean']}" for s in summary.keys()]
        print(" | ".join(f"{x:>11s}" for x in row))


def baseline(scene, rounds=30, out_dir="experiments/results"):
    os.makedirs(out_dir, exist_ok=True)
    summary = run_experiments(scene=scene, n_agvs=5, n_tasks=40, n_rounds=rounds, seed=42,
                              out_csv=os.path.join(out_dir, "baseline.csv"))
    _print_table("基线对比（%d 轮均值）" % rounds, summary)
    return summary


def ablation(scene, rounds=20, out_dir="experiments/results"):
    """消融：A1 去动态权重 / A2 去拍卖 / A3 去安全硬约束 / A4 去 MADQN 协同。"""
    os.makedirs(out_dir, exist_ok=True)
    gen = TaskGenerator(seed=42)
    tasks = [t.__dict__ for t in gen.generate(n_tasks=40)]
    agv_positions = []
    for z in AGV_START_ZONES[:5]:
        ap = scene.zone_access_point(z)
        agv_positions.append(ap if ap else (14, 2))

    configs = {
        "Ours完整": dict(safety=True, madqn=True, strategy="Ours"),
        "A1去动态权重": dict(safety=True, madqn=True, strategy="B2"),
        "A2去拍卖": dict(safety=True, madqn=True, strategy="B1"),
        "A3去安全约束": dict(safety=False, madqn=True, strategy="Ours"),
        "A4去MADQN": dict(safety=True, madqn=False, strategy="Ours"),
    }
    summary = {}
    for name, cfg in configs.items():
        rounds_data = []
        for r in range(rounds):
            import random
            rnd = list(tasks)
            random.Random(42 + r).shuffle(rnd)
            m = run_one(cfg["strategy"], scene, rnd, list(agv_positions),
                        safety_enabled=cfg["safety"], madqn_enabled=cfg["madqn"])
            rounds_data.append(m)
        summary[name] = _agg(rounds_data)

    _print_table("消融实验（%d 轮均值）" % rounds, summary)
    _write_csv(summary, os.path.join(out_dir, "ablation.csv"))
    return summary


def scalability(scene, rounds=15, out_dir="experiments/results"):
    """可扩展性：车队规模 3,4,5,6,8,10 台。"""
    os.makedirs(out_dir, exist_ok=True)
    gen = TaskGenerator(seed=42)
    tasks = [t.__dict__ for t in gen.generate(n_tasks=40)]
    summary = {}
    for n in [3, 4, 5, 6, 8, 10]:
        agv_positions = []
        for z in AGV_START_ZONES[:n]:
            ap = scene.zone_access_point(z)
            agv_positions.append(ap if ap else (14, 2))
        rounds_data = []
        for r in range(rounds):
            import random
            rnd = list(tasks)
            random.Random(42 + r).shuffle(rnd)
            m = run_one("Ours", scene, rnd, list(agv_positions), safety_enabled=True, madqn_enabled=True)
            rounds_data.append(m)
        summary["%d车" % n] = _agg(rounds_data)

    _print_table("可扩展性（Ours，%d 轮均值）" % rounds, summary)
    _write_csv(summary, os.path.join(out_dir, "scalability.csv"))
    return summary


def _agg(rounds):
    import statistics
    out = {}
    for k in rounds[0].keys():
        vals = [r[k] for r in rounds]
        out[k] = {"mean": round(statistics.mean(vals), 3),
                  "std": round(statistics.stdev(vals), 3) if len(vals) > 1 else 0.0}
    return out


def _write_csv(summary, path):
    import csv
    keys = list(summary[list(summary.keys())[0]].keys())
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["config"] + keys)
        for name, agg in summary.items():
            w.writerow([name] + [agg[k]["mean"] for k in keys])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="all", choices=["baseline", "ablation", "scalability", "all"])
    ap.add_argument("--rounds", type=int, default=30)
    args = ap.parse_args()

    scene = default_scene()
    if args.mode in ("baseline", "all"):
        baseline(scene, rounds=min(args.rounds, 30))
    if args.mode in ("ablation", "all"):
        ablation(scene, rounds=min(args.rounds, 20))
    if args.mode in ("scalability", "all"):
        scalability(scene, rounds=min(args.rounds, 15))
