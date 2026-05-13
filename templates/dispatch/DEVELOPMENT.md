# 调车模块开发历程

> **104 次提交** · 从零构建的 AGV 跨环境空车调度系统 · 生产环境稳定运行中

---

## 一、项目概述

调车模块是跨环境任务模板管理系统的核心子模块，负责监控多个物理区域（A2-1、A2-3、A4-3 等）的 AGV 设备平衡状态，自动/手动下发空车调度任务。系统基于本地 JSON 文件实现数据持久化，零外部数据库依赖，通过 ICS 标准接口与 RCS 调度系统交互。

```mermaid
graph LR
    subgraph 外部系统
        RCS[RCS 调度系统]
        AGV[AGV 设备群]
    end
    subgraph 调车模块
        API[状态上报 API]
        BAL[平衡计算引擎]
        DISP[任务下发引擎]
        HEAL[自愈检查引擎]
        LOG[日志系统]
    end
    subgraph 存储
        TPL[模板 JSON]
        CC[currentCount.json]
        DH[device_history.json]
    end
    AGV -->|status=6/8/10| RCS
    RCS -->|上报| API
    API --> TPL
    API --> CC
    API --> DH
    BAL -->|读取| TPL
    BAL -->|读取| CC
    BAL -->|触发| DISP
    DISP -->|HTTP 下发| RCS
    HEAL -->|定时检查| CC
    HEAL -->|查询状态| RCS
    LOG -->|记录| API
    LOG -->|记录| DISP
    LOG -->|记录| HEAL
```

---

## 二、Git 开发时间线

```mermaid
gitGraph
    commit id: "初始提交"
    branch v1.x
    checkout v1.x
    commit id: "状态上报+模板匹配"
    commit id: "平衡计算+下发"
    commit id: "分时段配置"
    commit id: "自恢复检查"
    commit id: "操作日志"
    checkout main
    merge v1.x
    branch v2.0
    checkout v2.0
    commit id: "设备网格视图"
    commit id: "折线图统计"
    commit id: "低电量回空车"
    commit id: "设备历史记录"
    commit id: "全量查询同步"
    commit id: "自动驾驶测试"
    checkout main
    merge v2.0
    branch v2.1
    checkout v2.1
    commit id: "自愈误清理修复"
    commit id: "跨区域清理"
    commit id: "任务超时清理"
    commit id: "日志归档"
    commit id: "同API去重"
    commit id: "任务追踪流"
    commit id: "order_id加区域ID"
    checkout main
    merge v2.1
```

### 版本里程碑

| 版本 | 提交数 | 核心主题 | 代码规模 |
|------|:-----:|---------|:-------:|
| **v1.x** 基础架构 | ~30 | 状态上报、平衡计算、下发、自愈 | ~2000 行 |
| **v2.0** 功能增强 | ~40 | 可视化看板、统计图表、设备追踪 | ~4000 行 |
| **v2.1** 稳定性修复 | ~30 | 误清理修复、去重、日志归档、追踪 | ~4500 行 |

---

## 三、核心技术难题与解决方案

### 难题 1：自愈误清理——连廊环境中的设备被错误移除

```mermaid
flowchart TD
    A[设备进入连廊] --> B[RCS 上报 Offline/Downlined]
    B --> C{自愈检查}
    C -->|修复前| D[❌ 直接清理]
    C -->|修复后| E{模板JSON中<br/>有 status in 6,10?}
    E -->|有且未超1h| F[✅ 保留<br/>可能在连廊中]
    E -->|有但超1h| G[🧹 清理<br/>超时任务]
    E -->|无| H[🧹 清理<br/>无活跃任务]
    D --> I[设备到达后<br/>区域设备数不准]
```

**场景**：AGV 在跨环境连廊中行驶时，RCS 上报状态为 `Offline`/`Downlined`。早期自愈逻辑直接清理，导致设备到达目标区域后 `currentCount` 不准确。

