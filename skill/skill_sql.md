---
name: sql-skill
description: cross_env_manager 项目数据库表结构和常用 SQL 查询指导
---

# 数据库 SQL Skill

## 数据库连接

### 测试环境
```toml
[database]
host = "47.98.244.173"
port = 53308
user = "root"
password = "Qq13235202993"
name = "wms"
charset = "utf8mb4"
```
可自由操作及创建表和数据。

### 生产环境（只读）
```toml
[database]
host = "10.68.2.32"
port = 3306
user = "wms"
password = "CCshenda889"
name = "wms"
charset = "utf8mb4"
```
仅允许读取，不允许修改。

## 核心表结构

### 1. task_group（任务组）
这个是单服务器内的任务索引表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键，自增 |
| template_code | varchar(64) | 任务模板编号 |
| task_type | tinyint(1) | 1:搬运 2:仓储 |
| priority | bigint | 优先级 |
| score | bigint | 分数/权重 |
| order_path | varchar(5000) | 订单路径 |
| path_points | varchar(5000) | 路径点集 |
| area_id | int | 区域ID |
| status | tinyint | 1:未发送 2:正在取消 3:已取消 4:正在发送 5:发送失败 6:执行中 7:执行失败 8:任务完成 9:已下发 |
| merge_tg_id | bigint | 合并任务组ID |
| order_id | bigint | 订单ID（关联 task_order.id） |
| out_order_id | varchar(64) | 外部订单ID |
| third_order_id | varchar(100) | 第三方订单ID |
| create_time | int | 创建时间(Unix时间戳) |
| start_time | int | 开始时间(Unix时间戳) |
| end_time | int | 结束时间(Unix时间戳) |
| robot_id | varchar(20) | 设备序列号 |
| robot_num | varchar(10) | 分派AGV编号 |
| robot_type | varchar(2000) | 设备类型 |
| shelf_num | varchar(200) | 货架号 |
| shelf_model | int | 货架模型 |
| load_type | int | 负载状态 |
| error_desc | varchar(200) | 错误描述 |
| display | tinyint(1) | 是否显示，默认1 |
| is_sequence | tinyint(1) | 是否顺序执行，默认0 |
| is_temp | tinyint(1) | 是否临时任务，默认0 |
| materiel | varchar(3000) | 物料信息 |
| work_id | int | 工作站ID |
| action_param | varchar(2000) | 动作参数 |
| merge_id | bigint | 合并ID |
| sub_ids | varchar(200) | 子任务ID列表 |
| merge_status | tinyint | 合并状态 |
| storage_num | varchar(200) | 库位编号 |
| agv_task_weight | varchar(200) | AGV任务权重 |
| stack_storage_num | tinyint | 堆叠库位编号 |
| carrier_type | int | 载体类型 0:无 1:货架 2:栈板 3:料箱 |
| carrier_code | varchar(200) | 载体编号 |
| is_release_robot | tinyint | 是否释放AGV |
| send_time | int | 发送时间(Unix时间戳) |
| has_next_move_task_info | int | 是否有下一移动任务信息，默认1 |
| is_create_task | int | 0:不需要 1:需要创建 2:已创建 |
| main_task_id | varchar(200) | 主任务ID |
| origin_task_info | varchar(1000) | 原始任务信息 |
| task_model | varchar(255) | 任务模型 |
| default_cancel_task_strategy | tinyint(1) | 默认取消策略，默认1 |
| default_cancel_task_strategy_fix_point | varchar(200) | 取消策略固定点 |
| default_cancel_task_strategy_fix_point_score | varchar(200) | 取消策略固定点分数 |
| pre_alloc | tinyint(1) | 是否预分配，默认0 |
| error_code | varchar(64) | 错误码 |

