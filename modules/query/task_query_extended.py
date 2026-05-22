#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务查询扩展模块
基于1.3项目的FindTheTask.php功能移植
"""

import pymysql
from pymysql.cursors import DictCursor
from datetime import datetime
from modules.database.connection import get_db_connection

def get_task_info_by_order_id(order_id, server_ip=None):
    """
    根据任务订单ID查询任务详细信息
    对应FindTheTask.php功能
    """
    if server_ip:
        # 如果指定了服务器IP，使用生产环境连接
        conn = connect_to_production_db(server_ip)
    else:
        # 使用默认配置的数据库连接
        conn = get_db_connection()
    
    if conn is None:
        return {"error": "数据库连接失败"}
    
    try:
        with conn.cursor() as cursor:
            # 查询任务组信息
            sql = "SELECT * FROM task_group WHERE third_order_id = %s"
            cursor.execute(sql, (order_id,))
            task_group = cursor.fetchone()
            
            if not task_group:
                return {"error": "未找到对应的任务信息"}
            
            # 获取设备IP
            device_ip = get_device_ip_by_code(conn, task_group['robot_id'])
            
            # 获取货架模型名称
            shelf_model_name = get_shelf_model_name(conn, task_group['shelf_model'])
            
            # 获取任务状态名称
            task_status_name = get_task_status_name(conn, task_group['status'])
            
            # 格式化时间
            create_time = format_timestamp(task_group['create_time'])
            start_time = format_timestamp(task_group['start_time'])
            end_time = format_timestamp(task_group['end_time'])
            
            result = {
                "area_id": task_group['area_id'],
                "template_code": task_group['template_code'],
                "robot_num": task_group['robot_num'],
                "robot_id": task_group['robot_id'],
                "device_ip": device_ip,
                "path_points": task_group['path_points'],
                "robot_type": task_group['robot_type'],
                "shelf_model": task_group['shelf_model'],
                "shelf_model_name": shelf_model_name,
                "carrier_code": task_group['carrier_code'],
                "error_desc": task_group['error_desc'],
                "create_time": create_time,
                "start_time": start_time,
                "end_time": end_time,
                "status": task_group['status'],
                "task_status_name": task_status_name,
                "order_id": task_group['order_id'],
                "out_order_id": task_group['out_order_id'],
                "tg_id": task_group['id']
            }
            
            return result
            
    except Exception as e:
        return {"error": f"查询失败: {str(e)}"}
    finally:
        conn.close()

def get_task_group_by_order_id(order_id, server_ip=None):
    """
    根据订单ID获取task_group和task_group_detail信息
    支持本地数据库和远程服务器查询
    按照FindTheTask.php的逻辑完善查询
    """
    from modules.database.connection import get_db_connection
    
    # 首先尝试查询本地数据库
    conn = get_db_connection()
    if conn is None:
        return {"error": "数据库连接失败"}
    
    try:
        with conn.cursor() as cursor:
            # 查询task_group信息（按照PHP文件的逻辑）
            sql = "SELECT * FROM task_group WHERE third_order_id = %s OR order_id = %s OR out_order_id = %s"
            cursor.execute(sql, (order_id, order_id, order_id))
            task_group = cursor.fetchone()
            
            if task_group:
                # 关联查询其他信息（按照PHP文件的逻辑）
                # 1. 查询设备IP
                device_ip = None
                if task_group.get('robot_id'):
                    try:
                        sql = "SELECT DEVICE_IP FROM agv_robot WHERE DEVICE_CODE = %s"
                        cursor.execute(sql, (task_group['robot_id'],))
                        device_ip_result = cursor.fetchone()
                        if device_ip_result:
                            device_ip = device_ip_result['DEVICE_IP']
                    except Exception as e:
                        print(f"查询设备IP失败: {e}")
                
                # 2. 查询货架模型名称
                shelf_model_name = None
                if task_group.get('shelf_model'):
                    try:
                        sql = "SELECT name FROM load_config WHERE model = %s"
                        cursor.execute(sql, (task_group['shelf_model'],))
                        shelf_model_result = cursor.fetchone()
                        if shelf_model_result:
                            shelf_model_name = shelf_model_result['name']
                    except Exception as e:
                        print(f"查询货架模型名称失败: {e}")
                
                # 3. 查询任务状态名称
                task_status_name = None
                if task_group.get('status') is not None:
                    try:
                        sql = "SELECT task_status_name FROM task_status_config WHERE task_status = %s"
                        cursor.execute(sql, (task_group['status'],))
                        status_result = cursor.fetchone()
                        if status_result:
                            task_status_name = status_result['task_status_name']
                    except Exception as e:
                        print(f"查询任务状态名称失败: {e}")
                
                # 添加关联查询结果到task_group
                task_group['device_ip'] = device_ip
                task_group['shelf_model_name'] = shelf_model_name
                task_group['task_status_name'] = task_status_name
                
                # 查询task_group_detail信息
                task_group_details = []
                try:
                    sql = """
                    SELECT 
                        id, tg_id, task_seq, start_point, end_point, 
                        x, y, action, angel, shelf_num, robot_id,
                        robot_num, start_time, end_time, status,
                        area_id, task_type, point_type, need_trigger,
                        notify_third, shelf_model
                    FROM task_group_detail 
                    WHERE tg_id = %s 
                    ORDER BY task_seq
                    """
                    cursor.execute(sql, (task_group['id'],))
                    task_group_details = cursor.fetchall()
                    
                    # 为每个子任务查询关联信息
                    for detail in task_group_details:
                        # 查询子任务设备IP
                        if detail.get('robot_id'):
                            try:
                                sql = "SELECT DEVICE_IP FROM agv_robot WHERE DEVICE_CODE = %s"
                                cursor.execute(sql, (detail['robot_id'],))
                                detail_device_ip = cursor.fetchone()
                                if detail_device_ip:
                                    detail['device_ip'] = detail_device_ip['DEVICE_IP']
                            except Exception as e:
                                print(f"查询子任务设备IP失败: {e}")
                        
                        # 查询子任务状态名称
                        if detail.get('status') is not None:
                            try:
                                sql = "SELECT task_status_name FROM task_status_config WHERE task_status = %s"
                                cursor.execute(sql, (detail['status'],))
                                detail_status = cursor.fetchone()
                                if detail_status:
                                    detail['task_status_name'] = detail_status['task_status_name']
                            except Exception as e:
                                print(f"查询子任务状态名称失败: {e}")
                                
                except Exception as detail_error:
                    # 如果查询失败，尝试简单查询
                    try:
                        sql = "SELECT * FROM task_group_detail WHERE tg_id = %s ORDER BY task_seq"
                        cursor.execute(sql, (task_group['id'],))
                        task_group_details = cursor.fetchall()
                    except Exception as e2:
                        print(f"注意: task_group_detail表查询失败: {e2}")
                        task_group_details = []
                
                return {
                    "taskGroup": task_group,
                    "details": task_group_details,
                    "source": "local"
                }
            
    except Exception as e:
        print(f"本地数据库查询失败: {e}")
    finally:
        conn.close()
    
    # 如果本地没有找到，尝试查询远程服务器（跨环境任务）
    try:
        if not server_ip:
            server_ip = "10.68.2.32"
        
        # 连接到生产环境数据库
        prod_conn = connect_to_production_db(server_ip)
        
        with prod_conn.cursor() as cursor:
            # 查询fy_cross_task表
            sql = "SELECT * FROM fy_cross_task WHERE orderId = %s"
            cursor.execute(sql, (order_id,))
            cross_task = cursor.fetchone()
            
            if cross_task:
                # 查询子任务详情
                sql = "SELECT * FROM fy_cross_task_detail WHERE order_id = %s"
                cursor.execute(sql, (order_id,))
                cross_task_details = cursor.fetchall()
                
                # 转换为task_group格式（兼容前端显示）
                task_group = {
                    "id": cross_task.get('id'),
                    "third_order_id": cross_task.get('orderId'),
                    "order_id": cross_task.get('orderId'),
                    "model_process_code": cross_task.get('model_process_code'),
                    "status": cross_task.get('task_status'),
                    "create_time": cross_task.get('create_time'),
                    "start_time": cross_task.get('start_time'),
                    "end_time": cross_task.get('end_time'),
                    "source": "cross_task"
                }
                
                # 转换子任务格式
                details = []
                for detail in cross_task_details:
                    details.append({
                        "id": detail.get('id'),
                        "sub_order_id": detail.get('sub_order_id'),
                        "service_url": detail.get('service_url'),
                        "create_time": detail.get('create_time'),
                        "source": "cross_task_detail"
                    })
                
                return {
                    "taskGroup": task_group,
                    "details": details,
                    "source": "remote"
                }
            else:
                return {"error": "未找到对应的任务记录（本地和远程）"}
                
    except Exception as e:
        print(f"远程服务器查询失败: {e}")
        return {"error": f"远程服务器查询失败: {str(e)}"}
    
    return {"error": "未找到对应的任务记录"}

def get_cross_task_info(order_id, server_ip=None):
    """
    查询跨环境任务信息
    对应FindTheTaskKua.php功能
    """
    if server_ip:
        conn = connect_to_production_db(server_ip)
    else:
        from modules.database.connection import get_db_connection
        conn = get_db_connection()
    
    if conn is None:
        return {"error": "数据库连接失败"}
    
    try:
        with conn.cursor() as cursor:
            # 查询跨环境任务详情（用 order_id 精确匹配，所有子任务共享同一个主 order_id）
            # 按 task_seq 排序确保第一个子任务（_1）排在前面
            sql = "SELECT * FROM fy_cross_task_detail WHERE order_id = %s ORDER BY task_seq ASC"
            cursor.execute(sql, (order_id,))
            cross_task_details = cursor.fetchall()
            
            # 查询跨环境任务模板信息
            sql = "SELECT model_process_code FROM fy_cross_task WHERE orderId = %s"
            cursor.execute(sql, (order_id,))
            model_process_code_result = cursor.fetchone()
            
            model_process_code = None
            active_task_count = 0
            related_tasks = []
            
            if model_process_code_result:
                model_process_code = model_process_code_result.get('model_process_code')
                
                if model_process_code:
                    # 统计当前执行中的任务数
                    sql = """
                        SELECT COUNT(0) as count 
                        FROM fy_cross_task 
                        WHERE model_process_code = %s 
                        AND task_status IN (0,1,6,4,9,10)
                    """
                    cursor.execute(sql, (model_process_code,))
                    count_result = cursor.fetchone()
                    active_task_count = count_result['count'] if count_result else 0
                    
                    # 查询所有相关任务
                    sql = """
                        SELECT * FROM fy_cross_task 
                        WHERE model_process_code = %s 
                        AND task_status IN (0,1,6,4,9,10)
                    """
                    cursor.execute(sql, (model_process_code,))
                    related_tasks = cursor.fetchall()
            
            result = {
                "cross_task_details": cross_task_details,
                "model_process_code": model_process_code,
                "active_task_count": active_task_count,
                "related_tasks": related_tasks
            }
            
            return result
            
    except Exception as e:
        return {"error": f"查询失败: {str(e)}"}
    finally:
        conn.close()

def get_device_ip_by_code(conn, device_code):
    """根据设备序列号获取设备IP"""
    try:
        with conn.cursor() as cursor:
            sql = "SELECT DEVICE_IP FROM agv_robot WHERE DEVICE_CODE = %s"
            cursor.execute(sql, (device_code,))
            result = cursor.fetchone()
            return result['DEVICE_IP'] if result else "未知"
    except:
        return "未知"

def get_shelf_model_name(conn, shelf_model):
    """根据货架模型编号获取货架模型名称"""
    try:
        with conn.cursor() as cursor:
            sql = "SELECT name FROM load_config WHERE model = %s"
            cursor.execute(sql, (shelf_model,))
            result = cursor.fetchone()
            return result['name'] if result else "未知"
    except:
        return "未知"

def get_task_status_name(conn, status):
    """根据任务状态值获取状态名称"""
    try:
        with conn.cursor() as cursor:
            sql = "SELECT task_status_name FROM task_status_config WHERE task_status = %s"
            cursor.execute(sql, (status,))
            result = cursor.fetchone()
            return result['task_status_name'] if result else "未知"
    except:
        return "未知"

def format_timestamp(timestamp):
    """格式化时间戳"""
    if timestamp:
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    return ""

def connect_to_production_db(server_ip, db_name="wms"):
    """连接到生产环境数据库（5秒超时）"""
    try:
        conn = pymysql.connect(
            host=server_ip,
            user='wms',
            password='CCshenda889',
            database=db_name,
            charset='utf8mb4',
            connect_timeout=5,
            cursorclass=pymysql.cursors.DictCursor
        )
        return conn
    except Exception as e:
        raise Exception(f"连接生产环境数据库失败: {str(e)}")

def search_tasks_by_template(template_code, server_ip="10.68.2.32"):
    """
    根据任务模板代码搜索任务
    对应Kua.php功能
    """
    conn = connect_to_production_db(server_ip)
    
    try:
        with conn.cursor() as cursor:
            # 统计当前执行中的任务数
            sql = """
                SELECT COUNT(0) as count 
                FROM fy_cross_task 
                WHERE model_process_code = %s 
                AND task_status IN (0,1,6,4,9,10)
            """
            cursor.execute(sql, (template_code,))
            count_result = cursor.fetchone()
            active_task_count = count_result['count'] if count_result else 0
            
            # 查询所有相关任务
            sql = """
                SELECT * FROM fy_cross_task 
                WHERE model_process_code = %s 
                AND task_status IN (0,1,6,4,9,10)
            """
            cursor.execute(sql, (template_code,))
            tasks = cursor.fetchall()
            
            return {
                "active_task_count": active_task_count,
                "tasks": tasks
            }
            
    except Exception as e:
        return {"error": f"查询失败: {str(e)}"}
    finally:
        conn.close()

def get_cross_model_process_info(template_code, server_ip="10.68.2.32"):
    """
    查询跨环境任务模板信息及子任务
    对应Chech_Kua_model_process.php功能
    """
    conn = connect_to_production_db(server_ip)
    
    try:
        with conn.cursor() as cursor:
            # 查询主模板信息
            sql = "SELECT * FROM fy_cross_model_process WHERE model_process_code = %s"
            cursor.execute(sql, (template_code,))
            main_template = cursor.fetchone()
            
            if not main_template:
                return {"error": "未找到对应的跨环境任务模板"}
            
            template_id = main_template['id']
            
            # 查询子任务信息
            sql = "SELECT * FROM fy_cross_model_process_detail WHERE model_process_id = %s"
            cursor.execute(sql, (template_id,))
            sub_tasks = cursor.fetchall()
            
            return {
                "main_template": main_template,
                "sub_tasks": sub_tasks,
                "template_id": template_id
            }
            
    except Exception as e:
        return {"error": f"查询失败: {str(e)}"}
    finally:
        conn.close()


def resend_cross_task(order_id, sub_order_id, task_seq, server_ip="10.68.2.32"):
    """
    跨环境任务重发逻辑（统一逻辑1+逻辑2+逻辑3）
    
    流程：
    0. 调用远端服务器取消任务接口
    1. 前置任务检查（task_seq-1 是否还在执行中）
    2. 检查大模板状态
    3. 检查子模板状态
    4. 生成新的 sub_order_id（子ID+1）
    5. 修改数据库状态
    
    返回: dict { success, message, newSubOrderId?, code?, precedingTaskId?, serverUrl? }
    """
    import urllib.request as _urllib
    import json as _json
    import time as _time
    
    conn = connect_to_production_db(server_ip)
    
    try:
        with conn.cursor() as cursor:
            # ========== 步骤0: 调用远端服务器取消任务接口 ==========
            # 先查询子任务的 service_url 获取服务器地址
            sql = """
                SELECT sub_order_id, service_url, status
                FROM fy_cross_task_detail
                WHERE order_id = %s AND task_seq = %s
            """
            cursor.execute(sql, (order_id, task_seq))
            sub_task_info = cursor.fetchone()
            
            if not sub_task_info:
                return {
                    "success": False,
                    "code": "SUBTASK_NOT_FOUND",
                    "message": f"未找到子任务: order_id={order_id}, task_seq={task_seq}"
                }
            
            service_url = sub_task_info.get('service_url', '')
            if service_url:
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(service_url)
                    cancel_server_ip = parsed.hostname
                    if cancel_server_ip:
                        cancel_url = f"http://{cancel_server_ip}:7000/ics/out/task/cancelTask"
                        cancel_body = [{"orderId": sub_order_id, "destPosition": ""}]
                        cancel_body_str = _json.dumps(cancel_body)
                        t0 = _time.time()
                        try:
                            req = _urllib.Request(cancel_url, data=cancel_body_str.encode('utf-8'),
                                headers={'Content-Type': 'application/json'}, method='POST')
                            resp = _urllib.urlopen(req, timeout=10)
                            elapsed_ms = round((_time.time() - t0) * 1000, 1)
                            raw = resp.read().decode('utf-8')
                            try:
                                cancel_resp = _json.loads(raw)
                            except:
                                cancel_resp = raw
                            # 检查取消结果：code=1000 表示成功
                            if isinstance(cancel_resp, dict) and cancel_resp.get('code') != 1000:
                                return {
                                    "success": False,
                                    "code": "CANCEL_FAILED",
                                    "message": f"远端取消任务失败: {cancel_resp.get('message', cancel_resp)}",
                                    "cancel_response": cancel_resp
                                }
                        except Exception as e:
                            elapsed_ms = round((_time.time() - t0) * 1000, 1)
                            return {
                                "success": False,
                                "code": "CANCEL_ERROR",
                                "message": f"调用远端取消接口失败: {str(e)}",
                                "cancel_url": cancel_url
                            }
                except Exception as e:
                    # 解析 service_url 失败不阻塞，继续重发流程
                    pass
            
            # ========== 步骤1: 前置任务检查（放到最前面） ==========
            if task_seq > 1:
                preceding_seq = task_seq - 1
                sql = """
                    SELECT sub_order_id, service_url, status
                    FROM fy_cross_task_detail
                    WHERE order_id = %s AND task_seq = %s
                """
                cursor.execute(sql, (order_id, preceding_seq))
                preceding_task = cursor.fetchone()
                
                if preceding_task and preceding_task['status'] in (4, 6, 9):
                    # 上一条任务仍在执行中，不允许重发
                    return {
                        "success": False,
                        "code": "PRECEDING_TASK_ACTIVE",
                        "precedingTaskId": preceding_task['sub_order_id'],
                        "serverUrl": preceding_task['service_url'],
                        "message": (
                            f"上一条任务（task_seq={preceding_seq}）仍在执行中"
                            f"（status={preceding_task['status']}），"
                            f"请先到对应服务器查询或取消该任务后再重发"
                        )
                    }
            
            # ========== 步骤2: 检查大模板状态 ==========
            sql = "SELECT task_status FROM fy_cross_task WHERE orderId = %s"
            cursor.execute(sql, (order_id,))
            main_task = cursor.fetchone()
            
            if not main_task:
                return {
                    "success": False,
                    "code": "TASK_NOT_FOUND",
                    "message": f"未找到大模板任务: {order_id}"
                }
            
            main_status = main_task['task_status']
            
            # 允许重发的大模板状态: 排除 6(执行中) 和 8(已完成)
            if main_status in (6, 8):
                return {
                    "success": False,
                    "code": "INVALID_STATUS",
                    "message": f"大模板状态不允许重发（当前状态: {main_status}）"
                }
            
            # ========== 步骤3: 检查子模板状态 ==========
            sql = """
                SELECT * FROM fy_cross_task_detail
                WHERE order_id = %s AND task_seq = %s
            """
            cursor.execute(sql, (order_id, task_seq))
            sub_task = cursor.fetchone()
            
            if not sub_task:
                return {
                    "success": False,
                    "code": "SUBTASK_NOT_FOUND",
                    "message": f"未找到子任务: order_id={order_id}, task_seq={task_seq}"
                }
            
            sub_status = sub_task['status']
            current_sub_order_id = sub_task['sub_order_id']
            
            # 允许重发的子模板状态: 排除 6(执行中) 和 8(已完成)
            if sub_status in (6, 8):
                return {
                    "success": False,
                    "code": "INVALID_STATUS",
                    "message": f"子任务状态不允许重发（当前状态: {sub_status}）"
                }
            
            # 逻辑3特殊处理: 检查是否有多个执行中的子任务（仅对状态4,6,9检查）
            if sub_status in (4, 9):
                sql = """
                    SELECT COUNT(*) as cnt FROM fy_cross_task_detail
                    WHERE order_id = %s AND status IN (4, 6, 9)
                """
                cursor.execute(sql, (order_id,))
                active_count = cursor.fetchone()['cnt']
                
                if active_count > 1:
                    # 多个执行中任务，异常情况
                    sql = """
                        SELECT sub_order_id, task_seq, status, service_url, error_desc
                        FROM fy_cross_task_detail
                        WHERE order_id = %s AND status IN (4, 6, 9)
                    """
                    cursor.execute(sql, (order_id,))
                    active_tasks = cursor.fetchall()
                    
                    return {
                        "success": False,
                        "code": "MULTIPLE_ACTIVE",
                        "message": (
                            "该异常任务可能与跨环境模块负荷异常或重启导致，"
                            "反馈研发后可使用该功能进行恢复。"
                            f"当前有 {active_count} 个执行中的子任务"
                        ),
                        "activeTasks": active_tasks
                    }
            
            # ========== 步骤4: 生成新的 sub_order_id ==========
            new_sub_order_id = _generate_new_sub_order_id(current_sub_order_id)
            if not new_sub_order_id:
                return {
                    "success": False,
                    "code": "PARSE_ERROR",
                    "message": f"无法解析 sub_order_id: {current_sub_order_id}"
                }
            
            # ========== 步骤5: 执行重发（修改数据库） ==========
            
            # 5.1 判断是否需要修改大模板状态
            # 大模板状态不是5,7时需要改为5
            if main_status not in (5, 7):
                sql = "UPDATE fy_cross_task SET task_status = 5 WHERE orderId = %s"
                cursor.execute(sql, (order_id,))
            
            # 5.2 更新子模板
            sql = """
                UPDATE fy_cross_task_detail
                SET sub_order_id = %s, status = 5, error_desc = '重发中'
                WHERE order_id = %s AND task_seq = %s
            """
            cursor.execute(sql, (new_sub_order_id, order_id, task_seq))
            conn.commit()
            
            return {
                "success": True,
                "newSubOrderId": new_sub_order_id,
                "message": f"重发成功，新子任务ID: {new_sub_order_id}，3秒后将自动刷新"
            }
            
    except Exception as e:
        conn.rollback()
        return {
            "success": False,
            "code": "SERVER_ERROR",
            "message": f"重发失败: {str(e)}"
        }
    finally:
        conn.close()


def _generate_new_sub_order_id(sub_order_id):
    """
    生成新的 sub_order_id，将最后一段数字+1
    
    格式: {orderId}_{taskSeq}_{subId}
    例如: "1.7771976967327742E12_2_5450" → "1.7771976967327742E12_2_5451"
    """
    try:
        # 从右边找到最后一个下划线
        last_underscore = sub_order_id.rfind('_')
        if last_underscore == -1:
            return None
        
        prefix = sub_order_id[:last_underscore + 1]
        sub_id_str = sub_order_id[last_underscore + 1:]
        
        # 尝试解析为数字
        sub_id = int(sub_id_str)
        new_sub_id = sub_id + 1
        
        return f"{prefix}{new_sub_id}"
    except (ValueError, TypeError):
        # 如果不是纯数字，追加 _1
        return f"{sub_order_id}_1"


def force_complete_cross_task(order_id, sub_order_id, task_seq, server_ip="10.68.2.32"):
    """
    异常完成：仅将子模板状态置为3（已取消）
    
    适用场景：重发中（status=5）的子任务卡住时，手动标记为已取消
    
    不修改大模板状态，不修改 sub_order_id
    """
    conn = connect_to_production_db(server_ip)
    
    try:
        with conn.cursor() as cursor:
            # 检查子模板状态
            sql = """
                SELECT status, sub_order_id FROM fy_cross_task_detail 
                WHERE order_id = %s AND task_seq = %s
            """
            cursor.execute(sql, (order_id, task_seq))
            sub_task = cursor.fetchone()
            
            if not sub_task:
                return {
                    "success": False,
                    "code": "SUBTASK_NOT_FOUND",
                    "message": f"未找到子任务: order_id={order_id}, task_seq={task_seq}"
                }
            
            if sub_task['status'] != 5:
                return {
                    "success": False,
                    "code": "INVALID_STATUS",
                    "message": f"仅允许对重发中（status=5）的子任务执行异常完成操作（当前状态: {sub_task['status']}）"
                }
            
            # 仅修改子模板状态为3
            sql = """
                UPDATE fy_cross_task_detail 
                SET status = 3, error_desc = '异常完成'
                WHERE order_id = %s AND task_seq = %s
            """
            cursor.execute(sql, (order_id, task_seq))
            conn.commit()
            
            return {
                "success": True,
                "message": f"异常完成成功，子任务 {sub_order_id} 状态已改为3（已取消），3秒后将自动刷新"
            }
            
    except Exception as e:
        conn.rollback()
        return {
            "success": False,
            "code": "SERVER_ERROR",
            "message": f"操作失败: {str(e)}"
        }
    finally:
        conn.close()


def get_order_id_by_device_num(device_num, server_ip="10.68.2.32"):
    """
    根据设备号(device_num)查询最近的任务单号(order_id)和设备序列号(device_code)
    查询 fy_cross_task_detail 表，按 update_time DESC 取最近一条
    """
    conn = connect_to_production_db(server_ip)
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT order_id, device_code, device_num, template_code, template_name,
                       service_url, status, update_time
                FROM fy_cross_task_detail
                WHERE device_num = %s
                ORDER BY update_time DESC
                LIMIT 1
            """
            cursor.execute(sql, (device_num,))
            row = cursor.fetchone()
            if not row:
                return {"error": f"未找到设备 {device_num} 的任务记录"}
            return {
                "order_id": row['order_id'],
                "device_code": row['device_code'],
                "device_num": row['device_num'],
                "template_code": row['template_code'],
                "template_name": row['template_name'],
                "service_url": row['service_url'],
                "status": row['status'],
                "update_time": str(row['update_time']) if row['update_time'] else ''
            }
    except Exception as e:
        return {"error": f"查询设备任务失败: {str(e)}"}
    finally:
        conn.close()


