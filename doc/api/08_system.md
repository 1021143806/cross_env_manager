# 8. 系统 API

## 8.1 健康检查
```
GET /actuator/health
```
**响应:**
```
1000
```
返回纯文本 `1000`，用于服务器监控。

## 8.2 系统信息
```
GET /api/system/info
```
**响应示例:**
```json
{
  "success": true,
  "info": {
    "app_version": "2.4.2",
    "python_version": "3.9.20",
    "platform": "Linux"
  }
}
```

## 8.3 数据库切换
```
GET  /api/db/servers    # 列出可用服务器
GET  /api/db/current    # 获取当前服务器
POST /api/db/switch     # 切换服务器
```

## 8.4 升级管理

### 8.4.1 升级管理页面
```
GET /system/upgrade
```
返回 `system/upgrade.html`。需登录，仅 admin 可操作。

### 8.4.2 上传并执行升级
```
POST /api/system/upgrade
Content-Type: multipart/form-data
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | file | 是 | .zip 升级包 |
| remark | string | 否 | 升级说明（如 "修复xxx，新增xxx"） |

**升级流程：**
1. 校验 admin 权限 + .zip 格式
2. 备份当前项目到 `backup/upgrade_yyyymmdd_hhmmss/`
3. 解压 ZIP，读取 `version.json`（若有）
4. 按排除列表覆盖文件（保留 config/env.toml、dispatch_config.json、venv/ 等）
5. 记录升级日志
6. 返回成功响应 → 3 秒后 `supervisorctl restart` 自动重启

**version.json 格式（放在 ZIP 根目录）：**
```json
{
  "title": "v2.4.3 安全更新",
  "changes": [
    "修复: xxx",
    "新增: xxx",
    "优化: xxx"
  ]
}
```

**成功响应：**
```json
{
  "success": true,
  "message": "升级完成（2.4.2 → 2.4.3），系统3秒后自动重启...",
  "backup": "upgrade_20260612_112124",
  "release_title": "v2.4.3 安全更新",
  "release_notes": ["修复: xxx", "新增: xxx"]
}
```

**排除覆盖的文件（保留不动）：**
- `config/env.toml`、`config/dispatch_config.json`、`config/postlook_servers.json`
- `config/old/`、`venv/`、`logs/`、`backup/`、`dev/`
- `.git/`、`.gitignore`、`skill.md`、`README.md`
- `deploy_iraypleos/`、`Plugin/postlook/deploy/`、`Plugin/postlook/venv/`
- `__pycache__/`、`*.pyc`

### 8.4.3 获取升级记录
```
GET /api/system/upgrade/records
```
**响应示例:**
```json
{
  "success": true,
  "records": [
    {
      "backup_name": "upgrade_20260612_112124",
      "timestamp": "20260612_112124",
      "old_version": "2.4.2",
      "new_version": "2.4.2",
      "files_overlay": 193,
      "status": "success",
      "release_title": "v2.4.3 安全更新",
      "release_notes": ["修复: xxx", "新增: xxx"]
    }
  ]
}
```

### 8.4.4 回滚到指定备份
```
POST /api/system/upgrade/rollback/<backup_name>
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| backup_name | string | 是 | 备份目录名（路径参数） |

**回滚流程：**
1. 先备份当前代码（`backup/prerollback_yyyymmdd_hhmmss/`）
2. 从备份目录 `files/` 恢复所有文件
3. 自动清理旧备份
4. 记录回滚日志
5. 3 秒后自动重启

**成功响应:**
```json
{
  "success": true,
  "message": "已从 upgrade_20260612_112124 回滚，共恢复 193 个文件，系统3秒后自动重启..."
}
```

**备份自动清理：** 保留最近 10 条（`MAX_BACKUPS=10`），超出自动删除最旧备份。
