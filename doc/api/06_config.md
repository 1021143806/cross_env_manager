# 6. 配置管理 API

## 6.1 调度配置 (dispatch_config.json)

### 6.1.1 获取配置
```
GET /addtask/config
```
返回 `config.js` 文件内容（text/plain）。

### 6.1.2 保存配置
```
POST /addtask/config
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| content | string | 是 | 配置文件内容 |
| message | string | 否 | 提交消息 |

自动补全 `_features.enable_roller_task` 字段。

### 6.1.3 备份列表
```
GET /addtask/config/backups
```

### 6.1.4 创建备份
```
POST /addtask/config/backup
```

### 6.1.5 获取备份内容
```
GET /addtask/config/backup/<backup_name>
```

### 6.1.6 恢复备份
```
POST /addtask/config/backup/<backup_name>/restore
```

### 6.1.7 删除备份
```
DELETE /addtask/config/backup/<backup_name>
```

## 6.2 系统配置 (env.toml)

### 6.2.1 获取配置
```
GET /api/system/config
```

### 6.2.2 保存配置
```
POST /api/system/config
```

### 6.2.3 获取原始 TOML
```
GET /api/system/config/raw
```

### 6.2.4 保存原始 TOML
```
POST /api/system/config/raw
```

### 6.2.5 备份管理
```
GET  /api/system/config/backups
POST /api/system/config/backup
POST /api/system/config/backup/<name>/restore
DELETE /api/system/config/backup/<name>
```

## 6.3 调车配置

### 6.3.1 获取调车配置
```
GET /api/dispatch/config
```

### 6.3.2 保存调车配置
```
POST /api/dispatch/config
```

### 6.3.3 获取 JS 版配置
```
GET /api/dispatch/config/js
```