**根因**：`_should_clean_device` 未检查设备是否有执行中任务。

**修复**：遍历该区域所有模板 JSON，查找该设备是否有 `status in (6, 10)` 的任务。有则保留（未超1小时），无则清理。

> 📦 相关提交：`19bcb78` `53d89f9` `5d31183`

---

### 难题 2：全量查询设备暴增——白名单机制过于宽松

```mermaid
flowchart LR
    subgraph 修复前
        API1[API 10.68.2.31] -->|返回全部设备| H1[device_history<br/>48h白名单]
        H1 -->|全部加入| CC1[currentCount<br/>14台 ❌]
    end
    subgraph 修复后
        API2[API 10.68.2.31] -->|同组共享查询| G[按 api_path+areaId 分组]
        G -->|比较 update_time| H2[只在最近上线区域保留]
        H2 --> CC2[currentCount<br/>3台 ✅]
    end
```

**场景**：A2-3 存储一部的全量查询 API 返回了该服务器下所有设备（包括其他区域的），`device_history.json` 白名单记录了48小时内所有"来过"的设备。全量查询时全部被加入 `currentCount`，从实际的3台暴增到14台。

**根因**：`_update_current_count_from_api` 只检查设备是否在 history 白名单中，不检查最近活动时间。

**修复**：
1. **同 API 区域共享查询**：按 `(api_path, areaId)` 分组，同组只查一次 API
2. **按最近上线区域分配**：比较同组各区域的 `update_time`，只在最新的区域保留设备
3. **离线设备不更新 `update_time`**：48h 后自动清理

> 📦 相关提交：`43260f6` `b9634e7` `7dd2681`

---

### 难题 3：空车回跨区域调车——共享模板导致车走到错误区域

```mermaid
flowchart TD
    A[自动下发空车回] --> B{修复前}
    B -->|不指定设备| C[RCS 随机分配]
    C --> D[❌ 可能分配其他区域的车]
    A --> E{修复后}
    E -->|指定区域内设备| F[三层排序选设备]
    F --> G[✅ 本区域车接任务]
    
    subgraph 三层排序
        H[1. 最近没被下发过的优先]
        I[2. 电量低的优先]
        J[3. 空闲的优先]
    end
```

**场景**：两个区域（如 A4-3 行业一部和行业二部）使用共享的空车回模板，自动下发时不指定设备，RCS 可能分配另一个区域的车来执行，导致车走到错误区域。

**修复**：
1. 空车回自动下发时指定区域内设备（`_select_device_for_empty_return`）
2. 三层排序策略：最近没被下发过的优先 → 电量低的优先 → 空闲的优先
3. 下发前检查设备状态，非空闲则跳过
4. **手动下发不指定设备**（异常恢复场景，让 RCS 自行分配更灵活）

> 📦 相关提交：`2d55c7d` `2cd3960` `54f6728`

---

### 难题 4：同一 order_id 重复写入——模板 JSON 残留

```mermaid
flowchart LR
    subgraph 修复前
        A1[dispatch_count=10] --> B1[生成1个 order_id]
        B1 --> C1[模板JSON写入10条<br/>全部相同ID]
        C1 --> D1[RCS只创建1个任务]
        D1 --> E1[完成后清理1条]
        E1 --> F1[❌ 残留9条]
    end
    subgraph 修复后
        A2[dispatch_count=10] --> B2[逐台生成10个 order_id]
        B2 --> C2[10次独立HTTP请求]
        C2 --> D2[模板JSON写入10条<br/>每条唯一ID]
        D2 --> E2[✅ 每条独立追踪]
    end
```

**场景**：`_execute_dispatch` 中 `for i in range(dispatch_count)` 循环写入模板 JSON，所有记录共用同一个 `order_id`。当 `dispatch_count=10` 时，10条记录都是同一个 ID，但 RCS 只创建了1个任务。任务完成后只清理1条，剩余9条永远残留。

