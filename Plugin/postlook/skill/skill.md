# postlook skill

## 项目概述
postlook — 轻量、安全的日志 HTTP 查询服务，FastAPI + 前端 SPA。

## 技术栈
- Python 3.9+ / FastAPI / Uvicorn / Pydantic / tomli
- 前端：原生 HTML/CSS/JS，Mac 暗黑风格
- 部署：Supervisor + 离线 pip 包 + CentOS 7 源码编译 Python

## 项目结构
```
postlook/
├── src/postlook/
│   ├── app.py          # 入口，版本号 __version__
│   ├── routes.py       # API 路由
│   ├── scanner.py      # 文件扫描
│   ├── config.py       # 配置加载/热更新
│   └── static/         # 前端
├── deploy/
│   ├── deploy.sh       # 一键部署
│   ├── deploy.conf     # 部署配置
│   ├── vendor_packages/ # 离线 pip 包
│   └── centos7_rpms/   # CentOS 7 编译依赖 RPM
├── config/
│   ├── env.toml        # 运行配置（.gitignore）
│   └── template/env.toml
└── test/
```

## API 接口
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/logs | 查询日志 |
| GET | /api/logs/self | 自身日志 |
| GET/POST | /api/config | 配置管理（热更新） |
| GET | /api/files | 文件列表 |
| GET | /api/health | 健康检查 |
| GET | /api/help | 接口文档 |

## 关键设计
- 版本号唯一来源：`app.py` 中 `__version__`
- 配置热更新：`config.py` 的 `reload_config()` + `save_config_toml()`
- 路径安全：白名单 `root_dirs`，拒绝符号链接
- CentOS 7：自动检测 python3 → 预编译包 → 源码编译回退

## 部署
```bash
cd Plugin/postlook
sudo bash deploy/deploy.sh
```

## 端口
默认 5011

## ds 说
- vendor_packages 需要 git 跟踪（离线部署必需），已从 .gitignore 移除
- config/env.toml 在 .gitignore 中（含敏感路径），deploy.sh 首次自动从模板初始化
- CentOS 7 glibc 2.17 与预编译包不兼容，需源码编译
- 前端静态文件修改后需强制刷新浏览器（Ctrl+Shift+R）
- 服务状态面板文件浏览器点击文件名自动填入日志查询
