#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
从源数据库查询指定设备类型的AGV记录，去除ID后插入目标数据库，重复则跳过。
使用方法：
    python script.py --source-host 10.68.2.32 --source-password CCshenda889 \
                     --target-host 10.68.2.40 --target-password CCshenda889 \
                     [--device-type "RTA-C060-Q-2L-410"] [--table agv_robot]
所有参数均可在命令行中指定，详情见 -h 帮助。
"""

import pymysql
import argparse
import sys
from pymysql.cursors import DictCursor

# 默认字段列表（除去 ID 后的顺序，必须与目标表一致）
DEFAULT_TARGET_FIELDS = [
    'DEVICE_CODE', 'DEVICE_IP', 'DEVICE_PORT', 'USRENAME', 'PASSWORD',
    'DEVICETYPE', 'CAPACITIES', 'DETAILTYPE', 'MAC', 'UPDATE_DATE',
    'CREATE_DATE', 'config', 'CONFIG_PARM', 'VERSION_SN', 'PROTOCOL',
    'MACS_VERSION', 'MILEAGE', 'DIRECT_CONNECTION'
]

def sync_robot_data(source_config, target_config, device_type, table_name, target_fields=None):
    """
    核心同步函数
    :param source_config: dict, 源数据库连接参数（含 host, port, user, password, database, charset 等）
    :param target_config: dict, 目标数据库连接参数
    :param device_type: str, 要查询的设备类型
    :param table_name: str, 目标表名
    :param target_fields: list, 目标表字段列表（除去ID），若为None则使用 DEFAULT_TARGET_FIELDS
    :return: (success_count, skip_count)
    """
    if target_fields is None:
        target_fields = DEFAULT_TARGET_FIELDS

    source_conn = None
    target_conn = None
    try:
        # 1. 连接源数据库并查询数据
        print("正在连接源数据库...")
        source_conn = pymysql.connect(**source_config)
        with source_conn.cursor() as cursor:
            sql = "SELECT * FROM agv_robot WHERE DEVICETYPE = %s"
            cursor.execute(sql, (device_type,))
            rows = cursor.fetchall()
            print(f"从源库查询到 {len(rows)} 条记录。")

        if not rows:
            print("没有符合条件的数据，程序结束。")
            return 0, 0

        # 2. 连接目标数据库
        print("正在连接目标数据库...")
        target_conn = pymysql.connect(**target_config)
        target_cursor = target_conn.cursor()

        # 3. 构造 INSERT IGNORE 语句（占位符方式）
        placeholders = ', '.join(['%s'] * len(target_fields))
        fields_str = ', '.join([f'`{f}`' for f in target_fields])
        insert_sql = f"INSERT IGNORE INTO `{table_name}` ({fields_str}) VALUES ({placeholders})"

        success_count = 0
        skip_count = 0

        # 4. 逐条插入数据
        for row in rows:
            values = [row.get(field) for field in target_fields]
            try:
                target_cursor.execute(insert_sql, values)
                if target_cursor.rowcount == 1:
                    success_count += 1
                else:
                    # rowcount = 0 表示被 IGNORE 忽略（重复键）
                    skip_count += 1
            except Exception as e:
                # 其他异常，回滚并计数为失败（此处选择跳过该条继续）
                target_conn.rollback()
                print(f"插入失败，错误信息：{e}")
                print(f"问题数据：{values}")
                continue

        target_conn.commit()
        return success_count, skip_count

    except Exception as e:
        print(f"同步过程中出现错误：{e}")
        raise
    finally:
        if source_conn:
            source_conn.close()
        if target_conn:
            target_conn.close()


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='同步AGV机器人数据从源库到目标库，去除ID，重复跳过。')
    # 源数据库参数
    parser.add_argument('--source-host', required=True, help='源数据库IP')
    parser.add_argument('--source-port', type=int, default=3306, help='源数据库端口，默认3306')
    parser.add_argument('--source-user', default='wms', help='源数据库用户名，默认wms')
    parser.add_argument('--source-password', required=True, help='源数据库密码')
    parser.add_argument('--source-database', default='wms', help='源数据库名，默认wms')
    # 目标数据库参数
    parser.add_argument('--target-host', required=True, help='目标数据库IP')
    parser.add_argument('--target-port', type=int, default=3306, help='目标数据库端口，默认3306')
    parser.add_argument('--target-user', default='wms', help='目标数据库用户名，默认wms')
    parser.add_argument('--target-password', required=True, help='目标数据库密码')
    parser.add_argument('--target-database', default='wms', help='目标数据库名，默认wms')
    # 其他参数
    parser.add_argument('--device-type', default='RTA-C060-Q-2L-410', help='设备类型，默认RTA-C060-Q-2L-410')
    parser.add_argument('--table', default='agv_robot', help='目标表名，默认agv_robot')
    parser.add_argument('--charset', default='utf8mb4', help='数据库字符集，默认utf8mb4')

    return parser.parse_args()


def main():
    args = parse_arguments()

    # 构造源数据库配置字典
    source_config = {
        'host': args.source_host,
        'port': args.source_port,
        'user': args.source_user,
        'password': args.source_password,
        'database': args.source_database,
        'charset': args.charset,
        'cursorclass': DictCursor   # 返回字典格式，便于字段操作
    }

    # 构造目标数据库配置字典（目标不需要 DictCursor，普通游标即可）
    target_config = {
        'host': args.target_host,
        'port': args.target_port,
        'user': args.target_user,
        'password': args.target_password,
        'database': args.target_database,
        'charset': args.charset
    }

    try:
        success, skip = sync_robot_data(
            source_config=source_config,
            target_config=target_config,
            device_type=args.device_type,
            table_name=args.table,
            target_fields=DEFAULT_TARGET_FIELDS   # 如需自定义字段，可在此修改
        )
        print(f"\n操作完成！成功插入 {success} 条，跳过（重复） {skip} 条。")
    except Exception as e:
        print(f"脚本执行失败：{e}")
        sys.exit(1)


if __name__ == '__main__':
    main()