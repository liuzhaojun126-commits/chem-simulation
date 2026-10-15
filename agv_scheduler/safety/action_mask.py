# -*- coding: utf-8 -*-
"""动作屏蔽（Action Masking，步骤7）。
mask(s)[j] = 1 iff AGV_j 可接受该任务，且存在满足时间窗与相容性约束的可行路径。
违规动作 → probability := 0；连续违规 → emergency_stop()。
"""
from __future__ import annotations

from typing import Callable, List, Optional


class ActionMasker:
    """向 RL 策略提供可行性掩码 mask ∈ {0,1}^m。"""

    def __init__(self, max_continuous_violation: int = 3):
        self.max_continuous_violation = max_continuous_violation
        self._violation_streak = 0
        self._stopped = False

    def mask(self, feasibility: List[bool]) -> List[int]:
        """feasibility[j] = True 表示动作 j 可接受。返回 {0,1} 掩码。"""
        return [1 if ok else 0 for ok in feasibility]

    def apply(self, probabilities: List[float], feasibility: List[bool]) -> List[float]:
        """违规动作概率置零后归一化（若无可行动作，返回全零）。"""
        m = self.mask(feasibility)
        probs = [p if m[j] == 1 else 0.0 for j, p in enumerate(probabilities)]
        s = sum(probs)
        if s <= 0:
            return [0.0] * len(probs)
        return [p / s for p in probs]

    def on_violation(self) -> bool:
        """记录一次违规动作；连续违规达阈值触发紧急制动。"""
        self._violation_streak += 1
        if self._violation_streak >= self.max_continuous_violation:
            self.emergency_stop()
            return True
        return False

    def on_legal(self):
        self._violation_streak = 0

    def emergency_stop(self):
        """触发减速停车（兜底）。"""
        self._stopped = True

    def reset(self):
        self._violation_streak = 0
        self._stopped = False

    @property
    def stopped(self) -> bool:
        return self._stopped
