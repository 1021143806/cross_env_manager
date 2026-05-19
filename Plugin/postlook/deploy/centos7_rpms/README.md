# CentOS 7 Python 3.9 离线安装

## 方法一：在联网 CentOS 7 上下载（推荐）

在一台联网的 CentOS 7 机器上执行：

```bash
# 安装 SCL 仓库
yum install -y centos-release-scl-rh

# 下载 Python 3.9 及依赖到当前目录
mkdir python39_rpms && cd python39_rpms
yum install -y --downloadonly --downloaddir=. rh-python39 rh-python39-python-devel
```

将 `python39_rpms/` 目录打包传到离线服务器。

## 方法二：使用预下载的 SCL 仓库包

本目录已包含 `centos-release-scl-rh` RPM 包。

在离线 CentOS 7 服务器上：

```bash
# 1. 安装 SCL 仓库
rpm -ivh centos-release-scl-rh-2-3.el7.centos.noarch.rpm

# 2. 安装 Python 3.9（需要先通过方法一准备好 RPM 包）
rpm -ivh python39_rpms/*.rpm --nodeps
# 或
yum localinstall python39_rpms/*.rpm -y
```

## 验证

```bash
/opt/rh/rh-python39/root/bin/python3 --version
# Python 3.9.x
```

## 创建 venv

```bash
/opt/rh/rh-python39/root/bin/python3 -m venv venv
```
