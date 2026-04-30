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