### 2. task_order（任务订单/大任务）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键，自增 |
| template_code | varchar(64) | 任务模板编号 |
| materiel | varchar(3000) | 物料信息 |
| priority | tinyint(1) | 优先级 |
| status | tinyint | 状态码（同 task_group） |
| area_id | int | 区域ID |
| work_id | int | 工作站ID |
| order_source | tinyint | 订单来源，默认0 |
| out_order_id | varchar(64) | 外部订单ID（唯一键） |
| third_order_id | varchar(100) | 第三方订单ID |
| relate_out_order_id | varchar(64) | 关联外部订单ID |
| is_sequence | tinyint(1) | 是否顺序执行，默认0 |
| is_temp | tinyint(1) | 是否临时任务，默认0 |
| action_param | varchar(200) | 动作参数 |
| handle_name | varchar(64) | 处理人名称 |
| error_desc | varchar(200) | 错误描述 |
| create_time | datetime | 创建时间 |
| order_file_id | int | 订单文件ID |
| start_time | datetime | 开始时间 |
| end_time | datetime | 结束时间 |
| is_delete | tinyint(1) | 是否删除，默认0 |
| order_type | tinyint | 订单类型，默认0 |

### 3. task_order_detail（任务订单子任务/子任务详情）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键，自增 |
| order_id | bigint | 关联 task_order.id |
| template_code | varchar(64) | 任务模板编号 |
| area_id | int | 区域ID |
| priority | tinyint(1) | 优先级 |
| shelf_num | varchar(32) | 货架编号 |
| shelf_model | int | 货架模型 |
| load_type | int | 负载状态 |
| order_path | varchar(5000) | 订单路径 |
| point_path | varchar(5000) | 点位路径 |
| robot_id | varchar(20) | 设备序列号 |
| robot_num | varchar(10) | 设备编号 |
| robot_type | varchar(200) | 设备类型 |
| create_time | datetime | 创建时间 |
| start_time | datetime | 开始时间 |
| end_time | datetime | 结束时间 |
| materiel | varchar(3000) | 物料信息 |
| status | tinyint | 状态码（同 task_group） |
| action_param | varchar(200) | 动作参数 |
| order_file_id | int | 订单文件ID |
| storage_num | varchar(200) | 库位编号 |
| dest_pod_angle | varchar(30) | 目标货架角度 |
| out_order_id | varchar(30) | 外部订单ID |
| stack_storage_num | tinyint | 堆叠库位编号 |
| parent_tg_id | int | 父任务组ID |
| allow_device_num | varchar(1000) | 允许的设备编号列表 |
| carrier_type | int | 载体类型 0:无 1:货架 2:栈板 3:料箱 |
| carrier_code | varchar(200) | 载体编号 |
| is_display | tinyint(1) | 是否显示，默认0 |
| release_robot | tinyint(1) | 是否释放AGV，默认0 |
| pre_alloc | tinyint(1) | 是否预分配，默认0 |
| pre_param | varchar(255) | 预分配参数 |
| start_at | int | 起始点，默认0 |
| start_at_point | varchar(255) | 起始点位 |

### 4. task_group_detail（子任务模板）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键，自增 |
| tg_id | bigint | 关联 task_group.id |
| area_id | int | 区域ID |
| task_type | tinyint | 子任务类型 |
| task_seq | tinyint | 子任务顺序号 |
| start_point | varchar(20) | 起始点 |
| end_point | varchar(512) | 目标点 |
| action | varchar(500) | 动作 |
| angel | int | 目标角度 |
| x / y | int | 坐标 |
| robot_id | varchar(20) | 设备序列号 |
| robot_num | varchar(10) | 设备编号 |
| status | tinyint | 0:未缓存 1:已缓存未发送 2:正在取消 3:已取消 4:正在发送 5:发送失败 6:执行中 7:执行失败 8:任务完成 |
| shelf_num | varchar(32) | 货架ID |
| shelf_model | varchar(32) | 负载模型 |
| need_trigger | tinyint | 0:不需要 1:需要 |
| notify_third | tinyint | 0:不需要 1:需要 |
| load_type | int | 子任务负载状态 |

### 3. fy_cross_task（跨环境任务/大模板）
这是跨环境核心任务总表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键，自增 |
| from_system | varchar(50) | 来源系统 |
| out_order_id | varchar(100) | 外部订单ID |
| area_id | int | 区域ID |
| model_process_name | varchar(100) | 订单任务名称 |
| model_process_id | int | 拆分模式ID |
| status | tinyint | 1:未发送 2:正在取消 3:已取消 4:正在发送 5:发送失败 6:执行中 7:执行失败 8:任务完成 9:已下发 |
| create_time | int | 创建时间 |
| start_time | int | 开始时间 |
| end_time | int | 结束时间 |
| order_type | int | 0:普通 1:覆盖 |

