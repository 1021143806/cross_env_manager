# 离线部署模块

## 目录结构

```
deploy/
├── deploy.sh                     # 一键部署入口（自动检测 OS + Python）
├── deploy.conf                   # 部署配置（端口/用户/日志等参数）
├── README.md                     # 本文件
├── lib/                          # 公共函数库
│   ├── common.sh                 # 日志输出 / 错误处理
│   ├── detect.sh                 # OS / Python / ABI 检测
│   ├── python.sh                 # Python 环境准备 + venv
│   ├── deps.sh                   # 离线依赖安装（Flask 专用，ABI 感知）
│   └── supervisor.sh             # Supervisor 配置生成 + 服务启动（Flask 适配）
├── vendor_packages/              # 离线 pip 依赖包（按 Python ABI 分层）
│   ├── common/                   # 纯 Python 包（py3-none-any，所有版本共享）
│   ├── cp39/                     # Python 3.9 ABI 专用（markupsafe / cryptography 等编译版）
│   └── requirements_py39_fixed.txt  # 版本锁定的依赖清单
├── platform/                     # 平台专属资源
│   ├── centos7/
│   │   └── setup.sh              # CentOS 7: 预编译包 → 源码编译 Python 3.9
│   └── openEuler/
│       └── setup.sh              # IRAYPLEOS / openEuler: 系统 Python + dnf 安装
└── backup/                       # Supervisor 配置备份（.gitignore）
```

## 架构设计

### 网络约束

目标服务器 **IRAYPLEOS** 为离线环境，无法连接 PyPI。部署模块采用「**在线打包 — 离线安装**」的双阶段模式：

```
开发机（在线）                         目标服务器（离线）
┌─────────────────┐                 ┌──────────────────┐
│ pip download     │── scp/rsync ──▶│ vendor_packages  │
│ → *.whl          │                 │ deploy/          │
│ → requirements   │                 │   deploy.sh      │
└─────────────────┘                 │ venv/ (自动创建)  │
                                    │ Supervisor 启动   │
                                    └──────────────────┘
```

### 核心设计原则

| 原则 | 实现 |
|------|------|
| **多平台适配** | 自动识别 IRAYPLEOS/CentOS/Debian，按 OS 分发安装策略 |
| **多级 Python 回退** | 6 级检测链：配置指定 → conda → 系统 → 共享路径 → SCL → 通用路径 |
| **完全离线** | 所有依赖以 `.whl` 形式按 ABI 分层存储，安装时使用 `--no-index --find-links` |
| **幂等部署** | venv 存在且完整则跳过；依赖已安装则跳过 |
| **安全防护** | `_safe_rm_dir()` 防误删 + glibc 兼容性验证 |
| **ABI 感知** | `vendor_packages/common/` + `vendor_packages/cp39/` 分层，安装前校验 ABI 匹配 |

## 支持平台

| 操作系统 | Python 策略 | 状态 |
|----------|------------|------|
| **IRAYPLEOS / openEuler** | 系统自带 Python 3.9+，或 dnf 安装 | ✅ 支持 |
| **CentOS 7** | 预编译包解压 → 源码编译回退 | ✅ 支持 |
| **Ubuntu / Debian** | 系统自带 Python（需 >= 3.9） | ⚠️ 通用支持 |

## 部署步骤

### 1. 准备离线依赖包（联网环境执行一次）

```bash
cd deploy/vendor_packages

# 通用包（所有 Python 版本共享，py3-none-any）
pip download flask pymysql werkzeug jinja2 click itsdangerous \
  markupsafe python-dotenv markdown tomli blinker zipp \
  dbutils flask-caching cachelib importlib_metadata \
  paramiko pyyaml cryptography bcrypt pynacl cffi pycparser invoke \
  typing_extensions \
  --python-version 3.9 --platform manylinux2014_x86_64 \
  -d common/

# Python 3.9 ABI 专用（cp39 编译版）
# 将下载的 cp39 编译版 whl 移动到 cp39/ 目录
```

### 2. 修改配置（按需）

```bash
vim deploy/deploy.conf
```

常用配置项：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `APP_PORT` | 5000 | 服务端口 |
| `SUPERVISOR_USER` | ymsk | Supervisor 运行用户 |
| `PYTHON3_PATH` | (空) | 手动指定 Python 路径（留空自动检测） |

### 3. 执行部署

