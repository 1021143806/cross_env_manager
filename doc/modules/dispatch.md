# 调车模块 (Dispatch)

> 最后更新: 2026-05-14 | 路由: `routes/dispatch_routes.py` | 版本: `DISPATCH_VERSION`

---

## 一、功能

- **调车看板** (`/dispatch`): 实时展示各 AGV 区域的空车平衡状态
- **调车配置** (`/dispatch/config`): 编辑区域配置、空车上下限
- **自动驾驶测试** (`/dispatch/test`): 手动下发测试任务
- **自动调度**: 定时检查各区域空车数量，按配置自动下发回空任务
- **自愈机制**: 检测超时未完成的任务，自动取消并重发

## 二、核心概念

### 区域平衡

每个区域配置了 A→B 和 B→A 两个方向的空车模板，系统根据当前两边空车数量差异自动调度。

### 空车任务限制

| 层级 | 配置方式 | 说明 |
|------|---------|------|
| 全局 | dispatch_config `_features.global_empty_task_limit` | 所有区域统一上限（默认 4） |
| 区域 | area config `empty_task_limit` | -1=全局、0=不限制、>0=自定义 |

## 三、自愈机制

| 参数 | 位置 | 说明 |
|------|------|------|
| timeout | `_check_dispatch_timeout` | 任务下发后超时时间，超时未完成则取消 |
| 间隔 | `_start_self_heal_thread` | 自愈检查线程间隔时间 |
| 取消策略 | `_cancel_empty_task` | 调用 ICS 取消接口 + 清理本地 JSON |

## 四、解死锁机制

当来任务=0、回空车已下发导致 `can_dispatch=False` 时：
1. 自动调用 `_get_task_server_info` + `_cancel_empty_task` 取消阻塞的反方向空车
2. 清理本地 JSON 记录
3. 重新检查阻塞是否解除
4. 若已解除则允许下发

## 五、本地 JSON 文件

| 文件 | 说明 |
|------|------|
| `data/dispatch_[area]_[direction].json` | 已下发的空车任务记录 |
| `data/stats.json` | 每日调度统计 |
