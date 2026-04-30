#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAO 基类 - 提供通用 CRUD 操作
"""

from modules.database.connection import execute_query


class BaseDAO:
    """DAO 基类 - 所有数据访问对象继承此类"""
    
    def __init__(self, table_name):
        self.table_name = table_name
    
    def get_by_id(self, id):
        result = execute_query(f"SELECT * FROM {self.table_name} WHERE id = %s", (id,))
        return result
    
    def get_all(self, order_by='id DESC', limit=None):
        sql = f"SELECT * FROM {self.table_name} ORDER BY {order_by}"
        if limit:
            sql += f" LIMIT {limit}"
        return execute_query(sql)
    
    def get_by_condition(self, condition, params=None, order_by='id DESC', limit=None):
        sql = f"SELECT * FROM {self.table_name} WHERE {condition} ORDER BY {order_by}"
        if limit:
            sql += f" LIMIT {limit}"
        return execute_query(sql, params)
    
    def insert(self, data):
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['%s'] * len(data))
        sql = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
        return execute_query(sql, tuple(data.values()), fetch=False)
    
    def update(self, id, data):
        set_clause = ', '.join([f"{k} = %s" for k in data.keys()])
        sql = f"UPDATE {self.table_name} SET {set_clause} WHERE id = %s"
        return execute_query(sql, tuple(data.values()) + (id,), fetch=False)
    
    def update_by_condition(self, condition, condition_params, data):
        set_clause = ', '.join([f"{k} = %s" for k in data.keys()])
        sql = f"UPDATE {self.table_name} SET {set_clause} WHERE {condition}"
        return execute_query(sql, tuple(data.values()) + tuple(condition_params), fetch=False)
    
    def delete(self, id):
        return execute_query(f"DELETE FROM {self.table_name} WHERE id = %s", (id,), fetch=False)
    
    def delete_by_condition(self, condition, params=None):
        return execute_query(f"DELETE FROM {self.table_name} WHERE {condition}", params, fetch=False)
    
    def count(self, condition=None, params=None):
        sql = f"SELECT COUNT(*) as count FROM {self.table_name}"
        if condition:
            sql += f" WHERE {condition}"
        result = execute_query(sql, params)
        return result[0]['count'] if result else 0
    
    def exists(self, condition, params=None):
        return self.count(condition, params) > 0
    
    def get_max(self, column, condition=None, params=None):
        sql = f"SELECT MAX({column}) as max_val FROM {self.table_name}"
        if condition:
            sql += f" WHERE {condition}"
        result = execute_query(sql, params)
        return result[0]['max_val'] if result and result[0]['max_val'] is not None else 0
