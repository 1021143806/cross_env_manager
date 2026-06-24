# 离线部署模块 — IRAYPLEOS

## 目录结构

```
deploy_iraypleos/
├── deploy_iraypleos.sh          # 主部署脚本（幂等）
├── README.md                    # 本文档
└── vendor_packages3.9/          # 离线包仓库（Python 3.9 兼容）
    ├── requirements_py39_fixed.txt   # 版本锁定的依赖清单
    └── *.whl                         # 25 个离线 wheel 包
```

## 架构设计

### 网络约束

目标服务器 **IRAYPLEOS** 为离线环境，无法连接 PyPI。部署模块采用「**在线打包 — 离线安装**」的双阶段模式：

```
开发机（在线）                         目标服务器（离线）
┌─────────────────┐                 ┌──────────────────┐
│ pip download     │── scp/rsync ──▶│ vendor_packages  │
│ → *.whl          │                 │ deploy_iraypleos │
│ → requirements   │                 │   .sh            │
└─────────────────┘                 │ venv/ (自动创建)  │
                                    │ Supervisord 启动  │
                                    └──────────────────┘
```

### 核心设计原则

| 原则 | 实现 |
|------|------|
| **完全离线** | 所有依赖以 `.whl` 形式存储在 git 仓库中，安装时使用 `--no-index --find-links` |
| **幂等部署** | 脚本可反复执行，先清理旧 venv 再重建，不依赖环境状态 |
| **版本锁定** | `requirements_py39_fixed.txt` 精确锁死版本号，杜绝意外升级 |
| **自动兼容处理** | 自动检测并修复 `mysql.connector` → `PyMySQL` 的引用替换 |
| **Supervisor 集成** | 配置 `/main/server/supervisor/cross_env_manager.conf`，需在 `/etc/supervisord.conf` 的 `[include]` 中**单行**添加该文件路径（多行 `files =` 会被覆盖） |

## 部署流程

| 步骤 | 操作 | 说明 |
|------|------|------|
| 1 | 环境检查 | 验证 Python 版本、用户权限、项目路径 |
| 2 | vendor 检查 | 扫描 11 个关键包是否存在，缺失立即终止 |
| 3 | 创建 venv | `python3 -m venv venv`，清理旧环境 |
| 4 | mysql.connector 修复 | 检测 `app.py` 中未注释的 `mysql.connector`，自动替换为 `pymysql` |
| 5 | 安装依赖 | **优先批量安装** → 失败则逐个安装，跳过不存在的包 |
| 6 | 导入验证 | 验证 `flask`、`pymysql`、`paramiko` 等关键包可导入 |
| 7 | Supervisor 配置 | 配置不存在时自动创建，已存在跳过 |
| 8 | 启动服务 | `supervisorctl restart`，失败则直接 `nohup` 启动 |

### 依赖安装策略

- **路径 1（快速路径）**：`pip install --no-index --find-links=... -r requirements_py39_fixed.txt`
- **路径 2（降级路径）**：逐行解析 `requirements_py39_fixed.txt`，按包名匹配 `.whl` 文件后逐个安装
- 路径 1 失败会自动降级到路径 2

## 依赖清单

### Flask 核心

| 包 | 版本 | 说明 |
|----|------|------|
| Flask | 2.3.3 | Web 框架 |
| Werkzeug | 2.3.7 | WSGI 工具 |
| Jinja2 | 3.1.2 | 模板引擎 |
| MarkupSafe | 2.1.3 | **cp39 编译版** |
| click | 8.1.6 | 命令行工具 |
| itsdangerous | 2.1.2 | 签名工具 |
| PyMySQL | 1.1.0 | MySQL 驱动（替代 mysql.connector） |
| python-dotenv | 1.0.0 | 环境变量加载 |
| Markdown | 3.5.1 | Markdown 渲染 |
| tomli | 2.0.1 | TOML 解析 |

### 扩展依赖

| 包 | 版本 | 说明 |
|----|------|------|
| DBUtils | 3.1.2 | 数据库连接池 |
| Flask-Caching | 2.3.1 | 缓存支持 |
| cachelib | 0.13.0 | 缓存后端 |
| blinker | 1.9.0 | 信号支持 |
| zipp | 3.23.0 | zip 工具 |
| importlib_metadata | 8.7.1 | 包元数据 |
| typing_extensions | 4.15.0 | 类型扩展 |

### 平台切换模块（SSH + YAML）

| 包 | 版本 | 说明 |
|----|------|------|
| paramiko | 5.0.0 | SSH 远程连接 |
| PyYAML | 6.0.3 | YAML 解析（rosservice） |
| cryptography | 43.0.3 | 加密（paramiko 依赖） |
| bcrypt | 5.0.0 | 密码哈希（paramiko 依赖） |
| pynacl | 1.6.2 | 网络加密（paramiko 依赖） |
| cffi | 2.0.0 | C 接口（cryptography 依赖） |
| pycparser | 2.23 | C 解析器（cffi 依赖） |
| invoke | 3.0.3 | 子进程管理（paramiko 依赖） |

## 维护指南

### 新增依赖包

```bash
cd deploy_iraypleos/vendor_packages3.9

# 1. 下载兼容 Python 3.9 的 wheel
pip download --only-binary=:all: \
  --platform manylinux2014_x86_64 \
  --python-version 3.9 \
  <package_name>

# 2. 添加到 requirements_py39_fixed.txt（锁定版本）
echo "<package_name>==<version>" >> requirements_py39_fixed.txt

# 3. 提交到 git
git add deploy_iraypleos/vendor_packages3.9/
git commit -m "deploy: add <package_name> to offline vendor"
```

### 更新依赖版本

1. 删除旧的 `.whl` 文件
2. 用 `pip download` 下载新版本
3. 更新 `requirements_py39_fixed.txt` 中的版本号
4. 运行部署脚本验证安装

### 常见问题

**Q: 批量 `pip install` 失败**
- 检查 `.whl` 文件名是否与 `requirements_py39_fixed.txt` 中的包名匹配
- 检查是否存在平台不兼容的 wheel（需要 `manylinux2014_x86_64`）
- 脚本会自动降级到逐个安装模式

**Q: MarkupSafe 编译错误**
- 必须使用预编译的 `cp39-cp39-manylinux` wheel
- 当前使用版本 2.1.3，Python 3.9 编译版

**Q: mysql.connector 报错**
- 部署脚本会自动检测并将 `mysql.connector` 替换为 `PyMySQL`
- 如果替换失败，手动检查 `app.py` 中是否有未注释的 `import mysql.connector`

## 验证命令

```bash
# 检查进程
pgrep -f 'python.*app.py'

# 检查端口
netstat -tlnp | grep :5000

# 健康检查
curl -s http://localhost:5000/actuator/health

# 查看日志
tail -f /main/app/cross_env_manager/logs/cross_env_manager.log
```
