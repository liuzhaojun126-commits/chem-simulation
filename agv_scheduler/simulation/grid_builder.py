# -*- coding: utf-8 -*-
"""栅格化脚本 CLI：把场景配置离散为 40×28 栅格底图并导出 JSON。
对应《项目落地实施方案 V1.42》步骤1的“栅格化脚本”。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulation.scene import scene_from_config_file


def main():
    ap = argparse.ArgumentParser(description="化工仓库场景栅格化")
    ap.add_argument("--config", default=None, help="scene.yaml 路径（默认 config/scene.yaml）")
    ap.add_argument("--out", default=None, help="输出 JSON 路径")
    args = ap.parse_args()

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = args.config or os.path.join(here, "config", "scene.yaml")
    out = args.out or os.path.join(here, "simulation", "warehouse_grid.json")

    scene = scene_from_config_file(cfg)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(scene.grid_as_dict(), f, ensure_ascii=False, indent=1)

    n_pass = sum(1 for r in range(scene.rows) for c in range(scene.cols) if scene.is_passable(r, c))
    print(f"栅格底图: {scene.cols}×{scene.rows} (res {scene.resolution}m)")
    print(f"可通行栅格: {n_pass} / {scene.cols * scene.rows}")
    print(f"输出: {out}")


if __name__ == "__main__":
    main()
