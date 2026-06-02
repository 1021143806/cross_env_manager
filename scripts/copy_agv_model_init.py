#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
设备型号添加工具
功能：将源库 agv_model 中的指定型号数据插入目标库 agv_model_init 表中（去除 ID），
      若目标库 agv_model 中已存在该型号则跳过。
使用方法：
    python copy_agv_model_init.py --source-host 10.68.2.32 --source-password CCshenda889 \
                                  --target-host 10.68.2.40 --target-password CCshenda889 \
                                  --models "RTA-C060-LQ-L-410"  # 可指定多个，逗号分隔
"""

import pymysql
import argparse
import sys
from typing import List, Dict, Any, Optional
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


class ModelSync:
    """型号数据同步处理器"""

    # agv_model 表的字段（包含 ID）
    AGV_MODEL_FIELDS = [
        'ID', 'SERIES_MODEL_NAME', 'PARENT_ID', 'SERIES_MODEL_TYPE', 'RUN_PARAM',
        'CONFIG_PARAM', 'CREATE_DATE', 'BASE_CONFIG', 'CHARGE_CONFIG', 'DEFAULT_ACTION',
        'ATTACH_PARAM', 'MODEL_TYPE', 'LOGO', 'LOAD_URL', 'CANCEL_TEMPLATE',
        'RECOVER_TEMPLATE', 'CROSS_RELATE_TEMPLATE', 'DEVICE_OUT_TYPE'
    ]

    # agv_model_init 表的字段（不包含 ID）
    AGV_MODEL_INIT_FIELDS = [
        'SERIES_MODEL_NAME', 'PARENT_ID', 'SERIES_MODEL_TYPE', 'RUN_PARAM',
        'CONFIG_PARAM', 'CREATE_DATE', 'BASE_CONFIG', 'CHARGE_CONFIG', 'DEFAULT_ACTION',
        'ATTACH_PARAM', 'MODEL_TYPE', 'LOGO', 'LOAD_URL', 'CANCEL_TEMPLATE',
        'RECOVER_TEMPLATE', 'CROSS_RELATE_TEMPLATE', 'DEVICE_OUT_TYPE'
    ]

    def __init__(self, source_cfg: DatabaseConfig, target_cfg: DatabaseConfig):
        self.source_cfg = source_cfg
        self.target_cfg = target_cfg

    def _connect_source(self) -> pymysql.Connection:
        """连接源数据库（返回字典游标）"""
        return pymysql.connect(
            host=self.source_cfg.host,
            port=self.source_cfg.port,
            user=self.source_cfg.user,
            password=self.source_cfg.password,
            database=self.source_cfg.database,
            charset=self.source_cfg.charset,
            cursorclass=DictCursor
        )

    def _connect_target(self) -> pymysql.Connection:
        """连接目标数据库（普通游标）"""
        return pymysql.connect(
            host=self.target_cfg.host,
            port=self.target_cfg.port,
            user=self.target_cfg.user,
            password=self.target_cfg.password,
            database=self.target_cfg.database,
            charset=self.target_cfg.charset
        )

    def model_exists_in_target(self, series_model_name: str) -> bool:
        """检查目标库 agv_model 中是否存在指定型号"""
        conn = self._connect_target()
        try:
            with conn.cursor() as cursor:
                sql = "SELECT 1 FROM agv_model WHERE SERIES_MODEL_NAME = %s"
                cursor.execute(sql, (series_model_name,))
                return cursor.fetchone() is not None
        finally:
            conn.close()

    def fetch_source_model(self, series_model_name: str) -> Optional[Dict[str, Any]]:
        """从源库 agv_model 中获取指定型号的数据（包含所有字段）"""
        conn = self._connect_source()
        try:
            with conn.cursor() as cursor:
                sql = "SELECT * FROM agv_model WHERE SERIES_MODEL_NAME = %s"
                cursor.execute(sql, (series_model_name,))
                return cursor.fetchone()
        finally:
            conn.close()

    def insert_into_target_init(self, model_data: Dict[str, Any]) -> bool:
        """
        将型号数据插入目标库 agv_model_init 表（去除 ID 字段）
        返回 True 表示插入成功，False 表示跳过（重复或其他错误）
        """
        # 提取目标字段的值（按 AGV_MODEL_INIT_FIELDS 顺序）
        values = [model_data[field] for field in self.AGV_MODEL_INIT_FIELDS]

        conn = self._connect_target()
        try:
            with conn.cursor() as cursor:
                # 构建 INSERT IGNORE 语句（防止因唯一约束冲突报错）
                fields_str = ', '.join([f'`{f}`' for f in self.AGV_MODEL_INIT_FIELDS])
                placeholders = ', '.join(['%s'] * len(self.AGV_MODEL_INIT_FIELDS))
                sql = f"INSERT IGNORE INTO `agv_model_init` ({fields_str}) VALUES ({placeholders})"

                cursor.execute(sql, values)
                conn.commit()
                # rowcount=1 表示插入成功，0 表示忽略（可能重复）
                return cursor.rowcount == 1
        except Exception as e:
            print(f"插入失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def sync_models(self, model_names: List[str]) -> None:
        """同步多个型号"""
        for name in model_names:
            print(f"\n处理型号: {name}")

            # 1. 检查目标库是否已存在
            if self.model_exists_in_target(name):
                print(f"  → 目标库 agv_model 中已存在型号 '{name}'，跳过")
                continue

            # 2. 从源库获取数据
            source_data = self.fetch_source_model(name)
            if not source_data:
                print(f"  → 源库 agv_model 中未找到型号 '{name}'，跳过")
                continue

            # 3. 插入目标库 agv_model_init
            if self.insert_into_target_init(source_data):
                print(f"  → 成功插入目标库 agv_model_init")
            else:
                print(f"  → 插入失败（可能已存在或数据错误）")


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='同步设备型号数据从源 agv_model 到目标 agv_model_init')
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
    parser.add_argument('--models', required=True, help='需要同步的型号列表，多个用逗号分隔，如 "RTA-C060-LQ-L-410,RTA-C060-Q-2L-410"')
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

    # 解析型号列表
    model_names = [name.strip() for name in args.models.split(',') if name.strip()]
    if not model_names:
        print("未提供有效型号，退出")
        sys.exit(0)

    sync = ModelSync(source_cfg, target_cfg)
    try:
        sync.sync_models(model_names)
    except Exception as e:
        print(f"执行出错: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()