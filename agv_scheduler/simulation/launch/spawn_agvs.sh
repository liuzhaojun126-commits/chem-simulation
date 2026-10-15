#!/usr/bin/env bash
# ============================================================
# AGV 多实例化启动脚本（步骤2：运行时批量生成）
# 使用 gazebo_ros spawn_model 按 ID 循环生成，命名空间 /agv{i}/
# 用法: ./spawn_agvs.sh [N]   (默认 N=5，最大 10)
# ============================================================
set -e

N=${1:-5}
if [ "$N" -gt 10 ]; then echo "最多 10 台"; N=10; fi

# 定位包目录：优先 rospack（安装后可用），否则回退到源码树相对路径
PKG_DIR="$(rospack find agv_scheduler 2>/dev/null || echo "$(cd "$(dirname "$0")/../.." && pwd)")"
MODEL_DIR="${PKG_DIR}/simulation/models/agv_light"
export GAZEBO_MODEL_PATH="${MODEL_DIR}:${GAZEBO_MODEL_PATH}"

# 初始位姿（对应 config/scene.yaml agv_spawn_poses，最多 10）
X=(19.0 19.0 0.75 1.25 18.75 10.0 11.0 12.0 13.0 14.0)
Y=(1.0  13.0 1.0  6.75 6.75  6.75 6.75 6.75 6.75 6.75)
YAW=(1.5708 -1.5708 1.5708 0.0 3.1416 0.0 0.0 0.0 0.0 0.0)

for i in $(seq 1 "$N"); do
  idx=$((i-1))
  echo "生成 agv$i @ (${X[$idx]}, ${Y[$idx]})"
  rosrun gazebo_ros spawn_model \
    -sdf \
    -file "${MODEL_DIR}/model.sdf" \
    -model "agv$i" \
    -robot_namespace "/agv$i" \
    -x "${X[$idx]}" -y "${Y[$idx]}" -z 0.15 -Y "${YAW[$idx]}"
done

echo "已生成 $N 台 AGV"
