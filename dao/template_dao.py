#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模板 DAO - fy_cross_model_process 表操作
"""

from dao import BaseDAO


class TemplateDAO(BaseDAO):
    """跨环境任务模板主表 DAO"""
    
    def __init__(self):
        super().__init__('fy_cross_model_process')
    
    def search_by_code(self, search_term):
        """模糊搜索模板代码"""
        return self.get_by_condition(
            'model_process_code LIKE %s',
            (f'%{search_term}%',)
        )
    
    def search_by_code_or_name(self, search_term, limit=10):
        """模糊搜索模板代码或名称"""
        return self.get_by_condition(
            'model_process_code LIKE %s OR model_process_name LIKE %s',
            (f'%{search_term}%', f'%{search_term}%'),
            limit=limit
        )
    
    def get_by_code(self, code):
        """根据模板代码精确查询"""
        return self.get_by_condition('model_process_code = %s', (code,))
    
    def get_enabled(self):
        """获取所有启用的模板"""
        return self.get_by_condition('enable = 1')
    
    def get_by_area(self, area_id):
        """根据区域ID查询"""
        return self.get_by_condition('area_id = %s', (area_id,))
    
    def get_by_server(self, server_ip):
        """根据目标服务器IP查询"""
        return self.get_by_condition('target_points_ip = %s', (server_ip,))
    
    def get_stats(self):
        """获取模板统计信息"""
        sql = """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN enable = 1 THEN 1 ELSE 0 END) as enabled,
            SUM(CASE WHEN enable = 0 THEN 1 ELSE 0 END) as disabled,
            COUNT(DISTINCT area_id) as areas,
            COUNT(DISTINCT target_points_ip) as servers
        FROM fy_cross_model_process
        """
        from modules.database.connection import execute_query
        result = execute_query(sql)
        return result[0] if result else None
    
    def get_recent(self, limit=5):
        """获取最近创建的模板"""
        return self.get_all(order_by='id DESC', limit=limit)
    
    def get_next_id(self):
        """获取下一个可用的数据库ID"""
        return self.get_max('id') + 1