def get_device_area_from_server(server_ip, device_code):
    """
    从指定服务器的 agv_robot_ext 表查询设备的 DEVICE_AREA
    """
    conn = connect_to_production_db(server_ip)
    try:
        with conn.cursor() as cursor:
            sql = "SELECT DEVICE_AREA, DEVICE_NUMBER, DEVICE_STATUS FROM agv_robot_ext WHERE DEVICE_CODE = %s"
            cursor.execute(sql, (device_code,))
            row = cursor.fetchone()
            if not row:
                return {"error": f"未在服务器 {server_ip} 找到设备 {device_code}"}
            return {
                "area_id": row['DEVICE_AREA'],
                "device_num": row['DEVICE_NUMBER'],
                "device_status": row['DEVICE_STATUS']
            }
    except Exception as e:
        return {"error": f"查询设备区域失败({server_ip}): {str(e)}"}
    finally:
        conn.close()


def query_device_status_via_service(service_url, area_id, device_code):
    """
    通过 service_url 调用设备查询接口 /ics/out/device/list/deviceInfo
    获取设备实时状态（state、battery 等），同时返回请求/响应详情
    返回字段包含 http_status、elapsed_ms 用于全链路调试
    """
    import urllib.request as _urllib
    import json as _json
    import time as _time
    # 从 service_url 提取 base URL（去掉路径部分，保留协议+主机+端口）
    # service_url 如 http://10.68.2.27:7000
    base_url = service_url.rstrip('/')
    url = f"{base_url}/ics/out/device/list/deviceInfo"
    body = {"areaId": str(area_id), "deviceType": "0", "deviceCode": device_code}
    t0 = _time.time()
    try:
        req = _urllib.Request(url,
            data=_json.dumps(body).encode('utf-8'),
            headers={'Content-Type': 'application/json'})
        resp = _urllib.urlopen(req, timeout=10)
        elapsed_ms = round((_time.time() - t0) * 1000, 1)
        http_status = resp.getcode()
        raw_response = resp.read().decode('utf-8')
        data = _json.loads(raw_response)
        response_body = data  # 完整响应
        if data.get('code') == 1000 and data.get('data'):
            device_info = data['data'][0]
            return {
                "state": device_info.get('state', '未知'),
                "battery": device_info.get('battery', ''),
                "device_code": device_info.get('deviceCode', device_code),
                "device_num": device_info.get('deviceNum', ''),
                "area_id": device_info.get('areaId', area_id),
                "raw": device_info,
                "request_url": url,
                "request_body": body,
                "response_body": response_body,
                "http_status": http_status,
                "elapsed_ms": elapsed_ms
            }
        return {
            "error": f"设备查询响应异常: code={data.get('code')}",
            "state": "查询失败",
            "request_url": url,
            "request_body": body,
            "response_body": response_body,
            "http_status": http_status,
            "elapsed_ms": elapsed_ms
        }
    except Exception as e:
        elapsed_ms = round((_time.time() - t0) * 1000, 1)
        return {
            "error": f"设备查询请求失败: {str(e)}",
            "state": "查询失败",
            "request_url": url,
            "request_body": body,
            "response_body": None,
            "http_status": None,
            "elapsed_ms": elapsed_ms
        }


