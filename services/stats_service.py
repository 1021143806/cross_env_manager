#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统计服务
"""

from modules.database.connection import execute_query
from middleware.cache import cache


class StatsService:
    """统计服务"""
    
    @cache.cached(timeout=300, key_prefix='stats_overview')
    def get_overview(self):
        """获取系统概览统计（缓存5分钟）"""
        template_stats = execute_query("""
        SELECT COUNT(*) as total_templates,
            SUM(CASE WHEN enable = 1 THEN 1 ELSE 0 END) as enabled_templates,
            SUM(CASE WHEN enable = 0 THEN 1 ELSE 0 END) as disabled_templates,
            COUNT(DISTINCT area_id) as distinct_areas,
            COUNT(DISTINCT target_points_ip) as distinct_servers
        FROM fy_cross_model_process""")
        
        detail_stats = execute_query("""
        SELECT COUNT(*) as total_subtasks,
            COUNT(DISTINCT model_process_id) as templates_with_subtasks,
            COUNT(DISTINCT task_servicec) as distinct_servers,
            COUNT(DISTINCT template_code) as distinct_template_codes
        FROM fy_cross_model_process_detail""")
        
        recent = execute_query("""
        SELECT id, model_process_code, model_process_name, enable
        FROM fy_cross_model_process ORDER BY id DESC LIMIT 5""")
        
        if template_stats and detail_stats:
            return {
                'template_stats': template_stats[0],
                'detail_stats': detail_stats[0],
                'recent_templates': recent or []
            }
        return None
    
    @cache.cached(timeout=300, key_prefix='stats_distribution')
    def get_distribution(self):
        """获取分布统计（缓存5分钟）"""
        enable_dist = execute_query("""
        SELECT enable as status, COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM fy_cross_model_process), 2) as percentage
        FROM fy_cross_model_process GROUP BY enable ORDER BY enable DESC""")
        
        server_dist = execute_query("""
        SELECT target_points_ip as server, COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM fy_cross_model_process), 2) as percentage
        FROM fy_cross_model_process WHERE target_points_ip IS NOT NULL AND target_points_ip != ''
        GROUP BY target_points_ip ORDER BY count DESC""")
        
        return {
            'enable_distribution': enable_dist or [],
            'server_distribution': server_dist or []
        }
    
    @cache.cached(timeout=300, key_prefix='stats_templates_by_server')
    def get_templates_by_server(self):
        """按服务器统计模板（缓存5分钟）"""
        return execute_query("""
        SELECT target_points_ip as server, COUNT(*) as count
        FROM fy_cross_model_process WHERE target_points_ip IS NOT NULL AND target_points_ip != ''
        GROUP BY target_points_ip ORDER BY count DESC""") or []
    
    def get_template_growth(self):
        """模板增长趋势"""
        return execute_query("""
        SELECT DATE(create_time) as date, COUNT(*) as count
        FROM fy_cross_model_process WHERE create_time IS NOT NULL
        GROUP BY DATE(create_time) ORDER BY date DESC LIMIT 30""") or []
    
    def get_detailed_analysis(self):
        """详细分析"""
        area_stats = execute_query("""
        SELECT area_id, COUNT(*) as count,
            SUM(CASE WHEN enable = 1 THEN 1 ELSE 0 END) as enabled,
            SUM(CASE WHEN enable = 0 THEN 1 ELSE 0 END) as disabled
        FROM fy_cross_model_process GROUP BY area_id ORDER BY count DESC""")
        
        capacity_stats = execute_query("""
        SELECT capacity, COUNT(*) as count
        FROM fy_cross_model_process WHERE capacity > 0
        GROUP BY capacity ORDER BY capacity""")
        
        return {
            'area_stats': area_stats or [],
            'capacity_stats': capacity_stats or []
        }
    
    def get_main_task_status(self):
        """大模板状态分布（当天）"""
        return execute_query("""
        SELECT task_status, COUNT(*) as count
        FROM fy_cross_task WHERE DATE(create_time) = CURDATE()
        GROUP BY task_status ORDER BY task_status""") or []
