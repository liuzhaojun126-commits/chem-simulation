#!/usr/bin/env bash
# ============================================================
# ROS2GO 一键部署脚本（在 ROS2GO / Ubuntu 20.04 + ROS Noetic 内运行）
# 用法:
#   ./setup_ros2go.sh                      # 包已在 ~/catkin_ws/src/agv_scheduler
#   ./setup_ros2go.sh /path/to/agv_scheduler  # 指定刚拷贝过来的包路径
# ============================================================
set -e

WS="${CATKIN_WS:-$HOME/catkin_ws}"
SRC_PKG="${1:-$WS/src/agv_scheduler}"

echo "== [1/5] 检查 ROS Noetic =="
if [ "$ROS_DISTRO" != "noetic" ]; then
  echo "  sourcing /opt/ros/noetic/setup.bash ..."
  source /opt/ros/noetic/setup.bash
fi
command -v rospack >/dev/null 2>&1 || { echo "错误: 未找到 ROS，请先安装/加载 ROS Noetic"; exit 1; }
echo "  ROS_DISTRO=$ROS_DISTRO  OK"

echo "== [2/5] 放置包到 catkin 工作空间 =="
mkdir -p "$WS/src"
if [ ! -d "$WS/src/agv_scheduler" ]; then
  if [ -d "$SRC_PKG" ]; then
    cp -r "$SRC_PKG" "$WS/src/agv_scheduler"
    echo "  已复制 $SRC_PKG -> $WS/src/agv_scheduler"
  else
    echo "错误: 找不到包目录 $SRC_PKG"; exit 1
  fi
else
  echo "  $WS/src/agv_scheduler 已存在，跳过复制"
fi

echo "== [3/5] 编译并安装（launch 文件安装到 share/ 供 roslaunch 查找）=="
cd "$WS"
catkin_make install

echo "== [4/5] 安装 Python 渲染依赖（仅纯 Python 网格仿真需要）=="
python3 -m pip install --user Pillow 2>/dev/null \
  && echo "  Pillow OK" || echo "  Pillow 安装失败（可忽略，仅影响 PNG 渲染；核心仿真已内置无依赖 YAML 解析）"

echo "== [5/5] 写入环境变量 =="
source "$WS/install/setup.bash"
export GAZEBO_MODEL_PATH="$WS/src/agv_scheduler/simulation/models:${GAZEBO_MODEL_PATH}"

if ! grep -q "catkin_ws/install/setup.bash" "$HOME/.bashrc" 2>/dev/null; then
  echo "source $WS/install/setup.bash" >> "$HOME/.bashrc"
fi
if ! grep -q "agv_scheduler/simulation/models" "$HOME/.bashrc" 2>/dev/null; then
  echo "export GAZEBO_MODEL_PATH=$WS/src/agv_scheduler/simulation/models:\$GAZEBO_MODEL_PATH" >> "$HOME/.bashrc"
fi

echo ""
echo "=============================================="
echo " 部署完成！"
echo " 启动 Gazebo 仿真:"
echo "   roslaunch agv_scheduler warehouse.launch n_agvs:=5"
echo " 运行纯 Python 网格仿真（无需 Gazebo）:"
echo "   cd $WS/src/agv_scheduler && python3 experiments/demo.py"
echo "=============================================="
