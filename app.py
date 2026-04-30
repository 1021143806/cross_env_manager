#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Python 3.9兼容性修改：使用pymysql替代mysql.connector
import pymysql
from pymysql.cursors import DictCursor
# pymysql.install_as_MySQLdb()  # 不再使用MySQLdb兼容层

"""
跨环境任务模板管理Web应用
用于查询、修改和插入跨环境任务模板
支持TOML配置文件和命令行参数指定配置文件
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
# import mysql.connector  # 已由pymysql替代
# from MySQLdb import Error  # 使用pymysql的错误
import re
import os
import sys
import argparse
import hashlib
from datetime import datetime
from dotenv import load_dotenv
import logging
from flask import template_rendered
from functools import wraps

# 导入查询功能模块
try:
    from modules.query import (
        task_query,
        device_validation,
        cross_model_query,
        join_point_query,
        shelf_model_query,
        shelf_query,
        agv_status,
        join_qr_node_query,
        task_query_extended,
        device_validation_extended
    )
    QUERY_MODULES_AVAILABLE = True
except ImportError as e:
    print(f"警告: 查询功能模块导入失败: {e}")
    print("查询功能将不可用")
    QUERY_MODULES_AVAILABLE = False
    # 创建空模块占位符
    class EmptyModule:
        def __getattr__(self, name):
            return lambda *args, **kwargs: None
    task_query = EmptyModule()
    device_validation = EmptyModule()
    cross_model_query = EmptyModule()
    join_point_query = EmptyModule()
    shelf_model_query = EmptyModule()
    shelf_query = EmptyModule()
    agv_status = EmptyModule()
    join_qr_node_query = EmptyModule()
    task_query_extended = EmptyModule()
    device_validation_extended = EmptyModule()
    task_query_extended = EmptyModule()

# 尝试导入tomli（Python 3.11+内置tomllib，低版本使用tomli）
try:
    # 先尝试导入tomli（第三方库，支持Python 3.7+）
    import tomli as tomllib
except ImportError:
    try:
        # Python 3.11+ 有内置的tomllib
        import tomllib
    except ImportError:
        print("错误: 需要安装tomli库 (pip install tomli)")
        raise

def load_config(config_path=None):
    """
    加载配置文件，支持.env和.toml格式
    优先级：命令行参数 > 环境变量 > 默认配置文件
    """
    config = {}
    
    # 默认配置文件路径
    default_config_path = os.path.join(os.path.dirname(__file__), 'config', 'env.toml')
    
    # 确定使用的配置文件路径
    if config_path:
        config_file = config_path
    elif os.getenv('CONFIG_PATH'):
        config_file = os.getenv('CONFIG_PATH')
    else:
        config_file = default_config_path
    
    print(f"使用配置文件: {config_file}")
    
    # 根据文件扩展名选择加载方式
    if config_file.endswith('.toml'):
        # 加载TOML配置文件
        try:
            with open(config_file, 'rb') as f:  # 使用二进制模式读取
                config = tomllib.load(f)
        except tomllib.TOMLDecodeError:
            # 如果标准TOML解析失败，尝试作为.env格式解析
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    toml_content = f.read()
                
                # 按行解析.env格式
                for line in toml_content.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            config[key.strip()] = value.strip().strip('"\'')  # 去掉引号
            except Exception as e:
                print(f"警告: 无法加载TOML配置文件 {config_file}: {e}")
                print("将使用环境变量和默认值")
        except Exception as e:
            print(f"警告: 无法加载TOML配置文件 {config_file}: {e}")
            print("将使用环境变量和默认值")
    elif config_file.endswith('.env'):
        # 加载.env文件
        load_dotenv(config_file)
    else:
        print(f"警告: 不支持的配置文件格式: {config_file}")
        print("将使用环境变量和默认值")
    
    return config

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='跨环境任务模板管理系统')
    parser.add_argument('--config', '-c', 
                       help='配置文件路径 (支持.env或.toml格式)',
                       default=None)
    parser.add_argument('--host', 
                       help='Flask服务主机地址',
                       default=None)
    parser.add_argument('--port', '-p', 
                       help='Flask服务端口',
                       type=int,
                       default=None)
    parser.add_argument('--debug', '-d', 
                       help='启用调试模式',
                       action='store_true')
    
    return parser.parse_args()

# 解析命令行参数
args = parse_arguments()

# 加载配置
config = load_config(args.config)

# 初始化Flask应用
app = Flask(__name__)

# 从配置或环境变量获取Flask密钥
# 注意：配置文件中flask配置在[flask]部分
flask_config = config.get('flask', {})
flask_secret_key = (flask_config.get('secret_key') or 
                   os.getenv('FLASK_SECRET_KEY') or 
                   'cross_env_manager_secret_key_2026')
app.secret_key = flask_secret_key
app.config['TEMPLATES_AUTO_RELOAD'] = True
# 支持 JSON 响应中的中文
app.json.ensure_ascii = False

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def find_project_root(base_dir):
    """查找项目根目录（包含projects目录的路径）"""
    current = base_dir
    # 向上遍历目录树，直到找到包含projects目录的路径
    while current != os.path.dirname(current):  # 直到根目录
        projects_dir = os.path.join(current, 'projects')
        if os.path.exists(projects_dir) and os.path.isdir(projects_dir):
            return current
        current = os.path.dirname(current)
    # 如果没找到，返回base_dir的父目录的父目录（假设标准结构）
    return os.path.dirname(os.path.dirname(os.path.dirname(base_dir)))

# 项目根目录（/main/app/toolsForPersonal）
PROJECT_ROOT = find_project_root(BASE_DIR)

def format_template_path(template_filename):
    """格式化模板路径为Linux目录样式，例如：@projects/agv_system/app/cross_env_manager/templates/xxx.html"""
    if not template_filename:
        return template_filename
    
    try:
        # 计算相对于项目根目录的路径
        rel_path = os.path.relpath(template_filename, PROJECT_ROOT)
        
        # 如果路径以projects/开头，添加@前缀
        if rel_path.startswith('projects/'):
            return f"@{rel_path}"
        else:
            # 否则返回原始相对路径
            return rel_path
    except (ValueError, OSError):
        # 如果计算相对路径失败，返回原始文件名
        return template_filename

# 配置访问日志 - 记录IP地址和访问的模板路径
def log_template_rendered(sender, template, context, **extra):
    """记录模板渲染事件"""
    # 获取客户端IP地址
    client_ip = request.remote_addr if request else 'N/A'
    # 获取代理IP（如果有）
    if request and request.headers.get('X-Forwarded-For'):
        client_ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
    
    # 获取模板路径
    template_path = template.name
    # 尝试获取绝对路径并格式化为Linux目录样式
    try:
        if hasattr(template, 'filename') and template.filename:
            # 格式化模板路径为Linux目录样式
            template_path = format_template_path(template.filename)
    except (ValueError, AttributeError):
        pass
    
    # 记录模板渲染信息
    app.logger.info(f"模板渲染: IP={client_ip}, 模板路径={template_path}")

def _get_user_info():
    """获取当前用户信息用于日志"""
    username = session.get('username', '-')
    is_admin = session.get('is_admin', False)
    role = '管理员' if is_admin else ('用户' if username != '-' else '-')
    return f"{username}({role})"

def log_request_info():
    """记录请求信息"""
    client_ip = request.remote_addr
    if request.headers.get('X-Forwarded-For'):
        client_ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
    app.logger.info(f"请求开始: IP={client_ip}, 路径={request.path}, 方法={request.method}, 用户={_get_user_info()}")

def log_response_info(response):
    """记录响应信息"""
    client_ip = request.remote_addr
    if request.headers.get('X-Forwarded-For'):
        client_ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
    app.logger.info(f"请求完成: IP={client_ip}, 路径={request.path}, 状态码={response.status_code}, 用户={_get_user_info()}")
    return response

# 设置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 连接模板渲染信号
template_rendered.connect(log_template_rendered, app)

# 注册请求钩子
app.before_request(log_request_info)
app.after_request(log_response_info)

# 数据库配置 - 从配置、环境变量或默认值读取
# 注意：配置文件中数据库配置在[database]部分
db_config = config.get('database', {})
DB_CONFIG = {
    'host': (db_config.get('host') or 
            os.getenv('DB_HOST') or 
            'localhost'),
    'port': int(db_config.get('port') or 
               os.getenv('DB_PORT') or 
               3306),
    'user': (db_config.get('user') or 
            os.getenv('DB_USER') or 
            'root'),
    'password': (db_config.get('password') or 
                os.getenv('DB_PASSWORD') or 
                ''),
    'database': (db_config.get('name') or 
                os.getenv('DB_NAME') or 
                'agv_cross_env_test'),
    'charset': (db_config.get('charset') or 
               os.getenv('DB_CHARSET') or 
               'utf8mb4')
}

# 登录认证配置
# 简单用户认证 - 使用配置中的用户名和密码
LOGIN_CONFIG = {
    'username': (flask_config.get('login_username') or 
                os.getenv('LOGIN_USERNAME') or 
                'admin'),
    'password': (flask_config.get('login_password') or 
                os.getenv('LOGIN_PASSWORD') or 
                'admin123')
}

def verify_bms_user(username, password):
    """通过本地数据库 bms_user 表验证普通用户"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor(DictCursor)
        cursor.execute("SELECT PASSWORD FROM bms_user WHERE LOGIN_NAME = %s", (username,))
        row = cursor.fetchone()
        conn.close()
        if row:
            # MD5 验证
            md5_password = hashlib.md5(password.encode()).hexdigest()
            return md5_password == row['PASSWORD']
        return False
    except Exception as e:
        print(f"bms_user验证失败: {e}")
        return False