**修复**：改为逐台下发——每台独立生成 `order_id`（毫秒时间戳+随机数），独立发送 HTTP 请求，独立写入模板 JSON。

```
修复前: CEM_auto_2026-05-10_11:27:55.235__4502 (10条相同)
修复后: CEM_auto_id4_2026-05-10_11:27:55.235__4502
        CEM_auto_id4_2026-05-10_11:27:55.236__7821
        CEM_auto_id4_2026-05-10_11:27:55.237__3194  ← 每条唯一
```

> 📦 相关提交：`1994ba2` `c9e0a72`

---

### 难题 5：状态上报模板匹配失败——code 名称不一致

```mermaid
flowchart TD
    A[RCS 上报 modelProcessCode] --> B{精确匹配 code}
    B -->|匹配| C[✅ 正常处理]
    B -->|不匹配| D{文件名匹配<br/>去.json后缀}
    D -->|匹配| C
    D -->|不匹配| E{按 order_id<br/>跨区域查找}
    E -->|找到| F[更新/清理对应记录]
    E -->|找不到| G[📌 report_unmatched<br/>静默接受 返回1000]
```

**场景**：RCS 上报的 `modelProcessCode` 是 `JuShengQ27to32-1`，但配置中的模板 code 是 `JuShengQ-1`。精确匹配失败后走 `report_unmatched` 静默接受，导致设备状态未正确更新。

**修复**：三级匹配策略——精确匹配 code → 回退文件名匹配（去 `.json`）→ 按 order_id 跨区域兜底。始终返回 1000 避免 RCS 重试风暴。

> 📦 相关提交：`827f28d` `f28d17b` `cba362e`

---

### 难题 6：日志系统演进——从内存到持久化

```mermaid
flowchart TD
    subgraph 日志存储架构
        HOT[global_log.json<br/>热数据 200条]
        ARCHIVE[global_log_YYYY-MM-DD.json<br/>归档日志 500条/天 保留2天]
        SUPERVISOR[logs/cross_env_manager.log<br/>Supervisor控制台 5MB]
    end
    subgraph 前端加载
        INC[增量拉取 ?since=timestamp]
        SEARCH[搜索时加载归档日志]
        EXPORT[导出全部日志]
    end
    HOT --> INC
    ARCHIVE --> SEARCH
    ARCHIVE --> EXPORT
    HOT --> EXPORT
```

**场景**：早期日志只存在内存中，重启丢失，无法排查历史问题。

**修复**：
1. 热数据 + 归档日志双层存储
2. 前端增量拉取（`?since=timestamp`），缓存400条
3. 搜索时自动加载归档日志，搜索模式下停用自动刷新
4. Supervisor 控制台日志查看 API（`/api/dispatch/logs`）

> 📦 相关提交：`cca03de` `15b979e` `f861f92` `5d31183`

---

### 难题 7：设备网格增量更新——避免全量 DOM 替换

```mermaid
flowchart LR
    A[5秒轮询刷新] --> B{比对设备列表}
    B -->|新设备| C[entering 动画滑入]
    B -->|离开设备| D[leaving 动画淡出]
    B -->|已有设备| E[保持不变]
    C --> F[✅ 展开面板不关闭]
    D --> F
    E --> F
```

**场景**：看板每5秒刷新时全量替换 HTML，导致展开的 JSON 面板被关闭、动画丢失。

**修复**：比对设备列表差异——新设备带 `entering` 动画滑入，离开的设备带 `leaving` 动画淡出。展开的 JSON 面板和历史设备网格不受影响。

> 📦 相关提交：`b7d3431` `adf1c09`

---

### 难题 8：跨环境子任务 order_id 规范化

```mermaid
flowchart TD
    A[跨环境任务 status=10] --> B{修复前}
    B -->|status==6 才匹配| C[❌ 清理逻辑跳过]
    A --> D{修复后}
    D -->|status in 6,10| E[✅ 正常清理]
    E --> F[共享模板 currentCount 同步更新]
```

