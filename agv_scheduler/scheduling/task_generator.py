# -*- coding: utf-8 -*-
"""任务生成器（步骤3：非齐次泊松过程 + 优先级合成）。
λ_i(t) = λ_i^base · (1 + A·sin(2πt/T + φ_i))
任务字段：task_id, chemical, hazard_class, mass, src, dst, t_release, t_due, priority
priority = 0.6·hazard_class + 0.4·urgency
对应《项目落地实施方案 V1.42》4.1 步骤 3。
"""
from __future__ import annotations

import csv
import math
import os
import random
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

from simulation.scene import CATEGORY_HAZARD, HAZARD_CLASSES

# 危化品等级分值（越高越危险越优先）
HAZARD_SCORE = {
    "corrosive": 5,
    "oxidizing": 5,
    "toxic": 4,
    "flammable": 3,
    "non_hazardous": 1,
}


@dataclass
class Task:
    task_id: int
    chemical: str          # 品类
    hazard_class: str      # 危化品等级
    mass: float            # kg
    src: str               # 源点（货架 zone id）
    dst: str               # 目的地（工位/装卸点 zone id）
    t_release: float       # 释放时刻（min）
    t_due: float           # 截止时刻（min）
    priority: float


class TaskGenerator:
    """按非齐次泊松过程生成化工仓储异构任务流。"""

    def __init__(self, config: Optional[dict] = None, seed: Optional[int] = None):
        if config is None:
            config = self._default_config()
        cfg = (config or {}).get("task", {})
        self.period = cfg.get("arrival", {}).get("period_T", 480.0)
        self.amplitude = cfg.get("arrival", {}).get("amplitude_A", 0.4)
        self.phases = cfg.get("arrival", {}).get("phases_phi", {})
        self.base_rate = cfg.get("base_rate", {})
        self.priority_cfg = cfg.get("priority", {})
        self.w_hazard = self.priority_cfg.get("w_hazard", 0.6)
        self.w_urgency = self.priority_cfg.get("w_urgency", 0.4)
        self.due_cfg = cfg.get("due_time", {})
        self.mass_range = cfg.get("mass_kg", [1.0, 50.0])
        self.rng = random.Random(seed)

        self.srcs = [z for z in self.base_rate.keys()]
        self.dsts = ["P1", "P2", "WS1", "WS2", "WS3", "WS4", "WS5", "WS6"]

    @staticmethod
    def _default_config() -> dict:
        """加载默认 task.yaml 配置。"""
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cfg_path = os.path.join(here, "config", "task.yaml")
        import _mini_yaml
        return _mini_yaml.load(cfg_path)

    # -- 强度函数 -------------------------------------------------
    def intensity(self, category: str, t: float) -> float:
        """λ_i(t)（件/班）：品类 i 在班内时刻 t 的到达强度（规格公式）。"""
        lam = self.base_rate.get(category, 1.0)
        phi = self.phases.get(category, 0.0)
        return max(0.0, lam * (1.0 + self.amplitude * math.sin(2 * math.pi * t / self.period + phi)))

    def _thinning_poisson(self, category: str, t_end: float) -> List[float]:
        """稀疏化（thinning）模拟非齐次泊松过程，返回该品类任务到达时刻（分钟）。
        λ^base 单位为「件/班」，1 班 = 480 min，故每分钟速率 = λ_i(t)/480。"""
        lam_per_min_max = self.base_rate.get(category, 1.0) * (1.0 + self.amplitude) / 480.0
        arrivals = []
        t = 0.0
        while t < t_end:
            t += -math.log(1.0 - self.rng.random()) / max(lam_per_min_max, 1e-6)
            if t >= t_end:
                break
            lam_min = self.intensity(category, t) / 480.0
            if self.rng.random() <= lam_min / lam_per_min_max:
                arrivals.append(t)
        return arrivals

    def generate(self, n_tasks: Optional[int] = None, t_end: float = 1440.0) -> List[Task]:
        """生成任务流。t_end 单位为分钟（默认 3 班 = 1440 min，约 500 任务）。
        n_tasks 缺省时按强度函数累计到达数。支持随机种子复现同一任务流。"""
        all_arrivals = []
        for cat in self.srcs:
            for t in self._thinning_poisson(cat, t_end):
                all_arrivals.append((t, cat))
        all_arrivals.sort(key=lambda x: x[0])

        if n_tasks is not None:
            # 截断或重复补足到指定数量
            if len(all_arrivals) >= n_tasks:
                all_arrivals = all_arrivals[:n_tasks]
            else:
                while len(all_arrivals) < n_tasks:
                    cat = self.rng.choice(self.srcs)
                    t = self.rng.uniform(0, t_end)
                    all_arrivals.append((t, cat))
                    all_arrivals.sort(key=lambda x: x[0])

        tasks = []
        for i, (t_rel, cat) in enumerate(all_arrivals):
            hazard = CATEGORY_HAZARD[cat]
            mass = round(self.rng.uniform(*self.mass_range), 1)
            src = "rack_" + cat
            dst = self.rng.choice(self.dsts)
            due_min = self.rng.uniform(self.due_cfg.get("min_hours", 1.0) * 60,
                                       self.due_cfg.get("max_hours", 4.0) * 60)
            t_due = t_rel + due_min
            urgency = self._urgency(t_due - t_rel)
            priority = round(self.w_hazard * HAZARD_SCORE[hazard] + self.w_urgency * urgency, 3)
            tasks.append(Task(
                task_id=i,
                chemical=cat,
                hazard_class=hazard,
                mass=mass,
                src=src,
                dst=dst,
                t_release=round(t_rel, 2),
                t_due=round(t_due, 2),
                priority=priority,
            ))
        return tasks

    def _urgency(self, remaining: float) -> float:
        """剩余时间窗越短越紧急（0~1）。"""
        span = self.due_cfg.get("max_hours", 4.0) * 60 - self.due_cfg.get("min_hours", 1.0) * 60
        return max(0.0, min(1.0, 1.0 - remaining / max(span, 1.0)))

    # -- 导出 -------------------------------------------------
    def to_csv(self, tasks: List[Task], path: str):
        fieldnames = list(asdict(tasks[0]).keys()) if tasks else []
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for t in tasks:
                w.writerow(asdict(t))

    def distribution(self, tasks: List[Task]) -> Dict[str, int]:
        dist = {}
        for t in tasks:
            dist[t.chemical] = dist.get(t.chemical, 0) + 1
        return dist


if __name__ == "__main__":
    gen = TaskGenerator(seed=42)
    tasks = gen.generate(t_end=480.0)
    print("生成任务数:", len(tasks))
    print("品类分布:", gen.distribution(tasks))
    for t in tasks[:5]:
        print(asdict(t))
