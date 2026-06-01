# RCS 算法日志分析 skill

## 服务器
- 10.68.2.31

## 目录结构

### 分配库 (rtpsa - Allocation)
| 目录 | 文件数 | 说明 |
|------|--------|------|
| `/main/app/rtpsa-7,20,8,10,19,23/logs` | 344 | 多实例合并 |
| `/main/app/rtpsa-2/logs` | 274 | |
| `/main/app/rtpsa-32,33,31,29/logs` | 234 | |
| `/main/app/rtpsa-25,26,27/logs` | 25 | |
| `/main/app/rtpsa-12,15/logs` | 9 | |
| `/main/app/rtpsa-9/logs` | 9 | |
| `/main/app/rtpsa/logs` | 0 | 空目录 |

### 规划库 (rtpsp - Planning)
| 目录 | 文件数 | 说明 |
|------|--------|------|
| `/main/app/rtpsp-2/logs` | 683 | 最大 |
| `/main/app/rtpsp-31/logs` | 457 | |
| `/main/app/rtpsp-7/logs` | 332 | |
| `/main/app/rtpsp-19/logs` | 180 | |
| `/main/app/rtpsp-10/logs` | 179 | |
| `/main/app/rtpsp-8/logs` | 162 | |
| `/main/app/rtpsp-20/logs` | 158 | |
| `/main/app/rtpsp-23/logs` | 106 | |
| `/main/app/rtpsp-29/logs` | 80 | |
| `/main/app/rtpsp-33/logs` | 44 | |
| `/main/app/rtpsp-32/logs` | 43 | |
| `/main/app/rtpsp-25/logs` | 23 | |
| `/main/app/rtpsp-26/logs` | 19 | |
| `/main/app/rtpsp-27/logs` | 17 | |
| `/main/app/rtpsp-12/logs` | 9 | |
| `/main/app/rtpsp-15/logs` | 9 | |
| `/main/app/rtpsp-9/logs` | 9 | |
| `/main/app/rtpsp/logs` | 0 | 空目录 |

### 子日志目录
| 路径 | 说明 |
|------|------|
| `rtpsa-*/TAL_log/` | 分配库 TAL 日志 |
| `rtpsa-*/DPL_log/` | 分配库 DPL 日志 |
| `rtpsp-*/TAL_log/` | 规划库 TAL 日志 |
| `rtpsp-*/DPL_log/` | 规划库 DPL 日志 |

## 日志格式

### dispatchTAL.log（分配库）
```
|时间戳|级别|线程ID|源文件:行号|内容|
|2026-05-29 16:49:23:141.714|INFO|139877169469184|../src/pathplan.cpp:172|GetPathCost2D time = 11.66ms|
```

### 关键字段
| 字段 | 示例 | 说明 |
|------|------|------|
| 时间戳 | `2026-05-29 16:49:23:141.714` | 精确到微秒 |
| 源文件 | `../src/pathplan.cpp:172` | C++ 源码位置 |
| veh | `DJ77370AAK00003` | AGV 设备序列号 |
| startPosition | `5511121` | 起始路径点 |
| endPosition | `77881279` | 目标路径点 |
| pathDis | `146.05` | 路径距离 |
| A* 路径 | `5511121;5511120;5511119...` | 路径点序列 |

## 核心逻辑

### 1. A* 路径规划 (pathplan.cpp)
- **关键字**：`AstarPathplan`、`GetPathCost2D`
- **内容**：计算 AGV 从起点到终点的最优路径点序列
- **耗时**：正常 4-12ms，超过 50ms 需关注
- **示例**：
  ```
  veh:DK19434AAK00006 startPosition:5511121 endPosition:77881279
  #*******a* AstarPathplan *********: 5511121;5511120;5511119;...
  GetPathCost2D time = 4.877ms
  ```

### 2. AGV 分配决策 (taskallocate.cpp:10187)
- **关键字**：`nrVeh`、`oriVeh`、`pathDis`、`config change dis`
- **逻辑**：比较候选 AGV 路径距离，决定是否切换 AGV
- **字段**：
  - `nrVeh`：新候选 AGV
  - `oriVeh`：原始分配的 AGV
  - `pathDis`：路径距离
  - `no over config change dis 10`：未超过切换阈值（10）
- **示例**：
  ```
  nrVeh DJ77370AAK00003 pathDis 146.05 no over config change dis 10
  oriVeh DL21474AAK00002 oriPathDis: 61.8311
  ```
  新 AGV 距离 146 > 原 AGV 距离 61.83，不切换

## 可分析的问题

### 1. 任务分配异常
- **关键字**：`分配失败`、`allocation fail`、`no available`、`capacity`
- **场景**：AGV 无法分配到任务、区域容量满

### 2. 路径规划异常
- **关键字**：`规划失败`、`planning fail`、`no path`、`blocked`、`deadlock`
- **场景**：AGV 找不到可行路径、路径被阻塞、死锁

### 3. 交通管制/碰撞
- **关键字**：`collision`、`碰撞`、`traffic`、`lock`、`wait`
- **场景**：AGV 之间碰撞风险、交通管制等待超时

### 4. 性能问题
- **关键字**：`timeout`、`slow`、`cost`、`time =`
- **场景**：`GetPathCost2D time = XXXms` 超过 50ms 需关注

### 5. 地图/点位问题
- **关键字**：`point`、`node`、`position`、`invalid`
- **场景**：地图数据异常、点位不存在

### 6. 通信/接口问题
- **关键字**：`http`、`request`、`response`、`error`、`fail`

