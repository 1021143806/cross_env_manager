#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨环境模板查询模块
基于agv-task-query的query-cross-model.php功能
"""

from ..database.helpers import fetch_all, fetch_one

def query_cross_model_by_code(model_code, use_production=False):
    """
    根据模板代码查询跨环境模板
    模仿query-cross-model.php的查询逻辑
    """
    query = """
    SELECT 
        cmp.*,
        s.server_name,
        s.server_ip,
        a.area_name,
        env.environment_name,
        u.username as creator_name
    FROM fy_cross_model_process cmp
    LEFT JOIN server s ON cmp.server_id = s.id
    LEFT JOIN area a ON cmp.area_id = a.id
    LEFT JOIN environment env ON cmp.environment_id = env.id
    LEFT JOIN user u ON cmp.creator_id = u.id
    WHERE cmp.model_process_code = %s
    LIMIT 1
    """
    
    return fetch_one(query, (model_code,), use_production)

def query_cross_model_details(model_process_id, use_production=False):
    """
    查询跨环境模板的详细信息
    """
    query = """
    SELECT 
        cmpd.*,
        tt.task_type_name,
        pt.process_type_name,
        jp.join_point_name,
        jp.join_point_code
    FROM fy_cross_model_process_detail cmpd
    LEFT JOIN task_type tt ON cmpd.task_type_id = tt.id
    LEFT JOIN process_type pt ON cmpd.process_type_id = pt.id
    LEFT JOIN join_point jp ON cmpd.join_point_id = jp.id
    WHERE cmpd.model_process_id = %s
    ORDER BY cmpd.task_seq
    """
    
    return fetch_all(query, (model_process_id,), use_production)

def query_cross_models_by_server(server_id, limit=50, use_production=False):
    """
    根据服务器查询跨环境模板
    """
    query = """
    SELECT 
        cmp.*,
        s.server_name,
        s.server_ip,
        a.area_name,
        env.environment_name
    FROM fy_cross_model_process cmp
    LEFT JOIN server s ON cmp.server_id = s.id
    LEFT JOIN area a ON cmp.area_id = a.id
    LEFT JOIN environment env ON cmp.environment_id = env.id
    WHERE cmp.server_id = %s
    ORDER BY cmp.create_time DESC
    LIMIT %s
    """
    
    return fetch_all(query, (server_id, limit), use_production)

def query_cross_models_by_area(area_id, limit=50, use_production=False):
    """
    根据区域查询跨环境模板
    """
    query = """
    SELECT 
        cmp.*,
        s.server_name,
        s.server_ip,
        a.area_name,
        env.environment_name
    FROM fy_cross_model_process cmp
    LEFT JOIN server s ON cmp.server_id = s.id
    LEFT JOIN area a ON cmp.area_id = a.id
    LEFT JOIN environment env ON cmp.environment_id = env.id
    WHERE cmp.area_id = %s
    ORDER BY cmp.create_time DESC
    LIMIT %s
    """
    
    return fetch_all(query, (area_id, limit), use_production)

def query_cross_models_by_environment(environment_id, limit=50, use_production=False):
    """
    根据环境查询跨环境模板
    """
    query = """
    SELECT 
        cmp.*,
        s.server_name,
        s.server_ip,
        a.area_name,
        env.environment_name
    FROM fy_cross_model_process cmp
    LEFT JOIN server s ON cmp.server_id = s.id
    LEFT JOIN area a ON cmp.area_id = a.id
    LEFT JOIN environment env ON cmp.environment_id = env.id
    WHERE cmp.environment_id = %s
    ORDER BY cmp.create_time DESC
    LIMIT %s
    """
    
    return fetch_all(query, (environment_id, limit), use_production)

def search_cross_models(search_term, limit=100, use_production=False):
    """
    搜索跨环境模板
    """
    query = """
    SELECT 
        cmp.*,
        s.server_name,
        s.server_ip,
        a.area_name,
        env.environment_name
    FROM fy_cross_model_process cmp
    LEFT JOIN server s ON cmp.server_id = s.id
    LEFT JOIN area a ON cmp.area_id = a.id
    LEFT JOIN environment env ON cmp.environment_id = env.id
    WHERE cmp.model_process_code LIKE %s 
       OR cmp.model_process_name LIKE %s
       OR cmp.description LIKE %s
    ORDER BY cmp.create_time DESC
    LIMIT %s
    """
    
    search_pattern = f"%{search_term}%"
    return fetch_all(query, (search_pattern, search_pattern, search_pattern, limit), use_production)

def validate_cross_model_configuration(model_process_id, use_production=False):
    """
    验证跨环境模板配置
    检查模板配置的完整性和一致性
    """
    # 获取模板基本信息
    model = query_cross_model_by_id(model_process_id, use_production)
    if not model:
        return {"valid": False, "errors": ["模板不存在"]}
    
    # 获取模板详细信息
    details = query_cross_model_details(model_process_id, use_production)
    
    validation_result = {
        "valid": True,
        "model_id": model_process_id,
        "model_code": model.get('model_process_code'),
        "model_name": model.get('model_process_name'),
        "total_details": len(details),
        "warnings": [],
        "errors": []
    }
    
    # 检查是否有详细信息
    if not details:
        validation_result["warnings"].append("模板没有配置详细信息")
    
    # 检查任务序列是否连续
    task_seqs = [detail.get('task_seq', 0) for detail in details]
    if task_seqs:
        expected_seqs = list(range(1, len(task_seqs) + 1))
        if task_seqs != expected_seqs:
            validation_result["warnings"].append(f"任务序列不连续: {task_seqs}")
    
    # 检查必要的字段
    required_fields = ['task_type_id', 'process_type_id']
    for detail in details:
        for field in required_fields:
            if not detail.get(field):
                validation_result["errors"].append(f"任务序列 {detail.get('task_seq')} 缺少必要字段: {field}")
    
    # 检查交接点配置
    for detail in details:
        if detail.get('join_point_id') and not detail.get('join_point_code'):
            validation_result["warnings"].append(f"任务序列 {detail.get('task_seq')} 配置了交接点ID但未配置交接点代码")
    
    validation_result["valid"] = len(validation_result["errors"]) == 0
    
    return validation_result

def query_cross_model_by_id(model_process_id, use_production=False):
    """
    根据ID查询跨环境模板
    """
    query = """
    SELECT 
        cmp.*,
        s.server_name,
        s.server_ip,
        a.area_name,
        env.environment_name,
        u.username as creator_name
    FROM fy_cross_model_process cmp
    LEFT JOIN server s ON cmp.server_id = s.id
    LEFT JOIN area a ON cmp.area_id = a.id
    LEFT JOIN environment env ON cmp.environment_id = env.id
    LEFT JOIN user u ON cmp.creator_id = u.id
    WHERE cmp.id = %s
    LIMIT 1
    """
    
    return fetch_one(query, (model_process_id,), use_production)