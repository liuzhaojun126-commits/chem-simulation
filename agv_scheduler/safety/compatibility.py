# -*- coding: utf-8 -*-
"""危化品相容性矩阵（步骤7：相容性判定）。
对应《项目落地实施方案 V1.42》4.2 步骤 7：M ∈ {0,1}ⁿˣⁿ，M[i][j]=0 表示品类 i 与 j 不可共用路径区域。
"""
from __future__ import annotations

from typing import Dict, Iterable, Optional

from simulation.scene import (
    CATEGORY_HAZARD,
    HAZARD_CLASSES,
    HAZARD_INCOMPATIBLE,
    INCOMPATIBLE_PAIRS,
)

CATEGORIES = list(CATEGORY_HAZARD.keys())


class CompatibilityMatrix:
    """品类级相容性矩阵 + 危化品等级级规则。

    判定优先级：
      1. 品类级硬约束（酸×碱、氧化剂×有机物）
      2. 危化品等级级硬约束（氧化性 × 易燃）
    """

    def __init__(self, incompatible_pairs: Optional[Iterable] = None,
                 hazard_incompatible: Optional[Iterable] = None):
        self.incompatible_pairs = set(map(tuple, incompatible_pairs or INCOMPATIBLE_PAIRS))
        self.hazard_incompatible = set(map(tuple, hazard_incompatible or HAZARD_INCOMPATIBLE))

    # -- 矩阵查询 -------------------------------------------------
    def is_compatible(self, cat_i: str, cat_j: str) -> bool:
        """品类 i 与 j 是否可共用路径区域（对称）。"""
        if (cat_i, cat_j) in self.incompatible_pairs or (cat_j, cat_i) in self.incompatible_pairs:
            return False
        hi, hj = CATEGORY_HAZARD[cat_i], CATEGORY_HAZARD[cat_j]
        if (hi, hj) in self.hazard_incompatible or (hj, hi) in self.hazard_incompatible:
            return False
        return True

    def matrix(self, categories: Optional[Iterable[str]] = None) -> Dict[str, Dict[str, int]]:
        """返回 M ∈ {0,1} 相容性矩阵（dict 形式）。"""
        cats = list(categories or CATEGORIES)
        return {i: {j: int(self.is_compatible(i, j)) for j in cats} for i in cats}

    def compatible_categories(self, cat: str) -> list:
        return [c for c in CATEGORIES if self.is_compatible(cat, c)]

    # -- 路径/区域判定 -------------------------------------------------
    def path_allowed_for(self, payload_category: str, zone_categories: Iterable[Optional[str]]) -> bool:
        """载荷品类 payload_category 是否可通行于给定区域（区域品类集合）。
        任一区域品类与载荷不相容 → 不可通行（硬剪枝）。
        """
        for zc in zone_categories:
            if zc is None:
                continue
            if not self.is_compatible(payload_category, zc):
                return False
        return True

    def hazard_of(self, category: str) -> str:
        return CATEGORY_HAZARD.get(category, "non_hazardous")

    def hazard_label(self, hazard: str) -> str:
        return HAZARD_CLASSES.get(hazard, hazard)


def hard_prune_cells(compat: CompatibilityMatrix, payload_category: str,
                     cells_zones) -> set:
    """对给定区域品类集合做硬剪枝：返回不可通行栅格集合。
    cells_zones: iterable of (rc, zone_category_or_None)
    """
    pruned = set()
    for rc, zcat in cells_zones:
        if zcat is not None and not compat.is_compatible(payload_category, zcat):
            pruned.add(rc)
    return pruned


if __name__ == "__main__":
    m = CompatibilityMatrix()
    print("相容性矩阵 M (1=相容, 0=不相容):")
    hdr = [" " * 12] + [c[:10] for c in CATEGORIES]
    print("".join(hdr))
    mat = m.matrix()
    for i in CATEGORIES:
        row = [f"{i:12s}"] + [f"{mat[i][j]:>10d}" for j in CATEGORIES]
        print("".join(row))