def login_required(f):
    """登录验证装饰器（普通用户或管理员均可）"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': '需要登录', 'redirect': '/login'}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """管理员验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            # AJAX/fetch 请求：返回 JSON（base.html 全局拦截用 Toast 提示）
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': '需要管理员权限，请在首页启用管理员提权'}), 403
            # 页面直接访问：返回弹窗 HTML，弹窗后返回上一页
            return '''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"></head>
<body><script>alert('需要管理员权限，请在首页启用管理员提权');history.back();</script></body></html>''', 403
        return f(*args, **kwargs)
    return decorated_function

def get_db_connection():
    """获取数据库连接"""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        return conn
    except pymysql.Error as e:
        print(f"数据库连接错误: {e}")
        return None

def execute_query(query, params=None, fetch=True):
    """执行SQL查询"""
    conn = get_db_connection()
    if not conn:
        return None
    
    cursor = None
    try:
        cursor = conn.cursor(DictCursor)
        cursor.execute(query, params or ())
        
        if fetch and query.strip().upper().startswith('SELECT'):
            result = cursor.fetchall()
        else:
            conn.commit()
            result = cursor.lastrowid if query.strip().upper().startswith('INSERT') else cursor.rowcount
        
        return result
    except pymysql.Error as e:
        print(f"查询执行错误: {e}")
        conn.rollback()
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def extract_id_from_code(model_process_code):
    """从model_process_code中提取ID后缀"""
    # 匹配末尾的数字ID，如_HJBY_test_484中的484
    match = re.search(r'_(\d+)$', model_process_code)
    if match:
        return int(match.group(1))
    return None

def get_next_available_id():
    """获取下一个可用的数据库ID（基于自增主键）"""
    # 查询当前最大的id值
    query = "SELECT MAX(id) as max_id FROM fy_cross_model_process"
    result = execute_query(query)
    
    if not result or result[0]['max_id'] is None:
        return 1
    
    return result[0]['max_id'] + 1

@app.route('/')
@login_required
def index():
    """主页 - 搜索页面"""
    return render_template('index.html')

@app.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    """搜索任务模板"""
    if request.method == 'POST':
        search_term = request.form.get('search_term', '').strip()
    else:  # GET请求
        search_term = request.args.get('search_term', '').strip()
    
    if not search_term:
        flash('请输入搜索关键词', 'warning')
        return redirect(url_for('index'))
    
    # 纯数字输入：优先通过ID精确查找
    if search_term.isdigit():
        id_query = "SELECT * FROM fy_cross_model_process WHERE id = %s"
        id_result = execute_query(id_query, (int(search_term),))
        if id_result and len(id_result) > 0:
            templates = id_result
        else:
            # ID未找到，回退到模糊搜索
            query = """
            SELECT * FROM fy_cross_model_process 
            WHERE model_process_code LIKE %s 
            ORDER BY id DESC
            """
            params = (f'%{search_term}%',)
            templates = execute_query(query, params)
    else:
        # 非纯数字：模糊搜索
        query = """
        SELECT * FROM fy_cross_model_process 
        WHERE model_process_code LIKE %s 
        ORDER BY id DESC
        """
        params = (f'%{search_term}%',)
        templates = execute_query(query, params)
    
    if not templates:
        flash(f'未找到包含 "{search_term}" 的任务模板', 'info')
        return redirect(url_for('index'))
    
    # 获取每个模板的子任务
    for template in templates:
        detail_query = """
        SELECT * FROM fy_cross_model_process_detail 
        WHERE model_process_id = %s 
        ORDER BY task_seq
        """
        details = execute_query(detail_query, (template['id'],))
        template['details'] = details or []
    
    return render_template('template/search_results.html', 
                         templates=templates, 
                         search_term=search_term)

@app.route('/template/<int:template_id>')
@login_required
def view_template(template_id):
    """查看单个任务模板详情"""
    # 获取主模板信息
    query = "SELECT * FROM fy_cross_model_process WHERE id = %s"
    template = execute_query(query, (template_id,))
    
    if not template:
        flash('任务模板不存在', 'error')
        return redirect(url_for('index'))
    
    template = template[0]
    
    # 获取子任务
    detail_query = """
    SELECT * FROM fy_cross_model_process_detail 
    WHERE model_process_id = %s 
    ORDER BY task_seq
    """
    details = execute_query(detail_query, (template_id,))
    
    return render_template('template/detail.html', 
                         template=template, 
                         details=details)