### 7. 实例负载不均
- **分析**：对比各实例文件数
- **当前**：rtpsp-2 (683) > rtpsp-31 (457) > rtpsp-7 (332)

## 查询方式
```bash
# 查分配库 dispatchTAL 日志
curl -X POST :5011/api/logs -d '{"folder":"/main/app/rtpsa-2/TAL_log/dispatchTAL.log","line_start":1,"line_end":100}'

# 查路径规划耗时
curl -X POST :5011/api/logs -d '{"folder":"/main/app/rtpsa-2/TAL_log/dispatchTAL.log","keyword":"GetPathCost2D","line_start":1,"line_end":500}'

# 查特定 AGV
curl -X POST :5011/api/logs -d '{"folder":"/main/app/rtpsa-2/TAL_log/dispatchTAL.log","keyword":"DJ77370","line_start":1,"line_end":500}'

# 查特定终点
curl -X POST :5011/api/logs -d '{"folder":"/main/app/rtpsa-2/TAL_log/dispatchTAL.log","keyword":"77881279","line_start":1,"line_end":500}'
```

## ds 说
- rtpsa 是分配库（Allocation），rtpsp 是规划库（Planning）
- 目录名中的数字是实例编号，多实例合并目录用逗号分隔
- 文件数最多的实例通常是负载最高的，rtpsp-2 有 683 个文件
- 算法日志通常包含详细的路径计算、AGV 分配、交通管制信息
- 排查 AGV 卡住/不动的问题时，优先查 rtpsp（规划库）的 `blocked`/`deadlock` 关键字
- TAL_log 和 DPL_log 是子目录，不在 `logs` 目录下，scan-dirs 扫不到
- dispatchTAL.log 中 `GetPathCost2D time` 正常 4-12ms，超过 50ms 需关注
- AGV 分配决策中 `config change dis` 是切换阈值，路径距离差超过阈值才会切换 AGV
- 10.68.2.31 上 postlook 的 config/env.toml 权限需确保 ymsk 可写才能热更新

## AGV 规划失败排查流程

### 第一步：确认 AGV 在哪个实例
```bash
# 在 rtpsp 各实例的 play.log 中搜索 AGV
curl -X POST :5011/api/logs -d '{"folder":"/main/app/rtpsp-31/logs","pattern":"play.log","keyword":"BL11637BAK00007","line_start":1,"line_end":500}'
```
- 找到后确认实例编号（如 rtpsp-31 → 对应分配库 rtpsa-32,33,31,29）

### 第二步：查看规划库 play.log
- **type 10**：AGV 状态上报（位置、电量、状态码）
- **type 13**：规划失败，`0` = 0条路径
- **type 14**：规划结果，路径点对列表

### 第三步：查看分配库 dispatchTAL.log
```bash
curl -X POST :5011/api/logs -d '{"folder":"/main/app/rtpsa-32,33,31,29/TAL_log/dispatchTAL.log","keyword":"BL11637BAK00007","line_start":1,"line_end":500}'
```
关键字段：
| 字段 | 含义 |
|------|------|
| `Not FitToEstRestCost` | 预估剩余代价不满足，AGV 不适合该任务 |
| `noCanVeh` | 没有候选 AGV |
| `nobackupVeh` | 没有备用 AGV |
| `PlanEnd in forbArea` | 终点在禁行区 |
| `Can't arrive Exit` | 无法到达出口点 |
| `AstarPathPlan2D Fail` | A* 路径规划失败 |
| `OverMap success` | 跨区域路径规划成功 |
| `Sta:1 subSta:0` | AGV 空闲 |
| `Pld:1` | 有货架 |
| `Pow:54` | 电量 54% |
| `wrk:29;31;32` | 工作区域 |

### 第四步：排查终点是否可用
```bash
# 查看某个终点是否被禁行
curl -X POST :5011/api/logs -d '{"folder":"...","keyword":"19960072","line_start":1,"line_end":500}'
```
- `PlanEnd in forbArea: XXX` → 终点在禁行区，检查 `TalForbiddenAreaInfo.txt`
- `Can't arrive Exit XXX from start` → 起点到终点无通路

### 第五步：对比其他 AGV
```bash
# 查看同区域其他 AGV 是否能规划成功
curl -X POST :5011/api/logs -d '{"folder":"...","keyword":"OverMap success","line_start":1,"line_end":100}'
```

### 常见失败原因速查
| 日志关键字 | 原因 | 排查方向 |
|-----------|------|---------|
| `Not FitToEstRestCost` | 代价不满足 | AGV 距离太远/电量不足/被预留 |
| `PlanEnd in forbArea` | 终点禁行 | 检查禁行区配置 |
| `Can't arrive Exit` | 无通路 | 检查地图连通性 |
| `noCanVeh` | 无可用 AGV | 检查其他 AGV 状态 |
| `AstarPathPlan2D Fail` | A* 失败 | 检查路径点是否可达 |
| type 13 `0` | 规划返回 0 条 | 综合以上原因 |
| `UnAccessEdge` | 不可达边 | 交通管制/单向边/AGV占用 |

### ⚠️ 禁行区排查注意事项
- **起点/终点在禁行区内**：算法在 A* 之前就过滤掉了，dispatchTAL.log 中**不会有** `PlanEnd in forbArea` 错误
- **途经点在禁行区内**：A* 能找到路径但包含 `UnAccessEdge`，路径不可用
- **确认方法**：直接查看 `TalForbiddenAreaInfo.txt` 文件，搜索点位编号
- **示例**：`11000050` 在禁行区内 → A* 路径中不包含该点 → 日志无直接错误 → 需查配置文件