def get_local_cross_task_detail(order_id):
    """
    从本地数据库直接查询 fy_cross_task 和 fy_cross_task_detail 表
    返回完整的数据库原始字段，用于前端 Tab 面板展示
    连接超时 5 秒，失败时静默返回错误
    """
    try:
        from modules.database.connection import get_db_config
        config = get_db_config()
        config['connect_timeout'] = 5
        conn = pymysql.connect(**config, cursorclass=DictCursor)
    except Exception as e:
        return {"error": f"数据库连接失败: {str(e)}"}
    
    try:
        with conn.cursor() as cursor:
            # 查询主任务
            cursor.execute(
                "SELECT * FROM fy_cross_task WHERE orderId = %s LIMIT 1",
                (order_id,)
            )
            main_task = cursor.fetchone()
            
            # 查询子任务
            cursor.execute(
                "SELECT * FROM fy_cross_task_detail WHERE order_id = %s ORDER BY id",
                (order_id,)
            )
            sub_tasks = cursor.fetchall()
            
            return {
                "success": True,
                "main_task": main_task,
                "sub_tasks": sub_tasks,
                "sub_task_count": len(sub_tasks) if sub_tasks else 0
            }
    except Exception as e:
        return {"error": f"查询失败: {str(e)}"}
    finally:
        conn.close()


