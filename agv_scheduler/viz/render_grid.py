# -*- coding: utf-8 -*-
"""仿真空间渲染器（Pillow）—— 把 40×28 栅格底图渲染为 PNG，
可叠加规划路径与 AGV 位姿。对应《项目落地实施方案 V1.42》步骤1/11/15 的可视化需求。
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from simulation.scene import Scene

# 区域 → 颜色（RGB）
ZONE_COLORS: Dict[str, Tuple[int, int, int]] = {
    "wall": (60, 60, 65),
    "rack_alkali": (214, 129, 137),
    "rack_acid": (242, 156, 90),
    "rack_organic": (247, 211, 110),
    "rack_catalyst": (170, 170, 170),
    "rack_oxidizer": (243, 118, 118),
    "rack_general": (198, 206, 218),
    "rack_toxic": (154, 111, 205),
    "rack_consumable": (184, 220, 190),
    "no_go": (200, 40, 40),
    "loading": (255, 176, 59),
    "ws": (86, 156, 214),
    "cp": (84, 190, 130),
    "passing": (235, 235, 150),
    "main_aisle": (245, 245, 245),
    "cross_aisle": (232, 232, 232),
}

# 品类短标签（用于图上标注，避免字体问题）
CAT_LABEL = {
    "alkali": "ALK", "acid": "ACID", "organic_solvent": "ORG",
    "catalyst": "CAT", "oxidizer": "OXI", "general": "GEN",
    "toxic": "TOX", "consumable": "CON",
}


def _load_font(size: int):
    for path in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
                 r"C:\Windows\Fonts\arial.ttf"]:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def render_scene(scene: Scene,
                 path: Optional[List[Tuple[int, int]]] = None,
                 agvs: Optional[Dict[str, Tuple[int, int]]] = None,
                 out_path: str = "warehouse.png",
                 cell_px: int = 26,
                 draw_labels: bool = True) -> str:
    """渲染场景。返回输出文件路径。"""
    cols, rows = scene.cols, scene.rows
    img = Image.new("RGB", (cols * cell_px, rows * cell_px), (255, 255, 255))
    d = ImageDraw.Draw(img)

    # 1) 逐格填充
    for r in range(rows):
        for c in range(cols):
            cell = scene.grid[r][c]
            color = ZONE_COLORS.get(cell.zone, (255, 255, 255))
            x0, y0 = c * cell_px, r * cell_px
            d.rectangle([x0, y0, x0 + cell_px - 1, y0 + cell_px - 1], fill=color)

    # 2) 网格线
    line_color = (200, 200, 200)
    for c in range(cols + 1):
        x = c * cell_px
        d.line([(x, 0), (x, rows * cell_px)], fill=line_color, width=1)
    for r in range(rows + 1):
        y = r * cell_px
        d.line([(0, y), (cols * cell_px, y)], fill=line_color, width=1)

    # 3) 区域标签
    if draw_labels:
        font = _load_font(max(8, cell_px // 3))
        small = _load_font(max(7, cell_px // 4))
        for z in scene.zones:
            if z.kind in ("wall", "cross_aisle", "main_aisle"):
                continue
            cx = (z.x0 + z.x1) / 2 * (1 / scene.resolution) * cell_px
            cy = (z.y0 + z.y1) / 2 * (1 / scene.resolution) * cell_px
            if z.kind == "rack":
                label = CAT_LABEL.get(z.category, z.id)
            elif z.kind == "no_go":
                label = z.id  # Z1/Z2
            else:
                label = z.id  # P1/P2/WS1..CP1..
            bbox = d.textbbox((0, 0), label, font=small)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            d.text((cx - w / 2, cy - h / 2), label, fill=(20, 20, 20), font=small)

    # 4) 路径叠加
    if path:
        pts = [((c + 0.5) * cell_px, (r + 0.5) * cell_px) for (r, c) in path]
        d.line(pts, fill=(30, 90, 220), width=max(2, cell_px // 8))
        for (r, c) in path[:: max(1, len(path) // 20)]:
            d.ellipse([c * cell_px + 2, r * cell_px + 2,
                       c * cell_px + cell_px - 3, r * cell_px + cell_px - 3],
                      fill=(30, 90, 220))

    # 5) AGV 标记
    if agvs:
        agv_font = _load_font(max(8, cell_px // 3))
        for agv_id, (r, c) in agvs.items():
            cx = (c + 0.5) * cell_px
            cy = (r + 0.5) * cell_px
            rad = cell_px // 3
            d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=(0, 140, 200), outline=(0, 0, 0))
            d.text((cx - rad, cy - rad), agv_id.replace("agv", ""), fill=(255, 255, 255), font=agv_font)

    img.save(out_path)
    return out_path


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from simulation.scene import scene_from_config_file

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scene = scene_from_config_file(os.path.join(here, "config", "scene.yaml"))
    out = os.path.join(here, "viz", "warehouse_scene.png")
    render_scene(scene, out_path=out)
    print("已渲染:", out)
