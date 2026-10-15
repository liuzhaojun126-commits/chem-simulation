# -*- coding: utf-8 -*-
"""任务分配仲裁器（步骤5：消除算法冲突的关键，三级结构边界显式实现）。
仲裁次序：
  on_tick():  L1 DQN 批量分配 → safety 校验 → dispatch / L1.replan
  on_event(): L3 GA 只估值 → L2 拍卖决策 → safety 校验 → dispatch / rollback_to(L1)
禁止：L3 直接改派任务；L2 无事件主动重算；任一层绕过 safety.check。
对应《项目落地实施方案 V1.42》4.2 步骤 5。
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional


class Arbiter:
    """三级结构仲裁器：L1 战略 / L2 战术 / L3 估值。"""

    def __init__(self, l1_allocate: Callable, l2_auction: Callable, l3_bid: Callable,
                 safety_check: Callable[[object], bool]):
        self.l1 = l1_allocate
        self.l2 = l2_auction
        self.l3 = l3_bid
        self.safety_check = safety_check

    def on_tick(self, task_queue: List) -> object:
        """常态：L1 基准方案。"""
        plan = self.l1(task_queue)
        if self.safety_check(plan):
            return plan
        return self.l1(task_queue)  # L1.replan（安全否决后回退重解）

    def on_event(self, fleet: List[str], task) -> object:
        """事件触发：L3 只估值、L2 做决策。"""
        bids = {r: self.l3(r, task) for r in fleet}   # L3 只算出价
        award = self.l2(bids)                          # L2 决策
        if self.safety_check(award):
            return award
        return None                                    # rollback_to(L1)


if __name__ == "__main__":
    def l1(q):
        return {"type": "L1", "tasks": list(q)}

    def l2(bids):
        return {"type": "L2", "winner": min(bids, key=bids.get)}

    def l3(r, task):
        return (r, task)

    arb = Arbiter(l1, l2, l3, lambda p: True)
    print("常态:", arb.on_tick([1, 2, 3]))
    print("事件:", arb.on_event(["agv1", "agv2"], 7))
