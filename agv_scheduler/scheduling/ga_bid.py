# -*- coding: utf-8 -*-
"""改进遗传算法出价内核（步骤5 L3：只算出价，不做决策）。
整数排列编码任务序列；适应度 f(σ)=Σ cost_ij + w_mk·makespan + w_e·空载率；
锦标赛选择(k=3)、OX 顺序交叉、交换/逆序变异(pm=0.1)、精英保留 2。
对应《项目落地实施方案 V1.42》4.2 步骤 5。
"""
from __future__ import annotations

import random
from typing import List, Optional


class GABidder:
    """用遗传算法求解最优任务序列代价，输出"插入新任务后的边际出价"。"""

    def __init__(self, population: int = 30, generations: int = 40,
                 tournament_k: int = 3, pm: float = 0.1, elite: int = 2,
                 w_makespan: float = 1.0, w_empty: float = 0.3, seed: Optional[int] = None):
        self.population = population
        self.generations = generations
        self.k = tournament_k
        self.pm = pm
        self.elite = elite
        self.w_makespan = w_makespan
        self.w_empty = w_empty
        self.rng = random.Random(seed)

    # 任务 i→j 的转移代价矩阵
    def _fitness(self, seq: List[int], cost: List[List[float]]) -> float:
        total = 0.0
        for a, b in zip(seq, seq[1:]):
            total += cost[a][b]
        makespan = sum(cost[a][b] for a, b in zip(seq, seq[1:]))
        empty = cost[0][seq[0]] if seq else 0.0
        return total + self.w_makespan * makespan + self.w_empty * empty

    def optimize(self, task_ids: List[int], cost: List[List[float]]) -> (List[int], float):
        """返回 (最优序列, 最优代价)。cost[i][j] 为任务 i→j 代价（含起点 0）。"""
        n = len(task_ids)
        if n == 0:
            return [], 0.0
        if n == 1:
            return list(task_ids), self._fitness(task_ids, cost)

        pop = [self.rng.sample(task_ids, n) for _ in range(self.population)]

        def fit(seq):
            return self._fitness(seq, cost)

        for _ in range(self.generations):
            scored = sorted(pop, key=fit)
            new_pop = scored[:self.elite]
            while len(new_pop) < self.population:
                p1 = self._tournament(pop, fit)
                p2 = self._tournament(pop, fit)
                c1, c2 = self._ox(p1, p2)
                self._mutate(c1)
                self._mutate(c2)
                new_pop.append(c1)
                if len(new_pop) < self.population:
                    new_pop.append(c2)
            pop = new_pop
        best = min(pop, key=fit)
        return best, fit(best)

    def _tournament(self, pop, fit):
        chosen = self.rng.sample(pop, self.k)
        return min(chosen, key=fit)

    def _ox(self, p1: List[int], p2: List[int]) -> (List[int], List[int]):
        n = len(p1)
        i, j = sorted(self.rng.sample(range(n), 2))
        c1 = [None] * n
        c1[i:j + 1] = p1[i:j + 1]
        self._fill_ox(c1, p2)
        c2 = [None] * n
        c2[i:j + 1] = p2[i:j + 1]
        self._fill_ox(c2, p1)
        return c1, c2

    def _fill_ox(self, child: List, other: List):
        n = len(other)
        used = set(x for x in child if x is not None)
        pos = 0
        for x in other:
            if x not in used:
                while child[pos] is not None:
                    pos += 1
                child[pos] = x

    def _mutate(self, seq: List[int]):
        if self.rng.random() < self.pm:
            op = self.rng.choice(["swap", "reverse"])
            if op == "swap" and len(seq) > 1:
                i, j = self.rng.sample(range(len(seq)), 2)
                seq[i], seq[j] = seq[j], seq[i]
            elif op == "reverse" and len(seq) > 1:
                i, j = sorted(self.rng.sample(range(len(seq)), 2))
                seq[i:j + 1] = reversed(seq[i:j + 1])

    def bid(self, current_seq: List[int], new_task: int, cost: List[List[float]]) -> float:
        """出价 = 插入新任务后的总代价增量（最优插入位置）。"""
        base, _ = self.optimize(current_seq, cost)
        best = float("inf")
        for pos in range(len(current_seq) + 1):
            cand = current_seq[:pos] + [new_task] + current_seq[pos:]
            _, val = self.optimize(cand, cost)
            best = min(best, val)
        return best - base


if __name__ == "__main__":
    ga = GABidder(seed=1)
    cost = [[0, 2, 9, 10], [1, 0, 6, 4], [15, 7, 0, 8], [6, 3, 12, 0]]
    seq, val = ga.optimize([1, 2, 3], cost)
    print("最优序列:", seq, "代价:", round(val, 2))
