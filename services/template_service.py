#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模板管理服务 - 核心业务逻辑
"""

import re
from modules.database.connection import execute_query

# 生产库连接配置（10.68.2.32），用于 RCS 模板同步
# task_template / task_relation 表位于生产库
PROD_DB_CONFIG = {
    'host': '10.68.2.32',
    'port': 3306,
    'user': 'wms',
    'password': 'CCshenda889',
    'database': 'wms',
    'charset': 'utf8mb4',
    'connect_timeout': 5,
}


class TemplateService:
    """模板管理服务"""

    def __init__(self, db_config=None):
        """
        :param db_config: 可选数据库配置 dict（host/port/user/password/database/charset），
                          传 None 则使用默认连接池
        """
        self.db_config = db_config
    
    def _execute(self, query, params=None, fetch=True):
        """使用当前 db_config 执行查询，若未设置则走默认连接池"""
        return execute_query(query, params, fetch=fetch, config=self.db_config)
    
    # ========== 搜索 ==========
    
    def search(self, search_term):
        """搜索任务模板（旧版全匹配，兼容保留）"""
        if not search_term:
            return None, '请输入搜索关键词'
        
        if search_term.isdigit():
            templates = self._execute(
                "SELECT * FROM fy_cross_model_process WHERE id = %s", (int(search_term),))
            if not templates or len(templates) == 0:
                templates = self._execute(
                    "SELECT * FROM fy_cross_model_process WHERE model_process_code LIKE %s ORDER BY id DESC",
                    (f'%{search_term}%',))
        else:
            templates = self._execute(
                "SELECT * FROM fy_cross_model_process WHERE model_process_code LIKE %s ORDER BY id DESC",
                (f'%{search_term}%',))
        
        if not templates:
            return None, f'未找到包含 "{search_term}" 的任务模板'
        
        for t in templates:
            details = self._execute(
                "SELECT * FROM fy_cross_model_process_detail WHERE model_process_id = %s ORDER BY task_seq",
                (t['id'],))
            t['details'] = details or []
        
        return templates, None
    
    def search_paginated(self, search_term='', page=1, per_page=20, server=None, status=None, sort_by='id', sort_order='DESC'):
        """分页搜索 + 筛选 + 排序，返回 {templates, total, servers, page, per_page, total_pages}"""
        allowed_sort = {'id', 'model_process_code', 'model_process_name', 'target_points_ip', 'enable', 'area_id'}
        if sort_by not in allowed_sort:
            sort_by = 'id'
        sort_order = 'ASC' if sort_order.upper() == 'ASC' else 'DESC'
        
        conditions = []
        params = []
        
        if search_term:
            if search_term.isdigit():
                conditions.append("(id = %s OR model_process_code LIKE %s)")
                params.extend([int(search_term), f'%{search_term}%'])
            else:
                conditions.append("(model_process_code LIKE %s OR model_process_name LIKE %s)")
                params.extend([f'%{search_term}%', f'%{search_term}%'])
        
        if server:
            conditions.append("target_points_ip = %s")
            params.append(server)
        
        if status is not None and status in ('0', '1'):
            conditions.append("enable = %s")
            params.append(int(status))
        
        where_clause = (' WHERE ' + ' AND '.join(conditions)) if conditions else ''
        
        # 计数
        count_sql = f"SELECT COUNT(*) as cnt FROM fy_cross_model_process{where_clause}"
        count_result = self._execute(count_sql, params)
        total = count_result[0]['cnt'] if count_result else 0
        
        # 分页
        offset = (page - 1) * per_page
        data_sql = f"SELECT * FROM fy_cross_model_process{where_clause} ORDER BY {sort_by} {sort_order} LIMIT %s OFFSET %s"
        templates = self._execute(data_sql, params + [per_page, offset]) or []
        
        # 同时获取 detail 数量（不加载完整子任务）
        for t in templates:
            detail_count = self._execute(
                "SELECT COUNT(*) as cnt FROM fy_cross_model_process_detail WHERE model_process_id = %s",
                (t['id'],))
            t['detail_count'] = detail_count[0]['cnt'] if detail_count else 0
        
        # 获取所有可用的 server 列表（用于筛选下拉）
        servers_result = self._execute(
            "SELECT DISTINCT target_points_ip FROM fy_cross_model_process WHERE target_points_ip IS NOT NULL AND target_points_ip != '' ORDER BY target_points_ip")
        servers = [r['target_points_ip'] for r in servers_result] if servers_result else []
        
        total_pages = max(1, (total + per_page - 1) // per_page)
        
        return {
            'templates': templates,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'servers': servers,
        }
    
    def search_suggestions(self, term):
        """搜索建议"""
        if not term:
            return []
        results = self._execute(
            "SELECT model_process_code, model_process_name FROM fy_cross_model_process "
            "WHERE model_process_code LIKE %s OR model_process_name LIKE %s LIMIT 10",
            (f'%{term}%', f'%{term}%'))
        return [{'code': r['model_process_code'], 'name': r['model_process_name']} for r in results] if results else []
    
    # ========== 模板 CRUD ==========
    
    def get_template(self, template_id):
        """获取模板详情（含子任务）"""
        template = self._execute("SELECT * FROM fy_cross_model_process WHERE id = %s", (template_id,))
        if not template:
            return None
        template = template[0]
        template['details'] = self._execute(
            "SELECT * FROM fy_cross_model_process_detail WHERE model_process_id = %s ORDER BY task_seq",
            (template_id,))
        return template
    
    def update_template(self, template_id, form_data):
        """更新模板主表"""
        def safe_int(value, default=0):
            if value is None or value == '':
                return default
            try:
                return int(value)
            except (ValueError, TypeError):
                return default
        
        update_query = """UPDATE fy_cross_model_process 
            SET model_process_name=%s, enable=%s, request_url=%s, capacity=%s,
                target_points=%s, area_id=%s, target_points_ip=%s,
                backflow_template_code=%s, comeback_template_code=%s,
                change_charge_template_code=%s, min_power=%s, back_wait_time=%s, check_area_name=%s
            WHERE id=%s"""
        
        params = (
            form_data.get('model_process_name'),
            safe_int(form_data.get('enable'), 0),
            form_data.get('request_url'),
            safe_int(form_data.get('capacity'), -1),
            form_data.get('target_points'),
            safe_int(form_data.get('area_id'), 0),
            form_data.get('target_points_ip'),
            form_data.get('backflow_template_code'),
            form_data.get('comeback_template_code'),
            form_data.get('change_charge_template_code'),
            form_data.get('min_power') if form_data.get('min_power') != '' else None,
            form_data.get('back_wait_time') if form_data.get('back_wait_time') != '' else None,
            form_data.get('check_area_name'),
            template_id
        )
        return self._execute(update_query, params, fetch=False)
    
    def update_details_batch(self, template_id, form_data):
        """批量更新子任务"""
        updated = 0
        detail_fields = {}
        for key, value in form_data.items():
            if key.startswith('detail_'):
                parts = key.split('_')
                if len(parts) >= 3:
                    detail_id = parts[1]
                    field_name = '_'.join(parts[2:])
                    detail_fields.setdefault(detail_id, {})[field_name] = value
        
        for detail_id_str, fields in detail_fields.items():
            try:
                detail_id = int(detail_id_str)
                task_seq = int(fields.get('task_seq', '0'))
                need_third = 1 if str(fields.get('need_third_trigger', '0')) == '1' else 0
                
                result = self._execute(
                    """UPDATE fy_cross_model_process_detail
                    SET task_seq=%s, template_code=%s, template_name=%s, task_servicec=%s, task_path=%s, need_third_trigger=%s
                    WHERE id=%s AND model_process_id=%s""",
                    (task_seq, fields.get('template_code', ''), fields.get('template_name', ''),
                     fields.get('task_servicec', ''), fields.get('task_path', ''), need_third,
                     detail_id, template_id), fetch=False)
                if result is not None:
                    updated += 1
            except (ValueError, KeyError) as e:
                print(f"更新子任务 {detail_id_str} 出错: {e}")
        
        # 自动同步大模板本身到 task_template
        sync_result = self.sync_template_to_rcs(template_id)
        if sync_result['synced']:
            print(f"[RCS同步] 编辑模板 {template_id} 时自动同步到 task_template")
        
        return updated
    
    # ========== 子任务 CRUD ==========
    
    def update_detail(self, detail_id, form_data):
        """更新单个子任务"""
        def get_val(data, key, default=None):
            value = data.get(key)
            if value is None:
                return default
            s = str(value).strip()
            if s == '' or s == '0':
                return default if default is not None else None
            return s
        
        back_wait_time = None
        bwt = form_data.get('back_wait_time', '').strip()
        if bwt:
            try:
                back_wait_time = int(bwt)
            except (ValueError, TypeError):
                pass
        
        need_third = 1 if form_data.get('need_third_trigger', '0').strip() == '1' else 0
        
        return self._execute(
            """UPDATE fy_cross_model_process_detail
            SET task_seq=%s, task_servicec=%s, template_code=%s, template_name=%s,
                task_path=%s, backflow_template_code=%s, comeback_template_code=%s,
                back_wait_time=%s, need_third_trigger=%s WHERE id=%s""",
            (int(form_data.get('task_seq', 0)), get_val(form_data, 'task_servicec', ''),
             get_val(form_data, 'template_code', ''), get_val(form_data, 'template_name', ''),
             get_val(form_data, 'task_path', ''), get_val(form_data, 'backflow_template_code'),
             get_val(form_data, 'comeback_template_code'), back_wait_time, need_third, detail_id),
            fetch=False)
    
    def get_detail_model_id(self, detail_id):
        """获取子任务所属模板ID"""
        result = self._execute(
            "SELECT model_process_id FROM fy_cross_model_process_detail WHERE id = %s", (detail_id,))
        return result[0]['model_process_id'] if result else None
    
    def add_detail(self, template_id, data):
        """添加子任务"""
        max_result = self._execute(
            "SELECT MAX(task_seq) as max_seq FROM fy_cross_model_process_detail WHERE model_process_id = %s",
            (template_id,))
        new_seq = (max_result[0]['max_seq'] + 1) if max_result and max_result[0]['max_seq'] is not None else 1
        
        def get_val(d, key, default=None):
            value = d.get(key)
            if value is None:
                return default
            s = str(value).strip()
            if s == '' or s == '0':
                return default if default is not None else None
            return s
        
        back_wait_time = None
        bw_val = data.get('back_wait_time', '')
        if bw_val is not None:
            try:
                bw_str = str(bw_val).strip()
                if bw_str:
                    back_wait_time = int(bw_str)
            except (ValueError, TypeError):
                pass
        
        need_third = 1 if str(data.get('need_third_trigger', 0)) == '1' else 0
        
        new_id = self._execute(
            """INSERT INTO fy_cross_model_process_detail
            (model_process_id, task_seq, task_servicec, template_code, template_name, task_path,
             backflow_template_code, comeback_template_code, back_wait_time, need_third_trigger)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (template_id, new_seq, get_val(data, 'task_servicec', ''),
             get_val(data, 'template_code', ''), get_val(data, 'template_name', ''),
             get_val(data, 'task_path', ''), get_val(data, 'backflow_template_code'),
             get_val(data, 'comeback_template_code'), back_wait_time, need_third),
            fetch=False)
        
        if new_id:
            detail = self._execute("SELECT * FROM fy_cross_model_process_detail WHERE id = %s", (new_id,))
            return detail[0] if detail else None
        return None
    
    def delete_detail(self, template_id, detail_id):
        """删除子任务"""
        verify = self._execute(
            "SELECT id FROM fy_cross_model_process_detail WHERE id = %s AND model_process_id = %s",
            (detail_id, template_id))
        if not verify:
            return False, '子任务不存在或不属于该模板'
        result = self._execute("DELETE FROM fy_cross_model_process_detail WHERE id = %s", (detail_id,), fetch=False)
        return bool(result), None
    
    def reorder_details(self, template_id, order_list):
        """重新排序子任务"""
        if not order_list:
            return False, '未提供排序数据'
        
        detail_ids = [item['id'] for item in order_list]
        placeholders = ', '.join(['%s'] * len(detail_ids))
        verify = self._execute(
            f"SELECT COUNT(*) as count FROM fy_cross_model_process_detail WHERE id IN ({placeholders}) AND model_process_id = %s",
            detail_ids + [template_id])
        
        if verify and verify[0]['count'] != len(detail_ids):
            return False, '部分子任务不属于该模板'
        
        success = 0
        for item in order_list:
            result = self._execute(
                "UPDATE fy_cross_model_process_detail SET task_seq = %s WHERE id = %s AND model_process_id = %s",
                (item['task_seq'], item['id'], template_id), fetch=False)
            if result:
                success += 1
        
        return success == len(order_list), f'{success}/{len(order_list)}'
    
    # ========== 复制模板 ==========
    
    def copy_template(self, template_id, form_data):
        """复制模板"""
        new_base_name = form_data.get('new_base_name', '').strip()
        if not new_base_name:
            return None, '请输入新模板的基础名称'
        
        original = self._execute("SELECT * FROM fy_cross_model_process WHERE id = %s", (template_id,))
        if not original:
            return None, '原模板不存在或无法访问'
        original = original[0]
        
        def safe_int(value, default=0):
            if value is None or value == '':
                return default
            try:
                return int(value)
            except (ValueError, TypeError):
                return default
        
        temp_code = f"{new_base_name}_temp"
        new_id = self._execute(
            """INSERT INTO fy_cross_model_process
            (model_process_code, model_process_name, enable, request_url, capacity,
             target_points, area_id, target_points_ip, backflow_template_code,
             comeback_template_code, change_charge_template_code, min_power, back_wait_time, check_area_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (temp_code, form_data.get('model_process_name', original['model_process_name']),
             safe_int(form_data.get('enable'), original['enable']),
             form_data.get('request_url', original['request_url']),
             safe_int(form_data.get('capacity'), original['capacity']),
             form_data.get('target_points', original['target_points']),
             safe_int(form_data.get('area_id'), original['area_id']),
             form_data.get('target_points_ip', original['target_points_ip']),
             form_data.get('backflow_template_code', original.get('backflow_template_code')),
             form_data.get('comeback_template_code', original.get('comeback_template_code')),
             form_data.get('change_charge_template_code', original.get('change_charge_template_code')),
             form_data.get('min_power') if form_data.get('min_power') != '' else None,
             form_data.get('back_wait_time') if form_data.get('back_wait_time') != '' else None,
             form_data.get('check_area_name', original.get('check_area_name'))),
            fetch=False)
        
        if not new_id:
            return None, '模板复制失败'
        
        new_code = f"{new_base_name}_{new_id}"
        original_name = form_data.get('model_process_name', original['model_process_name'])
        original_name_clean = re.sub(r'_\d+$', '', original_name)
        new_name = f"{original_name_clean}_{new_id}"
        
        self._execute("UPDATE fy_cross_model_process SET model_process_code=%s, model_process_name=%s WHERE id=%s",
                     (new_code, new_name, new_id), fetch=False)
        
        # 复制子任务
        details = self._execute(
            "SELECT * FROM fy_cross_model_process_detail WHERE model_process_id = %s ORDER BY task_seq",
            (template_id,))
        if details:
            for detail in details:
                def safe_get(d, key):
                    value = d.get(key)
                    if value is None:
                        return None
                    s = str(value).strip() if value is not None else ''
                    if s == '':
                        return None
                    if key == 'back_wait_time':
                        try:
                            return int(s) if s else None
                        except (ValueError, TypeError):
                            return None
                    if key in ('backflow_template_code', 'comeback_template_code') and s == '0':
                        return None
                    return value
                
                self._execute(
                    """INSERT INTO fy_cross_model_process_detail
                    (model_process_id, task_seq, task_servicec, template_code, template_name, task_path,
                     backflow_template_code, comeback_template_code, back_wait_time, need_third_trigger)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (new_id, detail['task_seq'], detail['task_servicec'], detail['template_code'],
                     detail['template_name'], detail['task_path'], safe_get(detail, 'backflow_template_code'),
                     safe_get(detail, 'comeback_template_code'), safe_get(detail, 'back_wait_time'),
                     detail.get('need_third_trigger', 0)), fetch=False)
        
        # 自动同步新复制的大模板到 task_template
        sync_result = self.sync_template_to_rcs(new_id)
        if sync_result['synced']:
            print(f"[RCS同步] 复制模板 {new_code} 时自动同步到 task_template")
        
        return {'id': new_id, 'code': new_code, 'name': new_name, 'rcs_sync': sync_result}, None
    
    # ========== RCS 四表同步 ==========
    # 同步跨环境大模板到 model_process / model_process_detail / task_template / task_relation
    # 以 xialiaoDA02-LH023_521 为模板复制新增
    
    def _prod_query(self, query, params=None, fetch=True):
        """使用生产库连接池执行查询"""
        from modules.database.connection import _pool_instance, execute_query as eq
        try:
            conn = _pool_instance.get_conn2()
        except Exception as e:
            print(f"[RCS同步] 生产库连接池不可用 ({e})，回退到直连")
            return eq(query, params, fetch=fetch, config=PROD_DB_CONFIG)
        
        from pymysql.cursors import DictCursor
        cursor = None
        try:
            cursor = conn.cursor(DictCursor)
            cursor.execute(query, params or ())
            if fetch:
                result = cursor.fetchall() if query.strip().upper().startswith('SELECT') else []
            else:
                conn.commit()
                result = cursor.lastrowid if query.strip().upper().startswith('INSERT') else cursor.rowcount
            return result
        except Exception as e:
            print(f"[RCS同步] 生产库查询错误: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
            return None
        finally:
            if cursor:
                cursor.close()
            # DBUtils 连接池的 connection.close() 会归还连接到池，不要关闭
    
    def _get_template_data(self, template_code):
        """获取 xialiaoDA02-LH023_521 的完整数据作为模板"""
        result = {}
        
        print(f"[RCS同步] 查询模板数据: {template_code}")
        
        # model_process
        sql1 = "SELECT * FROM model_process WHERE model_process_code = %s"
        print(f"[RCS同步] SQL: {sql1}  params: ({template_code},)")
        r = self._prod_query(sql1, (template_code,))
        if r:
            result['model_process'] = r[0]
            print(f"[RCS同步] model_process 查询成功: id={r[0]['id']}")
        else:
            print(f"[RCS同步] model_process 查询失败: 未找到 {template_code}")
        
        # model_process_detail
        sql2 = "SELECT * FROM model_process_detail WHERE template_code = %s"
        print(f"[RCS同步] SQL: {sql2}  params: ({template_code},)")
        r = self._prod_query(sql2, (template_code,))
        if r:
            result['model_process_detail'] = r[0]
            print(f"[RCS同步] model_process_detail 查询成功: id={r[0]['id']}")
        else:
            print(f"[RCS同步] model_process_detail 查询失败: 未找到 {template_code}")
        
        # task_template
        sql3 = "SELECT * FROM task_template WHERE template_code = %s"
        print(f"[RCS同步] SQL: {sql3}  params: ({template_code},)")
        r = self._prod_query(sql3, (template_code,))
        if r:
            result['task_template'] = r[0]
            print(f"[RCS同步] task_template 查询成功: id={r[0]['id']}")
        else:
            print(f"[RCS同步] task_template 查询失败: 未找到 {template_code}")
        
        # task_relation
        sql4 = ("SELECT tr.* FROM task_relation tr "
                "JOIN task_template tt ON tt.id = tr.template_id "
                "WHERE tt.template_code = %s ORDER BY tr.id")
        print(f"[RCS同步] SQL: {sql4}  params: ({template_code},)")
        r = self._prod_query(sql4, (template_code,))
        if r:
            result['task_relation'] = r
            print(f"[RCS同步] task_relation 查询成功: {len(r)}条")
        else:
            print(f"[RCS同步] task_relation 查询失败: 未找到 {template_code}")
        
        return result
    
    def check_four_tables_complete(self, template_code):
        """
        检查四张表内容是否都完整
        返回: {complete: bool, details: {表名: bool}}
        """
        details = {}
        
        r = self._prod_query(
            "SELECT id FROM model_process WHERE model_process_code = %s", (template_code,))
        details['model_process'] = bool(r)
        
        r = self._prod_query(
            "SELECT id FROM model_process_detail WHERE template_code = %s", (template_code,))
        details['model_process_detail'] = bool(r)
        
        r = self._prod_query(
            "SELECT id FROM task_template WHERE template_code = %s", (template_code,))
        details['task_template'] = bool(r)
        
        if r:
            r2 = self._prod_query(
                "SELECT COUNT(*) as cnt FROM task_relation WHERE template_id = %s",
                (r[0]['id'],))
            details['task_relation'] = r2 and r2[0]['cnt'] > 0
        else:
            details['task_relation'] = False
        
        complete = all(details.values())
        return {'complete': complete, 'details': details}
    
    def sync_four_tables(self, template_code, template_name):
        """
        以 xialiaoDA02-LH023_521 为模板，同步四张表
        返回: (success, message, details)
        """
        # 1. 检查四张表是否已完整
        status = self.check_four_tables_complete(template_code)
        if status['complete']:
            return False, f"模板 {template_code} 四张表已全部存在，跳过新增", status['details']
        
        # 2. 获取模板数据（以 xialiaoDA02-LH023_521 为模板）
        tmpl = self._get_template_data('xialiaoDA02-LH023_521')
        if not tmpl.get('model_process'):
            return False, "模板数据 xialiaoDA02-LH023_521 不完整，无法复制", None
        
        mp = tmpl['model_process']
        mpd = tmpl.get('model_process_detail', {})
        tt = tmpl.get('task_template', {})
        tr_list = tmpl.get('task_relation', [])
        
        new_details = {}
        
        # 3. 插入 model_process
        if not status['details'].get('model_process'):
            new_mp_id = self._prod_query(
                """INSERT INTO model_process
                (area_id, priority, model_process_code, model_process_name,
                 sys_auto_generate, exe_immediately, enable, is_support_agv)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (mp.get('area_id', 3), mp.get('priority', 6),
                 template_code, template_name or template_code,
                 mp.get('sys_auto_generate', 0), mp.get('exe_immediately', 1),
                 mp.get('enable', 1), mp.get('is_support_agv', 2)),
                fetch=False)
            if new_mp_id:
                new_details['model_process'] = new_mp_id
        else:
            r = self._prod_query(
                "SELECT id FROM model_process WHERE model_process_code = %s", (template_code,))
            if r:
                new_details['model_process'] = r[0]['id']
        
        # 4. 插入 model_process_detail
        if not status['details'].get('model_process_detail') and new_details.get('model_process'):
            # 先插入 task_template 获取 id
            new_tt_id = None
            if not status['details'].get('task_template'):
                new_tt_id = self._prod_query(
                    """INSERT INTO task_template
                    (template_code, name, processor, is_default, priority, areaId,
                     capacity_control, re_execute, template_type, allow_recover,
                     allow_charge_device, allow_merge, allow_device_cancel_task,
                     default_cancel_task_strategy, backup_device_ratio)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (template_code, template_name or template_code,
                     tt.get('processor', 'carry'), tt.get('is_default', '0'),
                     tt.get('priority', 6), tt.get('areaId', 3),
                     tt.get('capacity_control', 1), tt.get('re_execute', 1),
                     tt.get('template_type', 1), tt.get('allow_recover', 0),
                     tt.get('allow_charge_device', 0), tt.get('allow_merge', 0),
                     tt.get('allow_device_cancel_task', 1),
                     tt.get('default_cancel_task_strategy', 1),
                     tt.get('backup_device_ratio', 120)),
                    fetch=False)
                if new_tt_id:
                    new_details['task_template'] = new_tt_id
            else:
                r = self._prod_query(
                    "SELECT id FROM task_template WHERE template_code = %s", (template_code,))
                if r:
                    new_tt_id = r[0]['id']
                    new_details['task_template'] = new_tt_id
            
            if new_tt_id:
                new_mpd_id = self._prod_query(
                    """INSERT INTO model_process_detail
                    (model_process_id, template_code, task_template_id, template_name,
                     template_type, continue_condition, trigger_condition)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (new_details['model_process'], template_code, new_tt_id,
                     template_name or template_code,
                     mpd.get('template_type', 1), mpd.get('continue_condition', 1),
                     mpd.get('trigger_condition', 1)),
                    fetch=False)
                if new_mpd_id:
                    new_details['model_process_detail'] = new_mpd_id
        
        # 5. 插入 task_relation
        if not status['details'].get('task_relation') and new_details.get('task_template'):
            for tr in tr_list:
                self._prod_query(
                    """INSERT INTO task_relation
                    (template_id, type_id, need_trigger, point_access, point_access_ext,
                     notify_third, notify_end, skip)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (new_details['task_template'], tr.get('type_id', 1),
                     tr.get('need_trigger', 0), tr.get('point_access', 1),
                     tr.get('point_access_ext', 1), tr.get('notify_third', 2),
                     tr.get('notify_end'), tr.get('skip', 0)),
                    fetch=False)
            new_details['task_relation'] = len(tr_list)
        
        return True, f"模板 {template_code} 四张表同步完成", new_details
    
    def get_four_tables_status(self, template_id):
        """
        获取跨环境大模板在四张表中的同步状态
        返回: {template_code, template_name, complete, details}
        """
        try:
            # fy_cross_model_process 在生产库 10.68.2.32
            template = self._prod_query(
                "SELECT id, model_process_code, model_process_name FROM fy_cross_model_process WHERE id = %s",
                (template_id,))
            if not template:
                print(f"[RCS同步] fy_cross_model_process id={template_id} 在生产库中不存在")
                return None
            
            t = template[0]
            print(f"[RCS同步] 查询到跨环境模板: id={t['id']}, code={t['model_process_code']}")
            status = self.check_four_tables_complete(t['model_process_code'])
            return {
                'template_code': t['model_process_code'],
                'template_name': t['model_process_name'],
                'complete': status['complete'],
                'details': status['details']
            }
        except Exception as e:
            print(f"[RCS同步] 查询生产库失败: {e}")
            return None
    
    def sync_template_to_rcs(self, template_id):
        """
        同步跨环境大模板到四张表
        返回: {synced: [...], skipped: [...], errors: [...]}
        """
        status = self.get_four_tables_status(template_id)
        if not status:
            return {'synced': [], 'skipped': [], 'errors': [{'message': '跨环境模板不存在'}]}
        
        synced = []
        skipped = []
        errors = []
        
        if status['complete']:
            skipped.append({
                'template_code': status['template_code'],
                'message': f"模板 {status['template_code']} 四张表已全部存在，跳过新增",
                'details': status['details']
            })
        else:
            success, message, details = self.sync_four_tables(
                status['template_code'], status['template_name'])
            if success:
                synced.append({
                    'template_code': status['template_code'],
                    'message': message,
                    'details': details
                })
            else:
                errors.append({
                    'template_code': status['template_code'],
                    'message': message,
                    'details': details
                })
        
        return {'synced': synced, 'skipped': skipped, 'errors': errors}
