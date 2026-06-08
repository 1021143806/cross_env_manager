# postlook 多平台离线部署

## 目录结构

```
deploy/
├── deploy.sh                      # 一键部署入口（自动检测 OS + Python）
├── deploy.conf                    # 部署配置（端口/用户/日志等参数）
├── README.md                      # 本文件
├── lib/                           # 公共函数库
│   ├── common.sh                  # 日志输出 / 错误处理
│   ├── detect.sh                  # OS / Python / ABI 检测
│   ├── python.sh                  # Python 环境准备 + venv
│   ├── deps.sh                    # 离线依赖安装（ABI 感知）
│   └── supervisor.sh              # Supervisor 配置生成 + 服务启动
├── vendor_packages/               # 离线 pip 依赖包（按 Python ABI 分层）
│   ├── common/                    # 纯 Python 包（py3-none-any，所有版本共享）
│   ├── cp39/                      # Python 3.9 ABI 专用（如 pydantic_core）
│   └── cp311/                     # Python 3.11 ABI 专用
├── platform/                      # 平台专属资源
│   ├── centos7/
│   │   ├── setup.sh               # CentOS 7: 预编译包 / 源码编译 Python 3.9
│   │   └── rpms/                  # devel RPM + Python 源码/预编译包
│   └── openEuler/
│       └── setup.sh               # openEuler: 系统自带 Python 3.11（无额外操作）
└── backup/                        # 旧文件归档（.gitignore）
```

## 支持平台

| 操作系统 | Python 策略 | 状态 |
|----------|------------|------|
| **openEuler 24.03** | 系统自带 Python 3.11，直接创建 venv | ✅ 支持 |
| **CentOS 7** | 预编译包解压 → 源码编译回退 | ✅ 支持 |
| **Ubuntu / Debian** | 系统自带 Python（需 >= 3.9） | ✅ 支持（需手动安装 python3-venv） |
| 其他 Linux | 需 Python 3.9+ | ⚠️ 通用支持 |

## 部署步骤

### 1. 准备离线依赖包（联网环境执行一次）

**通用包（所有 Python 版本共享）：**
```bash
cd Plugin/postlook
pip download fastapi uvicorn pydantic starlette anyio annotated-types annotated-doc \
  click h11 idna tomli typing_extensions typing_inspection exceptiongroup \
  -d deploy/vendor_packages/common/
```

**Python 3.9 ABI 专用：**
```bash
pip download "pydantic_core" --python-version 3.9 --platform manylinux2014_x86_64 \
  --only-binary=:all: -d deploy/vendor_packages/cp39/ --no-deps
```

**Python 3.11 ABI 专用：**
```bash
pip download "pydantic_core" --python-version 3.11 --platform manylinux2014_x86_64 \
  --only-binary=:all: -d deploy/vendor_packages/cp311/ --no-deps
```

### 2. 修改配置（按需）

```bash
vim deploy/deploy.conf
```

常用配置项：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `APP_PORT` | 5011 | 服务端口 |
| `SUPERVISOR_USER` | ymsk | Supervisor 运行用户 |
| `PYTHON3_PATH` | (空) | 手动指定 Python 路径（留空自动检测） |

### 3. 执行部署

```bash
cd Plugin/postlook
chmod +x deploy/deploy.sh
sudo ./deploy/deploy.sh
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

## 安全机制

部署脚本内置多层防护，防止脚本 bug 污染系统：

| 防护层 | 机制 | 说明 |
|--------|------|------|
| **OS 白名单** | `OS_ALLOWLIST` 校验 | 只允许 openEuler / centos / debian / ubuntu，未知系统直接拒绝 |
| **路径安全** | `_safe_rm_dir()` | `rm -rf` 前校验路径非空、非系统关键路径、必须在项目目录内 |
| **ABI 校验** | whl 文件名 cp 标签 vs Python ABI | 安装前验证 `pydantic_core` 的 cp 标签与当前 Python 匹配，防止装错 |
| **配置备份** | 覆盖前自动备份 | Supervisor 配置被覆盖时自动备份到 `deploy/backup/` |
| **严格模式** | `set -euo pipefail` | 任何未定义变量、管道失败、命令失败立即退出 |
| **强制部署** | `BYPASS_OS_CHECK=1` | 非白名单系统可设置此环境变量跳过校验（风险自负） |

## 访问地址

- 前端页面: `http://localhost:5011`
- API 文档: `http://localhost:5011/docs`
- 健康检查: `http://localhost:5011/api/health`

## 平台适配说明

### CentOS 7 特别注意

- 系统默认 Python 2.7，脚本会自动尝试安装 Python 3.9
- 安装策略：预编译包 `python39_build.tar.gz` → 源码编译 `Python-3.9.20.tar.xz`
- 需要 `platform/centos7/rpms/` 目录下有对应的包文件
- glibc 2.17 可能不兼容预编译包，会自动回退源码编译

### openEuler 24.03

- 系统自带 Python 3.11.6，无需额外操作
- 部分镜像可能缺少 `python3-venv`，脚本会自动 `dnf install`

### 离线依赖包管理

- **纯 Python 包**（`py3-none-any.whl`）：放在 `vendor_packages/common/`，所有 Python 版本共享
- **ABI 专用包**（含 `cpXY` 标签）：放在 `vendor_packages/cpXY/`，按 Python 版本选择
- 唯一 ABI 专用包：`pydantic_core`（pydantic 的 C 扩展核心）