def _get_production_connection():
    """获取生产环境数据库连接（只读）"""
    import pymysql
    from pymysql.cursors import DictCursor
    return pymysql.connect(
        host='10.68.2.32', port=3306, user='wms', password='CCshenda889',
        database='wms', charset='utf8mb4', cursorclass=DictCursor,
        connect_timeout=5
    )


def enrich_device_info(device_code):
    """
    根据设备序列号从生产数据库查询完整设备信息
    返回 dict，包含：area_id, device_ip, device_type
    查询失败返回空 dict
    """
    if not device_code:
        return {}
    
    info = {}
    try:
        conn = _get_production_connection()
        with conn.cursor() as cursor:
            # agv_robot_ext：区域ID
            cursor.execute("SELECT DEVICE_AREA FROM agv_robot_ext WHERE DEVICE_CODE = %s", (device_code,))
            row = cursor.fetchone()
            if row and row.get('DEVICE_AREA'):
                info['area_id'] = row['DEVICE_AREA']
            
            # agv_robot：设备IP、设备类型
            cursor.execute("SELECT DEVICE_IP, DEVICETYPE FROM agv_robot WHERE DEVICE_CODE = %s", (device_code,))
            row2 = cursor.fetchone()
            if row2:
                if row2.get('DEVICE_IP'):
                    info['device_ip'] = row2['DEVICE_IP']
                if row2.get('DEVICETYPE'):
                    info['device_type'] = row2['DEVICETYPE']
        conn.close()
    except Exception:
        pass
    
    return info


