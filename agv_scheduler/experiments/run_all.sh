#!/usr/bin/env bash
# ============================================================
# 一键复跑实验脚本（步骤16：复现包）
# 对应《项目落地实施方案 V1.42》4.5 步骤 16
# ============================================================
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"

echo "=== 1) 场景栅格化 ==="
"$PYTHON" "$HERE/simulation/grid_builder.py"

echo "=== 2) 任务生成 ==="
"$PYTHON" - <<'EOF'
import sys; sys.path.insert(0, "$HERE")
from scheduling.task_generator import TaskGenerator
g = TaskGenerator(seed=42)
tasks = g.generate()
g.to_csv(tasks, "$HERE/experiments/tasks_seed42.csv")
print("已生成", len(tasks), "个任务 -> experiments/tasks_seed42.csv")
EOF

echo "=== 3) 相容性矩阵 ==="
"$PYTHON" "$HERE/safety/compatibility.py"

echo "=== 4) 仿真空间演示（栅格 + 导航 + 渲染）==="
"$PYTHON" "$HERE/experiments/demo.py"

echo "=== 全部完成 ==="
