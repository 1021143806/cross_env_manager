#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
自动同步设备脚本
功能：统一配置参数，自动调用 copy_agv_model_init.py、copy_robot.py 和 add_device_ext.py 完成完整设备同步

使用方法：
1. 修改下面的配置参数
2. 运行脚本：python 自动同步设备脚本.py
"""

import subprocess
import sys
import os

# 使用当前 Python 解释器路径，确保子脚本使用相同的 Python 环境
PYTHON_CMD = sys.executable

# ========== 统一配置参数（请根据实际情况修改）==========

# 数据库通用配置
DB_CONFIG = {
    'SOURCE_HOST': "10.68.2.27",      # 源数据库IP,当前已添加设备的服务器地址
    'TARGET_HOST': "10.68.2.31",      # 目标数据库IP，需要同步到的服务器地址
    'PASSWORD': "CCshenda889",        # 数据库密码（源和目标使用相同密码），默认
    'USER': "wms",                    # 数据库用户名，默认
    'DATABASE': "wms",                # 数据库名，默认
    'CHARSET': "utf8mb4",             # 字符集，默认
    'PORT': 3306                      # 数据库端口，默认
}

# 设备型号同步配置（copy_agv_model_init.py）
MODEL_SYNC_ENABLED = True             # 是否启用设备型号同步，一般启用，有重复不插入
MODEL_NAMES = "RTA-C060-Q-2L-410"     # 需要同步的型号列表，多个用逗号分隔

# 设备主表同步配置（copy_robot.py）
ROBOT_SYNC_ENABLED = True             # 是否启用设备主表同步
DEVICE_TYPE = "RTA-C060-Q-2L-410"     # 设备类型
TABLE_NAME = "agv_robot"              # 目标表名

# 设备扩展表同步配置（add_device_ext.py）
DEVICE_EXT_SYNC_ENABLED = True        # 是否启用设备扩展表同步
GROUP_NAME = "加车脚本使用"        # 设备组名称
TARGET_AREA = 4                       # 目标区域，父区域，需要填写，如果查表目标数据库ip的bms表查到是子区域，则查表找到父区域并提示用户当前输入是子区域，父区域是查询到的区域id，请重新输入。

# 脚本路径配置（相对路径）
MODEL_SYNC_SCRIPT = "function/copy_agv_model_init.py"
ROBOT_SYNC_SCRIPT = "function/copy_robot.py"
DEVICE_EXT_SYNC_SCRIPT = "function/add_device_ext.py"

# ========== 函数定义 ==========

def run_command(cmd_args, script_name):
    """运行子进程命令"""
    print(f"\n{'='*60}")
    print(f"开始执行: {script_name}")
    print(f"命令: {' '.join(cmd_args)}")
    print(f"{'='*60}")
    
    try:
        # 运行命令并捕获输出
        result = subprocess.run(
            cmd_args,
            capture_output=True,
            text=True,
            check=True
        )
        
        print(f"输出:\n{result.stdout}")
        if result.stderr:
            print(f"警告/错误:\n{result.stderr}")
        
        print(f"{script_name} 执行成功!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"{script_name} 执行失败!")
        print(f"错误代码: {e.returncode}")
        print(f"标准输出:\n{e.stdout}")
        print(f"标准错误:\n{e.stderr}")
        return False
    except FileNotFoundError:
        print(f"错误: 找不到脚本文件 {cmd_args[1]}")
        print(f"请确保脚本文件存在且路径正确")
        return False

def run_model_sync():
    """运行 copy_agv_model_init.py 脚本（设备型号同步）"""
    if not MODEL_SYNC_ENABLED:
        print("设备型号同步已禁用，跳过")
        return True
    
    cmd = [
        PYTHON_CMD, MODEL_SYNC_SCRIPT,
        "--source-host", DB_CONFIG['SOURCE_HOST'],
        "--source-port", str(DB_CONFIG['PORT']),
        "--source-user", DB_CONFIG['USER'],
        "--source-password", DB_CONFIG['PASSWORD'],
        "--source-database", DB_CONFIG['DATABASE'],
        "--target-host", DB_CONFIG['TARGET_HOST'],
        "--target-port", str(DB_CONFIG['PORT']),
        "--target-user", DB_CONFIG['USER'],
        "--target-password", DB_CONFIG['PASSWORD'],
        "--target-database", DB_CONFIG['DATABASE'],
        "--models", MODEL_NAMES,
        "--charset", DB_CONFIG['CHARSET']
    ]
    
    return run_command(cmd, "copy_agv_model_init.py (设备型号同步)")

def run_robot_sync():
    """运行 copy_robot.py 脚本（设备主表同步）"""
    if not ROBOT_SYNC_ENABLED:
        print("设备主表同步已禁用，跳过")
        return True
    
    cmd = [
        PYTHON_CMD, ROBOT_SYNC_SCRIPT,
        "--source-host", DB_CONFIG['SOURCE_HOST'],
        "--source-port", str(DB_CONFIG['PORT']),
        "--source-user", DB_CONFIG['USER'],
        "--source-password", DB_CONFIG['PASSWORD'],
        "--source-database", DB_CONFIG['DATABASE'],
        "--target-host", DB_CONFIG['TARGET_HOST'],
        "--target-port", str(DB_CONFIG['PORT']),
        "--target-user", DB_CONFIG['USER'],
        "--target-password", DB_CONFIG['PASSWORD'],
        "--target-database", DB_CONFIG['DATABASE'],
        "--device-type", DEVICE_TYPE,
        "--table", TABLE_NAME,
        "--charset", DB_CONFIG['CHARSET']
    ]
    
    return run_command(cmd, "copy_robot.py (设备主表同步)")

def run_device_ext_sync():
    """运行 add_device_ext.py 脚本（设备扩展表同步）"""
    if not DEVICE_EXT_SYNC_ENABLED:
        print("设备扩展表同步已禁用，跳过")
        return True
    
    cmd = [
        PYTHON_CMD, DEVICE_EXT_SYNC_SCRIPT,
        "--source-host", DB_CONFIG['SOURCE_HOST'],
        "--source-port", str(DB_CONFIG['PORT']),
        "--source-user", DB_CONFIG['USER'],
        "--source-password", DB_CONFIG['PASSWORD'],
        "--source-database", DB_CONFIG['DATABASE'],
        "--target-host", DB_CONFIG['TARGET_HOST'],
        "--target-port", str(DB_CONFIG['PORT']),
        "--target-user", DB_CONFIG['USER'],
        "--target-password", DB_CONFIG['PASSWORD'],
        "--target-database", DB_CONFIG['DATABASE'],
        "--group-name", GROUP_NAME,
        "--target-area", str(TARGET_AREA),
        "--charset", DB_CONFIG['CHARSET']
    ]
    
    return run_command(cmd, "add_device_ext.py (设备扩展表同步)")

def print_config():
    """打印当前配置"""
    print("="*60)
    print("自动同步设备脚本 - 当前配置")
    print("="*60)
    
    print("\n数据库配置:")
    print(f"  源数据库: {DB_CONFIG['SOURCE_HOST']}:{DB_CONFIG['PORT']}/{DB_CONFIG['DATABASE']}")
    print(f"  目标数据库: {DB_CONFIG['TARGET_HOST']}:{DB_CONFIG['PORT']}/{DB_CONFIG['DATABASE']}")
    print(f"  用户名: {DB_CONFIG['USER']}")
    print(f"  密码: {DB_CONFIG['PASSWORD']}")
    print(f"  字符集: {DB_CONFIG['CHARSET']}")
    
    print("\n设备型号同步配置 (copy_agv_model_init.py):")
    print(f"  启用: {'是' if MODEL_SYNC_ENABLED else '否'}")
    print(f"  型号列表: {MODEL_NAMES}")
    
    print("\n设备主表同步配置 (copy_robot.py):")
    print(f"  启用: {'是' if ROBOT_SYNC_ENABLED else '否'}")
    print(f"  设备类型: {DEVICE_TYPE}")
    print(f"  目标表: {TABLE_NAME}")
    
    print("\n设备扩展表同步配置 (add_device_ext.py):")
    print(f"  启用: {'是' if DEVICE_EXT_SYNC_ENABLED else '否'}")
    print(f"  设备组: {GROUP_NAME}")
    print(f"  目标区域: {TARGET_AREA}")
    
    print("\n脚本路径:")
    print(f"  设备型号同步: {MODEL_SYNC_SCRIPT}")
    print(f"  设备主表同步: {ROBOT_SYNC_SCRIPT}")
    print(f"  设备扩展表同步: {DEVICE_EXT_SYNC_SCRIPT}")
    print("="*60)

def check_script_files():
    """检查脚本文件是否存在"""
    scripts_to_check = []
    
    if MODEL_SYNC_ENABLED:
        scripts_to_check.append((MODEL_SYNC_SCRIPT, "设备型号同步"))
    if ROBOT_SYNC_ENABLED:
        scripts_to_check.append((ROBOT_SYNC_SCRIPT, "设备主表同步"))
    if DEVICE_EXT_SYNC_ENABLED:
        scripts_to_check.append((DEVICE_EXT_SYNC_SCRIPT, "设备扩展表同步"))
    
    missing_scripts = []
    for script_path, script_name in scripts_to_check:
        if not os.path.exists(script_path):
            missing_scripts.append((script_path, script_name))
    
    return missing_scripts

def main():
    """主函数"""
    print_config()
    
    # 检查脚本文件是否存在
    missing_scripts = check_script_files()
    if missing_scripts:
        print("\n错误: 以下脚本文件不存在:")
        for script_path, script_name in missing_scripts:
            print(f"  - {script_name}: {script_path}")
        print("请确保脚本文件存在且路径正确")
        return 1
    
    # 询问用户是否继续
    print("\n是否开始执行同步? (y/n): ", end="")
    response = input().strip().lower()
    
    if response not in ['y', 'yes', '是']:
        print("用户取消执行")
        return 0
    
    # 执行同步
    success = True
    
    # 执行设备型号同步
    if MODEL_SYNC_ENABLED:
        if not run_model_sync():
            success = False
            print("警告: 设备型号同步执行失败，但将继续执行下一个脚本")
    
    # 执行设备主表同步
    if ROBOT_SYNC_ENABLED:
        if not run_robot_sync():
            success = False
            print("警告: 设备主表同步执行失败，但将继续执行下一个脚本")
    
    # 执行设备扩展表同步
    if DEVICE_EXT_SYNC_ENABLED:
        if not run_device_ext_sync():
            success = False
    
    # 输出结果
    print("\n" + "="*60)
    print("同步完成!")
    
    if success:
        print("所有脚本执行成功!")
        return 0
    else:
        print("部分脚本执行失败，请检查上面的错误信息")
        return 1

if __name__ == "__main__":
    sys.exit(main())