def enrich_shelf_info(shelf_model=None, shelf_num=None):
    """
    根据货架型号和编号从生产数据库查询货架信息
    shelf_model: 货架型号ID（对应 load_config.model）
    shelf_num: 货架编号（对应 shelf_config.shelf_num）
    返回 dict，包含：shelf_model_name, shelf_num
    """
    info = {}
    if not shelf_model and not shelf_num:
        return info
    
    try:
        conn = _get_production_connection()
        with conn.cursor() as cursor:
            # 如果没有 shelf_model 但有 shelf_num，通过 shelf_config.shelf_type → load_config 链式查询
            if not shelf_model and shelf_num:
                cursor.execute("SELECT shelf_type FROM shelf_config WHERE shelf_num = %s LIMIT 1", (shelf_num,))
                row = cursor.fetchone()
                if row and row.get('shelf_type'):
                    shelf_model = row['shelf_type']
            
            # load_config：货架型号名称
            if shelf_model:
                try:
                    cursor.execute("SELECT name FROM load_config WHERE model = %s", (int(shelf_model),))
                    row = cursor.fetchone()
                    if row and row.get('name'):
                        info['shelf_model_name'] = row['name']
                        info['shelf_model'] = int(shelf_model)
                except (ValueError, TypeError):
                    pass
            
            # shelf_config：货架编号
            if shelf_num:
                cursor.execute("SELECT shelf_num FROM shelf_config WHERE shelf_num = %s LIMIT 1", (shelf_num,))
                row = cursor.fetchone()
                if row and row.get('shelf_num'):
                    info['shelf_num'] = row['shelf_num']
        conn.close()
    except Exception:
        pass
    
    return info


