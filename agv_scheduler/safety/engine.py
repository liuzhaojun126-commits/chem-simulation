# -*- coding: utf-8 -*-
"""安全约束规则引擎统一入口（步骤7）。
对上层调度/规划提供统一校验接口：相容性判定 → 时空冲突检测 → 动作屏蔽。
"""
from __future__ import annotations

from typing import List, Optional

from safety.action_mask import ActionMasker
from safety.collision import Conflict, TimeWindow, detect_conflicts
from safety.compatibility import CompatibilityMatrix


class SafetyEngine:
    """安全约束层：横跨调度/规划/执行，对下行指令具备一票否决权。"""

    def __init__(self):
        self.compat = CompatibilityMatrix()
        self.masker = ActionMasker()

    # 1) 相容性判定（硬剪枝）
    def compatible(self, payload_category: str, zone_category: Optional[str]) -> bool:
        if zone_category is None:
            return True
        return self.compat.is_compatible(payload_category, zone_category)

    def path_allowed(self, payload_category: str, zone_categories: List[Optional[str]]) -> bool:
        return self.compat.path_allowed_for(payload_category, zone_categories)

    # 2) 时空冲突检测
    def detect_conflicts(self, windows: List[TimeWindow], safety_radius: float = 0.5) -> List[Conflict]:
        return detect_conflicts(windows, safety_radius)

    # 3) 动作屏蔽
    def mask(self, feasibility: List[bool]) -> List[int]:
        return self.masker.mask(feasibility)

    def check_and_dispatch(self, plan, feasibility: List[bool]):
        """统一校验：mask 全零则拒绝。返回 (ok, 掩码)。"""
        m = self.mask(feasibility)
        return any(m), m


if __name__ == "__main__":
    eng = SafetyEngine()
    print("acid vs alkali 相容:", eng.compatible("acid", "alkali"))
    print("acid vs general 相容:", eng.compatible("acid", "general"))
    print("oxidizer vs organic_solvent 相容:", eng.compatible("oxidizer", "organic_solvent"))
    w1 = TimeWindow((10, 20), 0.0, 5.0, "agv1", "corrosive", 2.0, 10.0)
    w2 = TimeWindow((10, 20), 3.0, 8.0, "agv2", "non_hazardous", 1.0, 20.0)
    print("冲突:", eng.detect_conflicts([w1, w2]))
