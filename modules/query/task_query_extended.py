#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务查询扩展模块
基于1.3项目的FindTheTask.php功能移植
"""

import pymysql
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
            # 查询跨环境任务详情
            sql = "SELECT * FROM fy_cross_task_detail WHERE order_id = %s"
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
    """连接到生产环境数据库"""
    try:
        conn = pymysql.connect(
            host=server_ip,
            user='wms',
            password='CCshenda889',
            database=db_name,
            charset='utf8mb4',
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
    1. 前置任务检查（task_seq-1 是否还在执行中）
    2. 检查大模板状态
    3. 检查子模板状态
    4. 生成新的 sub_order_id（子ID+1）
    5. 修改数据库状态
    
    返回: dict { success, message, newSubOrderId?, code?, precedingTaskId?, serverUrl? }
    """
    conn = connect_to_production_db(server_ip)
    
    try:
        with conn.cursor() as cursor:
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
            
            # 允许重发的大模板状态: 3(已取消), 5(重发中), 7(失败), 6(已下发-逻辑3), 9(已下发-逻辑3)
            if main_status not in (3, 5, 6, 7, 9):
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
            
            # 允许重发的子模板状态: 3(已取消), 7(失败), 4,6,9(逻辑3)
            if sub_status not in (3, 4, 6, 7, 9):
                return {
                    "success": False,
                    "code": "INVALID_STATUS",
                    "message": f"子任务状态不允许重发（当前状态: {sub_status}）"
                }
            
            # 逻辑3特殊处理: 检查是否有多个执行中的子任务
            if sub_status in (4, 6, 9):
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
            # 大模板状态为 3,6,9 时需要改为5；已经是5,7时不需要改
            if main_status in (3, 6, 9):
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