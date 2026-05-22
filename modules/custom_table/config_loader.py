#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定制表配置加载器
解析 config/custom_tables.toml，提供服务器和表配置查询
"""

from __future__ import annotations

import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


class CustomTableConfig:
    """定制表配置管理器（单例）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._config = None
        self._config_path = None
        self._load()

    def _get_config_path(self):
        """获取配置文件路径"""
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'config', 'custom_tables.toml'
        )

    def _load(self):
        """加载配置文件"""
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                print("[CustomTableConfig] 错误: 需要安装 tomli 库")
                self._config = {'servers': []}
                return

        self._config_path = self._get_config_path()
        if not os.path.exists(self._config_path):
            print(f"[CustomTableConfig] 配置文件不存在: {self._config_path}")
            self._config = {'servers': []}
            return

        try:
            with open(self._config_path, 'rb') as f:
                self._config = tomllib.load(f)
            print(f"[CustomTableConfig] 已加载配置: {len(self.get_servers())} 个服务器")
        except Exception as e:
            print(f"[CustomTableConfig] 加载配置失败: {e}")
            self._config = {'servers': []}

    def reload(self):
        """重新加载配置（用于热更新）"""
        self._load()

    def get_servers(self) -> list:
        """获取所有服务器配置"""
        return self._config.get('servers', [])

    def get_server(self, key: str) -> dict | None:
        """根据 key 获取服务器配置"""
        for s in self.get_servers():
            if s.get('key') == key:
                return s
        return None

    def get_tables(self, server_key: str) -> list:
        """获取指定服务器的所有表配置"""
        server = self.get_server(server_key)
        if not server:
            return []
        return server.get('tables', [])

    def get_table(self, server_key: str, table_name: str) -> dict | None:
        """获取指定服务器和表的配置"""
        for t in self.get_tables(server_key):
            if t.get('table_name') == table_name:
                return t
        return None

    def get_db_config(self, server_key: str) -> dict | None:
        """获取数据库连接配置（pymysql 格式）"""
        server = self.get_server(server_key)
        if not server:
            return None
        return {
            'host': server.get('host', 'localhost'),
            'port': int(server.get('port', 3306)),
            'user': server.get('user', 'root'),
            'password': server.get('password', ''),
            'database': server.get('database', ''),
            'charset': server.get('charset', 'utf8mb4'),
        }

    def get_server_summary(self, server_key: str) -> dict | None:
        """获取服务器摘要信息（不含密码）"""
        server = self.get_server(server_key)
        if not server:
            return None
        return {
            'key': server.get('key'),
            'name': server.get('name'),
            'host': server.get('host'),
            'database': server.get('database'),
            'table_count': len(self.get_tables(server_key)),
        }

    def get_all_summaries(self) -> list:
        """获取所有服务器摘要"""
        summaries = []
        for s in self.get_servers():
            tables = s.get('tables', [])
            summaries.append({
                'key': s.get('key'),
                'name': s.get('name'),
                'host': s.get('host'),
                'database': s.get('database'),
                'table_count': len(tables),
                'table_names': [t.get('table_name', '') for t in tables],
            })
        return summaries


# 全局单例
_config_instance = CustomTableConfig()


def get_config() -> CustomTableConfig:
    """获取配置单例"""
    return _config_instance


def reload_config():
    """重新加载配置"""
    _config_instance.reload()