**场景**：跨环境任务（status=10）的 `order_id` 格式与普通任务不同，清理逻辑中 `status == 6` 无法匹配 status=10 的任务。

**修复**：
1. 清理和更新逻辑中 `status == 6` 改为 `status in (6, 10)`
2. status=10 上报时覆盖更新模板 JSON 中的 status 字段
3. 共享模板的 currentCount 同步更新

> 📦 相关提交：`53d89f9` `6a2c8b1` `055a34b`

---

## 四、架构演进

```mermaid
graph TD
    subgraph v1.0 单文件时代
        V1[dispatch_routes.py<br/>~2000行]
        V1 --> V1A[状态上报+模板匹配]
        V1 --> V1B[平衡计算+下发]
        V1 --> V1C[基础看板]
    end
    
    subgraph v2.0 模块化拆分
        V2A[routes/dispatch_routes.py<br/>~4000行]
        V2B[templates/dispatch/<br/>dashboard+config]
        V2C[modules/query/<br/>任务查询扩展]
        V2D[data/dispatch/<br/>JSON持久化]
    end
    
    subgraph v2.1 稳定性+可观测性
        V3A[routes/dispatch_routes.py<br/>~4500行]
        V3B[日志归档+增量拉取]
        V3C[设备历史追踪]
        V3D[全量查询去重]
        V3E[任务追踪流]
    end
    
    V1 --> V2A
    V2A --> V3A
```

### 数据流全景

```mermaid
flowchart LR
    subgraph 外部
        AGV[AGV设备]
    end
    subgraph 调车模块核心
        REPORT[report_status API]
        TPL[模板JSON文件]
        CC[currentCount.json]
        DH[device_history.json]
        EXEC[execute API]
        HEAL[自愈检查]
        LOG[操作日志]
    end
    subgraph 看板
        DASH[实时看板]
    end
    
    AGV -->|status=6/8/10| REPORT
    REPORT -->|写入/删除| TPL
    REPORT -->|写入/删除| CC
    REPORT -->|更新| DH
    TPL -->|统计a/b| EXEC
    CC -->|读取cur| EXEC
    EXEC -->|下发| TPL
    EXEC -->|记录| LOG
    HEAL -->|定时检查| CC
    HEAL -->|查询状态| AGV
    HEAL -->|记录| LOG
    TPL --> DASH
    CC --> DASH
    LOG --> DASH
    DASH -->|手动触发| EXEC
```

---

## 五、关键文件索引

| 文件 | 行数 | 职责 |
|------|:---:|------|
| `routes/dispatch_routes.py` | ~4500 | 核心调度逻辑、全部 API 接口 |
| `templates/dispatch/dashboard.html` | ~3700 | 实时看板、设备网格、折线图、日志面板 |
| `templates/dispatch/config.html` | ~480 | 可视化配置管理（三标签页） |
| `templates/dispatch/readme.md` | ~700 | 模块完整文档 |
| `templates/dispatch/test.html` | ~490 | 自动驾驶测试（彩蛋功能） |
| `modules/query/task_query_extended.py` | ~800 | 任务查询扩展 |

---

## 六、设计理念

### 零外部依赖
所有数据存储在本地 JSON 文件中，无需数据库服务。在 100 个文件以内性能优于数据库方案（无网络/连接开销）。

### 静默容错
状态上报接口始终返回 `{"code": 1000}`，即使匹配失败也不阻塞 RCS。匹配失败的信息记录到 `report_unmatched` 日志中供排查。

### 增量更新
看板采用增量刷新模式——比对设备列表差异，新设备动画滑入，离开设备动画淡出。展开的面板不受自动刷新影响。

### 防抖保护
自动调度、分时段切换、全量查询均设有防抖机制，避免短时间内重复触发。

### 可观测性
双层日志存储（热数据+归档）、增量拉取、搜索筛选、Supervisor 控制台日志查看，覆盖从开发调试到生产排查的全场景。
