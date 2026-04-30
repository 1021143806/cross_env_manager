#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交接点查询模块
"""

from ..database.helpers import fetch_all, fetch_one

def query_join_point_by_code(join_point_code, use_production=False):
    """
    根据交接点代码查询交接点信息
    """
    query = """
    SELECT 
        jp.*,
        a.area_name,
        z.zone_name,
        lt.location_type_name
    FROM join_point jp
    LEFT JOIN area a ON jp.area_id = a.id
    LEFT JOIN zone z ON jp.zone_id = z.id
    LEFT JOIN location_type lt ON jp.location_type_id = lt.id
    WHERE jp.join_point_code = %s
    LIMIT 1
    """
    
    return fetch_one(query, (join_point_code,), use_production)

def query_join_points_by_area(area_id, use_production=False):
    """
    根据区域查询交接点
    """
    query = """
    SELECT 
        jp.*,
        a.area_name,
        z.zone_name
    FROM join_point jp
    LEFT JOIN area a ON jp.area_id = a.id
    LEFT JOIN zone z ON jp.zone_id = z.id
    WHERE jp.area_id = %s
    ORDER BY jp.join_point_code
    """
    
    return fetch_all(query, (area_id,), use_production)

def query_join_points_by_zone(zone_id, use_production=False):
    """
    根据区域查询交接点
    """
    query = """
    SELECT 
        jp.*,
        a.area_name,
        z.zone_name
    FROM join_point jp
    LEFT JOIN area a ON jp.area_id = a.id
    LEFT JOIN zone z ON jp.zone_id = z.id
    WHERE jp.zone_id = %s
    ORDER BY jp.join_point_code
    """
    
    return fetch_all(query, (zone_id,), use_production)

def search_join_points(search_term, limit=100, use_production=False):
    """
    搜索交接点
    """
    query = """
    SELECT 
        jp.*,
        a.area_name,
        z.zone_name
    FROM join_point jp
    LEFT JOIN area a ON jp.area_id = a.id
    LEFT JOIN zone z ON jp.zone_id = z.id
    WHERE jp.join_point_code LIKE %s 
       OR jp.join_point_name LIKE %s
       OR jp.description LIKE %s
    ORDER BY jp.join_point_code
    LIMIT %s
    """
    
    search_pattern = f"%{search_term}%"
    return fetch_all(query, (search_pattern, search_pattern, search_pattern, limit), use_production)

def get_join_point_statistics(use_production=False):
    """
    获取交接点统计信息
    """
    query = """
    SELECT 
        COUNT(*) as total_join_points,
        COUNT(DISTINCT area_id) as areas_with_join_points,
        COUNT(DISTINCT zone_id) as zones_with_join_points,
        AVG(x_coordinate) as avg_x,
        AVG(y_coordinate) as avg_y,
        MIN(create_time) as first_created,
        MAX(create_time) as last_created
    FROM join_point
    """
    
    return fetch_one(query, use_production=use_production)