# 升级管理模块

> 最后更新: 2026-06-12 | 路由: `routes/system_upgrade_routes.py` | Service: `services/upgrade_service.py`

---

## 一、功能

- **升级管理页面** (`/system/upgrade`): 查看版本、上传 ZIP 升级、浏览升级记录、一键回滚
- **升级 API** (`POST /api/system/upgrade`): 支持 curl/Postman 调用
- **记录查询** (`GET /api/system/upgrade/records`): 查看历史升级记录
- **回滚 API** (`POST /api/system/upgrade/rollback/<name>`): 恢复到指定版本

## 二、升级流程

```
上传 ZIP → 校验(admin/格式/app.py)
         → 备份当前项目到 backup/upgrade_yyyymmdd_hhmmss/
         → 解压到临时目录
         → 读取 version.json（若有，读取后删除）
         → 逐文件覆盖（跳过排除项）
         → 记录升级日志
         → 返回成功 → 3 秒后 supervisorctl restart
```

## 三、排除覆盖的文件

升级时以下文件/目录不会被覆盖：

| 类型 | 条目 |
|------|------|
| 配置 | `config/env.toml`、`dispatch_config.json`、`postlook_servers.json`、`config/old/` |
| 环境 | `venv/`、`deploy_iraypleos/` |
| 运行时 | `logs/`、`backup/`、`dev/`、`__pycache__/` |
| 项目元 | `.git/`、`.gitignore`、`skill.md`、`README.md` |
| Plugin | `Plugin/postlook/deploy/`、`Plugin/postlook/venv/` |

## 四、版本号

| 位置 | 格式 | 说明 |
|------|------|------|
| `app.py APP_VERSION` | `x.x.x` | 全局版本，页脚显示 `CEM v{APP_VERSION}` |
| 升级记录 `version.json` | `{"title":"...", "changes":[...]}` | ZIP 包内可选 |
| 备份 meta.json | `{"old_version":"...","new_version":"..."}` | 自动生成 |

## 五、备份管理

| 参数 | 值 | 说明 |
|------|-----|------|
| MAX_BACKUPS | 10 | 保留最近 10 条备份 |
| 备份路径 | `backup/upgrade_yyyymmdd_hhmmss/` | 全量代码备份 |
| prerollback | `backup/prerollback_yyyymmdd_hhmmss/` | 回滚前的"后悔药" |
| 自动清理 | 升级/回滚成功后触发 | 删除最旧的备份 |
