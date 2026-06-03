#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交接点配置服务 - join_qr_node_info 配对管理

功能：
  1. 配对列表（按 qr_content 分组展示）
  2. 配对新增（一次创建 2 条记录，自动判断 type）
  3. 配对删除（按 qr_content 删除所有记录）
  4. 模板交接点检查（验证模板涉及的每个服务器是否已配置对应区域）

表结构 (join_qr_node_info):
  id, area_id, type, qr_content, environment_ip, enable, join_area, other_config, last_using_time
  type=0: 跨服务器, type=1: 同服务器内跨区域
"""

import re
from modules.database.connection import execute_query


class JoinQrService:
    """交接点配置服务"""

    # ======================== 配对列表 ========================

    def get_paired_list(self, server=None, area=None, search=None):
        """
        获取配对列表，按 qr_content 分组
        
        返回: [
            {
                'qr_content': '55301540',
                'count': 2,
                'is_paired': True,
                'type_label': '同服务器',
                'servers': ['10.68.2.32', '10.68.2.32'],
                'areas': ['1', '3'],
                'records': [{完整记录}, {完整记录}]
            },
            ...
        ]
        """
        sql = "SELECT * FROM join_qr_node_info WHERE qr_content IS NOT NULL AND qr_content != ''"
        params = []
        if server:
            sql += " AND environment_ip = %s"
            params.append(server)
        if area:
            sql += " AND area_id = %s"
            params.append(int(area))
        if search:
            sql += " AND (qr_content LIKE %s OR environment_ip LIKE %s)"
            params.extend([f'%{search}%', f'%{search}%'])
        sql += " ORDER BY qr_content DESC, id"

        records = execute_query(sql, tuple(params) if params else None) or []

        # 分组（跳过空的 qr_content）
        groups = {}
        for r in records:
            key = r.get('qr_content') or ''
            if not key:
                continue
            if key not in groups:
                groups[key] = []
            groups[key].append(r)

        # 构建返回
        result = []
        for qr, recs in sorted(groups.items(), reverse=True):
            ips = []
            area_ids = []
            types_set = set()
            for rec in recs:
                ip = rec.get('environment_ip', '')
                if ip and ip not in ips:
                    ips.append(ip)
                aid = str(rec.get('area_id', ''))
                if aid and aid not in area_ids:
                    area_ids.append(aid)
                t = rec.get('type')
                if t is not None:
                    types_set.add(int(t))

            is_cross = (len(set(ips)) > 1 or 0 in types_set)
            type_label = '跨服务器' if is_cross else '同服务器'

            result.append({
                'qr_content': qr,
                'count': len(recs),
                'is_paired': len(recs) >= 2,
                'type_label': type_label,
                'servers': ips,
                'areas': area_ids,
                'records': sorted(recs, key=lambda x: x.get('id', 0)),
            })

        return result

    # ======================== 获取配对详情（用于编辑） ========================

    def get_pair_by_qr(self, qr_content):
        """获取同一地码值的所有记录（编辑时用）"""
        records = execute_query(
            "SELECT * FROM join_qr_node_info WHERE qr_content = %s ORDER BY id",
            (qr_content,)
        ) or []
        return records

    # ======================== 新增配对 ========================

    def add_pair(self, qr_content, server_a, area_a, server_b, area_b):
        """
        新增一对交接点配置，自动判断 type
        跨服务器 → type=0，同服务器 → type=1
        """
        same_server = (server_a == server_b)
        qr_type = 1 if same_server else 0

        sql = (
            "INSERT INTO join_qr_node_info (area_id, type, qr_content, environment_ip, enable) "
            "VALUES (%s, %s, %s, %s, 1)"
        )
        execute_query(sql, (area_a, qr_type, qr_content, server_a), fetch=False)
        execute_query(sql, (area_b, qr_type, qr_content, server_b), fetch=False)

        return True

    # ======================== 更新配对 ========================

    def update_pair(self, old_qr_content, qr_content, server_a, area_a, server_b, area_b):
        """更新配对：删除旧记录，重新插入"""
        self.delete_pair(old_qr_content)
        self.add_pair(qr_content, server_a, area_a, server_b, area_b)
        return True

    # ======================== 删除配对 ========================

    def delete_pair(self, qr_content):
        """删除同一地码值的所有记录"""
        execute_query(
            "DELETE FROM join_qr_node_info WHERE qr_content = %s",
            (qr_content,), fetch=False
        )
        return True

    # ======================== 服务器列表 ========================

    def get_servers(self):
        """获取所有已配置的服务器 IP（从 join_qr_node_info 和 task_servicec 合并）"""
        rows = execute_query(
            "SELECT DISTINCT environment_ip FROM join_qr_node_info "
            "WHERE environment_ip IS NOT NULL AND environment_ip != '' "
            "ORDER BY environment_ip"
        ) or []
        return [r['environment_ip'] for r in rows]

    # ======================== 区域列表 ========================

    def get_areas(self):
        """获取 LEVEL=1 的父区域列表"""
        rows = execute_query(
            "SELECT id, name FROM bms_area WHERE level = 1 ORDER BY id"
        ) or []
        return [{'id': r['id'], 'name': r['name']} for r in rows]

    # ======================== 模板交接点检查 ========================

    def check_template_join_qr(self, template_id):
        """
        检查模板涉及的服务器是否都已配置对应区域的交接点
        
        返回: (data_dict, error_msg)
        data_dict = {
            'area_id': ...,
            'area_name': ...,
            'servers': [{'server': 'xx', 'configured': True, 'count': 5}, ...],
            'all_configured': True/False,
            'total_servers': N,
            'configured_servers': N
        }
        """
        template = execute_query(
            "SELECT area_id FROM fy_cross_model_process WHERE id = %s",
            (template_id,)
        )
        if not template:
            return None, '模板不存在'

        area_id = template[0].get('area_id')
        if not area_id:
            return None, '模板未设置区域ID'

        # 获取区域名称
        area_info = execute_query(
            "SELECT id, name FROM bms_area WHERE id = %s AND level = 1",
            (area_id,)
        )
        area_name = area_info[0]['name'] if area_info else str(area_id)

        # 获取子任务涉及的服务器
        details = execute_query(
            "SELECT DISTINCT task_servicec FROM fy_cross_model_process_detail "
            "WHERE model_process_id = %s AND task_servicec IS NOT NULL AND task_servicec != ''",
            (template_id,)
        ) or []

        servers = set()
        for d in details:
            url = d.get('task_servicec', '') or ''
            m = re.search(r'(\d+\.\d+\.\d+\.\d+)', url)
            if m:
                servers.add(m.group(1))

        if not servers:
            return {'area_id': area_id, 'area_name': area_name,
                    'servers': [], 'all_configured': False,
                    'total_servers': 0, 'configured_servers': 0}, None

        # 逐个检查
        items = []
        for ip in sorted(servers):
            rows = execute_query(
                "SELECT COUNT(*) as cnt FROM join_qr_node_info "
                "WHERE environment_ip = %s AND area_id = %s",
                (ip, area_id)
            )
            count = rows[0]['cnt'] if rows else 0
            items.append({
                'server': ip,
                'configured': count > 0,
                'count': count,
            })

        configured_count = sum(1 for i in items if i['configured'])
        return {
            'area_id': area_id,
            'area_name': area_name,
            'servers': items,
            'all_configured': all(i['configured'] for i in items),
            'total_servers': len(items),
            'configured_servers': configured_count
        }, None
