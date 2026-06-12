# 配置管理模块

> 最后更新: 2026-06-12 | 路由: `routes/config_routes.py` + `routes/system_routes.py`

---

## 一、配置体系

| 配置 | 位置 | 格式 | 管理方式 |
|------|------|------|---------|
| 系统配置 | `config/env.toml` | TOML | 系统管理 → 系统配置 |
| 调度配置 | `config/dispatch_config.json` | JSON | 任务下发 → 下发配置 |
| 定制表配置 | `config/custom_tables.toml` | TOML | 首页 → 定制表编辑 → 配置 Tab |
| Postlook 服务器 | `config/postlook_servers.json` | JSON | 日志查看 → 配置管理 |

## 二、调度配置结构 (dispatch_config.json)

```json
{
  "_features": {
    "enable_roller_task": true
  },
  "_version": 122,
  "areas": {
    "A1-1 PCBA": {
      "tasks": {
        "任务名": {
          "base_url": "http://10.68.2.32:7000/...",
          "code": "template_code",
          "requires_shelf": true,
          "capacity": 0,
          "roller_task": false,
          "roller_point": "",
          "roller_point_label": ""
        }
      }
    }
  }
}
```

### 2.1 自动补全机制

- `save_config()` 自动补全 `_features.enable_roller_task` 字段
- `_default_config()` 默认包含 `_features` 结构
- 前端 `ensureConfigCompatibility()` 在加载时补全

## 三、版本管理

| 配置 | 版本字段 | 说明 |
|------|---------|------|
| dispatch_config.json | `_version` | 整数递增，每次保存 +1 |
| env.toml | 无独立版本 | 依赖备份恢复 |

## 四、备份机制

调度配置支持完整的历史版本管理：
- 手动/自动创建备份
- 列表查看
- 一键恢复
- 删除旧备份
