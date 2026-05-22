#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定制表通用 CRUD 服务
基于配置动态生成 SQL，支持任意表结构的增删改查
"""

from __future__ import annotations

import pymysql
from pymysql.cursors import DictCursor
import csv
import io
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


class CustomTableService:
    """通用表 CRUD 服务"""

    def __init__(self, db_config: dict, table_config: dict):
        """
        :param db_config: 数据库连接配置
        :param table_config: 表配置（来自 custom_tables.toml）
        """
        self._db_config = db_config
        self._table_config = table_config
        self._table_name = table_config['table_name']
        self._primary_key = table_config.get('primary_key', 'id')
        self._columns = table_config.get('columns', [])
        self._editable_fields = [
            c['field'] for c in self._columns
            if not c.get('readonly', False)
        ]
        self._all_fields = [c['field'] for c in self._columns]

    def _get_conn(self):
        """获取数据库连接"""
        return pymysql.connect(**self._db_config, cursorclass=DictCursor)

    def _validate_fields(self, data: dict) -> list:
        """校验字段，返回错误列表"""
        errors = []
        for col in self._columns:
            field = col['field']
            if col.get('required') and field in data:
                if data[field] is None or str(data[field]).strip() == '':
                    errors.append(f"{col.get('label', field)} 不能为空")
        return errors

    def _build_where(self, search: str = None, search_field: str = None) -> tuple:
        """构建 WHERE 子句"""
        where_parts = []
        params = []

        if search and search_field:
            where_parts.append(f"`{search_field}` LIKE %s")
            params.append(f"%{search}%")
        elif search:
            # 全局搜索：在所有文本字段中搜索
            text_fields = [
                c['field'] for c in self._columns
                if c.get('type') == 'text'
            ]
            if text_fields:
                like_parts = [f"`{f}` LIKE %s" for f in text_fields]
                where_parts.append(f"({' OR '.join(like_parts)})")
                params.extend([f"%{search}%"] * len(text_fields))

        where_clause = ' AND '.join(where_parts) if where_parts else '1=1'
        return where_clause, params

    def query_rows(
        self,
        page: int = 1,
        page_size: int = 25,
        search: str = None,
        search_field: str = None,
        order_by: str = None,
        order_dir: str = 'asc',
        group_by: str = None,
    ) -> dict:
        """
        分页查询表数据
        返回: { rows, total, page, page_size, total_pages, groups }
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            where_clause, params = self._build_where(search, search_field)

            # 查询总数
            count_sql = f"SELECT COUNT(*) as cnt FROM `{self._table_name}` WHERE {where_clause}"
            cursor.execute(count_sql, params)
            total = cursor.fetchone()['cnt']

            # 排序
            pk = self._primary_key
            order_field = order_by if order_by and order_by in self._all_fields else pk
            order_dir = 'DESC' if order_dir.upper() == 'DESC' else 'ASC'

            # 分页查询
            offset = (page - 1) * page_size
            fields_str = ', '.join([f"`{f}`" for f in self._all_fields])
            query_sql = (
                f"SELECT {fields_str} FROM `{self._table_name}` "
                f"WHERE {where_clause} "
                f"ORDER BY `{order_field}` {order_dir} "
                f"LIMIT %s OFFSET %s"
            )
            cursor.execute(query_sql, params + [page_size, offset])
            rows = cursor.fetchall()

            # 分组信息
            groups = None
            if group_by and group_by in self._all_fields:
                group_sql = (
                    f"SELECT `{group_by}` as _group, COUNT(*) as _count "
                    f"FROM `{self._table_name}` "
                    f"WHERE {where_clause} "
                    f"GROUP BY `{group_by}` "
                    f"ORDER BY `{group_by}`"
                )
                cursor.execute(group_sql, params)
                groups = cursor.fetchall()

            total_pages = max(1, (total + page_size - 1) // page_size)

            return {
                'rows': rows,
                'total': total,
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages,
                'groups': groups,
            }
        finally:
            cursor.close()
            conn.close()

    def get_row(self, pk_value) -> dict | None:
        """获取单行数据"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            fields_str = ', '.join([f"`{f}`" for f in self._all_fields])
            sql = f"SELECT {fields_str} FROM `{self._table_name}` WHERE `{self._primary_key}` = %s"
            cursor.execute(sql, (pk_value,))
            return cursor.fetchone()
        finally:
            cursor.close()
            conn.close()

    def insert_row(self, data: dict) -> tuple:
        """
        新增一行
        返回: (success: bool, result: int|str)
        """
        errors = self._validate_fields(data)
        if errors:
            return False, '; '.join(errors)

        # 过滤出可编辑字段
        insert_data = {k: v for k, v in data.items() if k in self._editable_fields}
        if not insert_data:
            return False, '没有可插入的字段'

        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            fields = list(insert_data.keys())
            placeholders = ', '.join(['%s'] * len(fields))
            fields_str = ', '.join([f"`{f}`" for f in fields])
            sql = f"INSERT INTO `{self._table_name}` ({fields_str}) VALUES ({placeholders})"
            cursor.execute(sql, list(insert_data.values()))
            conn.commit()
            return True, cursor.lastrowid
        except pymysql.Error as e:
            conn.rollback()
            return False, str(e)
        finally:
            cursor.close()
            conn.close()

    def update_row(self, pk_value, data: dict) -> tuple:
        """
        更新一行
        返回: (success: bool, result: str)
        """
        # 过滤出可编辑字段
        update_data = {k: v for k, v in data.items() if k in self._editable_fields}
        if not update_data:
            return False, '没有可更新的字段'

        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            set_parts = [f"`{k}` = %s" for k in update_data.keys()]
            set_clause = ', '.join(set_parts)
            sql = (
                f"UPDATE `{self._table_name}` SET {set_clause} "
                f"WHERE `{self._primary_key}` = %s"
            )
            cursor.execute(sql, list(update_data.values()) + [pk_value])
            conn.commit()
            return True, f'已更新 {cursor.rowcount} 行'
        except pymysql.Error as e:
            conn.rollback()
            return False, str(e)
        finally:
            cursor.close()
            conn.close()

    def delete_row(self, pk_value) -> tuple:
        """
        删除一行
        返回: (success: bool, result: str)
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            sql = f"DELETE FROM `{self._table_name}` WHERE `{self._primary_key}` = %s"
            cursor.execute(sql, (pk_value,))
            conn.commit()
            return True, f'已删除 {cursor.rowcount} 行'
        except pymysql.Error as e:
            conn.rollback()
            return False, str(e)
        finally:
            cursor.close()
            conn.close()

    def batch_update(self, group_field: str, group_value, data: dict) -> tuple:
        """
        批量更新（按分组字段）
        返回: (success: bool, result: str)
        """
        update_data = {k: v for k, v in data.items() if k in self._editable_fields}
        if not update_data:
            return False, '没有可更新的字段'

        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            set_parts = [f"`{k}` = %s" for k in update_data.keys()]
            set_clause = ', '.join(set_parts)
            sql = (
                f"UPDATE `{self._table_name}` SET {set_clause} "
                f"WHERE `{group_field}` = %s"
            )
            cursor.execute(sql, list(update_data.values()) + [group_value])
            conn.commit()
            return True, f'已批量更新 {cursor.rowcount} 行'
        except pymysql.Error as e:
            conn.rollback()
            return False, str(e)
        finally:
            cursor.close()
            conn.close()

    def export_csv(self, search: str = None, search_field: str = None) -> str:
        """导出为 CSV 字符串"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            where_clause, params = self._build_where(search, search_field)
            fields_str = ', '.join([f"`{f}`" for f in self._all_fields])
            sql = f"SELECT {fields_str} FROM `{self._table_name}` WHERE {where_clause}"
            cursor.execute(sql, params)
            rows = cursor.fetchall()

            output = io.StringIO()
            writer = csv.writer(output)

            # 表头：使用 label
            labels = [
                c.get('label', c['field'])
                for c in self._columns
            ]
            writer.writerow(labels)

            # 数据行
            for row in rows:
                writer.writerow([row.get(f, '') for f in self._all_fields])

            return output.getvalue()
        finally:
            cursor.close()
            conn.close()

    def get_group_values(self, group_field: str) -> list:
        """获取分组字段的所有去重值"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            sql = (
                f"SELECT DISTINCT `{group_field}` as value "
                f"FROM `{self._table_name}` "
                f"ORDER BY `{group_field}`"
            )
            cursor.execute(sql)
            return [row['value'] for row in cursor.fetchall()]
        finally:
            cursor.close()
            conn.close()
