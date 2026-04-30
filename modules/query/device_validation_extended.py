#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设备验证扩展模块
整合SQL脚本的设备验证和数据库操作功能
"""

import pymysql
from pymysql.cursors import DictCursor
from modules.database.connection import get_db_connection

def validate_device_sn(device_sn, device_type="agv"):
    """
    验证设备序列号
    :param device_sn: 设备序列号
    :param device_type: 设备类型 (agv, shelf, rfid)
    :return: 验证结果字典
    """
    conn = get_db_connection()
    if conn is None:
        return {"error": "数据库连接失败"}
    
    try:
        with conn.cursor() as cursor:
            if device_type == "agv":
                # 验证AGV设备
                sql = "SELECT * FROM agv_robot WHERE DEVICE_CODE = %s"
                cursor.execute(sql, (device_sn,))
                device = cursor.fetchone()
                
                if device:
                    return {
                        "valid": True,
                        "device_type": "AGV",
                        "device_ip": device.get('DEVICE_IP'),
                        "device_model": device.get('DEVICETYPE'),
                        "area_id": device.get('AREA_ID'),
                        "status": device.get('STATUS'),
                        "message": "设备验证成功"
                    }
                else:
                    return {
                        "valid": False,
                        "message": "未找到该AGV设备"
                    }
                    
            elif device_type == "shelf":
                # 验证货架设备（需要根据实际表结构调整）
                sql = "SELECT * FROM shelf_config WHERE shelf_code = %s"
                cursor.execute(sql, (device_sn,))
                device = cursor.fetchone()
                
                if device:
                    return {
                        "valid": True,
                        "device_type": "货架",
                        "shelf_model": device.get('model'),
                        "status": device.get('status'),
                        "message": "货架验证成功"
                    }
                else:
                    return {
                        "valid": False,
                        "message": "未找到该货架设备"
                    }
                    
            elif device_type == "rfid":
                # 验证RFID设备（需要根据实际表结构调整）
                sql = "SELECT * FROM device_rfid WHERE rfid_code = %s"
                cursor.execute(sql, (device_sn,))
                device = cursor.fetchone()
                
                if device:
                    return {
                        "valid": True,
                        "device_type": "RFID",
                        "device_ip": device.get('device_ip'),
                        "status": device.get('status'),
                        "message": "RFID设备验证成功"
                    }
                else:
                    return {
                        "valid": False,
                        "message": "未找到该RFID设备"
                    }
            else:
                return {
                    "valid": False,
                    "message": "不支持的设备类型"
                }
                
    except Exception as e:
        return {"error": f"验证失败: {str(e)}"}
    finally:
        conn.close()

def sync_device_data(source_config, target_config, device_type, table_name="agv_robot"):
    """
    同步设备数据（基于copy_robot.py功能）
    :param source_config: 源数据库配置
    :param target_config: 目标数据库配置
    :param device_type: 设备类型
    :param table_name: 目标表名
    :return: 同步结果字典
    """
    try:
        # 连接源数据库
        source_conn = pymysql.connect(**source_config, cursorclass=DictCursor)
        
        # 查询源数据
        with source_conn.cursor() as cursor:
            sql = "SELECT * FROM agv_robot WHERE DEVICETYPE = %s"
            cursor.execute(sql, (device_type,))
            rows = cursor.fetchall()
            
        if not rows:
            return {"success": False, "message": "源数据库中没有符合条件的设备数据"}
        
        # 连接目标数据库
        target_conn = pymysql.connect(**target_config)
        target_cursor = target_conn.cursor()
        
        # 目标表字段（除去ID）
        target_fields = [
            'DEVICE_CODE', 'DEVICE_IP', 'DEVICE_PORT', 'USRENAME', 'PASSWORD',
            'DEVICETYPE', 'CAPACITIES', 'DETAILTYPE', 'MAC', 'UPDATE_DATE',
            'CREATE_DATE', 'config', 'CONFIG_PARM', 'VERSION_SN', 'PROTOCOL',
            'MACS_VERSION', 'MILEAGE', 'DIRECT_CONNECTION'
        ]
        
        # 构造INSERT IGNORE语句
        placeholders = ', '.join(['%s'] * len(target_fields))
        fields_str = ', '.join([f'`{f}`' for f in target_fields])
        insert_sql = f"INSERT IGNORE INTO `{table_name}` ({fields_str}) VALUES ({placeholders})"
        
        success_count = 0
        skip_count = 0
        
        # 逐条插入数据
        for row in rows:
            values = [row.get(field) for field in target_fields]
            try:
                target_cursor.execute(insert_sql, values)
                if target_cursor.rowcount == 1:
                    success_count += 1
                else:
                    skip_count += 1
            except Exception as e:
                target_conn.rollback()
                continue
        
        target_conn.commit()
        
        return {
            "success": True,
            "message": f"同步完成: 成功插入 {success_count} 条，跳过 {skip_count} 条",
            "success_count": success_count,
            "skip_count": skip_count
        }
        
    except Exception as e:
        return {"success": False, "message": f"同步失败: {str(e)}"}
    finally:
        if 'source_conn' in locals():
            source_conn.close()
        if 'target_conn' in locals():
            target_conn.close()

def add_device_to_group(device_sn, group_name, target_area):
    """
    添加设备到设备组（基于add_device_ext.py功能）
    :param device_sn: 设备序列号
    :param group_name: 设备组名称
    :param target_area: 目标区域
    :return: 操作结果字典
    """
    conn = get_db_connection()
    if conn is None:
        return {"error": "数据库连接失败"}
    
    try:
        with conn.cursor() as cursor:
            # 1. 验证设备是否存在
            sql = "SELECT * FROM agv_robot WHERE DEVICE_CODE = %s"
            cursor.execute(sql, (device_sn,))
            device = cursor.fetchone()
            
            if not device:
                return {"success": False, "message": "设备不存在"}
            
            # 2. 获取或创建设备组
            sql = "SELECT id FROM agv_robot_group WHERE group_name = %s"
            cursor.execute(sql, (group_name,))
            group_result = cursor.fetchone()
            
            if group_result:
                group_id = group_result['id']
            else:
                # 创建设备组
                sql = "INSERT INTO agv_robot_group (group_name, create_time) VALUES (%s, NOW())"
                cursor.execute(sql, (group_name,))
                group_id = cursor.lastrowid
            
            # 3. 添加设备到组
            sql = """
                INSERT IGNORE INTO agv_robot_group_detail 
                (group_id, device_code, device_number, create_time) 
                VALUES (%s, %s, %s, NOW())
            """
            cursor.execute(sql, (group_id, device_sn, f"DEV_{device_sn}"))
            
            # 4. 更新设备扩展表
            sql = """
                INSERT IGNORE INTO agv_robot_ext 
                (DEVICE_CODE, DEVICE_AREA, DEVICE_NUMBER, CREATE_DATE, ENABLE) 
                VALUES (%s, %s, %s, NOW(), 1)
            """
            cursor.execute(sql, (device_sn, target_area, f"DEV_{device_sn}"))
            
            conn.commit()
            
            return {
                "success": True,
                "message": f"设备 {device_sn} 已成功添加到组 {group_name}",
                "group_id": group_id
            }
            
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": f"添加失败: {str(e)}"}
    finally:
        conn.close()

def get_device_groups():
    """
    获取所有设备组
    :return: 设备组列表
    """
    conn = get_db_connection()
    if conn is None:
        return []
    
    try:
        with conn.cursor() as cursor:
            sql = "SELECT id, group_name, create_time FROM agv_robot_group ORDER BY create_time DESC"
            cursor.execute(sql)
            groups = cursor.fetchall()
            return groups
    except Exception as e:
        return []
    finally:
        conn.close()

def get_group_devices(group_id):
    """
    获取设备组内的设备列表
    :param group_id: 设备组ID
    :return: 设备列表
    """
    conn = get_db_connection()
    if conn is None:
        return []
    
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT d.device_code, d.device_number, r.DEVICE_IP, r.DEVICETYPE
                FROM agv_robot_group_detail d
                LEFT JOIN agv_robot r ON d.device_code = r.DEVICE_CODE
                WHERE d.group_id = %s
            """
            cursor.execute(sql, (group_id,))
            devices = cursor.fetchall()
            return devices
    except Exception as e:
        return []
    finally:
        conn.close()