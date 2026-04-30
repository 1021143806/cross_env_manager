#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务查询模块
基于agv-task-query的find-task.php功能
"""

from ..database.helpers import fetch_all, fetch_one

def query_task_by_number(task_number, use_production=False):
    """
    根据任务单号查询任务信息
    模仿find-task.php的查询逻辑
    """
    query = """
    SELECT 
        t.*,
        tg.group_name,
        a.robot_name,
        a.robot_code,
        s.shelf_name,
        s.shelf_code,
        sm.model_name,
        sm.model_code
    FROM fy_cross_task t
    LEFT JOIN task_group tg ON t.task_group_id = tg.id
    LEFT JOIN agv_robot a ON t.agv_robot_id = a.id
    LEFT JOIN shelf s ON t.shelf_id = s.id
    LEFT JOIN shelf_model sm ON s.shelf_model_id = sm.id
    WHERE t.task_number = %s
    ORDER BY t.create_time DESC
    LIMIT 1
    """
    
    return fetch_one(query, (task_number,), use_production)

def query_task_by_id(task_id, use_production=False):
    """
    根据任务ID查询任务信息
    """
    query = """
    SELECT 
        t.*,
        tg.group_name,
        a.robot_name,
        a.robot_code,
        s.shelf_name,
        s.shelf_code,
        sm.model_name,
        sm.model_code
    FROM fy_cross_task t
    LEFT JOIN task_group tg ON t.task_group_id = tg.id
    LEFT JOIN agv_robot a ON t.agv_robot_id = a.id
    LEFT JOIN shelf s ON t.shelf_id = s.id
    LEFT JOIN shelf_model sm ON s.shelf_model_id = sm.id
    WHERE t.id = %s
    """
    
    return fetch_one(query, (task_id,), use_production)

def query_tasks_by_agv(agv_code, limit=50, use_production=False):
    """
    根据AGV编码查询相关任务
    """
    query = """
    SELECT 
        t.*,
        tg.group_name,
        a.robot_name,
        a.robot_code,
        s.shelf_name,
        s.shelf_code,
        sm.model_name,
        sm.model_code
    FROM fy_cross_task t
    LEFT JOIN task_group tg ON t.task_group_id = tg.id
    LEFT JOIN agv_robot a ON t.agv_robot_id = a.id
    LEFT JOIN shelf s ON t.shelf_id = s.id
    LEFT JOIN shelf_model sm ON s.shelf_model_id = sm.id
    WHERE a.robot_code = %s
    ORDER BY t.create_time DESC
    LIMIT %s
    """
    
    return fetch_all(query, (agv_code, limit), use_production)

def query_tasks_by_shelf(shelf_code, limit=50, use_production=False):
    """
    根据货架编码查询相关任务
    """
    query = """
    SELECT 
        t.*,
        tg.group_name,
        a.robot_name,
        a.robot_code,
        s.shelf_name,
        s.shelf_code,
        sm.model_name,
        sm.model_code
    FROM fy_cross_task t
    LEFT JOIN task_group tg ON t.task_group_id = tg.id
    LEFT JOIN agv_robot a ON t.agv_robot_id = a.id
    LEFT JOIN shelf s ON t.shelf_id = s.id
    LEFT JOIN shelf_model sm ON s.shelf_model_id = sm.id
    WHERE s.shelf_code = %s
    ORDER BY t.create_time DESC
    LIMIT %s
    """
    
    return fetch_all(query, (shelf_code, limit), use_production)

def query_recent_tasks(limit=100, use_production=False):
    """
    查询最近的任务
    """
    query = """
    SELECT 
        t.*,
        tg.group_name,
        a.robot_name,
        a.robot_code,
        s.shelf_name,
        s.shelf_code,
        sm.model_name,
        sm.model_code
    FROM fy_cross_task t
    LEFT JOIN task_group tg ON t.task_group_id = tg.id
    LEFT JOIN agv_robot a ON t.agv_robot_id = a.id
    LEFT JOIN shelf s ON t.shelf_id = s.id
    LEFT JOIN shelf_model sm ON s.shelf_model_id = sm.id
    ORDER BY t.create_time DESC
    LIMIT %s
    """
    
    return fetch_all(query, (limit,), use_production)

def query_task_statistics(time_range='today', use_production=False):
    """
    查询任务统计信息
    :param time_range: 时间范围，可选值：today, yesterday, week, month
    """
    time_conditions = {
        'today': "DATE(t.create_time) = CURDATE()",
        'yesterday': "DATE(t.create_time) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)",
        'week': "t.create_time >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)",
        'month': "t.create_time >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)"
    }
    
    condition = time_conditions.get(time_range, "DATE(t.create_time) = CURDATE()")
    
    query = f"""
    SELECT 
        COUNT(*) as total_tasks,
        COUNT(DISTINCT t.agv_robot_id) as unique_agvs,
        COUNT(DISTINCT t.shelf_id) as unique_shelves,
        SUM(CASE WHEN t.task_status = 'completed' THEN 1 ELSE 0 END) as completed_tasks,
        SUM(CASE WHEN t.task_status = 'failed' THEN 1 ELSE 0 END) as failed_tasks,
        AVG(t.execution_time) as avg_execution_time
    FROM fy_cross_task t
    WHERE {condition}
    """
    
    return fetch_one(query, use_production=use_production)