# postlook 离线部署

## 文件说明

| 文件 | 说明 |
|------|------|
| `deploy.sh` | 一键部署脚本 |
| `deploy.conf` | 部署配置文件（修改参数改这里） |
| `vendor_packages/` | 离线依赖包（.whl 文件） |

## 部署步骤

### 1. 准备离线依赖包（联网环境执行一次）

```bash
cd Plugin/postlook
pip download fastapi uvicorn pydantic starlette anyio -d deploy/vendor_packages/
```

### 2. 修改配置（按需）

编辑 `deploy/deploy.conf`，调整端口、用户、日志路径等：

```bash
vim deploy/deploy.conf
```

### 3. 执行部署

```bash
cd Plugin/postlook
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

## 部署后管理

```bash
# 查看服务状态
supervisorctl status postlook

# 重启服务
supervisorctl restart postlook

# 停止服务
supervisorctl stop postlook

# 查看日志
tail -f /main/log/app/postlook.log
```

## 访问地址

- 前端页面: `http://localhost:5011`
- API 文档: `http://localhost:5011/docs`
- 健康检查: `http://localhost:5011/api/health`