### 4. fy_cross_task_detail（跨环境子任务）
这是跨环境任务的子表，记录每条大任务的各个子任务以及对应的下发的服务器

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键，自增 |
| ics_task_order_id | int | 任务ID |
| model_process_id | int | 拆分模式ID |
| model_process_detail_id | int | 拆分模式详情ID |
| template_code | varchar(60) | 任务模板编号 |
| task_path | varchar(512) | 任务路径 |
| device_code | varchar(64) | 设备序列号 |
| device_num | varchar(64) | 设备编号 |
| shelf_number | varchar(32) | 货架编号 |
| status | tinyint | 1:未发送 2:正在取消 3:已取消 4:正在发送 5:发送失败 6:执行中 7:执行失败 8:任务完成 9:已下发 |
| priority | int | 优先级 2:指定 4:高 6:中 8:低 |
| area_id | int | 区域ID |
| carrier_type | int | 载体类型 |
| carrier_code | varchar(12) | 载体编号 |
| shelf_model | int | 负载型号 |
| load_type | int | 负载状态 |
| error_desc | varchar(200) | 失败原因 |
| create_time | datetime | 创建时间 |
| start_time | datetime | 开始时间 |
| end_time | datetime | 结束时间 |
| order_type | int | 0:普通 1:覆盖 2:关联 |
| relateId | varchar(128) | 关联任务单号 |

### 5. fy_cross_model_process（跨环境模板）
这是跨环境模板表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| model_process_code | varchar | 模板代码 |
| model_process_name | varchar | 模板名称 |

### 6. fy_cross_model_process_detail（跨环境模板子任务）
这是跨环境模板的子模板，以及其子任务对应的下发的服务器

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| model_process_id | int | 关联模板ID |
| task_seq | int | 顺序号 |
| need_third_trigger | int | 0:不需要 1:需要第三方触发 |

### 7. agv_robot（AGV设备表）

| 字段 | 类型 | 说明 |
|------|------|------|
| DEVICE_CODE | varchar | 设备序列号 |
| DEVICE_IP | varchar | 设备IP |
| DEVICETYPE | varchar | 设备类型 |
| DEVICE_PORT | int | 端口 |

### 8. agv_robot_ext（AGV设备扩展表）

| 字段 | 类型 | 说明 |
|------|------|------|
| DEVICE_CODE | varchar | 设备序列号 |
| DEVICE_AREA | int | 设备所在区域 |
| DEVICE_NUMBER | varchar | 设备编号 |
| DEVICE_STATUS | varchar | 设备状态 |

### 9. join_qr_node_info（跨环境节点信息）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| area_id | int | 区域ID |
| type | int | 类型 |
| qr_content | varchar | 二维码内容 |
| environment_ip | varchar | 环境IP |
| enable | tinyint | 启用状态 |
| join_area | int | 对接区域 |

### 10. load_config（货架/负载型号配置表）

| 字段 | 类型 | 说明 |
|------|------|------|
| model | int | 主键，货架型号ID |
| name | varchar(50) | 货架型号名称（如"正方形货架"、"栈板"） |
| type | varchar(50) | 类型 |
| length/width/height | bigint | 尺寸 |

### 11. shelf_config（货架配置表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键，自增 |
| qr_content | varchar(50) | 二维码内容 |
| shelf_type | int | 货架类型 |
| area_id | tinyint | 区域ID |
| shelf_num | varchar(50) | 货架编号（如 AG03-020） |
| shelf_angle | tinyint | 货架角度 |
| shelf_name | varchar(50) | 货架名称 |

### 12. task_status_config（任务状态配置表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int unsigned | 主键 |
| task_type | varchar(255) | 任务类型 |
| task_status | int | 状态码 |
| task_status_name | varchar(255) | 状态名称（如"已完成"、"运行中"） |
| is_end_status | tinyint(1) | 是否终态 |
| is_start_status | tinyint(1) | 是否起始态 |