def enrich_task_dict(task_dict, device_code=None):
    """
    用本地数据库信息补充任务字典中的缺失字段
    task_dict: 任务字典（main_task 或 sub_task）
    device_code: 设备序列号，不传则从 task_dict 中取
    """
    if not device_code:
        device_code = task_dict.get('deviceCode') or task_dict.get('device_code') or ''
    
    # 补充设备信息
    if device_code:
        info = enrich_device_info(device_code)
        if info:
            if info.get('area_id') and not task_dict.get('areaId') and not task_dict.get('area_id'):
                task_dict['area_id'] = info['area_id']
            if info.get('device_ip') and not task_dict.get('deviceIp') and not task_dict.get('device_ip'):
                task_dict['device_ip'] = info['device_ip']
            if info.get('device_type') and not task_dict.get('robotType') and not task_dict.get('robot_type'):
                task_dict['robot_type'] = info['device_type']
    
    # 补充货架信息
    shelf_model = task_dict.get('shelfModel') or task_dict.get('shelf_model') or ''
    shelf_num = task_dict.get('shelfNum') or task_dict.get('shelf_num') or task_dict.get('carrierCode') or task_dict.get('carrier_code') or task_dict.get('shelfNumber') or task_dict.get('shelf_number') or ''
    
    # 从本地数据库补充缺失字段
    sub_order_id = task_dict.get('subOrderId') or task_dict.get('sub_order_id') or ''
    order_id = task_dict.get('orderId') or task_dict.get('order_id') or ''
    
    if sub_order_id or order_id:
        try:
            conn = _get_production_connection()
            with conn.cursor() as cursor:
                row = None
                if sub_order_id:
                    cursor.execute("SELECT * FROM fy_cross_task_detail WHERE sub_order_id = %s", (sub_order_id,))
                    row = cursor.fetchone()
                elif order_id:
                    # 主任务：查 fy_cross_task
                    cursor.execute("SELECT * FROM fy_cross_task WHERE orderId = %s", (order_id,))
                    row = cursor.fetchone()
                
                if row:
                    # 货架编号
                    shelf_val = row.get('shelf_number') or row.get('shelf_num')
                    if shelf_val:
                        if not shelf_num:
                            shelf_num = shelf_val
                        if not task_dict.get('shelf_num') and not task_dict.get('shelfNum'):
                            task_dict['shelf_num'] = shelf_val
                        if not task_dict.get('carrier_code') and not task_dict.get('carrierCode'):
                            task_dict['carrier_code'] = shelf_val
                    # 时间字段
                    for field in ['start_time', 'end_time', 'create_time', 'update_time']:
                        val = row.get(field)
                        if val and not task_dict.get(field):
                            task_dict[field] = val.isoformat() if hasattr(val, 'isoformat') else str(val)
                    # 变更状态
                    if row.get('change_status') is not None and not task_dict.get('changeStatus') and not task_dict.get('change_status'):
                        task_dict['change_status'] = row['change_status']
            conn.close()
        except Exception:
            pass
    
    if shelf_model or shelf_num:
        shelf_info = enrich_shelf_info(shelf_model, shelf_num)
        if shelf_info:
            if shelf_info.get('shelf_model_name') and not task_dict.get('shelfModelName') and not task_dict.get('shelf_model_name'):
                task_dict['shelf_model_name'] = shelf_info['shelf_model_name']
            if shelf_info.get('shelf_model') and not task_dict.get('shelfModel') and not task_dict.get('shelf_model'):
                task_dict['shelf_model'] = shelf_info['shelf_model']
            if shelf_info.get('shelf_num') and not task_dict.get('shelfNum') and not task_dict.get('shelf_num'):
                task_dict['shelf_num'] = shelf_info['shelf_num']
    
    # 补充任务状态名称（task_status_config 表）
    status_val = task_dict.get('status') or task_dict.get('taskStatus') or task_dict.get('task_status')
    status_name = task_dict.get('taskStatusName') or task_dict.get('task_status_name')
    if status_val is not None and not status_name:
        try:
            conn = _get_production_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT task_status_name FROM task_status_config WHERE task_status = %s", (int(status_val),))
                row = cursor.fetchone()
                if row and row.get('task_status_name'):
                    task_dict['task_status_name'] = row['task_status_name']
            conn.close()
        except Exception:
            pass
    
    # 从远端 task_group 获取真实的开始/结束时间
    svc_url = task_dict.get('serviceUrl') or task_dict.get('service_url') or ''
    dc = task_dict.get('deviceCode') or task_dict.get('device_code') or ''
    dn = task_dict.get('deviceNum') or task_dict.get('device_num') or ''
    if svc_url and (dc or dn):
        remote_times = fetch_remote_task_group_times(svc_url, dc, dn)
        if remote_times:
            if remote_times.get('start_time'):
                task_dict['startTime'] = remote_times['start_time']
            if remote_times.get('end_time'):
                task_dict['endTime'] = remote_times['end_time']


