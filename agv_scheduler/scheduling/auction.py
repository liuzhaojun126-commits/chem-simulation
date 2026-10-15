# -*- coding: utf-8 -*-
"""分布式拍卖（步骤5 L2 / 步骤9：无中心协调者的任务在线再分配）。
事件触发 → 任务发布 → 各车独立出价（由 L3 GA 计算）→ 出价最低者中标 → 更新任务序列。
引入价格调整因子 ε 缓解反复竞价。
对应《项目落地实施方案 V1.42》4.2 步骤 5、4.3 步骤 9。
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional


class Auction:
    """分布式拍卖解析器。"""

    def __init__(self, price_adjust_epsilon: float = 0.05):
        self.epsilon = price_adjust_epsilon

    def resolve(self, bids: Dict[str, float]) -> Optional[str]:
        """bids: {agv_id: 出价}。返回中标 AGV id（出价最低者）；空则 None。"""
        if not bids:
            return None
        return min(bids, key=bids.get)

    def adjusted_bid(self, raw_bid: float, previous_bid: Optional[float] = None) -> float:
        """价格调整因子 ε：对反复竞价者的出价做微调。"""
        if previous_bid is None:
            return raw_bid
        return raw_bid * (1.0 + self.epsilon)


def online_reallocate(tasks: List[int], fleet: Dict[str, list],
                      bid_fn: Callable[[str, int], float],
                      auction: Optional[Auction] = None) -> Optional[Dict[str, str]]:
    """对未完成任务触发再拍卖：返回 {task_id: agv_id}。"""
    auction = auction or Auction()
    assignment: Dict[str, str] = {}
    for task in tasks:
        bids = {agv: bid_fn(agv, task) for agv in fleet}
        winner = auction.resolve(bids)
        if winner is not None:
            assignment[str(task)] = winner
    return assignment
