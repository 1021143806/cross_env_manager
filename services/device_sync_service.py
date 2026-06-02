#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设备同步服务 - 跨服务器同步 AGV 设备数据

功能：
  1. 型号同步：源库 agv_model → 目标库 agv_model_init
  2. 设备主表同步：源库 agv_robot → 目标库 agv_robot
  3. 设备扩展表同步：按设备组查源库 agv_robot_ext → 目标库 agv_robot_ext

设计要点：
  - 所有服务器共享相同的 DB 凭据（user/password/port/database/charset），仅 IP 不同
  - 凭据从 config/env.toml 读取
  - 可用 IP 从 fy_cross_model_process_detail.task_servicec 解析
  - 写入均使用 INSERT IGNORE，不覆盖已有数据
  - 返回 SSE 流式日志供前端实时展示
"""

import os, sys, re, json, time
from datetime import datetime
from pymysql.cursors import DictCursor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import tomli as tomllib
except ImportError:
    tomllib = None

try:
    from modules.database.connection import execute_query
except ImportError:
    execute_query = None


# ========== 默认 AGV_ROBOT 字段（去 ID 后 18 列） ==========
AGV_ROBOT_FIELDS = [
    'DEVICE_CODE', 'DEVICE_IP', 'DEVICE_PORT', 'USRENAME', 'PASSWORD',
    'DEVICETYPE', 'CAPACITIES', 'DETAILTYPE', 'MAC', 'UPDATE_DATE',
    'CREATE_DATE', 'config', 'CONFIG_PARM', 'VERSION_SN', 'PROTOCOL',
    'MACS_VERSION', 'MILEAGE', 'DIRECT_CONNECTION'
]

# ========== AGV_MODEL_INIT 字段（去 ID 后 17 列） ==========
AGV_MODEL_INIT_FIELDS = [
    'SERIES_MODEL_NAME', 'PARENT_ID', 'SERIES_MODEL_TYPE', 'RUN_PARAM',
    'CONFIG_PARAM', 'CREATE_DATE', 'BASE_CONFIG', 'CHARGE_CONFIG', 'DEFAULT_ACTION',
    'ATTACH_PARAM', 'MODEL_TYPE', 'LOGO', 'LOAD_URL', 'CANCEL_TEMPLATE',
    'RECOVER_TEMPLATE', 'CROSS_RELATE_TEMPLATE', 'DEVICE_OUT_TYPE'
]

# ========== AGV_ROBOT_EXT 字段（去 ID 后 7 列） ==========
AGV_ROBOT_EXT_FIELDS = [
    'DEVICE_CODE', 'DEVICE_AREA', 'DEVICE_NUMBER', 'CREATE_DATE',
    'BIND_QRNODE', 'DEVICE_STATUS', 'ENABLE'
]


class DeviceSyncService:
    """设备同步服务"""

    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_config = self._load_db_config()

    # ======================== 配置加载 ========================

    def _load_db_config(self):
        """从 config/env.toml 加载数据库连接凭据"""
        config_path = os.path.join(self.base_dir, 'config', 'env.toml')
        if tomllib and os.path.exists(config_path):
            with open(config_path, 'rb') as f:
                cfg = tomllib.load(f)
            db = cfg.get('database', {})
            return {
                'user': db.get('user', 'wms'),
                'password': db.get('password', ''),
                'port': db.get('port', 3306),
                'database': db.get('name', 'wms'),
                'charset': db.get('charset', 'utf8mb4'),
            }
        # 回退默认值
        return {
            'user': 'wms',
            'password': 'CCshenda889',
            'port': 3306,
            'database': 'wms',
            'charset': 'utf8mb4',
        }

    # ======================== 连接管理 ========================

    def _connect(self, ip):
        """用指定 IP 创建 pymysql 连接（共享凭据）"""
        import pymysql
        return pymysql.connect(
            host=ip,
            port=self.db_config['port'],
            user=self.db_config['user'],
            password=self.db_config['password'],
            database=self.db_config['database'],
            charset=self.db_config['charset'],
            connect_timeout=5,
            cursorclass=DictCursor,
        )

    def test_connection(self, ip):
        """测试连接指定服务器，返回 (ok, info_dict, error_msg)"""
        try:
            conn = self._connect(ip)
            info = {}
            with conn.cursor() as cur:
                cur.execute("SELECT VERSION() as ver")
                info['version'] = cur.fetchone()['ver']
                for tbl in ['agv_robot', 'agv_robot_ext', 'agv_model', 'agv_model_init',
                           'agv_robot_group', 'agv_robot_group_detail']:
                    try:
                        cur.execute(f"SELECT COUNT(*) as cnt FROM `{tbl}`")
                        info[tbl] = cur.fetchone()['cnt']
                    except Exception:
                        info[tbl] = -1  # 表不存在
            conn.close()
            return True, info, None
        except Exception as e:
            return False, None, str(e)

    # ======================== 服务器列表 ========================

    def get_available_servers(self):
        """从 fy_cross_model_process_detail.task_servicec 获取所有服务器 IP 列表"""
        if execute_query:
            rows = execute_query(
                "SELECT DISTINCT task_servicec FROM fy_cross_model_process_detail "
                "WHERE task_servicec IS NOT NULL AND task_servicec != ''"
            )
            servers = []
            seen = set()
            for row in rows:
                url = (row.get('task_servicec') or '').strip()
                if not url:
                    continue
                # 解析 IP：http://10.68.2.27:7000 → 10.68.2.27
                m = re.search(r'(\d+\.\d+\.\d+\.\d+)', url)
                if m:
                    ip = m.group(1)
                    if ip not in seen:
                        seen.add(ip)
                        servers.append(ip)
            servers.sort()
            return servers
        return []

    def get_device_groups(self, ip):
        """从指定服务器的 agv_robot_group 获取设备组列表"""
        try:
            conn = self._connect(ip)
            with conn.cursor() as cur:
                cur.execute("SELECT id, group_name FROM agv_robot_group ORDER BY id")
                rows = cur.fetchall()
            conn.close()
            return [{'id': r['id'], 'name': r['group_name']} for r in rows]
        except Exception as e:
            return []

    def get_level1_areas(self, ip):
        """从指定服务器的 bms_area 获取 LEVEL=1 的父区域列表"""
        try:
            conn = self._connect(ip)
            with conn.cursor() as cur:
                cur.execute("SELECT ID, NAME, LEVEL FROM bms_area WHERE LEVEL = 1 ORDER BY ID")
                rows = cur.fetchall()
            conn.close()
            return [{'id': r['ID'], 'name': r['NAME']} for r in rows]
        except Exception as e:
            return []

    # ======================== 服务器信息预览 ========================

    def get_server_info(self, ip):
        """获取服务器基本信息（用于阶段三预览）"""
        try:
            conn = self._connect(ip)
            info = {}
            with conn.cursor() as cur:
                for tbl in ['agv_robot', 'agv_robot_ext', 'agv_model', 'agv_model_init',
                           'agv_robot_group', 'agv_robot_group_detail']:
                    try:
                        cur.execute(f"SELECT COUNT(*) as cnt FROM `{tbl}`")
                        info[tbl] = cur.fetchone()['cnt']
                    except Exception:
                        info[tbl] = None
            conn.close()
            return info
        except Exception as e:
            return None

    # ======================== SSE 工具 ========================

    def _sse(self, event_type, data):
        """构造一条 SSE 事件字符串"""
        return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    def _log(self, msg, level='info'):
        """快捷日志事件"""
        return self._sse('log', {'msg': msg, 'level': level, 'ts': datetime.now().strftime('%H:%M:%S')})

    # ======================== 执行同步（SSE 流式） ========================

    def execute_sync_stream(self, source_ip, target_ip, sync_types, params):
        """执行设备同步，返回 SSE 事件生成器"""
        source_conn = None
        target_conn = None
        summary = {'model': {'success': 0, 'skip': 0, 'fail': 0},
                   'robot': {'success': 0, 'skip': 0, 'fail': 0},
                   'ext': {'success': 0, 'skip': 0, 'fail': 0}}

        try:
            # ====== 连接 ======
            yield self._sse('progress', {'step': 'connect', 'percent': 0})
            yield self._log(f'🔌 正在连接源库 {source_ip}:{self.db_config["port"]} ...', 'info')

            try:
                source_conn = self._connect(source_ip)
                yield self._log(f'✅ 连接源库成功 ({source_ip})', 'success')
            except Exception as e:
                yield self._log(f'❌ 连接源库失败: {e}', 'error')
                yield self._sse('done', {'success': False, 'error': f'连接源库失败: {e}'})
                return

            yield self._log(f'🔌 正在连接目标库 {target_ip}:{self.db_config["port"]} ...', 'info')
            try:
                target_conn = self._connect(target_ip)
                yield self._log(f'✅ 连接目标库成功 ({target_ip})', 'success')
            except Exception as e:
                source_conn.close()
                yield self._log(f'❌ 连接目标库失败: {e}', 'error')
                yield self._sse('done', {'success': False, 'error': f'连接目标库失败: {e}'})
                return

            yield self._sse('progress', {'step': 'syncing', 'percent': 10})

            # ====== 型号同步 ======
            if 'model' in sync_types:
                yield from self._sync_models_stream(source_conn, target_conn, params, summary)

            # ====== 设备主表同步 ======
            if 'robot' in sync_types:
                yield from self._sync_robots_stream(source_conn, target_conn, params, summary)

            # ====== 设备扩展表同步 ======
            if 'ext' in sync_types:
                yield from self._sync_device_ext_stream(source_conn, target_conn, params, summary)

            # ====== 完成 ======
            yield self._sse('progress', {'step': 'done', 'percent': 100})
            yield self._log('')
            yield self._log('🎉 全部同步完成!', 'header')
            yield self._sse('done', {'success': True, 'summary': summary})

        except Exception as e:
            yield self._log(f'❌ 同步异常中止: {e}', 'error')
            yield self._sse('done', {'success': False, 'error': str(e)})
        finally:
            try:
                if source_conn:
                    source_conn.close()
                if target_conn:
                    target_conn.close()
            except Exception:
                pass

    # ======================== 型号同步子流程 ========================

    def _sync_models_stream(self, source_conn, target_conn, params, summary):
        """型号同步: agv_model → agv_model_init (SSE 流)"""
        model_names_str = params.get('model_names', '')
        if not model_names_str:
            yield self._log('⚠️ 未指定型号名称，跳过', 'warning')
            return

        model_names = [n.strip() for n in model_names_str.split(',') if n.strip()]
        yield self._log('')
        yield self._log('━━━ 型号同步 ━━━', 'header')
        yield self._log(f'共 {len(model_names)} 个型号待处理', 'info')

        s = k = f_cnt = 0
        for name in model_names:
            yield self._log(f'🔍 处理型号: {name}', 'info')

            # 1. 查询源库
            try:
                with source_conn.cursor() as cur:
                    cur.execute("SELECT * FROM agv_model WHERE SERIES_MODEL_NAME = %s", (name,))
                    model_data = cur.fetchone()
                if not model_data:
                    yield self._log(f'  ⚠️ 源库未找到型号 "{name}"，跳过', 'warning')
                    f_cnt += 1
                    continue
                yield self._log(f'  ✓ 源库找到型号 {name}', 'info')
            except Exception as e:
                yield self._log(f'  ❌ 查询源库失败: {e}', 'error')
                f_cnt += 1
                continue

            # 2. 检查目标库 agv_model 是否已存在
            try:
                with target_conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM agv_model WHERE SERIES_MODEL_NAME = %s", (name,))
                    if cur.fetchone():
                        yield self._log(f'  ⏭️ 目标库 agv_model 中已存在，跳过', 'skip')
                        k += 1
                        continue
            except Exception as e:
                yield self._log(f'  ❌ 查询目标库失败: {e}', 'error')
                f_cnt += 1
                continue

            # 3. 插入目标库 agv_model_init
            try:
                values = [model_data.get(field) for field in AGV_MODEL_INIT_FIELDS]
                fields_str = ', '.join([f'`{f}`' for f in AGV_MODEL_INIT_FIELDS])
                placeholders = ', '.join(['%s'] * len(AGV_MODEL_INIT_FIELDS))
                sql = f"INSERT IGNORE INTO `agv_model_init` ({fields_str}) VALUES ({placeholders})"

                with target_conn.cursor() as cur:
                    cur.execute(sql, values)
                    target_conn.commit()
                    if cur.rowcount == 1:
                        yield self._log(f'  ✅ 成功写入 agv_model_init', 'success')
                        s += 1
                    else:
                        yield self._log(f'  ⏭️ agv_model_init 已存在，跳过', 'skip')
                        k += 1
            except Exception as e:
                yield self._log(f'  ❌ 写入失败: {e}', 'error')
                f_cnt += 1

        yield self._log(f'💡 型号同步完成: 成功 {s}, 跳过 {k}, 失败 {f_cnt}', 'info')
        summary['model'] = {'success': s, 'skip': k, 'fail': f_cnt}

    # ======================== 设备主表同步子流程 ========================

    def _sync_robots_stream(self, source_conn, target_conn, params, summary):
        """设备主表同步: agv_robot → agv_robot (SSE 流)"""
        device_type = params.get('device_type', '')
        table_name = params.get('table_name', 'agv_robot')

        if not device_type:
            yield self._log('⚠️ 未指定设备类型，跳过', 'warning')
            return

        yield self._log('')
        yield self._log('━━━ 设备主表同步 ━━━', 'header')
        yield self._log(f'设备类型: {device_type}', 'info')

        # 1. 查询源库
        try:
            with source_conn.cursor() as cur:
                sql = f"SELECT * FROM agv_robot WHERE DEVICETYPE = %s"
                cur.execute(sql, (device_type,))
                rows = cur.fetchall()
            yield self._log(f'📊 源库查询到 {len(rows)} 条记录', 'info')
        except Exception as e:
            yield self._log(f'❌ 查询源库失败: {e}', 'error')
            summary['robot'] = {'success': 0, 'skip': 0, 'fail': 1}
            return

        if not rows:
            yield self._log('⚠️ 源库无匹配记录', 'warning')
            summary['robot'] = {'success': 0, 'skip': 0, 'fail': 0}
            return

        # 2. 构造 INSERT IGNORE
        fields_str = ', '.join([f'`{f}`' for f in AGV_ROBOT_FIELDS])
        placeholders = ', '.join(['%s'] * len(AGV_ROBOT_FIELDS))
        insert_sql = f"INSERT IGNORE INTO `{table_name}` ({fields_str}) VALUES ({placeholders})"

        s = k = f_cnt = 0
        yield self._log(f'💾 开始插入 {len(rows)} 条记录到目标库...', 'info')

        for i, row in enumerate(rows):
            values = [row.get(field) for field in AGV_ROBOT_FIELDS]
            device_code = row.get('DEVICE_CODE', f'#{i+1}')
            try:
                with target_conn.cursor() as cur:
                    cur.execute(insert_sql, values)
                    target_conn.commit()
                    if cur.rowcount == 1:
                        yield self._log(f'  ✅ [{i+1}/{len(rows)}] {device_code} 插入成功', 'success')
                        s += 1
                    else:
                        yield self._log(f'  ⏭️ [{i+1}/{len(rows)}] {device_code} 已存在，跳过', 'skip')
                        k += 1
            except Exception as e:
                yield self._log(f'  ❌ [{i+1}/{len(rows)}] {device_code} 插入失败: {e}', 'error')
                f_cnt += 1

        yield self._log(f'💡 设备主表同步完成: 成功 {s}, 跳过 {k}, 失败 {f_cnt}', 'info')
        summary['robot'] = {'success': s, 'skip': k, 'fail': f_cnt}

    # ======================== 设备扩展表同步子流程 ========================

    def _sync_device_ext_stream(self, source_conn, target_conn, params, summary):
        """设备扩展表同步: agv_robot_ext → agv_robot_ext (SSE 流)"""
        group_name = params.get('group_name', '')
        target_area = params.get('target_area', 0)

        if not group_name:
            yield self._log('⚠️ 未指定设备组名称，跳过', 'warning')
            return

        yield self._log('')
        yield self._log('━━━ 设备扩展表同步 ━━━', 'header')
        yield self._log(f'设备组: {group_name} → 目标区域: {target_area}', 'info')

        try:
            # 1. 获取组 ID
            with source_conn.cursor() as cur:
                cur.execute("SELECT id FROM agv_robot_group WHERE group_name = %s", (group_name,))
                grp = cur.fetchone()
            if not grp:
                yield self._log(f'  ❌ 未找到设备组 "{group_name}"', 'error')
                summary['ext'] = {'success': 0, 'skip': 0, 'fail': 1}
                return
            group_id = grp['id']
            yield self._log(f'  ✓ 组 ID: {group_id}', 'info')
        except Exception as e:
            yield self._log(f'  ❌ 查询设备组失败: {e}', 'error')
            summary['ext'] = {'success': 0, 'skip': 0, 'fail': 1}
            return

        try:
            # 2. 获取组内设备
            with source_conn.cursor() as cur:
                cur.execute("SELECT device_code, device_number FROM agv_robot_group_detail WHERE group_id = %s", (group_id,))
                group_devices = cur.fetchall()
            if not group_devices:
                yield self._log('  ⚠️ 该设备组下无设备', 'warning')
                summary['ext'] = {'success': 0, 'skip': 0, 'fail': 0}
                return
            device_codes = [d['device_code'] for d in group_devices]
            yield self._log(f'  📊 组内设备: {len(device_codes)} 台 ({", ".join(device_codes[:5])}{"..." if len(device_codes)>5 else ""})', 'info')
        except Exception as e:
            yield self._log(f'  ❌ 查询组内设备失败: {e}', 'error')
            summary['ext'] = {'success': 0, 'skip': 0, 'fail': 1}
            return

        try:
            # 3. 查询设备扩展信息
            placeholders = ','.join(['%s'] * len(device_codes))
            with source_conn.cursor() as cur:
                sql = f"SELECT * FROM agv_robot_ext WHERE DEVICE_CODE IN ({placeholders})"
                cur.execute(sql, device_codes)
                ext_records = cur.fetchall()
            if not ext_records:
                yield self._log('  ⚠️ 未找到设备扩展信息', 'warning')
                summary['ext'] = {'success': 0, 'skip': 0, 'fail': 0}
                return
            yield self._log(f'  📊 查询到 {len(ext_records)} 条扩展记录', 'info')
        except Exception as e:
            yield self._log(f'  ❌ 查询扩展信息失败: {e}', 'error')
            summary['ext'] = {'success': 0, 'skip': 0, 'fail': 1}
            return

        # 4. 插入目标库（修改 DEVICE_AREA）
        fields_str = ', '.join([f'`{f}`' for f in AGV_ROBOT_EXT_FIELDS])
        ph = ', '.join(['%s'] * len(AGV_ROBOT_EXT_FIELDS))
        insert_sql = f"INSERT IGNORE INTO `agv_robot_ext` ({fields_str}) VALUES ({ph})"

        s = k = f_cnt = 0
        yield self._log(f'💾 开始插入 {len(ext_records)} 条记录 (DEVICE_AREA→{target_area})...', 'info')

        for i, dev in enumerate(ext_records):
            values = []
            for field in AGV_ROBOT_EXT_FIELDS:
                if field == 'DEVICE_AREA':
                    values.append(int(target_area) if target_area else dev.get(field))
                else:
                    values.append(dev.get(field))
            device_code = dev.get('DEVICE_CODE', f'#{i+1}')
            try:
                with target_conn.cursor() as cur:
                    cur.execute(insert_sql, values)
                    target_conn.commit()
                    if cur.rowcount == 1:
                        yield self._log(f'  ✅ [{i+1}/{len(ext_records)}] {device_code} 插入成功', 'success')
                        s += 1
                    else:
                        yield self._log(f'  ⏭️ [{i+1}/{len(ext_records)}] {device_code} 已存在，跳过', 'skip')
                        k += 1
            except Exception as e:
                yield self._log(f'  ❌ [{i+1}/{len(ext_records)}] {device_code} 插入失败: {e}', 'error')
                f_cnt += 1

        yield self._log(f'💡 设备扩展表同步完成: 成功 {s}, 跳过 {k}, 失败 {f_cnt}', 'info')
        summary['ext'] = {'success': s, 'skip': k, 'fail': f_cnt}
