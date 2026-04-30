#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AGV状态查询模块
基于agv-task-query的agv-status.php功能
"""

from ..database.helpers import fetch_all, fetch_one

def query_agv_status_by_code(agv_code, use_production=False):
    """
    根据AGV代码查询AGV状态
    """
    query = """
    SELECT 
        a.*,
        at.type_name as agv_type_name,
        am.model_name as agv_model_name,
        ast.status_name as current_status_name,
        ast.status_description,
        b.battery_level,
        b.battery_health,
        b.last_charge_time
    FROM agv_robot a
    LEFT JOIN agv_type at ON a.agv_type_id = at.id
    LEFT JOIN agv_model am ON a.agv_model_id = am.id
    LEFT JOIN agv_status ast ON a.current_status_id = ast.id
    LEFT JOIN agv_battery b ON a.id = b.agv_robot_id
    WHERE a.robot_code = %s
    LIMIT 1
    """
    
    return fetch_one(query, (agv_code,), use_production)

def query_all_agv_status(limit=100, use_production=False):
    """
    查询所有AGV状态
    """
    query = """
    SELECT 
        a.*,
        at.type_name as agv_type_name,
        am.model_name as agv_model_name,
        ast.status_name as current_status_name,
        TIMESTAMPDIFF(MINUTE, a.last_heartbeat_time, NOW()) as minutes_since_last_heartbeat
    FROM agv_robot a
    LEFT JOIN agv_type at ON a.agv_type_id = at.id
    LEFT JOIN agv_model am ON a.agv_model_id = am.id
    LEFT JOIN agv_status ast ON a.current_status_id = ast.id
    ORDER BY a.is_online DESC, a.last_heartbeat_time DESC
    LIMIT %s
    """
    
    return fetch_all(query, (limit,), use_production)

def query_online_agvs(use_production=False):
    """
    查询在线AGV
    """
    query = """
    SELECT 
        a.*,
        at.type_name as agv_type_name,
        am.model_name as agv_model_name,
        ast.status_name as current_status_name
    FROM agv_robot a
    LEFT JOIN agv_type at ON a.agv_type_id = at.id
    LEFT JOIN agv_model am ON a.agv_model_id = am.id
    LEFT JOIN agv_status ast ON a.current_status_id = ast.id
    WHERE a.is_online = 1 
      AND TIMESTAMPDIFF(MINUTE, a.last_heartbeat_time, NOW()) < 5
    ORDER BY a.last_heartbeat_time DESC
    """
    
    return fetch_all(query, use_production=use_production)

def query_agv_status_history(agv_id, limit=100, use_production=False):
    """
    查询AGV状态历史记录
    """
    query = """
    SELECT 
        ash.*,
        ast.status_name,
        ast.status_description
    FROM agv_status_history ash
    LEFT JOIN agv_status_type ast ON ash.status_type_id = ast.id
    WHERE ash.agv_robot_id = %s
    ORDER BY ash.status_time DESC
    LIMIT %s
    """
    
    return fetch_all(query, (agv_id, limit), use_production)

def query_agv_tasks(agv_id, limit=50, use_production=False):
    """
    查询AGV的最近任务
    """
    query = """
    SELECT 
        t.*,
        tg.group_name,
        s.shelf_name,
        s.shelf_code
    FROM fy_cross_task t
    LEFT JOIN task_group tg ON t.task_group_id = tg.id
    LEFT JOIN shelf s ON t.shelf_id = s.id
    WHERE t.agv_robot_id = %s
    ORDER BY t.create_time DESC
    LIMIT %s
    """
    
    return fetch_all(query, (agv_id, limit), use_production)

def query_agv_battery_info(agv_id, use_production=False):
    """
    查询AGV电池信息
    """
    query = """
    SELECT 
        b.*,
        bt.battery_type_name,
        bh.health_status,
        bh.last_check_time
    FROM agv_battery b
    LEFT JOIN battery_type bt ON b.battery_type_id = bt.id
    LEFT JOIN battery_health bh ON b.battery_health_id = bh.id
    WHERE b.agv_robot_id = %s
    ORDER BY b.last_charge_time DESC
    LIMIT 1
    """
    
    return fetch_one(query, (agv_id,), use_production)

def query_agv_maintenance_records(agv_id, limit=50, use_production=False):
    """
    查询AGV维护记录
    """
    query = """
    SELECT 
        amr.*,
        mt.maintenance_type_name,
        u.username as maintenance_person
    FROM agv_maintenance_record amr
    LEFT JOIN maintenance_type mt ON amr.maintenance_type_id = mt.id
    LEFT JOIN user u ON amr.maintenance_person_id = u.id
    WHERE amr.agv_robot_id = %s
    ORDER BY amr.maintenance_time DESC
    LIMIT %s
    """
    
    return fetch_all(query, (agv_id, limit), use_production)

def get_agv_statistics(use_production=False):
    """
    获取AGV统计信息
    """
    query = """
    SELECT 
        COUNT(*) as total_agvs,
        SUM(CASE WHEN is_online = 1 THEN 1 ELSE 0 END) as online_agvs,
        COUNT(DISTINCT agv_type_id) as agv_types,
        COUNT(DISTINCT agv_model_id) as agv_models,
        AVG(battery_level) as avg_battery_level,
        MIN(create_time) as first_created,
        MAX(create_time) as last_created
    FROM agv_robot a
    LEFT JOIN agv_battery b ON a.id = b.agv_robot_id
    """
    
    return fetch_one(query, use_production=use_production)