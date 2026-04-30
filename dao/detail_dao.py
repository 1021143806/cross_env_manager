#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
子任务 DAO - fy_cross_model_process_detail 表操作
"""

from dao import BaseDAO


class DetailDAO(BaseDAO):
    """跨环境子任务模板明细表 DAO"""
    
    def __init__(self):
        super().__init__('fy_cross_model_process_detail')
    
    def get_by_model_id(self, model_process_id, order_by='task_seq'):
        """根据主模板ID获取所有子任务"""
        return self.get_by_condition(
            'model_process_id = %s',
            (model_process_id,),
            order_by=order_by
        )
    
    def get_max_seq(self, model_process_id):
        """获取指定模板的最大task_seq"""
        return self.get_max('task_seq', 'model_process_id = %s', (model_process_id,))
    
    def delete_by_model_id(self, model_process_id):
        """删除指定模板的所有子任务"""
        return self.delete_by_condition('model_process_id = %s', (model_process_id,))
    
    def update_seq(self, detail_id, model_process_id, task_seq):
        """更新子任务顺序"""
        return self.update_by_condition(
            'id = %s AND model_process_id = %s',
            (detail_id, model_process_id),
            {'task_seq': task_seq}
        )
    
    def verify_belongs_to(self, detail_id, model_process_id):
        """验证子任务是否属于指定模板"""
        return self.exists('id = %s AND model_process_id = %s', (detail_id, model_process_id))
    
    def count_by_model_id(self, model_process_id):
        """统计指定模板的子任务数量"""
        return self.count('model_process_id = %s', (model_process_id,))
    
    def get_stats(self):
        """获取子任务统计信息"""
        sql = """
        SELECT 
            COUNT(*) as total,
            COUNT(DISTINCT model_process_id) as templates_with_subtasks,
            COUNT(DISTINCT task_servicec) as distinct_servers,
            COUNT(DISTINCT template_code) as distinct_codes
        FROM fy_cross_model_process_detail
        """
        from modules.database.connection import execute_query
        result = execute_query(sql)
        return result[0] if result else None
