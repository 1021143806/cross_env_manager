#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库帮助函数模块
模仿agv-task-query的SQL帮助函数
"""

from .connection import execute_query, get_production_db_config, get_test_db_config

def fetch_all(query, params=None, use_production=False):
    """
    获取所有结果
    模仿agv-task-query的fetchAll函数
    """
    config = get_production_db_config() if use_production else None
    return execute_query(query, params, fetch=True, config=config)

def fetch_one(query, params=None, use_production=False):
    """
    获取单行结果
    模仿agv-task-query的fetchOne函数
    """
    config = get_production_db_config() if use_production else None
    result = execute_query(query, params, fetch=True, config=config)
    return result[0] if result else None

def execute(query, params=None, use_production=False):
    """
    执行非查询语句
    模仿agv-task-query的execute函数
    """
    config = get_production_db_config() if use_production else None
    return execute_query(query, params, fetch=False, config=config)

def get_last_insert_id(use_production=False):
    """
    获取最后插入的ID
    """
    config = get_production_db_config() if use_production else None
    result = execute_query("SELECT LAST_INSERT_ID() as id", fetch=True, config=config)
    return result[0]['id'] if result else None

def escape_string(value):
    """
    转义字符串（简单实现）
    注意：在实际使用中应该使用参数化查询而不是字符串转义
    """
    if value is None:
        return None
    return str(value).replace("'", "''").replace('"', '""')

def build_in_condition(field, values):
    """
    构建IN条件
    :param field: 字段名
    :param values: 值列表
    :return: (sql片段, 参数列表)
    """
    if not values:
        return ("1=0", [])  # 空列表返回假条件
    
    placeholders = ','.join(['%s'] * len(values))
    return (f"{field} IN ({placeholders})", values)

def build_like_condition(field, value, exact=False):
    """
    构建LIKE条件
    :param field: 字段名
    :param value: 搜索值
    :param exact: 是否精确匹配（False时使用%value%）
    :return: (sql片段, 参数)
    """
    if exact:
        return (f"{field} = %s", value)
    else:
        return (f"{field} LIKE %s", f"%{value}%")

def paginate_query(query, params=None, page=1, per_page=20, use_production=False):
    """
    分页查询
    :param query: 基础查询语句（不带LIMIT）
    :param params: 查询参数
    :param page: 页码（从1开始）
    :param per_page: 每页数量
    :param use_production: 是否使用生产环境数据库
    :return: (分页数据, 总数量)
    """
    # 计算偏移量
    offset = (page - 1) * per_page
    
    # 获取总数
    count_query = f"SELECT COUNT(*) as total FROM ({query}) as subquery"
    total_result = fetch_one(count_query, params, use_production)
    total = total_result['total'] if total_result else 0
    
    # 获取分页数据
    paginated_query = f"{query} LIMIT {per_page} OFFSET {offset}"
    data = fetch_all(paginated_query, params, use_production)
    
    return data, total