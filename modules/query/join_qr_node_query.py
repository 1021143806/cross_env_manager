#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
join_qr_node_info表查询模块
用于查询和管理wms数据库中的join_qr_node_info表数据
"""

import pymysql
from pymysql.cursors import DictCursor

def get_wms_db_config():
    """获取wms数据库配置"""
    return {
        'host': '10.68.2.32',
        'port': 3306,
        'user': 'wms',
        'password': 'CCshenda889',
        'database': 'wms',
        'charset': 'utf8mb4'
    }

def get_wms_db_connection():
    """获取wms数据库连接"""
    try:
        conn = pymysql.connect(**get_wms_db_config())
        return conn
    except pymysql.Error as e:
        print(f"wms数据库连接错误: {e}")
        return None

def execute_wms_query(query, params=None, fetch=True):
    """执行wms数据库查询"""
    conn = get_wms_db_connection()
    if not conn:
        return None
    
    cursor = None
    try:
        cursor = conn.cursor(DictCursor)
        cursor.execute(query, params or ())
        
        if fetch and query.strip().upper().startswith('SELECT'):
            result = cursor.fetchall()
        elif fetch:
            result = cursor.fetchone()
        else:
            result = cursor.lastrowid
            conn.commit()
        
        return result
    except pymysql.Error as e:
        print(f"wms数据库查询错误: {e}")
        conn.rollback()
        return None
    finally:
        if cursor:
            cursor.close()
        conn.close()

def get_all_join_qr_nodes():
    """获取所有join_qr_node_info记录"""
    query = """
    SELECT id, area_id, type, qr_content, environment_ip, enable, 
           join_area, other_config, last_using_time
    FROM join_qr_node_info
    ORDER BY id
    """
    return execute_wms_query(query)

def get_join_qr_node_by_id(node_id):
    """根据ID获取join_qr_node_info记录"""
    query = """
    SELECT id, area_id, type, qr_content, environment_ip, enable, 
           join_area, other_config, last_using_time
    FROM join_qr_node_info
    WHERE id = %s
    """
    result = execute_wms_query(query, (node_id,))
    if result and isinstance(result, list) and len(result) > 0:
        return result[0]  # 返回第一个（也是唯一一个）记录
    return None

def get_join_qr_nodes_by_area(area_id):
    """根据区域ID获取join_qr_node_info记录"""
    query = """
    SELECT id, area_id, type, qr_content, environment_ip, enable, 
           join_area, other_config, last_using_time
    FROM join_qr_node_info
    WHERE area_id = %s
    ORDER BY id
    """
    return execute_wms_query(query, (area_id,))

def get_join_qr_nodes_by_type(node_type):
    """根据类型获取join_qr_node_info记录"""
    query = """
    SELECT id, area_id, type, qr_content, environment_ip, enable, 
           join_area, other_config, last_using_time
    FROM join_qr_node_info
    WHERE type = %s
    ORDER BY id
    """
    return execute_wms_query(query, (node_type,))

def get_join_qr_nodes_by_ip(ip_address):
    """根据IP地址获取join_qr_node_info记录"""
    query = """
    SELECT id, area_id, type, qr_content, environment_ip, enable, 
           join_area, other_config, last_using_time
    FROM join_qr_node_info
    WHERE environment_ip = %s
    ORDER BY id
    """
    return execute_wms_query(query, (ip_address,))

def search_join_qr_nodes(search_term):
    """搜索join_qr_node_info记录"""
    query = """
    SELECT id, area_id, type, qr_content, environment_ip, enable, 
           join_area, other_config, last_using_time
    FROM join_qr_node_info
    WHERE qr_content LIKE %s 
       OR environment_ip LIKE %s
       OR join_area LIKE %s
    ORDER BY id
    """
    search_pattern = f"%{search_term}%"
    return execute_wms_query(query, (search_pattern, search_pattern, search_pattern))

def insert_join_qr_node(node_data):
    """插入新的join_qr_node_info记录"""
    query = """
    INSERT INTO join_qr_node_info 
    (area_id, type, qr_content, environment_ip, enable, join_area, other_config, last_using_time)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    params = (
        node_data.get('area_id'),
        node_data.get('type'),
        node_data.get('qr_content'),
        node_data.get('environment_ip'),
        node_data.get('enable', 1),
        node_data.get('join_area'),
        node_data.get('other_config'),
        node_data.get('last_using_time')
    )
    
    return execute_wms_query(query, params, fetch=False)

