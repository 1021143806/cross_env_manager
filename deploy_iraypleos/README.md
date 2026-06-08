# 离线部署操作

## 部署位置
项目文件位于: `/main/app/toolsForPersonal/projects/agv_system/app/cross_env_manager`

## 部署步骤
1. 进入项目目录:
   ```bash
   cd /main/app/toolsForPersonal/projects/agv_system/app/cross_env_manager
   ```

2. 确保部署脚本有执行权限:
   ```bash
   chmod +x ./deploy_iraypleos/deploy_iraypleos.sh
   ```

3. 运行部署脚本:
   ```bash
   ./deploy_iraypleos/deploy_iraypleos.sh
   ```

## 注意事项
- 离线依赖包位于: `deploy_iraypleos/vendor_packages3.9/`
- 脚本会自动创建虚拟环境并安装所有依赖
- Supervisor配置将保存到: `/main/server/supervisor/cross_env_manager.conf`

## 平台切换模块依赖

v2.4.0 新增「平台切换」功能（`routes/platform_switch_routes.py`），离线包已包含以下新增依赖：

| 包 | 版本 | 用途 |
|----|------|------|
| `paramiko` | 5.0.0 | SSH 远程连接 AGV |
| `PyYAML` | 6.0.3 | 解析 rosservice YAML 输出 |
| `cryptography` | 43.0.3 | paramiko 依赖（加密） |
| `bcrypt` | 5.0.0 | paramiko 依赖 |
| `pynacl` | 1.6.2 | paramiko 依赖 |
| `cffi` | 2.0.0 | paramiko 依赖 |
| `pycparser` | 2.23 | cffi 依赖 |
| `invoke` | 3.0.3 | paramiko 依赖 |

### 新增离线包

```bash
cd deploy_iraypleos/vendor_packages3.9
pip download --only-binary=:all: --platform manylinux2014_x86_64 --python-version 3.9 \
  paramiko pyyaml bcrypt pynacl invoke cffi pycparser cryptography
```