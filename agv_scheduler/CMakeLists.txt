cmake_minimum_required(VERSION 3.0.2)
project(agv_scheduler)

# 纯 launch/world/model/config + Python 脚本包，无 C++ 编译
find_package(catkin REQUIRED)

catkin_package()

# ---- 安装规则（安装后由 roslaunch/rospack 查找）----

# 1) launch 文件 → share/agv_scheduler/launch（roslaunch agv_scheduler warehouse.launch 查找位置）
install(DIRECTORY simulation/launch
        DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION})

# 2) Gazebo 世界 → share/agv_scheduler/simulation/world（launch 中 $(find agv_scheduler)/simulation/world/... 引用）
install(DIRECTORY simulation/world
        DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/simulation)

# 3) AGV 模型 → share/agv_scheduler/simulation/models
install(DIRECTORY simulation/models
        DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/simulation)

# 4) 配置 → share/agv_scheduler/config
install(DIRECTORY config
        DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION})

# 5) RViz 配置 → share/agv_scheduler/viz
install(DIRECTORY viz
        DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION})

# 6) 栅格底图 → share/agv_scheduler/simulation/warehouse_grid.json（导航节点加载）
install(FILES simulation/warehouse_grid.json
        DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/simulation)

# 7) 可执行脚本（spawn_agvs.sh）→ lib/agv_scheduler
install(PROGRAMS simulation/launch/spawn_agvs.sh
        DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION})

# 8) Python 节点（agv_nav.py / dispatcher.py / agv_common.py）→ lib/agv_scheduler
catkin_install_python(PROGRAMS
  scripts/agv_nav.py
  scripts/dispatcher.py
  scripts/agv_common.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION})

