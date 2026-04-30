#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
货架查询模块
"""

from ..database.helpers import fetch_all, fetch_one

def query_shelf_by_code(shelf_code, use_production=False):
    """
    根据货架代码查询货架信息
    """
    query = """
    SELECT 
        s.*,
        sm.model_name,
        sm.model_code as shelf_model_code,
        sm.max_capacity,
        a.area_name,
        z.zone_name,
        st.type_name as shelf_type_name
    FROM shelf s
    LEFT JOIN shelf_model sm ON s.shelf_model_id = sm.id
    LEFT JOIN area a ON s.area_id = a.id
    LEFT JOIN zone z ON s.zone_id = z.id
    LEFT JOIN shelf_type st ON sm.shelf_type_id = st.id
    WHERE s.shelf_code = %s
    LIMIT 1
    """
    
    return fetch_one(query, (shelf_code,), use_production)

def query_shelves_by_model(shelf_model_id, limit=100, use_production=False):
    """
    根据货架模型查询货架
    """
    query = """
    SELECT 
        s.*,
        sm.model_name,
        sm.model_code as shelf_model_code,
        a.area_name,
        z.zone_name
    FROM shelf s
    LEFT JOIN shelf_model sm ON s.shelf_model_id = sm.id
    LEFT JOIN area a ON s.area_id = a.id
    LEFT JOIN zone z ON s.zone_id = z.id
    WHERE s.shelf_model_id = %s
    ORDER BY s.shelf_code
    LIMIT %s
    """
    
    return fetch_all(query, (shelf_model_id, limit), use_production)

def query_shelves_by_area(area_id, limit=100, use_production=False):
    """
    根据区域查询货架
    """
    query = """
    SELECT 
        s.*,
        sm.model_name,
        sm.model_code as shelf_model_code,
        a.area_name,
        z.zone_name
    FROM shelf s
    LEFT JOIN shelf_model sm ON s.shelf_model_id = sm.id
    LEFT JOIN area a ON s.area_id = a.id
    LEFT JOIN zone z ON s.zone_id = z.id
    WHERE s.area_id = %s
    ORDER BY s.shelf_code
    LIMIT %s
    """
    
    return fetch_all(query, (area_id, limit), use_production)

def query_shelves_by_zone(zone_id, limit=100, use_production=False):
    """
    根据区域查询货架
    """
    query = """
    SELECT 
        s.*,
        sm.model_name,
        sm.model_code as shelf_model_code,
        a.area_name,
        z.zone_name
    FROM shelf s
    LEFT JOIN shelf_model sm ON s.shelf_model_id = sm.id
    LEFT JOIN area a ON s.area_id = a.id
    LEFT JOIN zone z ON s.zone_id = z.id
    WHERE s.zone_id = %s
    ORDER BY s.shelf_code
    LIMIT %s
    """
    
    return fetch_all(query, (zone_id, limit), use_production)

def search_shelves(search_term, limit=100, use_production=False):
    """
    搜索货架
    """
    query = """
    SELECT 
        s.*,
        sm.model_name,
        sm.model_code as shelf_model_code,
        a.area_name,
        z.zone_name
    FROM shelf s
    LEFT JOIN shelf_model sm ON s.shelf_model_id = sm.id
    LEFT JOIN area a ON s.area_id = a.id
    LEFT JOIN zone z ON s.zone_id = z.id
    WHERE s.shelf_code LIKE %s 
       OR s.shelf_name LIKE %s
       OR s.shelf_sn LIKE %s
    ORDER BY s.shelf_code
    LIMIT %s
    """
    
    search_pattern = f"%{search_term}%"
    return fetch_all(query, (search_pattern, search_pattern, search_pattern, limit), use_production)

def get_shelf_status(shelf_id, use_production=False):
    """
    获取货架状态信息
    """
    query = """
    SELECT 
        s.*,
        sm.model_name,
        ss.status_name,
        ss.status_description
    FROM shelf s
    LEFT JOIN shelf_model sm ON s.shelf_model_id = sm.id
    LEFT JOIN shelf_status ss ON s.current_status_id = ss.id
    WHERE s.id = %s
    """
    
    return fetch_one(query, (shelf_id,), use_production)

def get_shelf_statistics(use_production=False):
    """
    获取货架统计信息
    """
    query = """
    SELECT 
        COUNT(*) as total_shelves,
        COUNT(DISTINCT shelf_model_id) as shelf_models,
        COUNT(DISTINCT area_id) as areas_with_shelves,
        COUNT(DISTINCT zone_id) as zones_with_shelves,
        SUM(CASE WHEN is_available = 1 THEN 1 ELSE 0 END) as available_shelves,
        AVG(current_load) as avg_current_load
    FROM shelf
    """
    
    return fetch_one(query, use_production=use_production)