**状态码对照**：
| 状态码 | 名称 |
|--------|------|
| 0 | 未发送 |
| 1 | 未开始 |
| 2 | 正在取消 |
| 3 | 已取消 |
| 4 | 发送中 |
| 5 | 发送失败 |
| 6 | 运行中 |
| 7 | 失败 |
| 8 | 已完成 |
| 9 | 已下发 |

## 表关联关系

```
┌─────────────────────────────────────────────────────────────────────┐
│                    跨环境系统任务流程                          │
│                                                                     │
│  fy_cross_task (跨环境任务)（10.68.2.32）                           │
│  ├── orderId (PK)                                                   │
│  ├── create_task_id → task_order.out_order_id (下发后关联)           │
│  └── device_code / device_num / shelf_num                          │
│       │                                                             │
│       │ fy_cross_task_detail.order_id → fy_cross_task.orderId       │
│       ▼                                                             │
│  fy_cross_task_detail (跨环境子任务) （10.68.2.32）                              │
│  ├── order_id → fy_cross_task.orderId                               │
│  ├── sub_order_id (下发后的本地子任务ID)                              │
│  └── device_code / device_num / shelf_number / shelf_model          │
│       │                                                             │
│       │ task_group.out_order_id → fy_cross_task_detail.sub_order_id        │ 
│       ▼                                                             │
│  task_group (任务组表) （其他服务器->service_url）                             │
│  ├── id (PK)                                                        │
│  ├── order_id → task_order.id                                       │
│  ├── out_order_id / third_order_id                                  │
│  └── robot_id / robot_num / shelf_num / shelf_model                 │
│       │                                                             │
│       │ task_order_detail.order_id → task_order.id                  │
│       │ task_order_detail.parent_tg_id → task_group.id (可选)        │
│       ▼                                                             │
│  task_order_detail (子任务详情) （与任务组表一个服务器）                            │
│  ├── id (PK)                                                        │
│  ├── order_id → task_order.id                                       │
│  ├── parent_tg_id → task_group.id                                   │
│  └── robot_id / robot_num / shelf_num / shelf_model                 │
└─────────────────────────────────────────────────────────────────────┘

跨环境 → 远端服务器 下发链路:
  fy_cross_task_detail.sub_order_id ──→ task_group.out_order_id
  task_group.order_id ──→ task_order.id
  task_order_detail.order_id ──→ task_order.id
  task_order_detail.parent_tg_id ──→ task_group.id (可选)

注意：task_group / task_order / task_order_detail 位于远端服务器，
     通过 fy_cross_task_detail.service_url 访问，不在本地生产库(10.68.2.32)中。
     子任务的开始/结束时间从 task_order_detail.start_time / end_time 获取。
```

## enrich 函数说明

### enrich_device_info(device_code)
连接生产库，查询 `agv_robot_ext` + `agv_robot`，返回 `{area_id, device_ip, device_type}`

### enrich_shelf_info(shelf_model, shelf_num)
连接生产库，查询 `load_config` + `shelf_config`。
- 有 shelf_model → 直接查 load_config.name
- 无 shelf_model 有 shelf_num → shelf_config.shelf_type → load_config.model → name（链式查询）
返回 `{shelf_model_name, shelf_model, shelf_num}`

### enrich_task_dict(task_dict, device_code=None)
统一入口，自动补充：
- 设备信息：area_id, device_ip, device_type（agv_robot_ext + agv_robot）
- 货架信息：shelf_num（fy_cross_task_detail）→ shelf_model, shelf_model_name（shelf_config → load_config）
- 任务状态名称：task_status_name（task_status_config）

## 常用 SQL 查询

### 设备号查询任务单号
```sql
-- 按设备号查 fy_cross_task_detail（跨环境子任务）
SELECT * FROM fy_cross_task_detail 
WHERE device_num = 'DJC2' AND status IN (6,7,5,9,4,3,2,1,8)
ORDER BY FIELD(status, 6,7,5,9,4,3,2,1,8)
LIMIT 1;

-- 按 orderId 查主任务
SELECT * FROM fy_cross_task WHERE orderId = 'xxx' LIMIT 1;

-- 按主任务ID查子任务
SELECT * FROM fy_cross_task_detail WHERE order_id = 'xxx' ORDER BY task_seq;
```

