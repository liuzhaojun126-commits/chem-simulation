# -*- coding: utf-8 -*-
"""动态权重自学习模块（步骤10：多因子动态权重）。
cost(e) = w1·d(e) + w2·(1/f(e)) + w3·p_cong(e) + w4·r_safe(e)
w = softmax(θ)，θ ← θ + α·∇θ J，J = E[R] - β·H(π)（REINFORCE + 熵正则）。
对应《项目落地实施方案 V1.42》4.3 步骤 10。
"""
from __future__ import annotations

import math
from typing import Dict, Optional


class DynamicWeight:
    """四因子路径综合代价权重的在线自适应学习（简化、无依赖实现）。"""

    def __init__(self, alpha_outer: float = 5e-3, lr_inner: float = 1e-4,
                 f_ema_lambda: float = 0.05, momentum: float = 0.9,
                 entropy_beta: float = 0.01):
        # θ 为 4 维 logits，经 softmax 归一化为 w1..w4
        self.theta = [0.0, 0.0, 0.0, 0.0]
        self.alpha = alpha_outer
        self.lr = lr_inner
        self.f_lambda = f_ema_lambda
        self.momentum = momentum
        self.beta = entropy_beta
        self.velocity = [0.0, 0.0, 0.0, 0.0]

        # 路径段统计
        self.freq: Dict[tuple, float] = {}      # 使用频次 f（EMA）
        self.occupancy: Dict[tuple, float] = {} # 拥堵概率 p_cong

    # -- 权重 -------------------------------------------------
    def weights(self) -> list:
        m = max(self.theta)
        exps = [math.exp(t - m) for t in self.theta]
        s = sum(exps) or 1.0
        return [e / s for e in exps]

    # -- 四因子代价 -------------------------------------------------
    def cost(self, d: float, f: float, p_cong: float, r_safe: float) -> float:
        w1, w2, w3, w4 = self.weights()
        # f 防除零
        return w1 * d + w2 * (1.0 / max(f, 1e-3)) + w3 * p_cong + w4 * r_safe

    # -- 统计更新 -------------------------------------------------
    def update_freq(self, cell: tuple, used: bool = True):
        """指数滑动平均 f ← (1-λ)f + λ·1{该段被使用}。"""
        old = self.freq.get(cell, 0.0)
        self.freq[cell] = (1 - self.f_lambda) * old + self.f_lambda * (1.0 if used else 0.0)

    def update_occupancy(self, cell: tuple, p_cong: float):
        self.occupancy[cell] = p_cong

    def freq_of(self, cell: tuple) -> float:
        return self.freq.get(cell, 1e-3)

    def cong_of(self, cell: tuple) -> float:
        return self.occupancy.get(cell, 0.0)

    # -- 学习更新（REINFORCE + 熵正则 + 动量） -------------------
    def update(self, episode_reward: float, entropy: float = 0.0):
        """θ ← θ + α·∇θ J，∇θ J = (R - baseline)·∇log π + β·∇H。
        此处采用简化标量梯度：以奖励驱动 + 熵正则，动量抑制震荡。"""
        grad = episode_reward * (1.0 + self.beta * entropy)
        for i in range(4):
            self.velocity[i] = self.momentum * self.velocity[i] + self.alpha * grad * self._score_grad(i)
            self.theta[i] += self.velocity[i]

    def _score_grad(self, i: int) -> float:
        """softmax 梯度 wrt θ_i（用于标量奖励的单调驱动，简化）。"""
        w = self.weights()
        return w[i] * (1.0 - w[i])

    def converged(self, history: list, window: int = 50, tol: float = 0.01) -> bool:
        """相邻 window 轮权重变化 < 1% 视为收敛。"""
        if len(history) < window:
            return False
        recent = history[-window:]
        diffs = [abs(recent[k + 1][i] - recent[k][i]) for k in range(len(recent) - 1) for i in range(4)]
        return all(d < tol for d in diffs)

    def snapshot(self) -> dict:
        return {"theta": list(self.theta), "weights": self.weights()}


if __name__ == "__main__":
    dw = DynamicWeight()
    print("初始权重(softmax):", [round(w, 3) for w in dw.weights()])
    # 非均匀初始化 θ，观察 softmax 归一化与代价响应
    dw.theta = [1.0, 0.5, 0.3, 0.2]
    print("非均匀权重:", [round(w, 3) for w in dw.weights()])
    print("cost(d=5, f=1.0, p_cong=0.2, r_safe=0.1) =",
          round(dw.cost(5.0, 1.0, 0.2, 0.1), 3))
    # 在线更新（奖励驱动 + 熵正则）
    hist = []
    for _ in range(300):
        dw.update(episode_reward=0.5, entropy=0.1)
        hist.append(dw.weights())
    print("300 轮更新后权重:", [round(w, 3) for w in dw.weights()])
    print("收敛判定(50轮<1%):", dw.converged(hist))
