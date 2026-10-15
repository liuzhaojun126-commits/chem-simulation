# -*- coding: utf-8 -*-
"""指标看板（步骤15：数字孪生可视化与指标看板）。
把一次实验的 KPI 汇总渲染为 PNG 看板（Pillow，无 matplotlib 依赖）。
"""
from __future__ import annotations

import os
from typing import Dict, Optional

from PIL import Image, ImageDraw, ImageFont

from metrics.collector import MetricsCollector

# 指标中文名
FIELD_LABELS = {
    "makespan": "总完工时间",
    "wait": "平均等待时间",
    "total_length": "路径总长度",
    "conflict": "冲突次数",
    "violation": "安全违规",
    "congestion_rate": "拥堵率",
    "energy": "能耗",
    "brake_count": "紧急制动",
}


def _font(size: int):
    for p in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
              r"C:\Windows\Fonts\arial.ttf"]:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def render_dashboard(collector: MetricsCollector, out_path: str = "dashboard.png",
                     title: str = "化工仓储 AGV 调度指标看板") -> str:
    """渲染 KPI 看板 PNG。"""
    w, h = 520, 420
    img = Image.new("RGB", (w, h), (245, 246, 250))
    d = ImageDraw.Draw(img)
    title_font = _font(22)
    kpi_font = _font(18)
    small_font = _font(14)

    d.rectangle([0, 0, w, 60], fill=(30, 60, 110))
    d.text((20, 16), title, fill=(255, 255, 255), font=title_font)

    summary = collector.summary()
    y = 80
    for key, label in FIELD_LABELS.items():
        val = summary.get(key, 0.0)
        d.text((30, y), label, fill=(60, 60, 60), font=kpi_font)
        d.text((280, y), f"{val:>10.3f}", fill=(20, 20, 20), font=kpi_font)
        d.line([(30, y + 30), (w - 30, y + 30)], fill=(210, 210, 215), width=1)
        y += 40

    img.save(out_path)
    return out_path


if __name__ == "__main__":
    mc = MetricsCollector()
    mc.set("makespan", 4520.0)
    mc.set("wait", 31.2)
    mc.set("total_length", 812.5)
    mc.set("conflict", 0.0)
    mc.set("violation", 0.0)
    mc.set("congestion_rate", 0.12)
    mc.set("energy", 96.4)
    mc.set("brake_count", 2.0)
    out = render_dashboard(mc)
    print("看板已生成:", out)
