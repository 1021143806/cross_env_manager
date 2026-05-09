---
name: my-skill-log-viewer
description: cross_env_manager 调车模块远程部署环境日志查看指导
---

# 远程服务器信息

## 生产环境
- **地址**: http://10.68.2.40:5000
- **调车页面**: http://10.68.2.40:5000/dispatch
- **用户名**: admin
- **密码**: DHRTA@2018
- **管理员账号**: admin / admin123456
  
## 本地测试环境（后门账号）
- **地址**: http://172.21.128.46:5000
- **用户名**: admin
- **密码**: admin123456
- **管理员账号**: admin / admin123456

## 日志查看方式

### 1. 页面操作日志
- 调车页面底部"操作日志"区域可查看实时日志
- 支持搜索功能（搜索时会加载大日志，停用自动刷新）
- 支持导出功能

### 2. API 接口
- `GET /api/dispatch/global_log` - 获取热数据日志（最近200条）
- `GET /api/dispatch/global_log?since=timestamp` - 增量拉取日志
- `GET /api/dispatch/global_log/export` - 导出大日志（2天内归档日志）
- `GET /api/dispatch/device_info?deviceNum=C185` - 查询指定设备详情和历史日志
- `GET /api/dispatch/logs?lines=200&filter=SelfHeal` - 查看 supervisor 控制台日志（需管理员权限）

### 3. 日志存储
- 热数据: `data/dispatch/global_log.json`（最多200条）
- 归档日志: `data/dispatch/global_log_YYYY-MM-DD.json`（每天最多500条，保留2天）
- supervisor 日志: `logs/cross_env_manager.log`（print 输出，5MB 限制）

## 通过 curl 查询日志

### 登录获取 session
```bash
curl -s -c /tmp/cookies.txt -X POST 'http://10.68.2.40:5000/api/login' \
  -H 'Content-Type: application/json' \
  -d '{"username":"375563","password":"DHRTA@2018"}'
```

### 查询设备日志
```bash
curl -s -b /tmp/cookies.txt \
  'http://10.68.2.40:5000/api/dispatch/device_info?deviceNum=C185' | python3 -m json.tool
```

### 查询全局日志
```bash
curl -s -b /tmp/cookies.txt \
  'http://10.68.2.40:5000/api/dispatch/global_log' | python3 -m json.tool
```

### 查看 supervisor 控制台日志（print 输出）
```bash
# 查看最近 200 行
curl -s -b /tmp/cookies.txt 'http://10.68.2.40:5000/api/dispatch/logs'

# 只看 SelfHeal 相关
curl -s -b /tmp/cookies.txt 'http://10.68.2.40:5000/api/dispatch/logs?filter=SelfHeal'

# 只看最近 50 行
curl -s -b /tmp/cookies.txt 'http://10.68.2.40:5000/api/dispatch/logs?lines=50'
```

## 排查问题流程
1. 先通过页面操作日志查看最近的调度记录
2. 如需查看更早的日志，使用搜索功能或导出大日志
3. 关注 `[SelfHeal]` 前缀的日志排查自愈逻辑问题
4. 关注 `[Dispatch]` 前缀的日志排查下发任务问题
5. 排查特定设备问题时，使用 `/api/dispatch/device_info?deviceNum=XXX` 查询设备历史
6. 排查自愈误清理时，使用 `/api/dispatch/logs?filter=SelfHeal` 查看控制台日志确认 `status in (6,10)` 是否生效

## ds 说
- 远程服务器 10.68.2.40:5000 是生产环境，部署的是 cross_env_manager 调车模块
- 两个账号：普通用户 375563/DHRTA@2018，管理员 admin/admin123456
- 排查 self-heal 误清理问题时，先确认 `_should_clean_device` 的修复是否已部署到远程服务器
- 登录 API 是 `/api/login` POST，需要 JSON Content-Type，登录后 cookie 用于后续请求
- 设备日志查询接口 `/api/dispatch/device_info` 返回设备当前状态 + history 数组（按时间倒序）
- `/api/dispatch/logs` 接口需要管理员权限（admin/admin123456），可查看 supervisor 控制台 print 输出
- `_should_clean_device` 的决策日志通过 `write_global_log('self_heal_detail', ...)` 写入操作日志，可在页面搜索 `self_heal_detail` 查看
- `logs/` 目录已加入 git 跟踪（`.gitkeep`），但 `.log` 文件被 `.gitignore` 排除

