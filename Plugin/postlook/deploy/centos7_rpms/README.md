# CentOS 7 Python 3.9 离线安装

## 预编译包（推荐）

本目录包含 `python39_build.tar.gz`（~69MB），已编译好的 Python 3.9.20。

### 使用方式
直接运行 `deploy.sh`，脚本会自动解压到 `/usr/local/python3/`。

### 手动安装
```bash
tar -xzf python39_build.tar.gz -C /usr/local/
/usr/local/python3/bin/python3 --version
# Python 3.9.20
```

### 注意事项
- 预编译环境：IRAYPLEOS (CentOS 系)，glibc 2.28+
- 如果目标 CentOS 7 glibc 版本较低（2.17），可能不兼容
- 如不兼容，需在目标服务器上用源码编译（Python-3.9.20.tar.xz）
