# -*- coding: utf-8 -*-
"""指标采集与统计（步骤12：统一评价框架）。
指标：T_makespan, T_wait, L_total, N_conflict, N_violation,
      congestion_rate, E_energy, brake_count。
"""
from __future__ import annotations

import csv
import json
import os
from typing import Dict, List


class MetricsCollector:
    """收集一次实验运行的指标。"""

    FIELDS = ["makespan", "wait", "total_length", "conflict", "violation",
              "congestion_rate", "energy", "brake_count"]

    def __init__(self):
        self.events: List[dict] = []
        self.counters: Dict[str, float] = {f: 0.0 for f in self.FIELDS}

    def add(self, event: str, value: float = 1.0, **meta):
        self.events.append({"event": event, "value": value, **meta})

    def incr(self, key: str, value: float = 1.0):
        if key in self.counters:
            self.counters[key] += value

    def set(self, key: str, value: float):
        self.counters[key] = value

    def summary(self) -> dict:
        return dict(self.counters)

    def to_csv(self, path: str):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["event", "value"])
            for e in self.events:
                w.writerow([e["event"], e["value"]])

    def to_json(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"counters": self.counters, "events": self.events}, f, ensure_ascii=False, indent=1)


def summarize_runs(collectors: List[MetricsCollector]) -> dict:
    """多轮重复 → 均值±标准差（30 轮统计规范）。"""
    import statistics
    out = {}
    for f in MetricsCollector.FIELDS:
        vals = [c.counters[f] for c in collectors]
        if vals:
            out[f] = {"mean": round(statistics.mean(vals), 3),
                      "std": round(statistics.stdev(vals), 3) if len(vals) > 1 else 0.0}
    return out