```bash
cd cross_env_manager
chmod +x deploy/deploy.sh

# 默认：部署 CEM + postlook（如果 postlook 存在）
sudo ./deploy/deploy.sh

# 仅部署 cross_env_manager
sudo ./deploy/deploy.sh --cem-only
```

## 部署流程详解

| 步骤 | 操作 | 说明 |
|------|------|------|
| 1.1 | OS 检测 | 自动识别 IRAYPLEOS → openEuler |
| 1.2 | Python 检测 | 6 级检测链，确认 Python 3.9+ 可用 |
| 1.3 | Supervisor 检测 | 确认 supervisorctl 是否可用 |
| 1.4 | 项目文件检查 | 验证 app.py 存在 |
| 2 | Python 环境准备 | 按 OS 分发：CentOS 走预编译/编译，openEuler 走系统/dnf |
| 3 | 创建 venv | `python3 -m venv venv`，存在且完整则跳过 |
| 3.5 | mysql.connector 修复 | 自动注释 mysql.connector 引用，替换为 pymysql |
| 4 | 检查依赖包 | 扫描 vendor_packages 关键包完整性 |
| 5 | 安装依赖 | 批量安装 → 失败则逐个安装 |
| 6 | 验证安装 | 验证 flask、pymysql、paramiko 等可导入 |
| 7 | Supervisor 配置 | 配置不存在时自动创建，已存在则备份后覆盖 |
| 8 | 启动服务 | `supervisorctl restart`，失败则 `nohup` 直接启动 |
| 9 | 部署 postlook | 检测 `Plugin/postlook/deploy/deploy.sh`，存在则自动部署（`--cem-only` 跳过） |

### Python 检测链（6 级）

```
1. deploy.conf PYTHON3_PATH (手动指定)
          ↓
2. conda base Python (/home/a1/miniconda3/bin/python3)
          ↓
3. 系统默认 python3 (PATH 查找)
          ↓
4. 共享 Python 3.9 (/main/app/python39/bin/python3.9)
          ↓
5. CentOS 7 SCL (/opt/rh/rh-python39/root/bin/python3)
          ↓
6. 通用路径 (/usr/local/bin/python3, /usr/local/python3/bin/python3)
          ↓ (全部未命中)
7. 平台专属安装策略
```

### 依赖安装策略

- **路径 1（快速路径）**：`pip install --no-index --find-links=... -r requirements_py39_fixed.txt`
- **路径 2（降级路径）**：逐文件安装 whl，先无依赖安装，失败则带依赖重试

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
| PyMySQL | 1.1.0 | MySQL 驱动 |
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
| PyYAML | 6.0.3 | YAML 解析 |
| cryptography | 43.0.3 | 加密（paramiko 依赖） |
| bcrypt | 5.0.0 | 密码哈希 |
| pynacl | 1.6.2 | 网络加密 |
| cffi | 2.0.0 | C 接口 |
| pycparser | 2.23 | C 解析器 |
| invoke | 3.0.3 | 子进程管理 |

## 维护指南

### 新增依赖包

```bash
cd deploy/vendor_packages

# 1. 下载纯 Python 包
pip download --python-version 3.9 --platform manylinux2014_x86_64 \
  --only-binary=:all: <package_name> -d common/

# 2. 下载 cp39 编译版包（如有）移到 cp39/
mv common/*cp39*.whl cp39/ 2>/dev/null || true

# 3. 添加到 requirements_py39_fixed.txt（锁定版本）
echo "<package_name>==<version>" >> requirements_py39_fixed.txt
```

### 常见问题

**Q: 脚本执行时找不到 python3**
- 检查 `deploy.conf` 中 `PYTHON3_PATH` 可手动指定
- 对于 IRAYPLEOS：执行 `dnf install -y python3 python3-venv` 后重试
- 对于 CentOS 7：确保 `Plugin/postlook/deploy/platform/centos7/rpms/` 有预编译包

**Q: MarkupSafe 编译错误**
- 必须使用 `cp39` 编译版，位于 `vendor_packages/cp39/`
- 当前使用版本 2.1.3，Python 3.9 编译版

**Q: mysql.connector 报错**
- 部署脚本会自动检测并将 `mysql.connector` 替换为 `PyMySQL`
- 如果替换失败，手动检查 `app.py` 中是否有未注释的 `import mysql.connector`

**Q: Supervisor 启动失败**
- 检查配置：`cat /main/server/supervisor/cross_env_manager.conf`
- 查看日志：`tail -50 /main/app/cross_env_manager/logs/cross_env_manager.log`
- 手动启动测试：`./venv/bin/python app.py`

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
