# -*- coding: utf-8 -*-
"""时空冲突检测（步骤7）。
冲突判据：同一栅格的时间窗重叠且间距 < 0.5 m 安全半径。
冲突时按优先级（危化品等级 → 任务紧急度 → 剩余时间窗）确定通行次序。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

# 危化品等级数值（越高越优先，用于排序）
HAZARD_PRIORITY = {
    "oxidizing": 5,
    "corrosive": 5,
    "toxic": 4,
    "flammable": 3,
    "non_hazardous": 1,
}


@dataclass
class TimeWindow:
    """某路径段（栅格）的占用时间区间 [t_in, t_out]。"""
    rc: Tuple[int, int]
    t_in: float
    t_out: float
    agv_id: str
    hazard_class: str = "non_hazardous"
    urgency: float = 0.0
    remaining_time: float = 1e9


@dataclass
class Conflict:
    """一次时空冲突记录。"""
    rc: Tuple[int, int]
    a: TimeWindow
    b: TimeWindow
    resolved_order: List[str]  # 通行次序（先到先走）


def windows_overlap(a: TimeWindow, b: TimeWindow) -> bool:
    """区间重叠判定 [a.t_in, a.t_out) ∩ [b.t_in, b.t_out) 是否非空。"""
    return a.t_in < b.t_out and b.t_in < a.t_out


def _priority_key(w: TimeWindow) -> Tuple:
    """优先级：危化品等级(降序) → 紧急度(降序) → 剩余时间窗(升序)。"""
    return (-HAZARD_PRIORITY.get(w.hazard_class, 1), -w.urgency, w.remaining_time)


def detect_conflicts(windows: List[TimeWindow], safety_radius: float = 0.5) -> List[Conflict]:
    """检测所有两两时间窗冲突。"""
    conflicts: List[Conflict] = []
    n = len(windows)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = windows[i], windows[j]
            if a.rc != b.rc:
                continue
            if not windows_overlap(a, b):
                continue
            # 同一栅格时间窗重叠即违规交互（间距已由"同一栅格"保证 < 0.5 m）
            ordered = sorted([a, b], key=_priority_key)
            conflicts.append(Conflict(a.rc, a, b, [w.agv_id for w in ordered]))
    return conflicts


def resolve_order(a: TimeWindow, b: TimeWindow) -> List[str]:
    """返回两车的通行次序（先行的 AGV id 在前）。"""
    ordered = sorted([a, b], key=_priority_key)
    return [w.agv_id for w in ordered]
