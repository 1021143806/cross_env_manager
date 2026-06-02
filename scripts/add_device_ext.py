#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
设备扩展表添加工具
功能：根据指定的设备组名称，从源库查询组内所有设备的扩展信息，插入到目标库的agv_robot_ext表，
      并将DEVICE_AREA修改为指定区域，重复记录自动跳过。

使用方法：
    python add_device_ext.py --source-host 10.68.2.32 --source-password CCshenda889 \
                              --target-host 10.68.2.40 --target-password CCshenda889 \
                              --group-name "点胶4代车" --target-area 3
所有参数均可通过命令行指定，详情见 -h 帮助。
"""

import pymysql
import argparse
import sys
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pymysql.cursors import DictCursor


@dataclass
class DatabaseConfig:
    """数据库连接配置"""
    host: str
    port: int
    user: str
    password: str
    database: str
    charset: str = 'utf8mb4'


class GroupDeviceSync:
    """设备组同步处理器"""

    # 目标表字段列表（不含自增ID）
    TARGET_FIELDS = [
        'DEVICE_CODE', 'DEVICE_AREA', 'DEVICE_NUMBER', 'CREATE_DATE',
        'BIND_QRNODE', 'DEVICE_STATUS', 'ENABLE'
    ]

    def __init__(self, source_cfg: DatabaseConfig, target_cfg: DatabaseConfig):
        """
        初始化同步器
        :param source_cfg: 源数据库配置
        :param target_cfg: 目标数据库配置
        """
        self.source_cfg = source_cfg
        self.target_cfg = target_cfg

    def _connect_source(self) -> pymysql.Connection:
        """连接源数据库（返回字典游标）"""
        config = {
            'host': self.source_cfg.host,
            'port': self.source_cfg.port,
            'user': self.source_cfg.user,
            'password': self.source_cfg.password,
            'database': self.source_cfg.database,
            'charset': self.source_cfg.charset,
            'cursorclass': DictCursor
        }
        return pymysql.connect(**config)

    def _connect_target(self) -> pymysql.Connection:
        """连接目标数据库（普通游标）"""
        config = {
            'host': self.target_cfg.host,
            'port': self.target_cfg.port,
            'user': self.target_cfg.user,
            'password': self.target_cfg.password,
            'database': self.target_cfg.database,
            'charset': self.target_cfg.charset
        }
        return pymysql.connect(**config)

    def get_group_id(self, group_name: str) -> Optional[int]:
        """
        根据组名查询agv_robot_group表中的ID
        :param group_name: 设备组名称
        :return: 组ID，若不存在返回None
        """
        conn = self._connect_source()
        try:
            with conn.cursor() as cursor:
                sql = "SELECT id FROM agv_robot_group WHERE group_name = %s"
                cursor.execute(sql, (group_name,))
                result = cursor.fetchone()
                return result['id'] if result else None
        finally:
            conn.close()

    def get_group_devices(self, group_id: int) -> List[Dict[str, Any]]:
        """
        根据组ID查询agv_robot_group_detail表中的设备信息
        :param group_id: 组ID
        :return: 设备信息列表，每个元素包含device_code, device_number等字段
        """
        conn = self._connect_source()
        try:
            with conn.cursor() as cursor:
                sql = "SELECT device_code, device_number FROM agv_robot_group_detail WHERE group_id = %s"
                cursor.execute(sql, (group_id,))
                return cursor.fetchall()
        finally:
            conn.close()

    def fetch_device_ext(self, device_codes: List[str]) -> List[Dict[str, Any]]:
        """
        从源库agv_robot_ext表查询指定设备编码的完整记录
        :param device_codes: 设备编码列表
        :return: 设备扩展记录列表
        """
        if not device_codes:
            return []
        # 构造占位符
        placeholders = ','.join(['%s'] * len(device_codes))
        sql = f"SELECT * FROM agv_robot_ext WHERE device_code IN ({placeholders})"

        conn = self._connect_source()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, device_codes)
                return cursor.fetchall()
        finally:
            conn.close()

    def insert_into_target(self, devices: List[Dict[str, Any]], target_area: int) -> Tuple[int, int]:
        """
        将设备记录插入目标库agv_robot_ext表，修改DEVICE_AREA为指定区域，重复则跳过
        :param devices: 设备扩展记录列表（来自源库）
        :param target_area: 目标区域值
        :return: (成功插入数, 跳过数)
        """
        if not devices:
            return 0, 0

        target_conn = self._connect_target()
        try:
            with target_conn.cursor() as cursor:
                # 构建INSERT IGNORE语句
                fields_str = ', '.join([f'`{f}`' for f in self.TARGET_FIELDS])
                placeholders = ', '.join(['%s'] * len(self.TARGET_FIELDS))
                insert_sql = f"INSERT IGNORE INTO `agv_robot_ext` ({fields_str}) VALUES ({placeholders})"

                success = 0
                skipped = 0

                for dev in devices:
                    # 按TARGET_FIELDS顺序提取值，并替换DEVICE_AREA为目标区域
                    values = []
                    for field in self.TARGET_FIELDS:
                        if field == 'DEVICE_AREA':
                            values.append(target_area)
                        else:
                            # 其他字段保持原样，若不存在则设为None
                            values.append(dev.get(field))

                    try:
                        cursor.execute(insert_sql, values)
                        if cursor.rowcount == 1:
                            success += 1
                        else:
                            skipped += 1
                    except Exception as e:
                        # 其他异常，回滚并跳过该条（可根据需要处理）
                        target_conn.rollback()
                        print(f"插入失败，设备 {dev.get('DEVICE_CODE')} 错误: {e}")
                        continue

                target_conn.commit()
                return success, skipped
        finally:
            target_conn.close()

    def run(self, group_name: str, target_area: int) -> None:
        """
        执行完整的同步流程
        :param group_name: 设备组名称
        :param target_area: 目标区域
        """
        print(f"开始处理设备组 '{group_name}', 目标区域 {target_area}")

        # 1. 获取组ID
        group_id = self.get_group_id(group_name)
        if not group_id:
            print(f"错误：未找到组名 '{group_name}'")
            return
        print(f"组ID: {group_id}")

        # 2. 获取组内设备
        group_devices = self.get_group_devices(group_id)
        if not group_devices:
            print(f"组 '{group_name}' 下没有设备记录")
            return
        device_codes = [d['device_code'] for d in group_devices]
        print(f"组内设备编码: {', '.join(device_codes)}")

        # 3. 查询设备扩展信息
        ext_records = self.fetch_device_ext(device_codes)
        if not ext_records:
            print("警告：未找到任何设备的扩展信息")
            return
        print(f"从源库查询到 {len(ext_records)} 条设备扩展记录")

        # 4. 插入目标库
        success, skipped = self.insert_into_target(ext_records, target_area)
        print(f"操作完成：成功插入 {success} 条，跳过（重复） {skipped} 条")


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='将指定设备组的设备扩展信息同步到目标库，修改区域，重复跳过')
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
    # 业务参数
    parser.add_argument('--group-name', required=True, help='设备组名称，如"点胶4代车"')
    parser.add_argument('--target-area', type=int, required=True, help='目标区域，如3')
    parser.add_argument('--charset', default='utf8mb4', help='数据库字符集，默认utf8mb4')
    return parser.parse_args()


def main():
    args = parse_arguments()

    source_cfg = DatabaseConfig(
        host=args.source_host,
        port=args.source_port,
        user=args.source_user,
        password=args.source_password,
        database=args.source_database,
        charset=args.charset
    )
    target_cfg = DatabaseConfig(
        host=args.target_host,
        port=args.target_port,
        user=args.target_user,
        password=args.target_password,
        database=args.target_database,
        charset=args.charset
    )

    sync = GroupDeviceSync(source_cfg, target_cfg)
    try:
        sync.run(args.group_name, args.target_area)
    except Exception as e:
        print(f"执行出错: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()