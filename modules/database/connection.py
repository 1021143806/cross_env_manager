#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库连接池管理模块
基于 DBUtils.PooledDB 实现连接池，替代每次请求创建/关闭连接的模式

使用方式:
    from modules.database.connection import DatabasePool, get_db_connection, execute_query
    
    # 应用启动时初始化连接池
    pool = DatabasePool()
    pool.init_pool(config)
    
    # 获取连接（兼容旧接口）
    conn = get_db_connection()
"""

import pymysql
from pymysql.cursors import DictCursor
from dbutils.pooled_db import PooledDB
import os
import sys
import threading

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


class DatabasePool:
    """
    数据库连接池单例 - 线程安全
    
    特性:
    - 自动检测连接有效性 (ping=1)
    - 连接耗尽时阻塞等待 (blocking=True)
    - 支持多数据库配置
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._pool = None
            self._config = None
            self._initialized = True
    
    def init_pool(self, config):
        """
        初始化连接池
        
        :param config: 数据库配置字典，包含 host, port, user, password, database, charset
        """
        self._config = config.copy()
        pool_config = {
            'creator': pymysql,
            'maxconnections': config.get('maxconnections', 10),
            'mincached': config.get('mincached', 1),
            'maxcached': config.get('maxcached', 3),
            'maxshared': config.get('maxshared', 0),
            'blocking': config.get('blocking', True),
            'maxusage': config.get('maxusage', 0),
            'ping': config.get('ping', 1),
            'host': config.get('host', 'localhost'),
            'port': int(config.get('port', 3306)),
            'user': config.get('user', 'root'),
            'password': config.get('password', ''),
            'database': config.get('database', config.get('name', 'agv_cross_env_test')),
            'charset': config.get('charset', 'utf8mb4'),
            'cursorclass': DictCursor,
        }
        self._pool = PooledDB(**pool_config)
        print(f"[DatabasePool] 连接池初始化: max={pool_config['maxconnections']}, "
              f"min_cached={pool_config['mincached']}, max_cached={pool_config['maxcached']}")
    
    def get_conn(self):
        """从连接池获取连接"""
        if self._pool is None:
            raise RuntimeError("连接池未初始化，请先调用 init_pool()")
        return self._pool.connection()
    
    def close_all(self):
        """关闭所有连接"""
        if self._pool:
            self._pool.close()
            print("[DatabasePool] 连接池已关闭")
    
    @property
    def is_initialized(self):
        return self._pool is not None
    
    @property
    def config(self):
        if self._config:
            safe = self._config.copy()
            safe.pop('password', None)
            return safe
        return None


# ============================================================================
# 全局连接池实例
# ============================================================================
_pool_instance = DatabasePool()


def get_db_config(config_path=None):
    """
    获取数据库配置（兼容旧接口）
    从config/env.toml或环境变量读取配置
    """
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            print("[DatabasePool] 错误: 需要安装 tomli 库")
            raise
    
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'config', 'env.toml'
        )
    
    if not os.path.exists(config_path):
        print(f"[DatabasePool] 配置文件不存在: {config_path}，使用默认配置")
        return get_default_db_config()
    
    try:
        with open(config_path, 'rb') as f:
            config = tomllib.load(f)
        db_config = config.get('database', {})
        return {
            'host': db_config.get('host') or os.getenv('DB_HOST') or 'localhost',
            'port': int(db_config.get('port') or os.getenv('DB_PORT') or 3306),
            'user': db_config.get('user') or os.getenv('DB_USER') or 'root',
            'password': db_config.get('password') or os.getenv('DB_PASSWORD') or '',
            'database': db_config.get('name') or os.getenv('DB_NAME') or 'agv_cross_env_test',
            'charset': db_config.get('charset') or os.getenv('DB_CHARSET') or 'utf8mb4',
        }
    except Exception as e:
        print(f"[DatabasePool] 读取配置文件失败: {e}，使用默认配置")
        return get_default_db_config()


def get_default_db_config():
    """获取默认数据库配置"""
    return {
        'host': 'localhost', 'port': 3306, 'user': 'root',
        'password': '', 'database': 'agv_cross_env_test', 'charset': 'utf8mb4',
    }


def get_db_connection(config=None):
    """
    获取数据库连接（兼容旧接口）
    优先使用连接池，如果连接池未初始化则回退到直接连接
    
    :param config: 可选的数据库配置，如果为None则使用默认配置
    :return: 数据库连接对象或None
    """
    # 如果传入了自定义config，直接创建连接（不使用连接池）
    if config is not None:
        try:
            conn = pymysql.connect(**config, cursorclass=DictCursor)
            return conn
        except pymysql.Error as e:
            print(f"数据库连接错误: {e}")
            return None
    
    # 优先使用连接池
    try:
        if _pool_instance.is_initialized:
            return _pool_instance.get_conn()
    except Exception as e:
        print(f"[DatabasePool] 从连接池获取连接失败: {e}")
    
    # 回退：直接创建连接
    try:
        config = get_db_config()
        conn = pymysql.connect(**config, cursorclass=DictCursor)
        return conn
    except pymysql.Error as e:
        print(f"数据库连接错误: {e}")
        return None


def execute_query(query, params=None, fetch=True, config=None):
    """
    执行SQL查询（兼容旧接口）
    
    :param query: SQL查询语句
    :param params: 查询参数
    :param fetch: 是否获取结果（用于SELECT查询）
    :param config: 可选的数据库配置
    :return: 查询结果或None
    """
    conn = get_db_connection(config)
    if not conn:
        return None
    
    cursor = None
    try:
        cursor = conn.cursor(DictCursor)
        cursor.execute(query, params or ())
        
        if fetch:
            if query.strip().upper().startswith('SELECT'):
                result = cursor.fetchall()
            else:
                result = []
        else:
            conn.commit()
            result = cursor.lastrowid if query.strip().upper().startswith('INSERT') else cursor.rowcount
        
        return result
    except pymysql.Error as e:
        print(f"查询执行错误: {e}")
        conn.rollback()
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def get_production_db_config():
    """获取生产环境数据库配置（只读）"""
    return {
        'host': '10.68.2.32', 'port': 3306, 'user': 'wms',
        'password': 'CCshenda889', 'database': 'wms', 'charset': 'utf8mb4'
    }


def get_test_db_config():
    """获取测试环境数据库配置"""
    return {
        'host': '47.98.244.173', 'port': 53308, 'user': 'root',
        'password': 'Qq13235202993', 'database': 'ds', 'charset': 'utf8mb4'
    }