### 任务单号查询本地数据库
```sql
-- 查 task_order（订单）
SELECT * FROM task_order WHERE out_order_id = 'xxx' OR third_order_id = 'xxx';

-- 查 task_group（任务组，通过 order_id 关联 task_order）
SELECT * FROM task_group WHERE order_id = 123;
SELECT * FROM task_group WHERE third_order_id = 'xxx' OR out_order_id = 'xxx';

-- 查 task_order_detail（子任务详情，通过 order_id 关联 task_order）
SELECT * FROM task_order_detail WHERE order_id = 123 ORDER BY id;
-- 通过 parent_tg_id 关联 task_group
SELECT * FROM task_order_detail WHERE parent_tg_id = 123;

-- 查 fy_cross_task（跨环境任务）
SELECT * FROM fy_cross_task WHERE orderId = 'xxx';

-- 查 fy_cross_task_detail（跨环境子任务）
SELECT * FROM fy_cross_task_detail WHERE order_id = 'xxx' ORDER BY task_seq;
```

### 跨环境任务 → 本地任务 关联查询
```sql
-- 通过 create_task_id 查下发后的本地订单
SELECT fct.*, to2.*
FROM fy_cross_task fct
LEFT JOIN task_order to2 ON fct.create_task_id = to2.out_order_id
WHERE fct.orderId = 'xxx';

-- 查跨环境任务对应的本地 task_group（通过 order_id 链路）
SELECT fct.orderId, tg.*
FROM fy_cross_task fct
LEFT JOIN task_order to2 ON fct.create_task_id = to2.out_order_id
LEFT JOIN task_group tg ON tg.order_id = to2.id
WHERE fct.orderId = 'xxx';

-- 查跨环境子任务对应的本地 task_order_detail
SELECT fctd.*, tod.*
FROM fy_cross_task_detail fctd
LEFT JOIN task_order_detail tod ON fctd.sub_order_id = tod.id
WHERE fctd.order_id = 'xxx';
```

### task_order / task_group / task_order_detail 联合查询
```sql
-- 完整链路：订单 → 任务组 → 子任务
SELECT
  to2.out_order_id,
  to2.status as order_status,
  tg.id as tg_id,
  tg.status as tg_status,
  tg.robot_num,
  tod.id as detail_id,
  tod.status as detail_status,
  tod.robot_num as detail_robot
FROM task_order to2
LEFT JOIN task_group tg ON tg.order_id = to2.id
LEFT JOIN task_order_detail tod ON tod.order_id = to2.id
WHERE to2.out_order_id = 'xxx';

-- 按设备号查本地任务
SELECT DISTINCT to2.out_order_id, to2.status, to2.create_time
FROM task_order_detail tod
JOIN task_order to2 ON tod.order_id = to2.id
WHERE tod.robot_id = 'EM55907AAK00010' OR tod.robot_num = 'B100'
ORDER BY to2.create_time DESC
LIMIT 10;
```

### 设备信息查询
```sql
-- 查设备IP
SELECT DEVICE_IP FROM agv_robot WHERE DEVICE_CODE = 'EM55907AAK00010';

-- 查设备区域和状态
SELECT DEVICE_AREA, DEVICE_NUMBER, DEVICE_STATUS 
FROM agv_robot_ext WHERE DEVICE_CODE = 'EM55907AAK00010';
```

### 模板查询
```sql
-- 查模板
SELECT * FROM fy_cross_model_process WHERE model_process_code = 'xxx';

-- 查模板子任务
SELECT * FROM fy_cross_model_process_detail WHERE model_process_id = 123;
```

### 任务重发相关
```sql
-- 查大模板状态
SELECT task_status FROM fy_cross_task WHERE orderId = 'xxx';

-- 查子模板状态
SELECT * FROM fy_cross_task_detail WHERE order_id = 'xxx' AND task_seq = 1;

-- 更新大模板状态为重发中
UPDATE fy_cross_task SET task_status = 5 WHERE orderId = 'xxx';

-- 更新子模板状态为重发中
UPDATE fy_cross_task_detail SET sub_order_id = 'xxx', status = 5, error_desc = '重发中' WHERE ...;

-- 异常完成
UPDATE fy_cross_task_detail SET status = 3, error_desc = '异常完成' WHERE ...;
```

