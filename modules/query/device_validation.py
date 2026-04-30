#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设备验证模块
基于agv-task-query的validate-device.php功能
"""

from ..database.helpers import fetch_all, fetch_one

def validate_agv_device(device_sn, use_production=False):
    """
    验证AGV设备序列号
    模仿validate-device.php的验证逻辑
    """
    query = """
    SELECT 
        a.*,
        at.type_name as agv_type_name,
        at.max_load as agv_max_load,
        m.model_name,
        m.manufacturer
    FROM agv_robot a
    LEFT JOIN agv_type at ON a.agv_type_id = at.id
    LEFT JOIN agv_model m ON a.agv_model_id = m.id
    WHERE a.robot_sn = %s OR a.robot_code = %s
    LIMIT 1
    """
    
    return fetch_one(query, (device_sn, device_sn), use_production)

def validate_shelf_device(device_sn, use_production=False):
    """
    验证货架设备序列号
    """
    query = """
    SELECT 
        s.*,
        sm.model_name,
        sm.model_code,
        sm.max_capacity,
        sm.dimensions
    FROM shelf s
    LEFT JOIN shelf_model sm ON s.shelf_model_id = sm.id
    WHERE s.shelf_sn = %s OR s.shelf_code = %s
    LIMIT 1
    """
    
    return fetch_one(query, (device_sn, device_sn), use_production)

def validate_rfid_device(rfid_code, use_production=False):
    """
    验证RFID设备
    """
    query = """
    SELECT 
        r.*,
        rt.type_name as rfid_type,
        l.location_name,
        l.area_code
    FROM rfid_device r
    LEFT JOIN rfid_type rt ON r.rfid_type_id = rt.id
    LEFT JOIN location l ON r.location_id = l.id
    WHERE r.rfid_code = %s
    LIMIT 1
    """
    
    return fetch_one(query, (rfid_code,), use_production)

def get_device_status_history(device_id, device_type='agv', limit=100, use_production=False):
    """
    获取设备状态历史记录
    :param device_id: 设备ID
    :param device_type: 设备类型，可选值：agv, shelf, rfid
    :param limit: 返回记录数限制
    """
    if device_type == 'agv':
        query = """
        SELECT 
            ash.*,
            ast.status_name,
            ast.status_description
        FROM agv_status_history ash
        LEFT JOIN agv_status_type ast ON ash.status_type_id = ast.id
        WHERE ash.agv_robot_id = %s
        ORDER BY ash.status_time DESC
        LIMIT %s
        """
    elif device_type == 'shelf':
        query = """
        SELECT 
            ssh.*,
            sst.status_name,
            sst.status_description
        FROM shelf_status_history ssh
        LEFT JOIN shelf_status_type sst ON ssh.status_type_id = sst.id
        WHERE ssh.shelf_id = %s
        ORDER BY ssh.status_time DESC
        LIMIT %s
        """
    elif device_type == 'rfid':
        query = """
        SELECT 
            rsh.*,
            rst.status_name,
            rst.status_description
        FROM rfid_status_history rsh
        LEFT JOIN rfid_status_type rst ON rsh.status_type_id = rst.id
        WHERE rsh.rfid_device_id = %s
        ORDER BY rsh.status_time DESC
        LIMIT %s
        """
    else:
        return []
    
    return fetch_all(query, (device_id, limit), use_production)

def get_device_maintenance_records(device_id, device_type='agv', limit=50, use_production=False):
    """
    获取设备维护记录
    """
    if device_type == 'agv':
        query = """
        SELECT 
            amr.*,
            mt.maintenance_type_name,
            u.username as maintenance_person
        FROM agv_maintenance_record amr
        LEFT JOIN maintenance_type mt ON amr.maintenance_type_id = mt.id
        LEFT JOIN user u ON amr.maintenance_person_id = u.id
        WHERE amr.agv_robot_id = %s
        ORDER BY amr.maintenance_time DESC
        LIMIT %s
        """
    elif device_type == 'shelf':
        query = """
        SELECT 
            smr.*,
            mt.maintenance_type_name,
            u.username as maintenance_person
        FROM shelf_maintenance_record smr
        LEFT JOIN maintenance_type mt ON smr.maintenance_type_id = mt.id
        LEFT JOIN user u ON smr.maintenance_person_id = u.id
        WHERE smr.shelf_id = %s
        ORDER BY smr.maintenance_time DESC
        LIMIT %s
        """
    else:
        return []
    
    return fetch_all(query, (device_id, limit), use_production)

def check_device_availability(device_id, device_type='agv', use_production=False):
    """
    检查设备可用性
    """
    if device_type == 'agv':
        query = """
        SELECT 
            a.is_online,
            a.current_status,
            a.last_heartbeat_time,
            TIMESTAMPDIFF(MINUTE, a.last_heartbeat_time, NOW()) as minutes_since_last_heartbeat
        FROM agv_robot a
        WHERE a.id = %s
        """
    elif device_type == 'shelf':
        query = """
        SELECT 
            s.is_available,
            s.current_status,
            s.last_check_time
        FROM shelf s
        WHERE s.id = %s
        """
    else:
        return None
    
    result = fetch_one(query, (device_id,), use_production)
    
    if result:
        # 判断设备是否可用
        if device_type == 'agv':
            result['is_available'] = result['is_online'] == 1 and result['minutes_since_last_heartbeat'] < 5
        elif device_type == 'shelf':
            result['is_available'] = result['is_available'] == 1
        
        return result
    
    return None