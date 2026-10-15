# -*- coding: utf-8 -*-
"""实验图表生成（Pillow 柱状图，无 matplotlib 依赖）。
把实验汇总结果渲染为 PNG 对比图。
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont


def _font(size: int):
    for p in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
              r"C:\Windows\Fonts\arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def bar_chart(categories: List[str], values: List[float], title: str,
              out_path: str, value_fmt: str = "{:.2f}",
              width: int = 720, height: int = 420) -> str:
    """水平柱状图。"""
    colors = [(86, 156, 214), (242, 156, 90), (84, 190, 130), (214, 129, 137),
              (154, 111, 205), (170, 170, 170)]
    n = len(categories)
    img = Image.new("RGB", (width, height), (250, 250, 252))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, width, 56], fill=(30, 60, 110))
    d.text((20, 14), title, fill=(255, 255, 255), font=_font(20))

    max_v = max(values) if values else 1.0
    if max_v <= 0:
        max_v = 1.0
    top = 80
    row_h = int((height - top - 40) / n)
    bar_area_w = width - 280
    font = _font(14)
    small = _font(12)
    for i, (cat, v) in enumerate(zip(categories, values)):
        y = top + i * row_h
        d.text((16, y + row_h // 2 - 8), cat, fill=(40, 40, 40), font=font)
        bw = int(bar_area_w * (v / max_v))
        d.rectangle([180, y + 6, 180 + bw, y + row_h - 6], fill=colors[i % len(colors)])
        d.text((188 + bw, y + row_h // 2 - 8), value_fmt.format(v), fill=(20, 20, 20), font=small)

    img.save(out_path)
    return out_path


def render_summary_charts(summary: Dict[str, dict], out_dir: str,
                          title_prefix: str = "") -> List[str]:
    """把 {config: {metric: {mean, std}}} 汇总渲染为多张指标对比图。"""
    os.makedirs(out_dir, exist_ok=True)
    configs = list(summary.keys())
    metrics = list(summary[configs[0]].keys())
    labels = {
        "makespan": "总完工时间 (s)",
        "wait": "平均等待 (s)",
        "total_length": "路径总长度 (m)",
        "conflict": "冲突次数",
        "violation": "安全违规次数",
        "congestion_rate": "拥堵率",
        "energy": "能耗 (代理)",
        "brake_count": "紧急制动/转弯次数",
    }
    outs = []
    for m in metrics:
        vals = [summary[c][m]["mean"] for c in configs]
        title = f"{title_prefix} {labels.get(m, m)}"
        path = os.path.join(out_dir, f"chart_{m}.png")
        bar_chart(configs, vals, title, path)
        outs.append(path)
    return outs


if __name__ == "__main__":
    demo = {
        "B1": {"makespan": {"mean": 155.9}, "total_length": {"mean": 761.8},
               "conflict": {"mean": 247.8}, "violation": {"mean": 28.2}},
        "B2": {"makespan": {"mean": 182.3}, "total_length": {"mean": 703.6},
               "conflict": {"mean": 244.6}, "violation": {"mean": 24.4}},
        "B3": {"makespan": {"mean": 337.0}, "total_length": {"mean": 657.6},
               "conflict": {"mean": 188.2}, "violation": {"mean": 14.2}},
        "Ours": {"makespan": {"mean": 158.5}, "total_length": {"mean": 533.3},
                 "conflict": {"mean": 218.0}, "violation": {"mean": 0.0}},
    }
    outs = render_summary_charts(demo, "viz/charts", "基线对比")
    print("生成图表:", outs)