def fetch_remote_task_group_times(service_url, device_code=None, device_num=None):
    """
    通过远端数据库查询 task_group 的真实开始/结束时间。
    
    查询链路：
      fy_cross_task_detail.sub_order_id 下发后 → task_group.out_order_id
      但 sub_order_id 格式与 out_order_id 不直接匹配，
      因此通过 device_code + device_num 在远端 task_group 中匹配。
    
    参数：
      service_url: 远端服务地址（如 http://10.68.2.36:7000），用于提取数据库 IP
      device_code: 设备序列号（robot_id）
      device_num: 设备编号（robot_num）
    
    返回：
      {"start_time": datetime_str, "end_time": datetime_str} 或 None
    """
    if not service_url:
        return None
    if not device_code and not device_num:
        return None
    
    try:
        from urllib.parse import urlparse
        parsed = urlparse(service_url)
        host = parsed.hostname
        if not host:
            return None
        
        import pymysql
        from pymysql.cursors import DictCursor
        from datetime import datetime
        
        conn = pymysql.connect(
            host=host, port=3306, user='wms', password='CCshenda889',
            database='wms', charset='utf8mb4', cursorclass=DictCursor,
            connect_timeout=5
        )
        
        with conn.cursor() as cursor:
            conditions = []
            params = []
            if device_code:
                conditions.append("robot_id = %s")
                params.append(device_code)
            if device_num:
                conditions.append("robot_num = %s")
                params.append(device_num)
            
            where = " OR ".join(conditions)
            sql = f"SELECT start_time, end_time FROM task_group WHERE ({where}) AND start_time > 0 ORDER BY id DESC LIMIT 1"
            cursor.execute(sql, params)
            row = cursor.fetchone()
            
            if row and row.get('start_time'):
                result = {}
                # task_group 的 start_time/end_time 是 Unix 时间戳（int）
                start_ts = row['start_time']
                end_ts = row.get('end_time')
                if start_ts:
                    result['start_time'] = datetime.fromtimestamp(int(start_ts)).isoformat()
                if end_ts:
                    result['end_time'] = datetime.fromtimestamp(int(end_ts)).isoformat()
                return result if result else None
        
        conn.close()
    except Exception as e:
        import traceback
        print(f'[fetch_remote_task_group_times] 查询失败: host={host}, device_code={device_code}, device_num={device_num}, error={e}')
        traceback.print_exc()
    
    return None