# 化工仓储 AGV 协同调度仿真平台

> 依据《化工仓储 AGV 协同调度仿真平台—项目落地实施方案 V1.42》构建的仿真空间，
> 对应 P1 仿真环境搭建（第 1—3 周）的核心交付物，并预留 P2—P5 算法模块的工程骨架。

## 一、目录结构（与实施方案 3.1 节约定一致）

```
agv_scheduler/
├─ package.xml         # ROS 包清单（roslaunch 识别必需）
├─ CMakeLists.txt      # catkin 安装规则
├─ setup_ros2go.sh     # ROS2GO 一键部署脚本
├─ config/             # YAML 配置：场景、算法超参、安全规则、任务参数
│  ├─ scene.yaml       #   场景几何（货架/禁行区/装卸点/工位/充电桩/避让点）
│  ├─ agv.yaml         #   AGV 运动学与传感器参数
│  ├─ algorithm.yaml   #   DQN/拍卖/GA/蚁群/MADQN/动态权重超参
│  ├─ safety.yaml      #   相容性矩阵、冲突检测、动作屏蔽规则
│  └─ task.yaml        #   任务到达强度（非齐次泊松过程）与优先级
├─ simulation/         # Gazebo 世界、AGV 模型、launch 启动脚本、栅格化
│  ├─ scene.py         #   场景模型 + 40×28 栅格化（静态/语义/动态层）
│  ├─ grid_builder.py  #   栅格化脚本 CLI → warehouse_grid.json
│  ├─ world/chemical_warehouse.world   # Gazebo SDF 世界文件
│  ├─ models/agv_light/               # 轻量化 AGV 模型（差速驱动 SDF）
│  └─ launch/          #   warehouse.launch + spawn_agvs.sh（多实例化）
├─ envs/               # Gym 环境封装（单车版 / 多车版）
├─ scheduling/         # DQN 任务分配、拍卖算法、遗传算法出价、仲裁器、任务生成
├─ planning/           # A*、蚁群路径规划
├─ safety/             # 相容性矩阵、时间窗冲突检测、动作屏蔽、规则引擎
├─ weights/            # 动态权重学习模块
├─ metrics/            # 指标采集与统计脚本
├─ viz/                # RViz 配置、Pillow 渲染器、指标看板
└─ experiments/        # 演示脚本与一键复跑脚本
```

## 二、仿真空间（P1 核心交付物）

**场景规格（步骤1）**

| 要素 | 规格 |
|------|------|
| 外墙 | 20 m × 14 m |
| 栅格 | 40 × 28，分辨率 0.5 m/格 |
| 储区货架 | 8 个：碱类/酸类/有机溶剂/催化剂/氧化剂/一般原料/毒性品/耗材 |
| 主通道 | 宽 3 m，设 3 处会车避让点 |
| 禁行区 | Z1（酸×碱）、Z2（氧化剂×有机物） |
| 装卸点 | P1、P2 |
| 工位 | WS1—WS6 |
| 充电桩 | CP1—CP3 |

**AGV 模型（步骤2）**：Tianracer 轻量化差速驱动，
轴距 L=0.32 m，轮半径 r=0.05 m，v_max=1.2 m/s，a_max=0.8 m/s²，
激光雷达 360°/0.1~12 m/10 Hz，里程计 20 Hz，支持 5→10 台多实例化。

**任务生成（步骤3）**：非齐次泊松过程 λ_i(t)=λ_i^base·(1+A·sin(2πt/T+φ_i))，
8 品类频率模板（NaOH/H₂SO₄ 高频、特种催化剂低频），
priority = 0.6·hazard_class + 0.4·urgency。

## 三、快速运行（无需 ROS/Gazebo，纯 Python 网格环境）

```bash
cd agv_scheduler
python experiments/demo.py          # 一键：栅格化 + 任务生成 + 导航 + 安全校验 + 渲染
python simulation/grid_builder.py   # 仅栅格化，输出 warehouse_grid.json
python safety/compatibility.py      # 打印相容性矩阵
```

演示会输出到 `viz/warehouse_scene_demo.png`（含路径与 AGV 标记的仿真空间图）。

依赖见 `requirements.txt`；核心仿真空间仅需 `Pillow` + `PyYAML`，其余为可选。

