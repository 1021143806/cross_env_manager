#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模板管理服务 - 核心业务逻辑
"""

import re
from modules.database.connection import execute_query


class TemplateService:
    """模板管理服务"""
    
    # ========== 搜索 ==========
    
    def search(self, search_term):
        """搜索任务模板"""
        if not search_term:
            return None, '请输入搜索关键词'
        
        if search_term.isdigit():
            templates = execute_query(
                "SELECT * FROM fy_cross_model_process WHERE id = %s", (int(search_term),))
            if not templates or len(templates) == 0:
                templates = execute_query(
                    "SELECT * FROM fy_cross_model_process WHERE model_process_code LIKE %s ORDER BY id DESC",
                    (f'%{search_term}%',))
        else:
            templates = execute_query(
                "SELECT * FROM fy_cross_model_process WHERE model_process_code LIKE %s ORDER BY id DESC",
                (f'%{search_term}%',))
        
        if not templates:
            return None, f'未找到包含 "{search_term}" 的任务模板'
        
        for t in templates:
            details = execute_query(
                "SELECT * FROM fy_cross_model_process_detail WHERE model_process_id = %s ORDER BY task_seq",
                (t['id'],))
            t['details'] = details or []
        
        return templates, None
    
    def search_suggestions(self, term):
        """搜索建议"""
        if not term:
            return []
        results = execute_query(
            "SELECT model_process_code, model_process_name FROM fy_cross_model_process "
            "WHERE model_process_code LIKE %s OR model_process_name LIKE %s LIMIT 10",
            (f'%{term}%', f'%{term}%'))
        return [{'code': r['model_process_code'], 'name': r['model_process_name']} for r in results] if results else []
    
    # ========== 模板 CRUD ==========
    
    def get_template(self, template_id):
        """获取模板详情（含子任务）"""
        template = execute_query("SELECT * FROM fy_cross_model_process WHERE id = %s", (template_id,))
        if not template:
            return None
        template = template[0]
        template['details'] = execute_query(
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
        return execute_query(update_query, params, fetch=False)
    
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
                
                result = execute_query(
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
        
        return execute_query(
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
        result = execute_query(
            "SELECT model_process_id FROM fy_cross_model_process_detail WHERE id = %s", (detail_id,))
        return result[0]['model_process_id'] if result else None
    
    def add_detail(self, template_id, data):
        """添加子任务"""
        max_result = execute_query(
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
        
        new_id = execute_query(
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
            detail = execute_query("SELECT * FROM fy_cross_model_process_detail WHERE id = %s", (new_id,))
            return detail[0] if detail else None
        return None
    
    def delete_detail(self, template_id, detail_id):
        """删除子任务"""
        verify = execute_query(
            "SELECT id FROM fy_cross_model_process_detail WHERE id = %s AND model_process_id = %s",
            (detail_id, template_id))
        if not verify:
            return False, '子任务不存在或不属于该模板'
        result = execute_query("DELETE FROM fy_cross_model_process_detail WHERE id = %s", (detail_id,), fetch=False)
        return bool(result), None
    
    def reorder_details(self, template_id, order_list):
        """重新排序子任务"""
        if not order_list:
            return False, '未提供排序数据'
        
        detail_ids = [item['id'] for item in order_list]
        placeholders = ', '.join(['%s'] * len(detail_ids))
        verify = execute_query(
            f"SELECT COUNT(*) as count FROM fy_cross_model_process_detail WHERE id IN ({placeholders}) AND model_process_id = %s",
            detail_ids + [template_id])
        
        if verify and verify[0]['count'] != len(detail_ids):
            return False, '部分子任务不属于该模板'
        
        success = 0
        for item in order_list:
            result = execute_query(
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
        
        original = execute_query("SELECT * FROM fy_cross_model_process WHERE id = %s", (template_id,))
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
        new_id = execute_query(
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
        
        execute_query("UPDATE fy_cross_model_process SET model_process_code=%s, model_process_name=%s WHERE id=%s",
                     (new_code, new_name, new_id), fetch=False)
        
        # 复制子任务
        details = execute_query(
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
                
                execute_query(
                    """INSERT INTO fy_cross_model_process_detail
                    (model_process_id, task_seq, task_servicec, template_code, template_name, task_path,
                     backflow_template_code, comeback_template_code, back_wait_time, need_third_trigger)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (new_id, detail['task_seq'], detail['task_servicec'], detail['template_code'],
                     detail['template_name'], detail['task_path'], safe_get(detail, 'backflow_template_code'),
                     safe_get(detail, 'comeback_template_code'), safe_get(detail, 'back_wait_time'),
                     detail.get('need_third_trigger', 0)), fetch=False)
        
        return {'id': new_id, 'code': new_code, 'name': new_name}, None
