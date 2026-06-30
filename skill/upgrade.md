---
name: upgrade-skill
description: cross_env_manager 升级管理模块操作指导
---

# 升级管理 Skill

## 模块文件

| 文件 | 说明 |
|------|------|
| `services/upgrade_service.py` | 核心逻辑：备份、解压覆盖、回滚、记录管理、自动清理 |
| `routes/system_upgrade_routes.py` | 页面路由 + API 路由 |
| `templates/system/upgrade.html` | Web 管理页面 |

## 侧边栏入口

系统管理 → 升级管理（`/system/upgrade`），依赖 `base.html` 的 `data-module` 路径匹配：

```javascript
// 必须在 system 模块匹配中包含 /system/upgrade
path.indexOf('/system/upgrade') === 0
```

## 升级包要求

1. **ZIP 格式**，必须在根目录包含 `app.py`
2. 推荐在根目录放入 `version.json` 记录升级说明：

```json
{
  "title": "v2.4.3 安全更新",
  "changes": ["修复: xxx", "新增: xxx"]
}
```

3. 打包时排除（参考 `EXCLUDE_PATTERNS`）：
   - `venv/`、`.git/`、`logs/`、`backup/`、`dev/`
   - `config/env.toml`、`config/dispatch_config.json`、`config/postlook_servers.json`
   - `deploy/`、`Plugin/postlook/deploy/`、`Plugin/postlook/venv/`

## API 调用

```bash
# 升级
curl -X POST http://host:5000/api/system/upgrade \
  -H "Cookie: session=xxx" \
  -F "file=@upgrade.zip" \
  -F "remark=修复了xxx"

# 查记录
curl http://host:5000/api/system/upgrade/records \
  -H "Cookie: session=xxx"

# 回滚
curl -X POST http://host:5000/api/system/upgrade/rollback/upgrade_20260612_112124 \
  -H "Cookie: session=xxx"
```

## 升级流程

```
上传 ZIP → 校验(admin/格式/app.py)
         → 备份当前项目到 backup/upgrade_timestamp/
         → 解压到临时目录
         → 读取 version.json（若有）
         → 逐文件覆盖（跳排除项）
         → 记录升级日志
         → 返回成功 → 3 秒后 supervisorctl restart
```

## 回滚流程

```
POST /api/system/upgrade/rollback/backup_name
         → 先备份当前代码
         → 从 backup/backup_name/files/ 恢复
         → 记录回滚日志
         → 3 秒后重启
```

## 备份管理

- **路径**: `backup/upgrade_yyyymmdd_hhmmss/`
- **保留**: 最近 10 条（`MAX_BACKUPS=10`）
- **自动清理**: 超出时删除最旧的备份目录和日志
- **prerollback**: 回滚前自动生成的"后悔药"备份