## 四、ROS2GO / Gazebo 部署（真实仿真）

> 纯 Python 网格仿真（`experiments/demo.py`）**不需要 ROS**，任何 Ubuntu + Python3 + Pillow 即可跑，
> 它是"先仿真后优化"原则中的轻量迭代环境。下面的 ROS2GO 步骤只针对 Gazebo 3D 仿真。

### 4.1 不能只拷贝文件夹 —— 需要三步环境配置

ROS 通过 `package.xml` 识别"包"，`roslaunch agv_scheduler ...` 才能找到 launch 文件。
本包已随附 `package.xml` 与 `CMakeLists.txt`，部署只需：

1. **放进 catkin 工作空间**（ROS 包必须位于工作空间的 src 下）
2. **编译注册**（`catkin_make`，纯 launch/world/model 包，秒级完成）
3. **source 工作空间 + 设 GAZEBO_MODEL_PATH**

### 4.2 一键部署（推荐，在 ROS2GO 终端内执行）

```bash
cd agv_scheduler
./setup_ros2go.sh                      # 若包已在 ~/catkin_ws/src/agv_scheduler
# 或指定刚拷贝过来的位置：
./setup_ros2go.sh /media/$USER/ROS2GO/agv_scheduler
```

脚本自动完成：创建 `~/catkin_ws` → 复制包 → `catkin_make` → 装 Pillow → 写 `~/.bashrc`。

### 4.3 手动部署（等价步骤）

```bash
# 1) 拷贝到 catkin 工作空间 src
mkdir -p ~/catkin_ws/src
cp -r agv_scheduler ~/catkin_ws/src/

# 2) 编译注册
cd ~/catkin_ws
catkin_make

# 3) source 工作空间
source devel/setup.bash

# 4) 设置 Gazebo 模型路径（让 Gazebo 找到 agv_light 模型）
export GAZEBO_MODEL_PATH=~/catkin_ws/src/agv_scheduler/simulation/models:$GAZEBO_MODEL_PATH
```

### 4.4 启动

```bash
# 一键：世界 + 多实例化 5 台 AGV + RViz
roslaunch agv_scheduler warehouse.launch n_agvs:=5

# 或单独多实例化（5→10 台）
rosrun agv_scheduler spawn_agvs.sh 5
```

### 4.5 依赖检查（ROS Noetic desktop-full 一般已自带）

| 依赖 | 用途 | 缺失时安装 |
|------|------|-----------|
| gazebo_ros / gazebo_plugins | 世界加载、差速驱动、雷达/IMU 插件 | `sudo apt install ros-noetic-gazebo-ros-pkgs ros-noetic-gazebo-plugins` |
| rviz | 可视化 | `sudo apt install ros-noetic-rviz` |
| Pillow（Python） | 纯 Python 网格仿真渲染 | `pip3 install Pillow` |

> 说明：纯 Python 网格仿真已内置无依赖 YAML 解析器，PyYAML 非必需；完整 DQN/MADQN 训练需 `pip3 install torch`。

## 五、算法模块落位（P2—P5）

| 模块 | 文件 | 状态 |
|------|------|------|
| L1 DQN 分配 | `scheduling/dqn_allocator.py` | 规则回退可运行；完整 DQN 需 PyTorch |
| L2 分布式拍卖 | `scheduling/auction.py` | 可运行 |
| L3 GA 出价 | `scheduling/ga_bid.py` | 可运行 |
| 仲裁器 | `scheduling/arbiter.py` | 可运行 |
| A* | `planning/astar.py` | 可运行 |
| 蚁群 | `planning/aco.py` | 可运行（简化） |
| 安全规则引擎 | `safety/engine.py` + 子模块 | 可运行 |
| 动态权重 | `weights/dynamic_weight.py` | 可运行 |
| 指标采集 | `metrics/collector.py` | 可运行 |

## 六、验收对照（M1 里程碑）

- 世界文件可在 Gazebo 中加载（`simulation/world/chemical_warehouse.world`）
- 栅格底图与可视化布局一致（`simulation/warehouse_grid.json` ↔ `viz/*.png`）
- 禁行区在渲染图中正确显示（红色 Z1/Z2）
- 单车 A* 导航成功率（演示从 P1 → 货架 → 工位）