### 统计查询
```sql
-- 当天大模板状态分布
SELECT task_status, COUNT(*) as count 
FROM fy_cross_task 
WHERE DATE(create_time) = CURDATE() 
GROUP BY task_status;

-- 同模板其他执行中/异常任务
SELECT * FROM fy_cross_task 
WHERE model_process_code = 'xxx' 
  AND task_status IN (4,5,6,7,9) 
  AND orderId != 'xxx';
```

## 任务状态码

| 状态码 | 含义 |
|--------|------|
| 1 | 未发送 |
| 2 | 正在取消 |
| 3 | 已取消 |
| 4 | 正在发送 |
| 5 | 发送失败/重发中 |
| 6 | 执行中 |
| 7 | 执行失败 |
| 8 | 任务完成 |
| 9 | 已下发 |
| 10 | (扩展状态) |

## 代码中的 SQL 文件位置

| 文件 | 用途 |
|------|------|
| `modules/query/task_query_extended.py` | 任务查询、重发、设备状态查询 |
| `modules/query/task_query.py` | 基础任务查询 |
| `modules/query/device_validation.py` | 设备验证查询 |
| `modules/query/device_validation_extended.py` | 设备验证扩展（含 INSERT） |
| `modules/query/join_qr_node_query.py` | 跨环境节点 CRUD |
| `modules/query/agv_status.py` | AGV 状态查询 |
| `modules/query/shelf_query.py` | 货架查询 |
| `modules/query/cross_model_query.py` | 跨环境模板查询 |
| `dao/template_dao.py` | 模板 DAO 层 |
| `dao/detail_dao.py` | 详情 DAO 层 |

## 注意事项

1. **生产环境只读**：`10.68.2.32:3306` 仅允许 SELECT，不允许 INSERT/UPDATE/DELETE
2. **测试环境可写**：`47.98.244.173:53308` 可自由操作
3. **字符集**：统一使用 `utf8mb4`
4. **时间字段差异**：
   - `task_group` 用 int Unix 时间戳（create_time/start_time/end_time）
   - `task_order` / `task_order_detail` 用 datetime 类型
   - `fy_cross_task` / `fy_cross_task_detail` 用 datetime 类型
5. **字段命名**：本地表用下划线（`order_id`），远程 API 返回驼峰（`orderId`）
6. **连接池**：使用 DBUtils 连接池（`modules/database/connection.py`）
7. **表关系与服务器分布**：
   - **本地生产库 (10.68.2.32)**：`fy_cross_task`、`fy_cross_task_detail`、`agv_robot`、`agv_robot_ext`、`load_config`、`shelf_config`、`task_status_config`
   - **远端服务器 (通过 service_url 访问)**：`task_group`、`task_order`、`task_order_detail`
   - 下发链路：`fy_cross_task_detail.sub_order_id` → `task_group.out_order_id` → `task_group.order_id` → `task_order.id`
   - `task_order_detail.order_id` → `task_order.id`，`task_order_detail.parent_tg_id` → `task_group.id` (可选)
   - 子任务开始/结束时间从 `task_order_detail.start_time` / `end_time` 获取
8. **生产库没有 `task_group_detail` 表**，子任务详情在远端 `task_order_detail` 中

## ds 说
- 2026-05-09: 整理核心表结构和常用 SQL，覆盖 task_group、task_order、task_order_detail、fy_cross_task、fy_cross_task_detail、agv_robot、agv_robot_ext、join_qr_node_info、load_config、shelf_config、task_status_config
- 任务状态码 1-9 标准定义，10 为扩展状态
- 重发逻辑涉及 UPDATE fy_cross_task 和 fy_cross_task_detail 两张表
- 设备区域修正通过 agv_robot_ext.DEVICE_AREA 查询
- 2026-05-09: 新增 task_order、task_order_detail 表结构及关联关系图。关键纠正：task_group/task_order/task_order_detail 位于远端服务器(通过 service_url 访问)，不在本地生产库。下发链路为 fy_cross_task_detail.sub_order_id → task_group.out_order_id。子任务时间从 task_order_detail 获取
