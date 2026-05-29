# task_template & task_relation 表结构文档

> **数据库**: `wms` (10.68.2.32:3306)
> **字符集**: `utf8mb3`
> **引擎**: InnoDB
> **最后更新**: 2026-05-28

---

## 核心关联字段

`task_template` 与 `task_relation` 通过 **`task_template.id` → `task_relation.template_id`** 关联：

```
task_template.id (PK, 自增)  ────→  task_relation.template_id (FK)
                                          │
                                          ├── type_id ──→ task_type.id (子任务动作类型)
                                          ├── skip_id ──→ task_relation_skip.id (跳过条件)
                                          └── relate_template → task_template.template_code (关联模板)
```

- **一对多关系**：一个 `task_template` 可对应多个 `task_relation` 记录（一个模板包含多个子任务步骤）
- **示例**：模板 `coaxialFork1`（id=41）在 `task_relation` 中有 6 条记录（6 个子任务步骤）

---

## 目录

- [task\_template \& task\_relation 表结构文档](#task_template--task_relation-表结构文档)
  - [核心关联字段](#核心关联字段)
  - [目录](#目录)
  - [1. 表关系总览](#1-表关系总览)
  - [2. task\_template — 任务模板表](#2-task_template--任务模板表)
    - [字段说明](#字段说明)
    - [关键字段枚举](#关键字段枚举)
    - [样本数据](#样本数据)
  - [3. task\_relation — 模板子任务关联表](#3-task_relation--模板子任务关联表)
    - [字段说明](#字段说明-1)
    - [关键字段说明](#关键字段说明)
  - [4. 关联表](#4-关联表)
    - [4.1 task\_type — 子任务类型表](#41-task_type--子任务类型表)
    - [4.2 task\_relation\_skip — 跳过条件表](#42-task_relation_skip--跳过条件表)
    - [4.3 template\_weight\_config — 任务权重配置表](#43-template_weight_config--任务权重配置表)
  - [5. 核心关联关系](#5-核心关联关系)
    - [5.1 关联链路](#51-关联链路)
    - [5.2 业务关联说明](#52-业务关联说明)
    - [5.3 模板与跨环境模板的关系](#53-模板与跨环境模板的关系)
  - [6. 常用 SQL](#6-常用-sql)
    - [6.1 查询模板及其子任务步骤](#61-查询模板及其子任务步骤)
    - [6.2 查询模板的子任务数量统计](#62-查询模板的子任务数量统计)
    - [6.3 查询使用特定子任务类型的模板](#63-查询使用特定子任务类型的模板)
    - [6.4 查询需要第三方触发的子任务](#64-查询需要第三方触发的子任务)
    - [6.5 查询有关联关系的模板](#65-查询有关联关系的模板)
    - [6.6 查询可跳过的子任务](#66-查询可跳过的子任务)
    - [6.7 按区域查询模板](#67-按区域查询模板)
    - [6.8 查询完整的模板定义（含动作指令）](#68-查询完整的模板定义含动作指令)
  - [7. 业务场景说明](#7-业务场景说明)
    - [7.1 典型模板流程示例](#71-典型模板流程示例)
    - [7.2 取消模板的特殊用途](#72-取消模板的特殊用途)
    - [7.3 模板优先级说明](#73-模板优先级说明)
    - [7.4 注意事项](#74-注意事项)
  - [8. model\_process \& model\_process\_detail — 业务流程模板](#8-model_process--model_process_detail--业务流程模板)
    - [8.1 概述](#81-概述)
    - [8.2 model\_process — 业务流程模板](#82-model_process--业务流程模板)
    - [8.3 model\_process\_detail — 业务流程子任务](#83-model_process_detail--业务流程子任务)
    - [8.4 四表完整关联链路](#84-四表完整关联链路)
    - [8.5 关键发现](#85-关键发现)
    - [8.6 常用 SQL](#86-常用-sql)
  - [9. 按模板名称查询](#9-按模板名称查询)
    - [8.1 查询模板基本信息及子任务步骤](#81-查询模板基本信息及子任务步骤)
    - [8.2 查询模板的完整关联链路](#82-查询模板的完整关联链路)
    - [8.3 查询模板被引用情况](#83-查询模板被引用情况)
    - [8.4 一键查询脚本（Python）](#84-一键查询脚本python)
│                                                                 │
│  task_template (任务模板)                                        │
│  ├── id (PK)                                                    │
│  ├── template_code (UK) — 模板编号                               │
│  ├── name — 模板名称                                             │
│  ├── processor — 处理器类型 (carry/temp/fork/storage)            │
│  ├── areaId — 区域ID (-2=非跨区域, -1=跨区域, 1/2/3/5=具体区域)   │
│  ├── template_type — 任务类型 (1=RCS, 2=机械臂, 3=传送带, 4=备料) │
│  └── priority — 优先级 (2=指定, 4=高, 6=中, 8=低)                │
│       │                                                         │
│       │ task_relation.template_id → task_template.id            │
│       ▼                                                         │
│  task_relation (模板子任务关联)                                    │
│  ├── id (PK)                                                    │
│  ├── template_id → task_template.id                             │
│  ├── type_id → task_type.id (子任务类型)                          │
│  ├── need_trigger — 是否需要第三方触发                             │
│  ├── skip / skip_id — 跳过条件                                   │
│  ├── relate_template — 关联的模板编号                              │
│  └── sub_template — 关联的子模板                                  │
│       │                                                         │
│       │ task_relation.type_id → task_type.id                     │
│       ▼                                                         │
│  task_type (子任务类型)                                           │
│  ├── id (PK)                                                    │
│  ├── type_code — 类型编码 (MOVE/LIFT/DOWN/ROLLER 等)             │
│  ├── name — 类型名称                                             │
│  ├── action — 动作指令 JSON                                      │
│  └── description — 详细说明                                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. task_template — 任务模板表

**表注释**: 任务模板表  
**记录数**: 586 条  
**主键**: `id` (自增)  
**唯一键**: `template_code`

### 字段说明

| 字段 | 类型 | 空 | 默认值 | 说明 |
|------|------|----|--------|------|
| id | int unsigned | NO | | 主键，自增 |
| template_code | varchar(64) | YES | NULL | **任务模板编号**（唯一键），如 `move`、`loadCancle`、`coaxialFork1` |
| name | varchar(64) | YES | NULL | 任务模板名称，如"指定设备空车移动"、"料箱搬运" |
| processor | varchar(64) | YES | NULL | **处理器类型**：`carry`=搬运, `temp`=临时/取消, `fork`=叉车, `storage`=仓储 |
| is_default | char(1) | YES | NULL | 是否默认模板：`0`=否, `1`=是, `2`=区域默认 |
| merge_template | varchar(64) | YES | NULL | 合并的任务模板编号 |
| merge_exe_seq | tinyint(1) | YES | NULL | 合并任务的执行顺序：`1`=先执行, `2`=后执行 |
| fix_point_areaId | varchar(50) | YES | NULL | 合并区域：片区域ID集 |
| priority | tinyint(1) | YES | NULL | **任务优先级**：`2`=指定, `4`=高, `6`=中, `8`=低 |
| areaId | int | **NO** | | **区域ID**：`-2`=非跨区域(全局), `-1`=跨区域, `1/2/3/5`=具体区域 |
| capacity_control | tinyint(1) | YES | `0` | 是否容量管控：`0`=否, `1`=是 |
| re_execute | tinyint(1) | **NO** | `1` | 是否允许重新执行：`0`=不允许, `1`=允许 |
| agv_task_weight | varchar(1000) | YES | NULL | 设备执行任务权重 JSON，如 `{"DH-RTA-FL-L15":50}` |
| template_type | tinyint | **NO** | `1` | **任务类型**：`1`=RCS任务, `2`=机械臂任务, `3`=传送带任务, `4`=备料任务 |
| allow_recover | tinyint(1) | **NO** | `0` | 是否允许回收：`0`=不允许, `1`=允许 |
| allow_charge_device | tinyint(1) | **NO** | `0` | 是否允许换车：`0`=允许, `1`=不允许 |
| allow_device_num | varchar(1000) | YES | NULL | 允许执行的设备编号列表 |
| allow_merge | tinyint(1) | **NO** | `0` | 是否允许同模板合并：`0`=不允许, `1`=允许 |
| weight_id | int | YES | NULL | 任务权重ID，关联 `template_weight_config` |
| no_load_speed | float(10,3) | YES | `-1.000` | 空载速度（-1=使用默认） |
| pay_load_speed | float(10,3) | YES | `-1.000` | 负载速度（-1=使用默认） |
| is_release_robot | tinyint | YES | NULL | `0`=任务完成时释放设备, `1`=不释放 |
| share_device | varchar(1000) | YES | NULL | 允许分享的设备 |
| share_condition | varchar(1000) | YES | NULL | 允许分享的条件 |
| share_template | varchar(1000) | YES | NULL | 允许分享的任务模板 |
| allow_agv_model | varchar(255) | YES | NULL | 允许执行的设备型号 |
| allow_device_cancel_task | int | YES | `1` | 是否允许设备取消任务：`1`=允许, `0`=不允许 |
| default_cancel_task_strategy | tinyint(1) | YES | `1` | 负载取消策略：`1`=默认取消动作, `2`=指定片区域, `3`=回原库位 |
| default_cancel_task_strategy_fix_point | varchar(200) | YES | NULL | 取消任务指定点 |
| default_cancel_task_strategy_fix_point_score | varchar(200) | YES | NULL | 取消任务指定点分数 |
| backup_device_num | varchar(1000) | YES | NULL | 备用设备编号 |
| backup_device_ratio | int | YES | `0` | 备用设备比例 |
| backup_device_code | varchar(1000) | YES | NULL | 备用设备序列号 |
| is_cross | tinyint(1) | YES | NULL | 是否跨区域模板：`1`=是, `0`=否 |
| task_capacity | varchar(255) | YES | NULL | 任务数量管控（TPS使用） |
| allow_device_group | varchar(500) | YES | NULL | 允许设备分组ID |
| backup_device_group | varchar(500) | YES | NULL | 备用设备分组ID |

### 关键字段枚举

**processor 分布**:
| processor | 数量 | 说明 |
|-----------|------|------|
| carry | 556 | 搬运类模板（主流） |
| temp | 24 | 临时/取消类模板 |
| fork | 5 | 叉车类模板 |
| storage | 1 | 仓储类模板 |

**areaId 分布**:
| areaId | 数量 | 说明 |
|--------|------|------|
| 3 | 286 | 区域3 |
| 1 | 264 | 区域1 |
| 5 | 12 | 区域5 |
| -2 | 10 | 非跨区域（全局模板） |
| -1 | 8 | 跨区域模板 |
| 2 | 6 | 区域2 |

**template_type**: 当前全部为 `1`（RCS任务）

### 样本数据

| id | template_code | name | processor | areaId | priority | is_default |
|----|---------------|------|-----------|--------|----------|------------|
| 1 | move | 指定设备空车移动 | carry | -2 | NULL | 1 |
| 3 | loadCancle | 辊筒设备任务取消 | temp | -1 | 6 | 1 |
| 4 | storageCancel | 举升型设备任务取消 | temp | -1 | 6 | 1 |
| 17 | xiaojianjieliao | 小分拣小件接料任务 | carry | 1 | 6 | 0 |
| 18 | hedanshangliao | 同轴叉车合单上料到接驳口任务 | fork | 1 | 6 | 0 |
| 34 | fenjianshangjia | 潜伏举升车大件排出口上架任务 | storage | 1 | 6 | 0 |

---

## 3. task_relation — 模板子任务关联表

**表注释**: 任务模板子任务类型关联表  
**记录数**: 1652 条  
**主键**: `id` (自增)

### 字段说明

| 字段 | 类型 | 空 | 默认值 | 说明 |
|------|------|----|--------|------|
| id | int unsigned | NO | | 主键，自增 |
| template_id | int | YES | NULL | **关联 task_template.id**，所属模板 |
| type_id | int | YES | NULL | **关联 task_type.id**，子任务类型 |
| need_trigger | tinyint(1) | YES | NULL | 是否需要第三方触发：`0`=否, `1`=是 |
| trigger_type | tinyint | YES | NULL | 第三方触发方式 |
| point_access | tinyint | YES | NULL | 点位获取方式 |
| point_access_ext | tinyint | YES | `1` | ICS使用的点位获取方式 |
| point_type | tinyint | YES | NULL | **点位类型**：`1`=电梯点, `2`=电梯入口, `3`=电梯出口, `4`=门禁点, `5`=扫描门入口, `6`=扫描门出口, `7`=货架点, `8`=工作台 |
| choose_mode | tinyint(1) | YES | NULL | 无可用点是否继续：`0`=不继续, `1`=继续 |
| notify_third | tinyint(1) | YES | NULL | 是否需要通知第三方：`0`=否, `1`=是 |
| notify_start | varchar(2000) | YES | NULL | 开始通知配置 |
| notify_end | varchar(2000) | YES | NULL | 结束通知配置 |
| skip | tinyint(1) | YES | NULL | 是否跳过：`0`=必做, `1`=选做（可跳过） |
| skip_id | int | YES | `0` | 跳过条件，关联 `task_relation_skip.id` |
| relate_template | varchar(64) | YES | NULL | **关联的任务模板编号**，用于任务间关联 |
| relate_exe_seq | tinyint(1) | YES | NULL | 关联任务顺序：`1`=向前关联, `2`=向后关联 |
| fix_point | varchar(1000) | YES | NULL | 指定点 |
| fix_point_score | varchar(5000) | YES | NULL | 指定点分数 |
| is_alarm | tinyint | YES | `0` | 是否告警：`0`=否, `1`=是 |
| auto_trigger_time | int | YES | NULL | 自动触发时间（秒） |
| select_chance | int | YES | NULL | 选点时机：`1`=任务下发前选点, `2`=任务中选点 |
| select_tactics | int | YES | NULL | 选点策略 |
| sub_template | varchar(100) | YES | NULL | **关联的子模板编号** |
| config_name | varchar(30) | YES | NULL | 目标点获取方式-第三方获取 |
| select_scene | varchar(255) | YES | NULL | 选点场景名 |
| select_scene_param | varchar(2048) | YES | NULL | 选点场景相关配置 |
| load_type | int | YES | NULL | 子任务负载状态 |
| notify_start_extra_status_id | varchar(100) | YES | NULL | ICS任务开始时上报状态ID |
| notify_end_extra_status_id | varchar(100) | YES | NULL | ICS任务结束时上报状态ID |
| trigger_over_time | int | YES | NULL | 触发超时时间 |
| trigger_over_time_handle | tinyint | YES | NULL | 触发超时处理：`0`=任务取消, `1`=继续等待 |
| auto_cancel_task | tinyint(1) | YES | `0` | 是否自动取消任务：`0`=否, `1`=是 |
| cancel_actions | varchar(255) | YES | NULL | 取消后动作（临时模板编号） |

### 关键字段说明

**type_id 分布（前10）**:
| type_id | 数量 | 对应 task_type |
|---------|------|----------------|
| 1 | 417 | MOVE — 空车移动 |
| 2 | 305 | MOVE_POD — 移动货架/栈板(负载到达) |
| 75 | 176 | (需查 task_type 表确认) |
| 5 | 100 | DOWN — 放下货架 |
| 4 | 78 | LIFT — 举升货架 |
| 13 | 25 | MOVE — 空车移动(至识别准备点，无高度调节) |
| 29 | 16 | SHELF_BUTT — 货架识别 |
| 7 | 14 | PEND — 人工干预 |
| 10 | 13 | MOVE_GOODS — 移动货物 |
| 38 | 9 | ROLLER — 辊筒滚动(辊筒无传感器) |

**point_type**: 当前全部为 NULL（未使用点位类型区分）

---

## 4. 关联表

### 4.1 task_type — 子任务类型表

**表注释**: 任务类型定义表  
**记录数**: 58 种动作类型

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| type_code | varchar(64) | 类型编码（如 `MOVE`、`LIFT`、`DOWN`、`ROLLER`） |
| name | varchar(64) | 类型名称 |
| action | json | 动作指令 JSON 数组 |
| is_default | tinyint(1) | 是否默认：`1`=是 |
| task_fail_retry_times | int | 任务失败重试次数 |
| arrival_type | tinyint | 到达类型 |
| continue_after_fail | tinyint | 失败后是否继续 |
| use_pos | tinyint | 是否使用位置 |
| dest_shift | tinyint | 目标偏移 |
| move_action | tinyint | 移动动作 |
| storage_action | tinyint | 存储动作 |
| load_action | tinyint | 负载动作 |
| exec_time | int | 执行时间 |
| payload_change | tinyint | 负载变化 |
| pend_action | tinyint | 暂停动作 |
| action_check | tinyint | 动作检查 |
| must_update | tinyint | 必须更新 |
| arc_butt_action | tinyint | 弧形对接动作 |
| sub_template | varchar(64) | 关联子模板 |
| description | text | 详细说明 |
| action_not_use_pos | tinyint | 动作不使用位置 |
| update_stock_status | tinyint | 更新库存状态 |
| load_status | tinyint | 负载状态 |
| failed_change_robot_times | int | 失败换车次数 |
| must_create | tinyint | 必须创建 |
| dock_mode | tinyint | 对接模式 |

**常用 type_code 对照**:

| id | type_code | name | 说明 |
|----|-----------|------|------|
| 1 | MOVE | 空车移动 | 全序列AMR不带action的空车移动 |
| 2 | MOVE_POD | 移动货架/栈板(负载到达) | 以负载到点为准的货架/栈板移动 |
| 3 | ROLLER | 辊筒滚动(上料) | 辊筒AMR往传输线上料 |
| 4 | LIFT | 举升货架 | 举升型AMR到达货架下后举升 |
| 5 | DOWN | 放下货架 | 举升型AMR放下货架 |
| 6 | DOCK | 充电对接V1 | 二维码导航设备充电（旧版） |
| 7 | PEND | 人工干预 | 需要人工操作确认 |
| 9 | PUTTER | 推杆限位 | 辊筒AMR调节辊筒宽度 |
| 10 | MOVE_GOODS | 移动货物 | 辊筒AMR移动货物 |
| 11 | DOCK_TO_PLATFORM | 线体对接 | 辊筒AMR与生产线对接 |
| 12 | TIPPER | 翻盖/复位 | 小分拣设备翻盖推货 |
| 13 | MOVE | 空车移动(至识别准备点，无高度调节) | 空车移到识别准备点 |
| 14 | ROLLER | 辊筒滚动(下料) | 传输线往AMR下料 |
| 15 | LIFT_ROLLER | 辊筒举升 | 调节辊筒对接高度 |
| 16 | FROK | 叉取货箱 | 料箱搬运AMR叉取料箱 |
| 17 | TAKE_GOODS | 放下货箱 | 料箱搬运AMR放下料箱 |
| 21 | PALLET_LIFT | 栈板对接(堆垛式叉车) | 堆垛式叉车对接栈板 |
| 22 | MOVE_PALLET_POD | 移动栈板 | 堆垛式叉车搬运栈板 |
| 24 | PALLET_DOWN | 放下栈板(堆垛式叉车) | 堆垛式叉车放下栈板 |
| 25 | DOCK_V2 | 充电对接V2 | 新版充电对接 |
| 29 | SHELF_BUTT | 货架识别 | 举升型AMR识别货架 |
| 33 | MOVE_POD | 移动货架/栈板/料箱(设备到达) | 以设备到点为准 |
| 37 | COMMON | 叉齿高度调节 | 托盘搬运AMR调节叉齿 |
| 38 | ROLLER | 辊筒滚动(辊筒无传感器) | 无传感器辊筒 |
| 53 | PREPARE_MATERIAL | 备料任务 | 备料任务类型 |
| 54 | ARM_TASK | 机械臂任务 | 机械臂任务类型 |
| 55 | CONVEYER_BELT_TASK | 传送带任务 | 传送带任务类型 |
| 56 | ELEVATOR_TASK | 电梯任务 | 电梯任务类型 |

### 4.2 task_relation_skip — 跳过条件表

**表注释**: 跳过条件表  
**记录数**: 少量

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int unsigned | 主键，自增 |
| skip_condition | varchar(1000) | 跳过条件 |
| skip_name | varchar(255) | 跳过名称 |

`task_relation.skip_id` 关联此表 `id`，用于配置子任务在满足特定条件时可跳过执行。

### 4.3 template_weight_config — 任务权重配置表

`task_template.weight_id` 关联此表，用于配置任务权重策略。

---

## 5. 核心关联关系

### 5.1 关联链路

```
task_template (任务模板)
    │
    ├── id ──────────────────→ task_relation.template_id
    │                              │
    │                              ├── type_id ──→ task_type.id (子任务动作类型)
    │                              ├── skip_id ──→ task_relation_skip.id (跳过条件)
    │                              └── relate_template → task_template.template_code (关联模板)
    │
    ├── weight_id ──→ template_weight_config.id (权重配置)
    │
    └── template_code ──→ task_relation.relate_template (被关联)
```

### 5.2 业务关联说明

1. **一个模板包含多个子任务步骤**：`task_template` 的一条记录对应 `task_relation` 的多条记录（通过 `template_id` 关联）
2. **每个子步骤对应一个动作类型**：`task_relation.type_id` 指向 `task_type.id`，定义了该步骤的具体动作（移动、举升、放下等）
3. **子任务可关联其他模板**：`task_relation.relate_template` 可指向另一个 `task_template.template_code`，实现模板间的串联
4. **子任务可引用子模板**：`task_relation.sub_template` 可指向子模板编号，用于复杂任务的嵌套
5. **子任务可配置跳过条件**：`task_relation.skip_id` 关联 `task_relation_skip`，满足条件时可跳过该步骤

### 5.3 模板与跨环境模板的关系

> 注意：`task_template` / `task_relation` 是 **RCS 系统内部**的任务模板定义表，位于 `10.68.2.32` 生产库。
>
> 跨环境模板（`fy_cross_model_process` / `fy_cross_model_process_detail`）是另一套独立的模板体系，用于跨环境任务下发。
>
> 下发链路中，`fy_cross_task_detail.template_code` 对应的是下发到远端服务器的模板编号，与 `task_template.template_code` 可能对应。

---

## 6. 常用 SQL

### 6.1 查询模板及其子任务步骤

```sql
-- 查询指定模板的所有子任务步骤
SELECT
  tt.id AS template_id,
  tt.template_code,
  tt.name AS template_name,
  tr.id AS relation_id,
  tr.type_id,
  tty.type_code,
  tty.name AS task_type_name,
  tty.description AS task_type_desc,
  tr.need_trigger,
  tr.notify_third,
  tr.skip,
  tr.relate_template,
  tr.sub_template
FROM task_template tt
JOIN task_relation tr ON tr.template_id = tt.id
LEFT JOIN task_type tty ON tty.id = tr.type_id
WHERE tt.template_code = 'coaxialFork1'
ORDER BY tr.id;
```

### 6.2 查询模板的子任务数量统计

```sql
-- 统计每个模板包含的子任务数量
SELECT
  tt.id,
  tt.template_code,
  tt.name,
  COUNT(tr.id) AS relation_count
FROM task_template tt
LEFT JOIN task_relation tr ON tr.template_id = tt.id
GROUP BY tt.id
ORDER BY relation_count DESC
LIMIT 20;
```

### 6.3 查询使用特定子任务类型的模板

```sql
-- 查询所有包含"举升货架"(type_id=4)的模板
SELECT DISTINCT
  tt.template_code,
  tt.name,
  tt.areaId,
  tt.processor
FROM task_template tt
JOIN task_relation tr ON tr.template_id = tt.id
WHERE tr.type_id = 4
ORDER BY tt.template_code;
```

### 6.4 查询需要第三方触发的子任务

```sql
-- 查询所有 need_trigger=1 的子任务及其所属模板
SELECT
  tt.template_code,
  tt.name,
  tr.id AS relation_id,
  tty.type_code,
  tty.name AS task_type_name,
  tr.trigger_type,
  tr.auto_trigger_time,
  tr.trigger_over_time,
  tr.trigger_over_time_handle
FROM task_relation tr
JOIN task_template tt ON tt.id = tr.template_id
LEFT JOIN task_type tty ON tty.id = tr.type_id
WHERE tr.need_trigger = 1;
```

### 6.5 查询有关联关系的模板

```sql
-- 查询模板间的关联关系
SELECT
  tt1.template_code AS source_template,
  tt1.name AS source_name,
  tr.relate_template AS target_template,
  tt2.name AS target_name,
  tr.relate_exe_seq AS execute_order
FROM task_relation tr
JOIN task_template tt1 ON tt1.id = tr.template_id
LEFT JOIN task_template tt2 ON tt2.template_code = tr.relate_template
WHERE tr.relate_template IS NOT NULL;
```

### 6.6 查询可跳过的子任务

```sql
-- 查询配置了跳过条件的子任务
SELECT
  tt.template_code,
  tt.name,
  tr.id AS relation_id,
  tty.type_code,
  tty.name AS task_type_name,
  tr.skip,
  trs.skip_name,
  trs.skip_condition
FROM task_relation tr
JOIN task_template tt ON tt.id = tr.template_id
LEFT JOIN task_type tty ON tty.id = tr.type_id
LEFT JOIN task_relation_skip trs ON trs.id = tr.skip_id
WHERE tr.skip = 1 OR tr.skip_id > 0;
```

### 6.7 按区域查询模板

```sql
-- 查询指定区域的所有模板
SELECT
  tt.template_code,
  tt.name,
  tt.processor,
  tt.priority,
  tt.is_default,
  COUNT(tr.id) AS sub_task_count
FROM task_template tt
LEFT JOIN task_relation tr ON tr.template_id = tt.id
WHERE tt.areaId = 1
GROUP BY tt.id
ORDER BY tt.template_code;
```

### 6.8 查询完整的模板定义（含动作指令）

```sql
-- 查询模板的完整定义，包含每个子步骤的动作指令
SELECT
  tt.template_code,
  tt.name,
  tt.processor,
  tt.areaId,
  tt.priority,
  GROUP_CONCAT(
    CONCAT(tty.type_code, '(', tty.name, ')')
    ORDER BY tr.id
    SEPARATOR ' → '
  ) AS task_flow
FROM task_template tt
JOIN task_relation tr ON tr.template_id = tt.id
JOIN task_type tty ON tty.id = tr.type_id
GROUP BY tt.id
LIMIT 30;
```

---

## 7. 业务场景说明

### 7.1 典型模板流程示例

以 **料箱搬运模板** (`coaxialFork1`, id=41) 为例，包含 6 个子任务步骤：

| 步骤 | type_id | type_code | 动作说明 |
|------|---------|-----------|----------|
| 1 | 13 | MOVE | 空车移动至识别准备点（无高度调节） |
| 2 | 16 | FROK | 叉取货箱 |
| 3 | 33 | MOVE_POD | 移动货架/栈板/料箱（设备到达） |
| 4 | 17 | TAKE_GOODS | 放下货箱 |
| 5 | 26 | DOWN_FORK | 放下叉齿 |
| 6 | 13 | MOVE | 空车移动至识别准备点（无高度调节） |

### 7.2 取消模板的特殊用途

`processor='temp'` 的模板（如 `loadCancle`、`storageCancel` 等）是**任务取消模板**，用于在任务取消时执行特定的取消动作序列。这些模板通常：
- `areaId=-1`（跨区域）
- `is_default=1`（默认模板）
- `re_execute=0`（不允许重新执行）

### 7.3 模板优先级说明

| priority | 含义 | 说明 |
|----------|------|------|
| 2 | 指定 | 最高优先级，通常用于指定设备执行 |
| 4 | 高 | 高优先级任务 |
| 6 | 中 | 普通优先级（默认） |
| 8 | 低 | 低优先级任务 |

### 7.4 注意事项

1. **只读约束**：`task_template` 和 `task_relation` 位于生产库 `10.68.2.32`，仅允许 SELECT 查询
2. **模板编号唯一**：`template_code` 是唯一键，全局不可重复
3. **子任务顺序**：`task_relation` 中没有显式的 `seq` 字段，子任务执行顺序由 `id` 递增决定
4. **区域隔离**：不同区域的模板通过 `areaId` 隔离，`-2` 为全局模板，`-1` 为跨区域模板
5. **与跨环境模板的区别**：`task_template` 是 RCS 内部模板，`fy_cross_model_process` 是跨环境模板，两者独立

---

## 8. model_process & model_process_detail — 业务流程模板

### 8.1 概述

`model_process` 和 `model_process_detail` 是 RCS 系统的**业务流程模板配置表**，与 `task_template` / `task_relation` 共同构成完整的模板体系。

**统计**：
- `model_process`：534 条（业务流程模板）
- `model_process_detail`：536 条（子任务关联）
- `task_template`：534 条（任务模板）
- `task_relation`：1095 条（子任务步骤）

### 8.2 model_process — 业务流程模板

**表注释**: 流程模式  
**记录数**: 534 条  
**主键**: `id` (自增)  
**唯一键**: `model_process_code`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 主键，自增 |
| `area_id` | int | 区域ID |
| `priority` | int | 优先级：4=低, 6=中, 8=高 |
| `model_process_code` | varchar(64) | **流程模板编号**（唯一键） |
| `model_process_name` | varchar(64) | 流程模板名称 |
| `create_time` | datetime | 创建时间 |
| `update_time` | datetime | 更新时间 |
| `sys_auto_generate` | int | 系统自动创建：0=否, 1=是 |
| `exe_immediately` | int | 立即执行：0=否, 1=是 |
| `enable` | tinyint | 是否允许第三方下发订单：0=不允许, 1=允许 |
| `is_support_agv` | int | 是否支持多车：1=单车, 2=多车 |

### 8.3 model_process_detail — 业务流程子任务

**表注释**: 流程模式子任务  
**记录数**: 536 条  
**主键**: `id` (自增)

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 主键，自增 |
| `model_process_id` | int | 关联 `model_process.id` |
| `template_code` | varchar(64) | 任务流程子任务编号 |
| `task_template_id` | int | **关联 `task_template.id`**（536条全部有值） |
| `template_name` | varchar(100) | 子任务名称 |
| `template_type` | int | 任务类型：1=RCS, 2=机械臂, 3=传送带 |
| `continue_condition` | int | 继续任务类型：1=无, 2=其他子任务, 3=第三方确认 |
| `trigger_condition` | int | 触发条件类型：1=无, 2=其他任务 |

### 8.4 四表完整关联链路

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RCS 模板体系完整 ER 图                            │
│                                                                     │
│  model_process (业务流程模板) — 534条                                │
│  ├── id (PK)                                                        │
│  ├── model_process_code (UK) — 流程模板编号                          │
│  ├── model_process_name — 流程模板名称                               │
│  ├── area_id — 区域ID                                               │
│  ├── priority — 优先级 (4低/6中/8高)                                 │
│  └── enable — 启用状态                                              │
│       │                                                             │
│       │ model_process_detail.model_process_id → model_process.id    │
│       ▼                                                             │
│  model_process_detail (业务流程子任务) — 536条                       │
│  ├── id (PK)                                                        │
│  ├── model_process_id → model_process.id                            │
│  ├── template_code — 子任务模板编号                                  │
│  ├── task_template_id → task_template.id (100%覆盖)                 │
│  ├── template_name — 子任务名称                                      │
│  ├── template_type — 任务类型 (1=RCS)                                │
│  ├── continue_condition — 继续条件                                   │
│  └── trigger_condition — 触发条件                                    │
│       │                                                             │
│       │ model_process_detail.task_template_id → task_template.id    │
│       ▼                                                             │
│  task_template (任务模板) — 534条                                    │
│  ├── id (PK)                                                        │
│  ├── template_code (UK) — 模板编号                                   │
│  ├── name — 模板名称                                                │
│  ├── processor — 处理器类型 (carry/temp/fork/storage)                │
│  ├── areaId — 区域ID                                                │
│  └── priority — 优先级 (2指定/4高/6中/8低)                           │
│       │                                                             │
│       │ task_relation.template_id → task_template.id                │
│       ▼                                                             │
│  task_relation (模板子任务关联) — 1095条                             │
│  ├── id (PK)                                                        │
│  ├── template_id → task_template.id                                 │
│  ├── type_id → task_type.id (子任务动作类型)                          │
│  ├── need_trigger — 是否需要第三方触发                               │
│  ├── skip / skip_id — 跳过条件                                      │
│  ├── relate_template — 关联的模板编号                                │
│  └── sub_template — 关联的子模板                                     │
│       │                                                             │
│       │ task_relation.type_id → task_type.id                        │
│       ▼                                                             │
│  task_type (子任务类型) — 58种                                       │
│  ├── id (PK)                                                        │
│  ├── type_code — 类型编码 (MOVE/LIFT/DOWN/ROLLER 等)                │
│  ├── name — 类型名称                                                │
│  ├── action — 动作指令 JSON                                         │
│  └── description — 详细说明                                         │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.5 关键发现

1. **`model_process_detail.task_template_id` 100% 覆盖**：536条子任务全部关联了 `task_template.id`，说明业务流程模板和任务模板之间是**强关联**关系。

2. **`model_process` 与 `task_template` 数量接近**：534 vs 534，说明一个业务流程模板通常对应一个任务模板。

3. **`task_relation` 数量多于 `task_template`**：1095 vs 534，说明一个任务模板平均有约 2 个子任务步骤。

4. **关联链路**：
   ```
   model_process (业务流程)
     → model_process_detail (子任务)
       → task_template (任务模板)
         → task_relation (子任务步骤)
           → task_type (动作类型)
   ```

5. **与跨环境模板的关系**：
   - `model_process` / `model_process_detail` — RCS 系统内部业务流程模板
   - `fy_cross_model_process` / `fy_cross_model_process_detail` — 跨环境任务模板
   - 两套体系独立，但 `fy_cross_model_process_detail.template_code` 指向 `task_template.template_code`

### 8.6 常用 SQL

```sql
-- 查询业务流程模板及其完整链路
SELECT
  mp.id,
  mp.model_process_code,
  mp.model_process_name,
  mp.area_id,
  mp.priority,
  mp.enable,
  mpd.id AS detail_id,
  mpd.template_code,
  mpd.task_template_id,
  mpd.template_name,
  tt.name AS task_template_name,
  tt.processor,
  tt.areaId AS task_template_area,
  COUNT(tr.id) AS relation_count
FROM model_process mp
LEFT JOIN model_process_detail mpd ON mpd.model_process_id = mp.id
LEFT JOIN task_template tt ON tt.id = mpd.task_template_id
LEFT JOIN task_relation tr ON tr.template_id = tt.id
WHERE mp.model_process_code = 'xiaojianjieliao'
GROUP BY mp.id, mpd.id
ORDER BY mpd.id;

-- 查询业务流程模板的子任务步骤（含动作类型）
SELECT
  mp.model_process_code,
  mp.model_process_name,
  mpd.template_code,
  mpd.template_name,
  tt.name AS task_template_name,
  tr.type_id,
  tty.type_code,
  tty.name AS action_name,
  tty.description
FROM model_process mp
JOIN model_process_detail mpd ON mpd.model_process_id = mp.id
JOIN task_template tt ON tt.id = mpd.task_template_id
JOIN task_relation tr ON tr.template_id = tt.id
JOIN task_type tty ON tty.id = tr.type_id
WHERE mp.id = 1
ORDER BY mpd.id, tr.id;

-- 统计每个业务流程模板的子任务数量
SELECT
  mp.id,
  mp.model_process_code,
  mp.model_process_name,
  COUNT(mpd.id) AS detail_count,
  SUM(tr_count.cnt) AS total_relation_count
FROM model_process mp
LEFT JOIN model_process_detail mpd ON mpd.model_process_id = mp.id
LEFT JOIN (
  SELECT mpd2.id AS detail_id, COUNT(tr.id) AS cnt
  FROM model_process_detail mpd2
  JOIN task_template tt ON tt.id = mpd2.task_template_id
  JOIN task_relation tr ON tr.template_id = tt.id
  GROUP BY mpd2.id
) tr_count ON tr_count.detail_id = mpd.id
GROUP BY mp.id
ORDER BY mp.id
LIMIT 20;
```

---

## 9. 按模板名称查询

以下查询以模板名称 `K31CCto191F_go_522` 为例，展示如何根据模板名称（`template_code` 或 `name`）查询两张表的关联数据。

### 8.1 查询模板基本信息及子任务步骤

```sql
-- 按模板名称模糊搜索 task_template
SELECT * FROM task_template
WHERE template_code LIKE '%K31CCto191F_go_522%'
   OR name LIKE '%K31CCto191F_go_522%';

-- 查询该模板关联的所有子任务步骤（含动作类型）
SELECT
  tt.id AS template_id,
  tt.template_code,
  tt.name AS template_name,
  tt.processor,
  tt.areaId,
  tt.priority,
  tr.id AS relation_id,
  tr.type_id,
  tty.type_code,
  tty.name AS task_type_name,
  tty.description AS task_type_desc,
  tr.need_trigger,
  tr.notify_third,
  tr.skip,
  tr.relate_template,
  tr.sub_template
FROM task_template tt
LEFT JOIN task_relation tr ON tr.template_id = tt.id
LEFT JOIN task_type tty ON tty.id = tr.type_id
WHERE tt.template_code = 'K31CCto191F_go_522'
ORDER BY tr.id;
```

### 8.2 查询模板的完整关联链路

```sql
-- 查询模板信息 + 子任务步骤 + 被引用情况（一次查出）
SELECT
  tt.id,
  tt.template_code,
  tt.name,
  tt.processor,
  tt.areaId,
  tt.priority,
  tt.re_execute,
  tt.capacity_control,
  tt.allow_recover,
  tt.allow_charge_device,
  tt.allow_merge,
  tt.backup_device_ratio,
  -- 子任务信息
  tr.id AS relation_id,
  tr.type_id,
  tty.type_code,
  tty.name AS task_type_name,
  tr.need_trigger,
  tr.skip,
  tr.relate_template,
  tr.sub_template,
  -- 被引用计数
  (SELECT COUNT(*) FROM task_relation sub WHERE sub.relate_template = tt.template_code) AS referenced_count
FROM task_template tt
LEFT JOIN task_relation tr ON tr.template_id = tt.id
LEFT JOIN task_type tty ON tty.id = tr.type_id
WHERE tt.template_code = 'K31CCto191F_go_522'
ORDER BY tr.id;
```

### 8.3 查询模板被引用情况

```sql
-- 查询该模板被哪些其他模板引用（作为 relate_template）
SELECT
  tt.template_code AS source_template,
  tt.name AS source_name,
  tr.relate_template AS referenced_template,
  tr.relate_exe_seq
FROM task_relation tr
JOIN task_template tt ON tt.id = tr.template_id
WHERE tr.relate_template = 'K31CCto191F_go_522';

-- 查询该模板在跨环境任务中的使用情况
SELECT
  ftd.id,
  ftd.order_id,
  ftd.template_code,
  ftd.status,
  ftd.device_num,
  ftd.create_time
FROM fy_cross_task_detail ftd
WHERE ftd.template_code = 'K31CCto191F_go_522'
ORDER BY ftd.create_time DESC
LIMIT 10;

-- 查询该模板在本地任务组中的使用情况
SELECT
  tg.id,
  tg.template_code,
  tg.status,
  tg.robot_num,
  tg.create_time
FROM task_group tg
WHERE tg.template_code = 'K31CCto191F_go_522'
ORDER BY tg.create_time DESC
LIMIT 10;
```

### 8.4 一键查询脚本（Python）

```python
import pymysql

conn = pymysql.connect(
    host='10.68.2.32', port=3306,
    user='wms', password='CCshenda889',
    database='wms', charset='utf8mb4'
)
cursor = conn.cursor()

template_code = 'K31CCto191F_go_522'

# 1. 查模板基本信息
cursor.execute('SELECT * FROM task_template WHERE template_code = %s', (template_code,))
cols = [d[0] for d in cursor.description]
row = cursor.fetchone()
print('=== task_template 基本信息 ===')
for i, col in enumerate(cols):
    print(f'  {col}: {row[i]}')

# 2. 查关联子任务
template_id = row[0]
cursor.execute('''
    SELECT tr.*, tty.type_code, tty.name AS type_name, tty.description
    FROM task_relation tr
    LEFT JOIN task_type tty ON tty.id = tr.type_id
    WHERE tr.template_id = %s
    ORDER BY tr.id
''', (template_id,))
rows = cursor.fetchall()
print(f'\n=== task_relation 关联子任务 ({len(rows)} 条) ===')
for r in rows:
    print(f'  relation_id={r[0]}, type_id={r[2]}, type_code={r[-3]}, type_name={r[-2]}')
    print(f'    need_trigger={r[3]}, notify_third={r[8]}, skip={r[11]}')

# 3. 查被引用情况
cursor.execute('''
    SELECT tt.template_code, tt.name
    FROM task_relation tr
    JOIN task_template tt ON tt.id = tr.template_id
    WHERE tr.relate_template = %s
''', (template_code,))
rows = cursor.fetchall()
print(f'\n=== 被引用 ({len(rows)} 处) ===')
for r in rows:
    print(f'  被 {r[0]}({r[1]}) 引用')

cursor.close()
conn.close()
```