def update_join_qr_node(node_id, node_data):
    """更新join_qr_node_info记录"""
    query = """
    UPDATE join_qr_node_info 
    SET area_id = %s, type = %s, qr_content = %s, environment_ip = %s, 
        enable = %s, join_area = %s, other_config = %s, last_using_time = %s
    WHERE id = %s
    """
    
    params = (
        node_data.get('area_id'),
        node_data.get('type'),
        node_data.get('qr_content'),
        node_data.get('environment_ip'),
        node_data.get('enable', 1),
        node_data.get('join_area'),
        node_data.get('other_config'),
        node_data.get('last_using_time'),
        node_id
    )
    
    return execute_wms_query(query, params, fetch=False)

def delete_join_qr_node(node_id):
    """删除join_qr_node_info记录"""
    query = "DELETE FROM join_qr_node_info WHERE id = %s"
    return execute_wms_query(query, (node_id,), fetch=False)

def get_join_qr_node_stats():
    """获取join_qr_node_info统计信息"""
    stats = {}
    
    # 总记录数
    query = "SELECT COUNT(*) as total FROM join_qr_node_info"
    result = execute_wms_query(query)
    if result and isinstance(result, list) and len(result) > 0:
        stats['total'] = result[0]['total']
    else:
        stats['total'] = 0
    
    # 按类型统计
    query = "SELECT type, COUNT(*) as count FROM join_qr_node_info GROUP BY type"
    result = execute_wms_query(query)
    if result and isinstance(result, list):
        stats['by_type'] = {row['type']: row['count'] for row in result}
    else:
        stats['by_type'] = {}
    
    # 按区域统计
    query = "SELECT area_id, COUNT(*) as count FROM join_qr_node_info GROUP BY area_id"
    result = execute_wms_query(query)
    if result and isinstance(result, list):
        stats['by_area'] = {row['area_id']: row['count'] for row in result}
    else:
        stats['by_area'] = {}
    
    # 按IP统计
    query = "SELECT environment_ip, COUNT(*) as count FROM join_qr_node_info GROUP BY environment_ip"
    result = execute_wms_query(query)
    if result and isinstance(result, list):
        stats['by_ip'] = {row['environment_ip']: row['count'] for row in result}
    else:
        stats['by_ip'] = {}
    
    # 启用/禁用统计
    query = "SELECT enable, COUNT(*) as count FROM join_qr_node_info GROUP BY enable"
    result = execute_wms_query(query)
    if result and isinstance(result, list):
        stats['by_enable'] = {row['enable']: row['count'] for row in result}
    else:
        stats['by_enable'] = {}
    
    return stats

if __name__ == "__main__":
    # 测试代码
    print("测试join_qr_node_info查询模块")
    
    # 测试获取所有记录
    nodes = get_all_join_qr_nodes()
    if nodes and isinstance(nodes, list):
        print(f"总记录数: {len(nodes)}")
    else:
        print("总记录数: 0")
    
    # 测试统计信息
    stats = get_join_qr_node_stats()
    print(f"统计信息: {stats}")
    
    # 测试搜索
    search_result = search_join_qr_nodes("55301540")
    if search_result and isinstance(search_result, list):
        print(f"搜索'55301540'结果数: {len(search_result)}")
    else:
        print("搜索'55301540'结果数: 0")