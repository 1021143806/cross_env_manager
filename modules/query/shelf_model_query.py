#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
货架模型查询模块
"""

from ..database.helpers import fetch_all, fetch_one

def query_shelf_model_by_code(model_code, use_production=False):
    """
    根据货架模型代码查询货架模型信息
    """
    query = """
    SELECT 
        sm.*,
        st.type_name as shelf_type_name,
        mf.manufacturer_name
    FROM shelf_model sm
    LEFT JOIN shelf_type st ON sm.shelf_type_id = st.id
    LEFT JOIN manufacturer mf ON sm.manufacturer_id = mf.id
    WHERE sm.model_code = %s
    LIMIT 1
    """
    
    return fetch_one(query, (model_code,), use_production)

def query_shelf_models_by_type(shelf_type_id, use_production=False):
    """
    根据货架类型查询货架模型
    """
    query = """
    SELECT 
        sm.*,
        st.type_name as shelf_type_name,
        mf.manufacturer_name
    FROM shelf_model sm
    LEFT JOIN shelf_type st ON sm.shelf_type_id = st.id
    LEFT JOIN manufacturer mf ON sm.manufacturer_id = mf.id
    WHERE sm.shelf_type_id = %s
    ORDER BY sm.model_code
    """
    
    return fetch_all(query, (shelf_type_id,), use_production)

def query_shelf_models_by_manufacturer(manufacturer_id, use_production=False):
    """
    根据制造商查询货架模型
    """
    query = """
    SELECT 
        sm.*,
        st.type_name as shelf_type_name,
        mf.manufacturer_name
    FROM shelf_model sm
    LEFT JOIN shelf_type st ON sm.shelf_type_id = st.id
    LEFT JOIN manufacturer mf ON sm.manufacturer_id = mf.id
    WHERE sm.manufacturer_id = %s
    ORDER BY sm.model_code
    """
    
    return fetch_all(query, (manufacturer_id,), use_production)

def search_shelf_models(search_term, limit=100, use_production=False):
    """
    搜索货架模型
    """
    query = """
    SELECT 
        sm.*,
        st.type_name as shelf_type_name,
        mf.manufacturer_name
    FROM shelf_model sm
    LEFT JOIN shelf_type st ON sm.shelf_type_id = st.id
    LEFT JOIN manufacturer mf ON sm.manufacturer_id = mf.id
    WHERE sm.model_code LIKE %s 
       OR sm.model_name LIKE %s
       OR sm.description LIKE %s
    ORDER BY sm.model_code
    LIMIT %s
    """
    
    search_pattern = f"%{search_term}%"
    return fetch_all(query, (search_pattern, search_pattern, search_pattern, limit), use_production)

def get_shelf_model_statistics(use_production=False):
    """
    获取货架模型统计信息
    """
    query = """
    SELECT 
        COUNT(*) as total_models,
        COUNT(DISTINCT shelf_type_id) as shelf_types,
        COUNT(DISTINCT manufacturer_id) as manufacturers,
        AVG(max_capacity) as avg_max_capacity,
        MIN(create_time) as first_created,
        MAX(create_time) as last_created
    FROM shelf_model
    """
    
    return fetch_one(query, use_production=use_production)