@app.route('/edit/<int:template_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_template(template_id):
    """编辑任务模板"""
    if request.method == 'GET':
        # 获取主模板信息
        query = "SELECT * FROM fy_cross_model_process WHERE id = %s"
        template = execute_query(query, (template_id,))
        
        if not template:
            flash('任务模板不存在', 'error')
            return redirect(url_for('index'))
        
        template = template[0]
        
        # 获取子任务
        detail_query = """
        SELECT * FROM fy_cross_model_process_detail 
        WHERE model_process_id = %s 
    ORDER BY task_seq
        """
        details = execute_query(detail_query, (template_id,))
        
        return render_template('template/edit.html', 
                             template=template, 
                             details=details)
    
    else:  # POST请求 - 更新模板
        # 获取表单数据
        form_data = request.form
        
        # 更新主模板
        update_query = """
        UPDATE fy_cross_model_process 
        SET model_process_name = %s,
            enable = %s,
            request_url = %s,
            capacity = %s,
            target_points = %s,
            area_id = %s,
            target_points_ip = %s,
            backflow_template_code = %s,
            comeback_template_code = %s,
            change_charge_template_code = %s,
            min_power = %s,
            back_wait_time = %s,
            check_area_name = %s
        WHERE id = %s
        """
        
        # 辅助函数：安全地将值转换为整数，处理空字符串
        def safe_int(value, default=0):
            if value is None or value == '':
                return default
            try:
                return int(value)
            except (ValueError, TypeError):
                return default
        
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
        
        result = execute_query(update_query, params, fetch=False)
        
        if result is not None:
            flash('任务模板更新成功', 'success')
            
            # 更新子任务信息
            update_detail_count = update_template_details(template_id, form_data)
            if update_detail_count > 0:
                flash(f'成功更新 {update_detail_count} 个子任务', 'success')
        else:
            flash('任务模板更新失败', 'error')
        
        return redirect(url_for('view_template', template_id=template_id))

def update_template_details(template_id, form_data):
    """更新模板的子任务信息"""
    updated_count = 0
    
    # 解析表单中所有以'detail_'开头的字段
    detail_fields = {}
    for key, value in form_data.items():
        if key.startswith('detail_'):
            # 解析字段名格式: detail_{detail_id}_{field_name}
            parts = key.split('_')
            if len(parts) >= 3:
                detail_id = parts[1]
                field_name = '_'.join(parts[2:])
                
                if detail_id not in detail_fields:
                    detail_fields[detail_id] = {}
                detail_fields[detail_id][field_name] = value
    
    # 更新每个子任务
    for detail_id_str, fields in detail_fields.items():
        try:
            detail_id = int(detail_id_str)
            
            # 构建更新查询
            update_query = """
            UPDATE fy_cross_model_process_detail
            SET task_seq = %s,
                template_code = %s,
                template_name = %s,
                task_servicec = %s,
                task_path = %s,
                need_third_trigger = %s
            WHERE id = %s AND model_process_id = %s
            """
            
            # 获取字段值，使用空字符串作为默认值
            task_seq = fields.get('task_seq', '0')
            template_code = fields.get('template_code', '')
            template_name = fields.get('template_name', '')
            task_servicec = fields.get('task_servicec', '')
            task_path = fields.get('task_path', '')
            need_third_trigger_str = fields.get('need_third_trigger', '0')
            need_third_trigger = 1 if str(need_third_trigger_str) == '1' else 0
            
            # 验证task_seq是否为数字
            try:
                task_seq_int = int(task_seq)
            except (ValueError, TypeError):
                task_seq_int = 0
            
            params = (
                task_seq_int,
                template_code,
                template_name,
                task_servicec,
                task_path,
                need_third_trigger,
                detail_id,
                template_id
            )
            
            result = execute_query(update_query, params, fetch=False)
            if result is not None:
                updated_count += 1
                
        except (ValueError, KeyError) as e:
            print(f"更新子任务 {detail_id_str} 时出错: {e}")
            continue
    
    return updated_count

@app.route('/edit_detail/<int:detail_id>', methods=['POST'])
@login_required
@admin_required
def edit_detail(detail_id):
    """编辑子任务"""
    form_data = request.form
    
    update_query = """
    UPDATE fy_cross_model_process_detail
    SET task_seq = %s,
        task_servicec = %s,
        template_code = %s,
        template_name = %s,
        task_path = %s,
        backflow_template_code = %s,
        comeback_template_code = %s,
        back_wait_time = %s,
        need_third_trigger = %s
    WHERE id = %s
    """
    
    # 辅助函数：处理表单中的空值和0值
    def get_form_value(data, key, default=None):
        """获取表单值，处理空字符串和'0'值"""
        value = data.get(key)
        if value is None:
            return default
        str_value = str(value).strip()
        if str_value == '' or str_value == '0':
            return default if default is not None else None
        return str_value
    
    # 对于back_wait_time需要特殊处理转换为整数
    back_wait_time_str = form_data.get('back_wait_time', '').strip()
    back_wait_time = None
    if back_wait_time_str and back_wait_time_str != '':
        try:
            back_wait_time = int(back_wait_time_str)
        except (ValueError, TypeError):
            back_wait_time = None
    
    # 处理 need_third_trigger 字段
    need_third_trigger_str = form_data.get('need_third_trigger', '0').strip()
    need_third_trigger = 1 if need_third_trigger_str == '1' else 0

    params = (
        int(form_data.get('task_seq', 0)),
        get_form_value(form_data, 'task_servicec', ''),
        get_form_value(form_data, 'template_code', ''),
        get_form_value(form_data, 'template_name', ''),
        get_form_value(form_data, 'task_path', ''),
        get_form_value(form_data, 'backflow_template_code'),  # 空字符串或'0'会变成NULL
        get_form_value(form_data, 'comeback_template_code'),  # 空字符串或'0'会变成NULL
        back_wait_time,  # 处理后的整数值或NULL
        need_third_trigger,  # 0或1
        detail_id
    )
    
    result = execute_query(update_query, params, fetch=False)
    
    if result is not None:
        flash('子任务更新成功', 'success')
    else:
        flash('子任务更新失败', 'error')
    
    # 获取模板ID以便重定向
    query = "SELECT model_process_id FROM fy_cross_model_process_detail WHERE id = %s"
    detail = execute_query(query, (detail_id,))
    
    if detail:
        template_id = detail[0]['model_process_id']
        return redirect(url_for('view_template', template_id=template_id))
    
    return redirect(url_for('index'))

@app.route('/copy/<int:template_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def copy_template(template_id):
    """复制任务模板"""
    if request.method == 'GET':
        # 获取原模板信息
        query = "SELECT * FROM fy_cross_model_process WHERE id = %s"
        template = execute_query(query, (template_id,))
        
        if not template:
            flash('任务模板不存在', 'error')
            return redirect(url_for('index'))
        
        template = template[0]
        
        # 获取子任务
        detail_query = """
        SELECT * FROM fy_cross_model_process_detail 
        WHERE model_process_id = %s 
        ORDER BY task_seq
        """
        details = execute_query(detail_query, (template_id,))
        
        return render_template('template/copy.html', 
                             template=template, 
                             details=details)
    
    else:  # POST请求 - 创建新模板
        form_data = request.form
        new_base_name = form_data.get('new_base_name', '').strip()
        
        if not new_base_name:
            flash('请输入新模板的基础名称', 'error')
            return redirect(url_for('copy_template', template_id=template_id))
        
        # 先插入记录，获取数据库生成的id
        # 临时使用一个占位符作为model_process_code
        temp_model_process_code = f"{new_base_name}_temp"
        
        # 获取原模板信息
        query = "SELECT * FROM fy_cross_model_process WHERE id = %s"
        original_templates = execute_query(query, (template_id,))
        
        if not original_templates:
            flash('原模板不存在或无法访问', 'error')
            return redirect(url_for('copy_template', template_id=template_id))
        
        original_template = original_templates[0]
        
        # 插入新模板
        insert_query = """
        INSERT INTO fy_cross_model_process 
        (model_process_code, model_process_name, enable, request_url, capacity, 
         target_points, area_id, target_points_ip, backflow_template_code, 
         comeback_template_code, change_charge_template_code, min_power, 
         back_wait_time, check_area_name)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        # 辅助函数：安全地将值转换为整数，处理None值
        def safe_int(value, default=0):
            if value is None:
                return default
            try:
                return int(value)
            except (ValueError, TypeError):
                return default
        
        params = (
            temp_model_process_code,
            form_data.get('model_process_name', original_template['model_process_name']),
            safe_int(form_data.get('enable'), original_template['enable']),
            form_data.get('request_url', original_template['request_url']),
            safe_int(form_data.get('capacity'), original_template['capacity']),
            form_data.get('target_points', original_template['target_points']),
            safe_int(form_data.get('area_id'), original_template['area_id']),
            form_data.get('target_points_ip', original_template['target_points_ip']),
            form_data.get('backflow_template_code', original_template.get('backflow_template_code')),
            form_data.get('comeback_template_code', original_template.get('comeback_template_code')),
            form_data.get('change_charge_template_code', original_template.get('change_charge_template_code')),
            form_data.get('min_power') if form_data.get('min_power') != '' else None,
            form_data.get('back_wait_time') if form_data.get('back_wait_time') != '' else None,
            form_data.get('check_area_name', original_template.get('check_area_name'))
        )
        
        new_template_id = execute_query(insert_query, params, fetch=False)
        
        if new_template_id:
            # 使用实际的数据库id更新model_process_code和model_process_name
            new_model_process_code = f"{new_base_name}_{new_template_id}"
            
            # 获取原model_process_name并添加后缀
            original_name = form_data.get('model_process_name', original_template['model_process_name'])
            # 移除原名称中可能存在的数字后缀
            import re
            original_name_clean = re.sub(r'_\d+$', '', original_name)
            new_model_process_name = f"{original_name_clean}_{new_template_id}"
            
            update_code_query = """
            UPDATE fy_cross_model_process 
            SET model_process_code = %s,
                model_process_name = %s
            WHERE id = %s
            """
            execute_query(update_code_query, (new_model_process_code, new_model_process_name, new_template_id), fetch=False)
            
            # 复制子任务
            detail_query = """
            SELECT * FROM fy_cross_model_process_detail 
            WHERE model_process_id = %s 
            ORDER BY task_seq
            """
            original_details = execute_query(detail_query, (template_id,))
            
            if original_details:
                for detail in original_details:
                    insert_detail_query = """
                    INSERT INTO fy_cross_model_process_detail
                    (model_process_id, task_seq, task_servicec, template_code,
                     template_name, task_path, backflow_template_code,
                     comeback_template_code, back_wait_time, need_third_trigger)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    
                    # 确保正确处理NULL值
                    # 这些字段在数据库中可能是NULL，需要正确传递
                    def safe_get_value(detail, key):
                        """安全获取字典值，处理NULL和空字符串情况"""
                        value = detail.get(key)
                        if value is None:
                            return None
                        
                        # 将字符串值转为字符串处理
                        str_value = str(value).strip() if value is not None else ''
                        
                        # 处理空字符串
                        if str_value == '':
                            return None
                        
                        # 特别的：back_wait_time可能需要转换为整数
                        if key == 'back_wait_time':
                            try:
                                if str_value and str_value != '':
                                    return int(str_value)
                                else:
                                    return None
                            except (ValueError, TypeError):
                                return None
                        
                        # 对于模板代码字段，如果为'0'则视为NULL
                        code_fields = ['backflow_template_code', 'comeback_template_code']
                        if key in code_fields and str_value == '0':
                            return None
                        
                        return value
                    
                    detail_params = (
                        new_template_id,
                        detail['task_seq'],
                        detail['task_servicec'],
                        detail['template_code'],
                        detail['template_name'],
                        detail['task_path'],
                        safe_get_value(detail, 'backflow_template_code'),
                        safe_get_value(detail, 'comeback_template_code'),
                        safe_get_value(detail, 'back_wait_time'),
                        detail.get('need_third_trigger', 0)
                    )
                    
                    execute_query(insert_detail_query, detail_params, fetch=False)
            
            flash(f'模板复制成功！新模板代码: {new_model_process_code}, 新模板名称: {new_model_process_name}', 'success')
            return redirect(url_for('view_template', template_id=new_template_id))
        else:
            flash('模板复制失败', 'error')
            return redirect(url_for('copy_template', template_id=template_id))

@app.route('/api/search_suggestions', methods=['GET'])
@login_required
def search_suggestions():
    """搜索建议API"""
    term = request.args.get('term', '').strip()
    
    if not term:
        return jsonify([])
    
    query = """
    SELECT model_process_code, model_process_name 
    FROM fy_cross_model_process 
    WHERE model_process_code LIKE %s OR model_process_name LIKE %s
    LIMIT 10
    """
    params = (f'%{term}%', f'%{term}%')
    results = execute_query(query, params)
    
    suggestions = []
    for row in results:
        suggestions.append({
            'code': row['model_process_code'],
            'name': row['model_process_name']
        })
    
    return jsonify(suggestions)

@app.route('/api/template/<int:template_id>/details/add', methods=['POST'])
@login_required
@admin_required
def add_detail(template_id):
    """添加新子任务"""
    try:
        data = request.get_json()
        
        # 获取当前最大的task_seq
        max_seq_query = """
        SELECT MAX(task_seq) as max_seq 
        FROM fy_cross_model_process_detail 
        WHERE model_process_id = %s
        """
        max_result = execute_query(max_seq_query, (template_id,))
        
        if max_result and max_result[0]['max_seq'] is not None:
            new_seq = max_result[0]['max_seq'] + 1
        else:
            new_seq = 1
        
        # 插入新子任务
        insert_query = """
        INSERT INTO fy_cross_model_process_detail
        (model_process_id, task_seq, task_servicec, template_code,
         template_name, task_path, backflow_template_code,
         comeback_template_code, back_wait_time, need_third_trigger)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        # 辅助函数：处理表单中的空值和0值
        def get_form_value(data, key, default=None):
            """获取表单值，处理空字符串和'0'值"""
            value = data.get(key)
            if value is None:
                return default
            str_value = str(value).strip()
            if str_value == '' or str_value == '0':
                return default if default is not None else None
            return str_value
        
        # 对于back_wait_time需要特殊处理转换为整数
        back_wait_time_value = data.get('back_wait_time', '')
        back_wait_time = None
        if back_wait_time_value is not None:
            try:
                # 先转换为字符串再去除空格
                back_wait_time_str = str(back_wait_time_value).strip()
                if back_wait_time_str and back_wait_time_str != '':
                    back_wait_time = int(back_wait_time_str)
            except (ValueError, TypeError):
                back_wait_time = None
        
        # 处理 need_third_trigger 字段
        need_third_trigger_value = data.get('need_third_trigger', 0)
        need_third_trigger = 1 if str(need_third_trigger_value) == '1' else 0

        params = (
            template_id,
            new_seq,
            get_form_value(data, 'task_servicec', ''),
            get_form_value(data, 'template_code', ''),
            get_form_value(data, 'template_name', ''),
            get_form_value(data, 'task_path', ''),
            get_form_value(data, 'backflow_template_code'),  # 空字符串或'0'会变成NULL
            get_form_value(data, 'comeback_template_code'),  # 空字符串或'0'会变成NULL
            back_wait_time,  # 处理后的整数值或NULL
            need_third_trigger  # 0或1
        )
        
        new_detail_id = execute_query(insert_query, params, fetch=False)
        
        if new_detail_id:
            # 获取新创建的子任务详情
            detail_query = "SELECT * FROM fy_cross_model_process_detail WHERE id = %s"
            detail = execute_query(detail_query, (new_detail_id,))
            
            if detail:
                return jsonify({
                    'success': True,
                    'message': '子任务添加成功',
                    'detail': detail[0]
                })
        
        return jsonify({
            'success': False,
            'message': '子任务添加失败'
        }), 500
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/template/<int:template_id>/details/<int:detail_id>/delete', methods=['DELETE'])
@login_required
@admin_required
def delete_detail(template_id, detail_id):
    """删除子任务"""
    try:
        # 先验证子任务属于该模板
        verify_query = """
        SELECT id FROM fy_cross_model_process_detail 
        WHERE id = %s AND model_process_id = %s
        """
        verify_result = execute_query(verify_query, (detail_id, template_id))
        
        if not verify_result:
            return jsonify({
                'success': False,
                'message': '子任务不存在或不属于该模板'
            }), 404
        
        # 删除子任务
        delete_query = "DELETE FROM fy_cross_model_process_detail WHERE id = %s"
        result = execute_query(delete_query, (detail_id,), fetch=False)
        
        if result:
            return jsonify({
                'success': True,
                'message': '子任务删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '子任务删除失败'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/template/<int:template_id>/details/reorder', methods=['POST'])
@login_required
@admin_required
def reorder_details(template_id):
    """重新排序子任务"""
    try:
        data = request.get_json()
        detail_order = data.get('order', [])  # 格式: [{"id": 1, "task_seq": 1}, ...]
        
        if not detail_order:
            return jsonify({
                'success': False,
                'message': '未提供排序数据'
            }), 400
        
        # 验证所有子任务都属于该模板
        detail_ids = [item['id'] for item in detail_order]
        placeholders = ', '.join(['%s'] * len(detail_ids))
        
        verify_query = f"""
        SELECT COUNT(*) as count FROM fy_cross_model_process_detail 
        WHERE id IN ({placeholders}) AND model_process_id = %s
        """
        verify_params = detail_ids + [template_id]
        verify_result = execute_query(verify_query, verify_params)
        
        if verify_result and verify_result[0]['count'] != len(detail_ids):
            return jsonify({
                'success': False,
                'message': '部分子任务不属于该模板'
            }), 400
        
        # 批量更新task_seq
        success_count = 0
        for item in detail_order:
            update_query = """
            UPDATE fy_cross_model_process_detail 
            SET task_seq = %s 
            WHERE id = %s AND model_process_id = %s
            """
            update_params = (item['task_seq'], item['id'], template_id)
            result = execute_query(update_query, update_params, fetch=False)
            
            if result:
                success_count += 1
        
        if success_count == len(detail_order):
            return jsonify({
                'success': True,
                'message': f'成功更新 {success_count} 个子任务的顺序'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'部分更新失败，成功更新 {success_count}/{len(detail_order)} 个'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/docs')
@login_required
def show_docs():
    """显示本地README.md文档"""
    try:
        # 读取README.md文件
        return render_template('docs/index.html')
    except Exception as e:
        return f"无法加载文档: {str(e)}", 500

@app.route('/docs/module/<name>')
@login_required
def docs_module(name):
    """加载指定模块的readme文档"""
    try:
        # 模块路径映射
        module_paths = {
            'template': 'templates/template/readme.md',
            'addTask': 'templates/addTask/readme.md',
            'query': 'templates/query/readme.md',
            'stats': 'templates/stats/readme.md',
            'components': 'templates/components/readme.md',
            'api': 'doc/API.md',
            'dispatch': 'templates/dispatch/readme.md',
        }
        
        if name not in module_paths:
            return f"未找到模块: {name}", 404
        
        file_path = os.path.join(os.path.dirname(__file__), module_paths[name])
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        import markdown
        html_content = markdown.markdown(content, extensions=['fenced_code', 'tables'])
        
        return f'''<!DOCTYPE html>
<html lang="zh-CN" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>文档 - {name}</title>
    <link href="/static/vendor/bootstrap/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="/static/vendor/bootstrap-icons/bootstrap-icons.min.css">
    <style>
        body {{ background: #121212; color: #e9ecef; padding: 2rem; }}
        .container {{ max-width: 900px; }}
        h1, h2, h3 {{ color: #e9ecef; border-bottom: 1px solid #495057; padding-bottom: 0.3em; }}
        code {{ background: #2d2d2d; padding: 0.2em 0.4em; border-radius: 3px; }}
        pre {{ background: #2d2d2d; padding: 1rem; border-radius: 8px; overflow: auto; }}
        table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
        th, td {{ border: 1px solid #495057; padding: 8px 12px; text-align: left; }}
        th {{ background: #2d2d2d; }}
        a {{ color: #6ea8fe; }}
    </style>
</head>
<body>
    <div class="container">
        <a href="/docs" class="btn btn-outline-light btn-sm mb-3">&larr; 返回文档中心</a>
        {html_content}
    </div>
</body>
</html>'''
    except Exception as e:
        return f"无法加载文档: {str(e)}", 500

@app.route('/stats')
@login_required
def show_stats():
    """显示统计页面"""
    return render_template('stats/index.html')

@app.route('/api/stats/overview')
@login_required
def get_stats_overview():
    """获取系统概览统计"""
    try:
        # 模板统计
        template_stats_query = """
        SELECT 
            COUNT(*) as total_templates,
            SUM(CASE WHEN enable = 1 THEN 1 ELSE 0 END) as enabled_templates,
            SUM(CASE WHEN enable = 0 THEN 1 ELSE 0 END) as disabled_templates,
            AVG(capacity) as avg_capacity,
            MIN(capacity) as min_capacity,
            MAX(capacity) as max_capacity,
            COUNT(DISTINCT area_id) as distinct_areas,
            COUNT(DISTINCT target_points_ip) as distinct_servers
        FROM fy_cross_model_process
        """
        template_stats = execute_query(template_stats_query)
        
        # 子任务统计
        detail_stats_query = """
        SELECT 
            COUNT(*) as total_subtasks,
            COUNT(DISTINCT model_process_id) as templates_with_subtasks,
            AVG(task_seq) as avg_task_seq,
            MIN(task_seq) as min_task_seq,
            MAX(task_seq) as max_task_seq,
            COUNT(DISTINCT task_servicec) as distinct_servers,
            COUNT(DISTINCT template_code) as distinct_template_codes
        FROM fy_cross_model_process_detail
        """
        detail_stats = execute_query(detail_stats_query)
        
        # 最近创建的模板
        recent_templates_query = """
        SELECT id, model_process_code, model_process_name, enable, created_at
        FROM fy_cross_model_process
        ORDER BY id DESC
        LIMIT 5
        """
        recent_templates = execute_query(recent_templates_query)
        
        if template_stats and detail_stats:
            return jsonify({
                'success': True,
                'data': {
                    'template_stats': template_stats[0],
                    'detail_stats': detail_stats[0],
                    'recent_templates': recent_templates or []
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': '无法获取统计信息'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/stats/distribution')
@login_required
def get_stats_distribution():
    """获取分布统计"""
    try:
        # 启用状态分布
        enable_distribution_query = """
        SELECT 
            enable as status,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM fy_cross_model_process), 2) as percentage
        FROM fy_cross_model_process
        GROUP BY enable
        ORDER BY enable DESC
        """
        enable_distribution = execute_query(enable_distribution_query)
        
        # 容量分布
        capacity_distribution_query = """
        SELECT 
            capacity,
            COUNT(*) as count
        FROM fy_cross_model_process
        WHERE capacity > 0
        GROUP BY capacity
        ORDER BY capacity
        """
        capacity_distribution = execute_query(capacity_distribution_query)
        
        # 服务器分布
        server_distribution_query = """
        SELECT 
            target_points_ip as server,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM fy_cross_model_process), 2) as percentage
        FROM fy_cross_model_process
        WHERE target_points_ip IS NOT NULL AND target_points_ip != ''
        GROUP BY target_points_ip
        ORDER BY count DESC
        """
        server_distribution = execute_query(server_distribution_query)
        
        # 区域分布
        area_distribution_query = """
        SELECT 
            area_id as area,
            COUNT(*) as count
        FROM fy_cross_model_process
        WHERE area_id IS NOT NULL
        GROUP BY area_id
        ORDER BY area_id
        """
        area_distribution = execute_query(area_distribution_query)
        
        return jsonify({
            'success': True,
            'data': {
                'enable_distribution': enable_distribution or [],
                'capacity_distribution': capacity_distribution or [],
                'server_distribution': server_distribution or [],
                'area_distribution': area_distribution or []
            }
        })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/stats/templates_by_server')
@login_required
def get_templates_by_server():
    """按服务器分组获取模板信息"""
    try:
        query = """
        SELECT 
            target_points_ip as server,
            COUNT(*) as template_count,
            GROUP_CONCAT(model_process_code ORDER BY id DESC SEPARATOR ', ') as template_codes,
            SUM(CASE WHEN enable = 1 THEN 1 ELSE 0 END) as enabled_count,
            SUM(CASE WHEN enable = 0 THEN 1 ELSE 0 END) as disabled_count
        FROM fy_cross_model_process
        WHERE target_points_ip IS NOT NULL AND target_points_ip != ''
        GROUP BY target_points_ip
        ORDER BY template_count DESC
        """
        results = execute_query(query)
        
        if results:
            return jsonify({
                'success': True,
                'data': results
            })
        else:
            return jsonify({
                'success': False,
                'message': '无法获取服务器分组信息'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/stats/template_growth')
@login_required
def get_template_growth():
    """获取模板增长趋势（基于ID顺序）"""
    try:
        query = """
        SELECT 
            FLOOR((id - 1) / 10) * 10 + 1 as range_start,
            FLOOR((id - 1) / 10) * 10 + 10 as range_end,
            COUNT(*) as count,
            GROUP_CONCAT(id ORDER BY id SEPARATOR ',') as ids
        FROM fy_cross_model_process
        GROUP BY range_start, range_end
        ORDER BY range_start
        """
        results = execute_query(query)
        
        if results:
            return jsonify({
                'success': True,
                'data': results
            })
        else:
            return jsonify({
                'success': False,
                'message': '无法获取增长趋势信息'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/task_group/<order_id>')
@login_required
def get_task_group_info(order_id):
    """获取task_group和task_group_detail信息，支持本地和远程查询"""
    try:
        # 获取可选的服务器IP参数
        server_ip = request.args.get('server_ip', '').strip()
        
        result = task_query_extended.get_task_group_by_order_id(order_id, server_ip if server_ip else None)
        
        if 'error' in result:
            return jsonify({
                'success': False,
                'message': result['error']
            }), 404
        
        return jsonify({
            'success': True,
            'taskGroup': result.get('taskGroup'),
            'details': result.get('details'),
            'source': result.get('source', 'unknown')
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/task/resend', methods=['POST'])
@login_required
def resend_task():
    """跨环境任务重发接口"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'code': 'INVALID_REQUEST',
                'message': '请求体不能为空'
            }), 400
        
        order_id = data.get('orderId', '').strip()
        sub_order_id = data.get('subOrderId', '').strip()
        task_seq = data.get('taskSeq')
        server_ip = data.get('serverIp', '10.68.2.32').strip()
        
        if not order_id or not sub_order_id or task_seq is None:
            return jsonify({
                'success': False,
                'code': 'MISSING_PARAMS',
                'message': '缺少必要参数: orderId, subOrderId, taskSeq'
            }), 400
        
        # 确保 task_seq 是整数
        try:
            task_seq = int(task_seq)
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'code': 'INVALID_PARAMS',
                'message': f'taskSeq 必须是整数: {task_seq}'
            }), 400
        
        result = task_query_extended.resend_cross_task(
            order_id, sub_order_id, task_seq, server_ip
        )
        
        if result.get('success'):
            app.logger.info(f"[RESEND] 用户={_get_user_info()} 重发子任务 {sub_order_id} → {result.get('newSubOrderId')}")
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'code': 'SERVER_ERROR',
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/task/force_complete', methods=['POST'])
@login_required
def force_complete_task():
    """跨环境任务异常完成接口（仅将子任务状态置为3）"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'code': 'INVALID_REQUEST',
                'message': '请求体不能为空'
            }), 400
        
        order_id = data.get('orderId', '').strip()
        sub_order_id = data.get('subOrderId', '').strip()
        task_seq = data.get('taskSeq')
        server_ip = data.get('serverIp', '10.68.2.32').strip()
        
        if not order_id or not sub_order_id or task_seq is None:
            return jsonify({
                'success': False,
                'code': 'MISSING_PARAMS',
                'message': '缺少必要参数: orderId, subOrderId, taskSeq'
            }), 400
        
        try:
            task_seq = int(task_seq)
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'code': 'INVALID_PARAMS',
                'message': f'taskSeq 必须是整数: {task_seq}'
            }), 400
        
        result = task_query_extended.force_complete_cross_task(
            order_id, sub_order_id, task_seq, server_ip
        )
        
        if result.get('success'):
            app.logger.info(f"[FORCE_COMPLETE] 用户={_get_user_info()} 异常完成子任务 {sub_order_id}")
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'code': 'SERVER_ERROR',
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/stats/detailed_analysis')
@login_required
def get_detailed_analysis():
    """获取详细分析数据"""
    try:
        # 模板基本信息分析
        template_analysis_query = """
        SELECT 
            'total_templates' as metric,
            COUNT(*) as value
        FROM fy_cross_model_process
        UNION ALL
        SELECT 
            'enabled_templates' as metric,
            SUM(CASE WHEN enable = 1 THEN 1 ELSE 0 END) as value
        FROM fy_cross_model_process
        UNION ALL
        SELECT 
            'disabled_templates' as metric,
            SUM(CASE WHEN enable = 0 THEN 1 ELSE 0 END) as value
        FROM fy_cross_model_process
        UNION ALL
        SELECT 
            'templates_with_capacity' as metric,
            SUM(CASE WHEN capacity > 0 THEN 1 ELSE 0 END) as value
        FROM fy_cross_model_process
        UNION ALL
        SELECT 
            'templates_without_capacity' as metric,
            SUM(CASE WHEN capacity <= 0 THEN 1 ELSE 0 END) as value
        FROM fy_cross_model_process
        UNION ALL
        SELECT 
            'avg_subtasks_per_template' as metric,
            ROUND(
                (SELECT COUNT(*) FROM fy_cross_model_process_detail) * 1.0 / 
                (SELECT COUNT(*) FROM fy_cross_model_process), 
                2
            ) as value
        """
        template_analysis = execute_query(template_analysis_query)
        
        # 子任务分析
        subtask_analysis_query = """
        SELECT 
            'total_subtasks' as metric,
            COUNT(*) as value
        FROM fy_cross_model_process_detail
        UNION ALL
        SELECT 
            'templates_with_subtasks' as metric,
            COUNT(DISTINCT model_process_id) as value
        FROM fy_cross_model_process_detail
        UNION ALL
        SELECT 
            'avg_task_seq' as metric,
            ROUND(AVG(task_seq), 2) as value
        FROM fy_cross_model_process_detail
        UNION ALL
        SELECT 
            'max_task_seq' as metric,
            MAX(task_seq) as value
        FROM fy_cross_model_process_detail
        """
        subtask_analysis = execute_query(subtask_analysis_query)
        
        return jsonify({
            'success': True,
            'data': {
                'template_analysis': template_analysis or [],
                'subtask_analysis': subtask_analysis or []
            }
        })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/stats/main_task_status')
@login_required
def get_main_task_status():
    """获取当天大模板状态分布统计（含error_desc细分）"""
    try:
        from datetime import date
        from modules.query.task_query_extended import connect_to_production_db
        today = date.today().strftime('%Y-%m-%d')
        
        conn = connect_to_production_db("10.68.2.32")
        cursor = conn.cursor()
        
        # 按状态分组统计
        sql = """
            SELECT task_status, COUNT(*) as count 
            FROM fy_cross_task 
            WHERE create_time >= %s
            GROUP BY task_status
            ORDER BY task_status
        """
        cursor.execute(sql, (today,))
        results = cursor.fetchall() or []
        
        # 状态映射（含子项说明）
        status_map = {
            -1: {'label': '容量管控', 'color': '#6c757d', 'subs': []},
            3: {'label': '已被异常完成', 'color': '#ffc107', 'subs': [
                '请勿频繁请求', '任务异常结束', '小车预占失败', '请勿重复下发任务', '已下发'
            ]},
            4: {'label': '正在发送', 'color': '#0dcaf0', 'subs': []},
            5: {'label': '重发中', 'color': '#fd7e14', 'subs': ['请勿频繁请求']},
            6: {'label': '已下发', 'color': '#0d6efd', 'subs': []},
            7: {'label': '任务失败', 'color': '#dc3545', 'subs': [
                '货架未初始化(7301)', '找不到任务模板',
                '车没有预占(7027)', 'action条件判断错误(0X2032)'
            ]},
            8: {'label': '任务完成', 'color': '#198754', 'subs': []}
        }
        
        distribution = []
        total = 0
        for row in results:
            status = row['task_status']
            count = row['count']
            total += count
            info = status_map.get(status, {'label': f'未知({status})', 'color': '#6c757d', 'subs': []})
            distribution.append({
                'status': status,
                'label': info['label'],
                'color': info['color'],
                'count': count,
                'subs': info['subs']
            })
        
        # 查询异常状态的 task_error 细分（status=3 和 status=7）
        error_sql = """
            SELECT task_status, task_error, COUNT(*) as count 
            FROM fy_cross_task 
            WHERE create_time >= %s AND task_status IN (3, 7)
            GROUP BY task_status, task_error
            ORDER BY task_status, count DESC
        """
        cursor.execute(error_sql, (today,))
        error_results = cursor.fetchall() or []
        
        error_detail = []
        for row in error_results:
            error_detail.append({
                'status': row['task_status'],
                'errorDesc': row['task_error'] or '(无描述)',
                'count': row['count']
            })
        
        return jsonify({
            'success': True,
            'total': total,
            'date': today,
            'distribution': distribution,
            'errorDetail': error_detail
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500
    finally:
        if 'conn' in locals():
            conn.close()

# ============================================================================
# 查询功能路由
# ============================================================================

@app.route('/query')
@login_required
def query_index():
    """查询功能主页"""
    if not QUERY_MODULES_AVAILABLE:
        flash('查询功能模块未正确加载，请检查模块配置', 'error')
        return redirect(url_for('index'))
    
    return render_template('query/unified_home.html')

@app.route('/query/legacy')
@login_required
def query_legacy():
    """旧版查询功能主页（兼容性）"""
    if not QUERY_MODULES_AVAILABLE:
        flash('查询功能模块未正确加载，请检查模块配置', 'error')
        return redirect(url_for('index'))
    
    return render_template('query/index_optimized.html')

@app.route('/query/task', methods=['GET', 'POST'])
@login_required
def query_task_extended():
    """整合任务查询页面"""
    if not QUERY_MODULES_AVAILABLE:
        flash('查询功能模块未正确加载，请检查模块配置', 'error')
        return redirect(url_for('index'))
    
    return render_template('query/task_extended.html')

@app.route('/query/device', methods=['GET', 'POST'])
@login_required
def query_device():
    """设备验证"""
    if not QUERY_MODULES_AVAILABLE:
        return jsonify({'success': False, 'message': '查询功能不可用'}), 503
    
    if request.method == 'POST':
        device_sn = request.form.get('device_sn', '').strip()
        device_type = request.form.get('device_type', 'agv').strip()
        
        if not device_sn:
            flash('请输入设备序列号', 'warning')
            return render_template('query/device_validation.html')
        
        try:
            if device_type == 'agv':
                device_info = device_validation.validate_agv_device(device_sn, use_production=False)
            elif device_type == 'shelf':
                device_info = device_validation.validate_shelf_device(device_sn, use_production=False)
            elif device_type == 'rfid':
                device_info = device_validation.validate_rfid_device(device_sn, use_production=False)
            else:
                flash(f'不支持的设备类型: {device_type}', 'error')
                return render_template('query/device_validation.html')
            
            if device_info:
                return render_template('query/device_result.html',
                                     device_info=device_info,
                                     device_sn=device_sn,
                                     device_type=device_type)
            else:
                flash(f'未找到设备: {device_sn}', 'info')
                return render_template('query/device_validation.html')
                
        except Exception as e:
            flash(f'验证失败: {str(e)}', 'error')
            return render_template('query/device_validation.html')
    
    return render_template('query/device_validation.html')

# @app.route('/query/cross_model', methods=['GET', 'POST'])
# def query_cross_model():
#     """跨环境模型查询 - 已禁用"""
#     flash('此查询功能已暂时禁用', 'info')
#     return redirect(url_for('query_home'))

# @app.route('/query/join_point', methods=['GET', 'POST'])
# def query_join_point():
#     """交接点查询 - 已禁用"""
#     flash('此查询功能已暂时禁用', 'info')
#     return redirect(url_for('query_home'))
        

# @app.route('/query/shelf_model', methods=['GET', 'POST'])
# def query_shelf_model():
#     """货架模型查询 - 已禁用"""
#     flash('此查询功能已暂时禁用', 'info')
#     return redirect(url_for('query_home'))
        

# @app.route('/query/shelf', methods=['GET', 'POST'])
# def query_shelf():
#     """货架查询 - 已禁用"""
#     flash('此查询功能已暂时禁用', 'info')
#     return redirect(url_for('query_home'))

# @app.route('/query/agv_status', methods=['GET', 'POST'])
# def query_agv_status():
#     """AGV状态查询 - 已禁用"""
#     flash('此查询功能已暂时禁用', 'info')
#     return redirect(url_for('query_home'))

# @app.route('/query/agv_status/all')
# def query_all_agv_status():
#     """查询所有AGV状态 - 已禁用"""
#     flash('此查询功能已暂时禁用', 'info')
#     return redirect(url_for('query_home'))

# ============================================================================
# 1.3项目功能整合 - 任务查询路由
# ============================================================================

@app.route('/task_query')
@login_required
def task_query_home():
    """任务查询主页 - 对应1.3项目的home.html功能"""
    return render_template('query/task_query_home.html')

@app.route('/task_query/result')
@login_required
def task_query_result():
    """任务单号查询结果 - 对应FindTheTask.php功能"""
    order_id = request.args.get('order_id', '').strip()
    server_ip = request.args.get('server_ip', '').strip()
    
    if not order_id:
        flash('请输入任务单号', 'warning')
        return redirect(url_for('task_query_home'))
    
    try:
        # 处理服务器IP格式（支持简写如"31"或完整IP）
        if server_ip and len(server_ip) < 4:
            server_ip = f"10.68.2.{server_ip}"
        
        result = task_query_extended.get_task_info_by_order_id(order_id, server_ip)
        
        if 'error' in result:
            flash(result['error'], 'error')
            return redirect(url_for('task_query_home'))
        
        return render_template('query/task_query_result.html', result=result)
        
    except Exception as e:
        flash(f'查询失败: {str(e)}', 'error')
        return redirect(url_for('task_query_home'))

@app.route('/task_query/cross_task_by_template')
@login_required
def cross_task_by_template():
    """跨环境任务模板查询 - 对应Kua.php功能"""
    template_code = request.args.get('template_code', '').strip()
    
    if not template_code:
        flash('请输入跨环境任务模板', 'warning')
        return redirect(url_for('task_query_home'))
    
    try:
        result = task_query_extended.search_tasks_by_template(template_code)
        
        if 'error' in result:
            flash(result['error'], 'error')
            return redirect(url_for('task_query_home'))
        
        return render_template('query/cross_task_by_template.html', 
                             result=result, 
                             template_code=template_code)
        
    except Exception as e:
        flash(f'查询失败: {str(e)}', 'error')
        return redirect(url_for('task_query_home'))

@app.route('/task_query/cross_model_process_info')
@login_required
def cross_model_process_info():
    """跨环境任务模板详情 - 对应Chech_Kua_model_process.php功能"""
    template_code = request.args.get('template_code', '').strip()
    
    if not template_code:
        flash('请输入跨环境任务模板', 'warning')
        return redirect(url_for('task_query_home'))
    
    try:
        result = task_query_extended.get_cross_model_process_info(template_code)
        
        if 'error' in result:
            flash(result['error'], 'error')
            return redirect(url_for('task_query_home'))
        
        return render_template('query/cross_model_process_info.html', result=result)
        
    except Exception as e:
        flash(f'查询失败: {str(e)}', 'error')
        return redirect(url_for('task_query_home'))

@app.route('/task_query/cross_task_info')
@login_required
def cross_task_info():
    """跨环境任务详情 - 对应FindTheTaskKua.php功能"""
    order_id = request.args.get('order_id', '').strip()
    
    if not order_id:
        flash('请输入跨环境任务编号', 'warning')
        return redirect(url_for('task_query_home'))
    
    try:
        result = task_query_extended.get_cross_task_info(order_id)
        
        if 'error' in result:
            flash(result['error'], 'error')
            return redirect(url_for('task_query_home'))
        
        return render_template('query/cross_task_info.html', result=result)
        
    except Exception as e:
        flash(f'查询失败: {str(e)}', 'error')
        return redirect(url_for('task_query_home'))

# ============================================================================
# join_qr_node_info 相关路由
# ============================================================================

@app.route('/join_qr_nodes')
@login_required
def list_join_qr_nodes():
    """显示所有join_qr_node_info记录"""
    if not QUERY_MODULES_AVAILABLE:
        flash('查询功能不可用', 'error')
        return render_template('join_qr_nodes.html', nodes=[])
    
    try:
        nodes = join_qr_node_query.get_all_join_qr_nodes()
        stats = join_qr_node_query.get_join_qr_node_stats()
        
        return render_template('join_qr_nodes.html', 
                             nodes=nodes or [], 
                             stats=stats or {})
    except Exception as e:
        flash(f'查询失败: {str(e)}', 'error')
        return render_template('join_qr_nodes.html', nodes=[], stats={})

@app.route('/join_qr_nodes/search')
@login_required
def search_join_qr_nodes():
    """搜索join_qr_node_info记录"""
    if not QUERY_MODULES_AVAILABLE:
        return jsonify({'success': False, 'message': '查询功能不可用'}), 503
    
    search_term = request.args.get('search_term', '').strip()
    if not search_term:
        return jsonify({'success': False, 'message': '请输入搜索关键词'}), 400
    
    try:
        nodes = join_qr_node_query.search_join_qr_nodes(search_term)
        return jsonify({
            'success': True,
            'nodes': nodes or [],
            'count': len(nodes) if nodes else 0
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'搜索失败: {str(e)}'}), 500

@app.route('/join_qr_nodes/<int:node_id>')
@login_required
def view_join_qr_node(node_id):
    """查看join_qr_node_info记录详情"""
    if not QUERY_MODULES_AVAILABLE:
        flash('查询功能不可用', 'error')
        return redirect(url_for('list_join_qr_nodes'))
    
    try:
        node = join_qr_node_query.get_join_qr_node_by_id(node_id)
        if not node:
            flash(f'未找到ID为 {node_id} 的记录', 'error')
            return redirect(url_for('list_join_qr_nodes'))
        
        return render_template('join_qr_node_detail.html', node=node)
    except Exception as e:
        flash(f'查询失败: {str(e)}', 'error')
        return redirect(url_for('list_join_qr_nodes'))

@app.route('/join_qr_nodes/<int:node_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_join_qr_node(node_id):
    """编辑join_qr_node_info记录"""
    if not QUERY_MODULES_AVAILABLE:
        flash('查询功能不可用', 'error')
        return redirect(url_for('list_join_qr_nodes'))
    
    if request.method == 'POST':
        try:
            node_data = {
                'area_id': request.form.get('area_id'),
                'type': request.form.get('type'),
                'qr_content': request.form.get('qr_content'),
                'environment_ip': request.form.get('environment_ip'),
                'enable': request.form.get('enable', 1),
                'join_area': request.form.get('join_area'),
                'other_config': request.form.get('other_config'),
                'last_using_time': request.form.get('last_using_time')
            }
            
            result = join_qr_node_query.update_join_qr_node(node_id, node_data)
            if result:
                flash('记录更新成功', 'success')
            else:
                flash('记录更新失败', 'error')
            
            return redirect(url_for('view_join_qr_node', node_id=node_id))
        except Exception as e:
            flash(f'更新失败: {str(e)}', 'error')
            return redirect(url_for('edit_join_qr_node', node_id=node_id))
    
    try:
        node = join_qr_node_query.get_join_qr_node_by_id(node_id)
        if not node:
            flash(f'未找到ID为 {node_id} 的记录', 'error')
            return redirect(url_for('list_join_qr_nodes'))
        
        return render_template('edit_join_qr_node.html', node=node)
    except Exception as e:
        flash(f'查询失败: {str(e)}', 'error')
        return redirect(url_for('list_join_qr_nodes'))

@app.route('/join_qr_nodes/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_join_qr_node():
    """添加新的join_qr_node_info记录"""
    if not QUERY_MODULES_AVAILABLE:
        flash('查询功能不可用', 'error')
        return redirect(url_for('list_join_qr_nodes'))
    
    if request.method == 'POST':
        try:
            node_data = {
                'area_id': request.form.get('area_id'),
                'type': request.form.get('type'),
                'qr_content': request.form.get('qr_content'),
                'environment_ip': request.form.get('environment_ip'),
                'enable': request.form.get('enable', 1),
                'join_area': request.form.get('join_area'),
                'other_config': request.form.get('other_config'),
                'last_using_time': request.form.get('last_using_time')
            }
            
            result = join_qr_node_query.insert_join_qr_node(node_data)
            if result:
                flash('记录添加成功', 'success')
                return redirect(url_for('list_join_qr_nodes'))
            else:
                flash('记录添加失败', 'error')
        except Exception as e:
            flash(f'添加失败: {str(e)}', 'error')
    
    return render_template('add_join_qr_node.html')

@app.route('/api/join_qr_nodes/<int:node_id>/delete', methods=['DELETE'])
@login_required
@admin_required
def delete_join_qr_node(node_id):
    """删除join_qr_node_info记录"""
    if not QUERY_MODULES_AVAILABLE:
        return jsonify({'success': False, 'message': '查询功能不可用'}), 503
    
    try:
        result = join_qr_node_query.delete_join_qr_node(node_id)
        if result:
            return jsonify({'success': True, 'message': '记录删除成功'})
        else:
            return jsonify({'success': False, 'message': '记录删除失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'}), 500

@app.route('/api/join_qr_nodes/stats')
@login_required
def get_join_qr_node_stats_api():
    """获取join_qr_node_info统计信息API"""
    if not QUERY_MODULES_AVAILABLE:
        return jsonify({'success': False, 'message': '查询功能不可用'}), 503
    
    try:
        stats = join_qr_node_query.get_join_qr_node_stats()
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取统计信息失败: {str(e)}'}), 500

@app.route('/addtask')
@login_required
def addtask():
    """AGV任务下发页面"""
    # 传递登录状态到模板
    return render_template('addTask/addtask.html', 
                          logged_in=session.get('logged_in', False),
                          username=session.get('username', ''))

@app.route('/help')
@login_required
def index_help():
    """提供首页的帮助文档"""
    try:
        readme_path = os.path.join(os.path.dirname(__file__), 'templates', 'index_help.md')
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        import markdown
        html_content = markdown.markdown(content, extensions=['fenced_code', 'tables'])
        
        return html_content, 200, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception as e:
        return f"无法加载帮助文档: {str(e)}", 500

@app.route('/query/help')
@login_required
def query_help():
    """提供查询页面的帮助文档"""
    try:
        readme_path = os.path.join(os.path.dirname(__file__), 'templates', 'query', 'readme.md')
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        import markdown
        html_content = markdown.markdown(content, extensions=['fenced_code', 'tables'])
        
        return html_content, 200, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception as e:
        return f"无法加载帮助文档: {str(e)}", 500

@app.route('/addtask/help')
@login_required
def addtask_help():
    """提供addtask页面的帮助文档"""
    try:
        # 读取readme.md文件
        readme_path = os.path.join(os.path.dirname(__file__), 'templates', 'addTask', 'readme.md')
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 预处理：将Mermaid代码块直接转换为HTML，避免markdown库转义其中的HTML实体
        # markdown库的fenced_code扩展会对代码块内容做HTML实体转义（如 --> → --&gt;）
        # 而Mermaid 10.9.5需要原始语法文本，因此先提取并直接输出为HTML
        def mermaid_to_html(match):
            code_content = match.group(1)
            return f'<pre><code class="language-mermaid">{code_content}</code></pre>'
        
        content = re.sub(
            r'```mermaid\n(.*?)```',
            mermaid_to_html,
            content,
            flags=re.DOTALL
        )
        
        # 将Markdown转换为HTML（使用与/docs相同的渲染逻辑）
        import markdown
        html_content = markdown.markdown(content, extensions=['fenced_code', 'tables'])
        
        return html_content, 200, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception as e:
        return f"无法加载帮助文档: {str(e)}", 500

@app.route('/config')
@login_required
@admin_required
def config_editor():
    """配置管理页面"""
    return render_template('addTask/config_editor.html')

@app.route('/addtask/config')
@login_required
@admin_required
def get_addtask_config():
    """获取当前配置"""
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'static', 'js', 'config.js')
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 直接返回文件内容，让前端处理JSON提取
        return content, 200, {'Content-Type': 'text/plain; charset=utf-8'}
    except Exception as e:
        return jsonify({'error': f'无法加载配置: {str(e)}'}), 500

@app.route('/addtask/config', methods=['POST'])
@login_required
@admin_required
def save_addtask_config():
    """保存配置（支持版本控制和提交消息）"""
    try:
        new_config = request.json
        config_path = os.path.join(os.path.dirname(__file__), 'static', 'js', 'config.js')
        
        # 提取提交消息（可选）
        message = request.json.get('message', '').strip()
        
        # 读取当前配置文件以获取当前版本号
        current_version = 0
        parent_version = None
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # 尝试解析JSON来提取_version字段
                import json
                match = re.search(r'const config = ({.*?});', content, re.DOTALL)
                if match:
                    try:
                        config_obj = json.loads(match.group(1))
                        current_version = config_obj.get('_version', 0)
                    except json.JSONDecodeError:
                        pass
        
        # 检查客户端版本（导入时跳过版本检查）
        client_version = request.json.get('_client_version')  # 可选字段
        is_import = request.json.get('_is_import', False)  # 导入标志
        force_overwrite = request.json.get('_force_overwrite', False)  # 强制覆盖标志
        
        if client_version is not None and not (is_import or force_overwrite):
            if int(client_version) != current_version:
                return jsonify({
                    'success': False, 
                    'error': '版本冲突',
                    'message': f'当前配置文件版本为 {current_version}，您提交的版本为 {client_version}。请刷新页面后重试。',
                    'current_version': current_version,
                    'client_version': client_version
                }), 409
        
        # 创建备份目录
        backup_dir = os.path.join(os.path.dirname(config_path), 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        # 创建自动备份（带提交消息和父版本信息）
        import datetime
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"config_auto_{timestamp}.js"
        backup_path = os.path.join(backup_dir, backup_name)
        
        # 备份当前配置（添加提交消息和父版本信息作为注释）
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                current_content = f.read()
            
            # 添加提交消息和父版本信息作为注释
            if message:
                commit_line = f"// commit: {message}\n"
            else:
                commit_line = "// commit: (no message)\n"
            
            # 添加父版本信息
            parent_line = f"// parent_version: {current_version}\n"
            
            content_with_comment = commit_line + parent_line + current_content
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(content_with_comment)
        
        # 设置新版本号（递增）
        new_version = current_version + 1
        # 确保新配置对象不包含_version字段（我们将添加自己的）
        if '_version' in new_config:
            del new_config['_version']
        new_config['_version'] = new_version
        
        # 保存新配置
        import json
        config_content = f"const config = {json.dumps(new_config, indent=4, ensure_ascii=False)};"
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        return jsonify({
            'success': True, 
            'backup_name': backup_name,
            'new_version': new_version,
            'parent_version': current_version,
            'message': message if message else '(no message)'
        })
    except Exception as e:
        return jsonify({'error': f'保存配置失败: {str(e)}'}), 500

@app.route('/addtask/config/backups')
@login_required
@admin_required
def list_backups():
    """列出所有备份文件（包含提交消息和父版本信息）"""
    try:
        backup_dir = os.path.join(os.path.dirname(__file__), 'static', 'js', 'backups')
        backups = []
        
        if os.path.exists(backup_dir):
            for filename in sorted(os.listdir(backup_dir), reverse=True):
                if filename.endswith('.js'):
                    filepath = os.path.join(backup_dir, filename)
                    stat = os.stat(filepath)
                    
                    # 从文件名提取版本信息
                    version_match = filename.split('_')[-1].replace('.js', '')
                    
                    # 提取提交消息和父版本信息（文件前两行）
                    message = ''
                    parent_version = None
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                            if len(lines) > 0 and lines[0].startswith('// commit:'):
                                message = lines[0][10:].strip()
                            if len(lines) > 1 and lines[1].startswith('// parent_version:'):
                                parent_str = lines[1][18:].strip()
                                if parent_str and parent_str != 'None':
                                    try:
                                        parent_version = int(parent_str)
                                    except ValueError:
                                        parent_version = None
                    except Exception:
                        pass  # 忽略读取错误
                    
                    # 尝试从配置内容中提取版本号
                    config_version = 0
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                            import json
                            match = re.search(r'const config = ({.*?});', content, re.DOTALL)
                            if match:
                                try:
                                    config_obj = json.loads(match.group(1))
                                    config_version = config_obj.get('_version', 0)
                                except json.JSONDecodeError:
                                    pass
                    except Exception:
                        pass
                    
                    backups.append({
                        'name': filename,
                        'version': version_match,
                        'config_version': config_version,
                        'message': message,
                        'parent_version': parent_version,
                        'timestamp': stat.st_mtime * 1000,  # 转换为毫秒
                        'size': stat.st_size
                    })
        
        return jsonify(backups)
    except Exception as e:
        return jsonify({'error': f'无法列出备份: {str(e)}'}), 500

@app.route('/addtask/config/backup', methods=['POST'])
@login_required
@admin_required
def create_backup():
    """创建手动备份（支持提交消息和父版本信息）"""
    try:
        backup_type = request.json.get('type', 'manual')
        message = request.json.get('message', '').strip()
        config_path = os.path.join(os.path.dirname(__file__), 'static', 'js', 'config.js')
        backup_dir = os.path.join(os.path.dirname(config_path), 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        # 读取当前配置文件以获取当前版本号
        current_version = 0
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # 尝试解析JSON来提取_version字段
                import json
                match = re.search(r'const config = ({.*?});', content, re.DOTALL)
                if match:
                    try:
                        config_obj = json.loads(match.group(1))
                        current_version = config_obj.get('_version', 0)
                    except json.JSONDecodeError:
                        pass
        
        import datetime
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"config_{backup_type}_{timestamp}.js"
        backup_path = os.path.join(backup_dir, backup_name)
        
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            # 添加提交消息和父版本信息作为注释
            if message:
                commit_line = f"// commit: {message}\n"
            else:
                commit_line = "// commit: (no message)\n"
            
            # 添加父版本信息
            parent_line = f"// parent_version: {current_version}\n"
            
            content_with_comment = commit_line + parent_line + content
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(content_with_comment)
        
        return jsonify({'success': True, 'backup_name': backup_name, 'parent_version': current_version})
    except Exception as e:
        return jsonify({'error': f'创建备份失败: {str(e)}'}), 500

@app.route('/addtask/config/backup/<backup_name>')
@login_required
@admin_required
def get_backup(backup_name):
    """获取备份文件内容"""
    try:
        backup_path = os.path.join(os.path.dirname(__file__), 'static', 'js', 'backups', backup_name)
        if not os.path.exists(backup_path):
            return jsonify({'error': '备份文件不存在'}), 404
        
        with open(backup_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return content, 200, {'Content-Type': 'text/plain; charset=utf-8'}
    except Exception as e:
        return jsonify({'error': f'无法读取备份: {str(e)}'}), 500

@app.route('/addtask/config/backup/<backup_name>/restore', methods=['POST'])
@login_required
@admin_required
def restore_backup(backup_name):
    """恢复备份"""
    try:
        backup_path = os.path.join(os.path.dirname(__file__), 'static', 'js', 'backups', backup_name)
        config_path = os.path.join(os.path.dirname(__file__), 'static', 'js', 'config.js')
        
        if not os.path.exists(backup_path):
            return jsonify({'error': '备份文件不存在'}), 404
        
        # 读取备份内容
        with open(backup_path, 'r', encoding='utf-8') as f:
            backup_content = f.read()
        
        # 恢复配置
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(backup_content)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': f'恢复备份失败: {str(e)}'}), 500

@app.route('/addtask/config/backup/<backup_name>', methods=['DELETE'])
@login_required
@admin_required
def delete_backup(backup_name):
    """删除备份"""
    try:
        backup_path = os.path.join(os.path.dirname(__file__), 'static', 'js', 'backups', backup_name)
        
        if not os.path.exists(backup_path):
            return jsonify({'error': '备份文件不存在'}), 404
        
        os.remove(backup_path)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': f'删除备份失败: {str(e)}'}), 500

# ==================== 登录认证路由 ====================

@app.route('/login')
def login_page():
    """登录页面"""
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def login():
    """用户登录（RCS账号 + 可选管理员提权）"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        admin_username = data.get('admin_username', '').strip()
        admin_password = data.get('admin_password', '').strip()
        
        if not username or not password:
            return jsonify({'success': False, 'error': '用户名和密码不能为空'}), 400
        
        # 先验证 RCS 用户
        if not verify_bms_user(username, password):
            return jsonify({'success': False, 'error': '用户名或密码错误'}), 401
        
        session['logged_in'] = True
        session['username'] = username
        session['login_time'] = datetime.now().isoformat()
        
        # 检查是否需要管理员提权
        if admin_username and admin_password:
            if admin_username == LOGIN_CONFIG['username'] and admin_password == LOGIN_CONFIG['password']:
                session['is_admin'] = True
                print(f"[LOGIN] 管理员提权: {username} (by {admin_username}) @ {session['login_time']}")
                return jsonify({'success': True, 'message': f'登录成功（管理员权限）', 'username': username, 'is_admin': True})
            else:
                # 管理员验证失败，但RCS登录成功，给普通权限
                session['is_admin'] = False
                print(f"[LOGIN] 管理员提权失败: {username} @ {session['login_time']}")
                return jsonify({'success': True, 'message': '登录成功（管理员验证失败，普通权限）', 'username': username, 'is_admin': False})
        else:
            session['is_admin'] = False
            print(f"[LOGIN] 普通用户登录: {username} @ {session['login_time']}")
            return jsonify({'success': True, 'message': '登录成功', 'username': username, 'is_admin': False})
    except Exception as e:
        return jsonify({'success': False, 'error': f'登录失败: {str(e)}'}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    """用户注销"""
    username = session.get('username', 'unknown')
    print(f"[LOGOUT] 用户注销: {username}")
    session.clear()
    return jsonify({'success': True, 'message': '已注销'})

@app.route('/api/auth/status')
def auth_status():
    """获取认证状态"""
    return jsonify({
        'logged_in': session.get('logged_in', False),
        'is_admin': session.get('is_admin', False),
        'username': session.get('username', ''),
        'login_time': session.get('login_time', '')
    })

@app.route('/actuator/health')
def health_check():
    """健康检查接口 - 用于服务器监控"""
    return '1000', 200, {'Content-Type': 'text/plain; charset=utf-8'}

@app.route('/test/version_tree')
@login_required
def test_version_tree():
    """测试版本历史树状图页面"""
    return render_template('test_version_tree.html')

if __name__ == '__main__':
    # 创建模板目录
    os.makedirs('templates', exist_ok=True)
    
    # ========================================================================
    # Phase 1 架构优化：初始化数据库连接池
    # ========================================================================
    pool = None
    try:
        from modules.database.connection import DatabasePool, get_db_config_from_toml
        pool = DatabasePool()
        db_pool_config = get_db_config_from_toml(args.config)
        pool.init_pool(db_pool_config)
        print(f"[启动] 数据库连接池已初始化")
    except Exception as e:
        print(f"[启动] 警告: 连接池初始化失败，将使用传统连接方式: {e}")
    
    # ========================================================================
    # Phase 1 架构优化：注册统一异常处理器
    # ========================================================================
    try:
        from middleware.error_handler import register_error_handlers
        register_error_handlers(app)
        print(f"[启动] 统一异常处理器已注册")
    except Exception as e:
        print(f"[启动] 警告: 异常处理器注册失败: {e}")
    
    # ========================================================================
    # Phase 2 架构优化：注册蓝图路由
    # ========================================================================
    try:
        from routes import register_blueprints
        register_blueprints(app)
        print(f"[启动] 蓝图路由已注册")
    except Exception as e:
        print(f"[启动] 警告: 蓝图注册失败，使用原有路由: {e}")
    
    # ========================================================================
    # Phase 4 架构优化：初始化缓存
    # ========================================================================
    try:
        from middleware.cache import init_cache
        init_cache(app)
        print(f"[启动] 缓存层已初始化")
    except Exception as e:
        print(f"[启动] 警告: 缓存初始化失败: {e}")
    
    # ========================================================================
    # 启动自恢复后台线程
    # ========================================================================
    try:
        from routes.dispatch_routes import _start_self_heal_thread
        _start_self_heal_thread()
        print(f"[启动] 自恢复后台线程已启动")
    except Exception as e:
        print(f"[启动] 警告: 自恢复线程启动失败: {e}")
    
    # 获取Flask运行参数（命令行参数优先，然后是配置，最后是环境变量）
    # 注意：配置文件使用小写字段名（如 host, port），环境变量使用大写（如 FLASK_HOST, FLASK_PORT）
    flask_config = config.get('flask', {})
    host = (args.host or 
           flask_config.get('host') or 
           os.getenv('FLASK_HOST') or 
           '0.0.0.0')
    
    port = (args.port or 
           (flask_config.get('port') and int(flask_config.get('port'))) or 
           (os.getenv('FLASK_PORT') and int(os.getenv('FLASK_PORT'))) or 
           5000)
    
    debug = (args.debug or 
            (flask_config.get('debug') and str(flask_config.get('debug')).lower() == 'true') or 
            (os.getenv('FLASK_DEBUG') and os.getenv('FLASK_DEBUG').lower() == 'true') or 
            False)
    
    print("=" * 60)
    print("跨环境任务模板管理系统")
    print("=" * 60)
    print(f"配置文件: {args.config or '默认 (config/env.toml)'}")
    print(f"数据库: {DB_CONFIG['database']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"服务地址: http://{host}:{port}")
    print(f"调试模式: {'是' if debug else '否'}")
    print(f"连接池: {'已启用' if pool and pool.is_initialized else '未启用（使用传统连接）'}")
    print("=" * 60)
    print("启动服务中...")
    
    app.run(debug=debug, host=host, port=port)