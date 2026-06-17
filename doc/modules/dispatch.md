# 调车模块 (Dispatch)

> 最后更新: 2026-06-17 | 路由: `routes/dispatch_routes.py` | 版本: `DISPATCH_VERSION` v2.3.1 | CEM: v2.5.5

---

## 一、功能

- **调车看板** (`/dispatch`): 实时展示各 AGV 区域的空车平衡状态，设备池 (currentCount)，操作日志流
- **调车配置** (`/dispatch/config`): 编辑区域配置、空车上下限、模板注册
- **自动驾驶测试** (`/dispatch/test`): 手动下发测试任务
- **自动调度**: 定时检查各区域空车数量，按配置自动下发回空任务
- **自愈机制**: 检测离线设备、超时任务，自动清理并恢复设备池
- **设备历史追踪**: `device_history.json` 记录区域 48h 内访问过的设备
- **操作日志**: 全局日志 + 日归档，保留 30 天

## 二、核心概念

### 2.1 区域平衡公式

```
a = 所有来区域模板中 status=6/9 的任务数之和
b = 所有离开模板中 status=6/9 的任务数之和
currentCount = currentCount.json 中的设备数
expectedCount = currentCount + a - b

if expectedCount < xmin → 需调入 AGV
if expectedCount > xmax → 需调出 AGV
else → 平衡
```

### 2.2 设备生命周期

```
ICS 上报 status=6(运行中) → CEM 模板 JSON 记录
  ↓
status=8/10(完成) → 模板清理 + currentCount+1(来) / currentCount-1(离)
  ↓
_device_history → confirmed=True (status=8/10 完成的车辆标记已移动)
  ↓
_update_current_count_from_api → 仅补入 confirmed=True 的历史设备
  ↓
自愈轮询 → 清理 Offline/Downlined/_not_found 设备
```

### 2.3 Order ID 匹配 (ICS Suffix)

ICS 对 CEM 下发的 order_id 会拼接子任务后缀 `_X_YYYY`：
```
CEM 下发:   CEM_auto_id5_2026-06-17_11:39:03.788__8724
ICS 上报:   CEM_auto_id5_2026-06-17_11:39:03.788__8724_1_4123  (后缀)
```

`_order_id_matches()` 双向前缀匹配：精确匹配 + `startsWith(base + '_')` 双向检测，防止同前缀不同任务号误匹配。

### 2.4 空车任务限制

| 层级 | 配置方式 | 说明 |
|------|---------|------|
| 全局 | dispatch_config `_features.global_empty_task_limit` | 所有区域统一上限（默认 4） |
| 区域 | area config `empty_task_limit` | -1=全局、0=不限制、>0=自定义 |

## 三、自愈机制

### 3.1 自动轮询 (每 check_interval 秒)

1. 遍历 `currentCount.json` 中所有设备，逐个查询 ICS 状态
2. `_not_found` → 不在该 areaId → 清理
3. `Offline/Downlined` + 无活跃任务 → 清理
4. `Offline/Downlined` + 活跃任务超 1h → 清理
5. 在线设备 → 更新 state/battery

### 3.2 全量同步 (每 fetch_all_interval_hours 小时)

1. 同 API 组共享一次 ICS 全量查询
2. 各区域独立更新 `device_history.json`（匹配模式，不新增）
3. `_assign_devices_to_regions` 按最近上线区域分配设备到 currentCount

### 3.3 任务超时清理

模板 JSON 中 `create_time` 超过 `task_timeout_hours` 小时的 status=6/9/10 任务自动清理，同时从 currentCount 移除对应设备。

## 四、解死锁机制

当来任务=0、回空车已下发导致 `can_dispatch=False` 时：
1. 自动调用 ICS 取消接口取消阻塞的反方向空车
2. 清理本地模板 JSON 记录
3. 重新检查阻塞是否解除
4. 动态冷却期：连续解死锁时延长冷却时间（基础 120s → 每次 +60s → 上限 600s）

## 五、本地 JSON 文件

| 文件 | 说明 |
|------|------|
| `data/dispatch/{region}/currentCount.json` | 区域当前设备池（仅 confirmed=True 设备） |
| `data/dispatch/{region}/{template}.json` | 模板任务队列（status=6/9/10） |
| `data/dispatch/{region}/device_history.json` | 设备历史（48h 内来访设备 + confirmed 标记） |
| `data/dispatch/{region}/dispatch_log.json` | 下发记录 |
| `data/dispatch/daily_stats.json` | 每日统计（来/回/下发/取消次数） |
| `data/dispatch/global_log.json` | 全局操作日志（热数据） |
| `data/dispatch/logs/global_log_{date}.json` | 日志日归档（保留 30 天） |
| `data/dispatch/cache_index.json` | 区域配置缓存 |

## 六、并发安全

- `_load_json` / `_save_json` 共用全局 `_write_lock` 读写锁，防并发 JSON 文件损坏
- `_save_json` 先备份 `.bak`，再原子 `os.replace(tmp, target)`

## 七、诊断日志

### 操作日志 icon 标记

| icon | 含义 |
|------|------|
| 🔴 | 设备离开网格 / 自愈清理 |
| 📤 | 下发完毕 |
| ⚠️ | 未匹配上报 |
| `[oid诊断]` | order_id 跨区域匹配失败摘要 |

### order_id 诊断格式

```
[oid诊断] CEM_auto...8724 (DJ13/AAK00014) → 0/10模板 前缀命中: region/templ oid=...
```

- `→ 0/N模板`：检查了 N 个模板，精确匹配 0 条
- `前缀命中`: 找到了前缀部分一致的 order_id（ICS suffix 差异）
- `活跃oid`: 当前模板中的 active order_id 列表
