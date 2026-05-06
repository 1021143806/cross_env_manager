#!/usr/bin/env python3
"""
调车模块自动驾驶测试 - 设备池管理 + 任务执行计时

设备池模型：
  设备池1（空闲池）：所有空闲AGV，初始 --pool-size 台，不够时动态增长
  区域设备：各区域的 currentCount.json（车已到达该区域）

任务闭环（每条任务有独立执行计时）：
  负载来任务：设备池1选车 → status=6 → 加入进行中队列 → 计时结束 → status=8 → 车到达区域
  负载回任务：区域设备选车 → status=6 → 加入进行中队列 → 计时结束 → status=8 → 车回到设备池1
  空车来任务：系统下发 → 加入进行中队列 → 计时结束 → 设备池1选车 → status=8 → 车到达区域
  空车回任务：系统下发 → 加入进行中队列 → 计时结束 → 区域设备选车 → status=8 → 车回到设备池1

速度配置（命令行参数）：
  --load-interval-min  负载任务上报最小间隔，默认 1.0s
  --load-interval-max  负载任务上报最大间隔，默认 20.0s
  --task-duration   任务执行时长范围，默认 30.0-120.0s（随机）
  --empty-duration  空车任务执行时长范围，默认 30.0-120.0s（随机）
  --duration        运行时长(秒)，0=无限，默认 0
  --pool-size       初始设备池大小，默认 20（不够时自动增长）

用法：
  python3 dispatch_auto_pilot.py                          # 默认参数无限运行
  python3 dispatch_auto_pilot.py --duration 60            # 运行60秒
  python3 dispatch_auto_pilot.py --load-interval 2.0      # 减慢上报速度
  python3 dispatch_auto_pilot.py --task-duration 3.0-8.0  # 任务执行3~8秒
"""
import urllib.request, json, time, random, sys, argparse, threading, math
from datetime import datetime
from http.cookiejar import CookieJar

BASE = "http://127.0.0.1:5000"

# 空车模板集合（从配置动态加载）
EMPTY_TPL = set()

cookie_jar = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

def req(m, u, d=None, auth=True):
    try:
        b = json.dumps(d).encode() if d else None
        from urllib.parse import quote
        u = quote(u, safe='/:?=&')
        r = urllib.request.Request(u, data=b, method=m)
        if d: r.add_header('Content-Type','application/json')
        if auth:
            with opener.open(r, timeout=5) as x:
                return json.loads(x.read().decode())
        else:
            with urllib.request.urlopen(r, timeout=5) as x:
                return json.loads(x.read().decode())
    except urllib.error.HTTPError as e:
        try: return json.loads(e.read().decode())
        except: return {"success":False,"error":f"HTTP {e.code}"}
    except Exception as e:
        return {"success":False,"error":str(e)}

def login():
    r = req("POST", f"{BASE}/api/login", {
        "username":"375563","password":"DHRTA@2018",
        "admin_username":"admin","admin_password":"admin123456"
    }, auth=True)
    if r.get('success'):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 登录成功")
        return True
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 登录失败: {r.get('error','')}")
    return False

def report(tpl, dev, st, rk, device_code=None, order_id=None):
    """按实际报文格式上报"""
    if device_code is None:
        device_code = f"EM{random.randint(10000,99999)}DAK{random.randint(1000,9999)}"
    if order_id is None:
        order_id = f"pad_html{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_{random.randint(100,999)}_{random.randint(1000,9999)}"
    data = {
        "shelfCurrPosition": str(random.randint(10000000, 99999999)),
        "subTaskStatus": "3" if st == 6 else "8",
        "orderId": order_id,
        "deviceCode": device_code,
        "modelProcessCode": tpl,
        "subTaskTypeId": "75",
        "subTaskId": str(random.randint(10000000, 99999999)),
        "deviceNum": dev,
        "qrContent": str(random.randint(10000000, 99999999)),
        "subTaskSeq": "3",
        "shelfNumber": f"DJ{random.randint(1,9999):04d}",
        "icsTaskOrderDetailId": str(random.randint(100000000, 999999999)),
        "processRate": "1/1",
        "status": st
    }
    return req("POST", f"{BASE}/api/dispatch/report_status", data, auth=False)

def status(): return req("GET", f"{BASE}/api/dispatch/status")
def execute(rk): return req("POST", f"{BASE}/api/dispatch/execute/{rk}")
def reset_all(rk): return req("POST", f"{BASE}/api/dispatch/reset_all/{rk}")
def glog(): return req("GET", f"{BASE}/api/dispatch/global_log")
def cfg(): return req("GET", f"{BASE}/api/dispatch/config")
def save_cfg(d): return req("POST", f"{BASE}/api/dispatch/config", d)
def region_files(rk): return req("GET", f"{BASE}/api/dispatch/region_files/{rk}")
def region_file(rk, fn): return req("GET", f"{BASE}/api/dispatch/region_file/{rk}/{fn}")

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def load_regions():
    """从配置文件加载区域，同时填充 EMPTY_TPL"""
    global EMPTY_TPL
    c = cfg()
    regions = {}
    empty_set = set()
    for rk, region in c.items():
        if not isinstance(region, dict) or 'templates' not in region:
            continue
        in_tpls, out_tpls = [], []
        for t in region.get('templates', []):
            tpl_code = t.get('code') or t.get('name', '')
            task_type = t.get('task_type', '')
            if not task_type:
                d = t.get('direction', '')
                task_type = 'load_in' if d == 'in' else 'load_out' if d == 'out' else ''
            if task_type in ('empty_in', 'empty_out'):
                empty_set.add(tpl_code)
            if task_type in ('empty_in', 'load_in'):
                in_tpls.append(tpl_code)
            elif task_type in ('empty_out', 'load_out'):
                out_tpls.append(tpl_code)
        if in_tpls or out_tpls:
            regions[rk] = {'in_tpls': in_tpls, 'out_tpls': out_tpls}
    EMPTY_TPL = empty_set
    return regions

def get_backend_empty_tasks(regions):
    """从后端获取空车模板中 status=6 的任务（系统自动下发的空车任务）"""
    tasks = []
    try:
        st = status()
        for a in st.get('areas', []):
            rk = a['region_key']
            if rk not in regions: continue
            for t_list_key in ('incoming', 'outgoing'):
                for t in a.get('templates', {}).get(t_list_key, []):
                    if t.get('count', 0) > 0 and t['code'] in EMPTY_TPL:
                        files_resp = region_files(rk)
                        if files_resp.get('files'):
                            for f in files_resp['files']:
                                if f['filename'].replace('.json', '') == t['code'] and f.get('exists'):
                                    cr = region_file(rk, f['filename'])
                                    if cr.get('content'):
                                        try:
                                            for task in json.loads(cr['content']):
                                                if task.get('status') == 6:
                                                    tasks.append({
                                                        'region_key': rk,
                                                        'template': t['code'],
                                                        'task_type': t.get('task_type', ''),
                                                        'order_id': task.get('order_id', ''),
                                                        'create_time': task.get('create_time', '')
                                                    })
                                        except: pass
    except: pass
    return tasks

def print_summary(regions):
    try:
        for a in status().get('areas', []):
            if a['region_key'] in regions:
                log(f"  [{a['region_key']}] cur:{a['currentCount']} a:{a['a']} b:{a['b']} need:{a['need']} dir:{a['direction']}")
    except: pass


# ========== 设备池管理 ==========

class DevicePool:
    """设备池1（空闲池）：所有空闲AGV"""
    
    def __init__(self, initial_size=20):
        self._next_id = 1
        self._free = {}
        self._code_map = {}
        for _ in range(initial_size):
            self._add_new_device()
    
    def _add_new_device(self):
        dev_num = f"DJC{self._next_id}"
        dev_code = f"XAGV{self._next_id:02d}"
        self._free[dev_num] = dev_code
        self._code_map[dev_num] = dev_code
        self._next_id += 1
        return dev_num, dev_code
    
    def take(self):
        if not self._free:
            return self._add_new_device()
        dev_num = random.choice(list(self._free.keys()))
        dev_code = self._free.pop(dev_num)
        return dev_num, dev_code
    
    def put_back(self, dev_num, dev_code):
        self._free[dev_num] = dev_code
        if dev_num not in self._code_map:
            self._code_map[dev_num] = dev_code
    
    def stats(self):
        return f"空闲:{len(self._free)} 已创建:{self._next_id - 1}"


def parse_range(arg_str, default_min, default_max):
    """解析 'min-max' 格式的范围参数"""
    try:
        parts = arg_str.split('-')
        if len(parts) == 2:
            return float(parts[0]), float(parts[1])
    except:
        pass
    return default_min, default_max


def main():
    parser = argparse.ArgumentParser(description='调车模块自动驾驶测试')
    parser.add_argument('--duration', type=int, default=0, help='运行时长(秒)，0=无限')
    parser.add_argument('--load-interval-min', type=float, default=1.0, help='负载任务上报最小间隔(秒)')
    parser.add_argument('--load-interval-max', type=float, default=20.0, help='负载任务上报最大间隔(秒)')
    parser.add_argument('--task-duration', type=str, default='30.0-120.0', help='负载任务执行时长范围(秒)，如 30.0-120.0')
    parser.add_argument('--empty-duration', type=str, default='30.0-120.0', help='空车任务执行时长范围(秒)，如 30.0-120.0')
    parser.add_argument('--pool-size', type=int, default=20, help='初始设备池大小，默认20（不够时自动增长）')
    args = parser.parse_args()
    
    load_dur_min, load_dur_max = parse_range(args.task_duration, 30.0, 120.0)
    empty_dur_min, empty_dur_max = parse_range(args.empty_duration, 30.0, 120.0)
    
    print("="*60)
    print(f"  调车模块自动驾驶测试（潮汐批量版）")
    print(f"  设备池:{args.pool_size}台  上报间隔:{args.load_interval_min}~{args.load_interval_max}s")
    print(f"  负载任务执行:{load_dur_min:.1f}~{load_dur_max:.1f}s  空车任务执行:{empty_dur_min:.1f}~{empty_dur_max:.1f}s")
    print(f"  时长:{'无限' if args.duration==0 else str(args.duration)+'s'}")
    print(f"  开始:{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    if not login(): sys.exit(1)
    
    REGIONS = load_regions()
    if not REGIONS:
        log("错误: 未从配置中找到有效区域")
        sys.exit(1)
    
    log(f"加载 {len(REGIONS)} 个区域: {list(REGIONS.keys())}")
    for rk, r in REGIONS.items():
        log(f"  {rk}: 来{len(r['in_tpls'])}个 {r['in_tpls']}, 离{len(r['out_tpls'])}个 {r['out_tpls']}")
    
    pool = DevicePool(args.pool_size)
    log(f"设备池初始化: {pool.stats()}")
    
    log("初始化: 禁用所有区域（模拟下发）")
    c = cfg()
    for rk in REGIONS:
        if rk in c: c[rk]['enabled'] = False
    save_cfg(c)
    
    log("初始化: 清空所有数据")
    for rk in REGIONS: reset_all(rk)
    
    log("开始自动驾驶循环")
    round_num, total_ops = 0, {'load_in':0, 'load_out':0, 'done_load':0, 'done_empty':0, 'exec':0}
    start_time = time.time()
    
    pool_lock = threading.Lock()
    region_devices = {}
    region_devices_lock = threading.Lock()
    
    # 进行中任务队列：每条任务有独立的完成时间
    # [{type, region_key, template, task_type, deviceNum, deviceCode, order_id, done_at}]
    pending_tasks = []
    pending_lock = threading.Lock()
    
    # 已处理的空车 order_id 集合（防止重复完成）
    completed_empty_orders = set()
    
    # ========== 完成线程：统一处理所有任务的计时完成 ==========
    def done_loop():
        """统一完成线程：检查进行中队列，到期后上报 status=8"""
        while True:
            time.sleep(0.5)  # 每0.5秒检查一次
            try:
                now_ts = time.time()
                with pending_lock:
                    ready = [t for t in pending_tasks if t['done_at'] <= now_ts]
                    for t in ready:
                        pending_tasks.remove(t)
                
                for task in ready:
                    rk = task['region_key']
                    tpl = task['template']
                    task_type = task['task_type']
                    dev_num = task['deviceNum']
                    dev_code = task['deviceCode']
                    order_id = task['order_id']
                    is_load = task.get('is_load', True)
                    
                    r = report(tpl, dev_num, 8, rk, device_code=dev_code, order_id=order_id)
                    if r.get('code') == 1000:
                        if is_load:
                            total_ops['done_load'] += 1
                        else:
                            total_ops['done_empty'] += 1
                        
                        with pool_lock, region_devices_lock:
                            if task_type in ('load_out', 'empty_out'):
                                pool.put_back(dev_num, dev_code)
                                if rk in region_devices and dev_num in region_devices[rk]:
                                    del region_devices[rk][dev_num]
                                tag = "回负载" if is_load else "回空车"
                                log(f"  [{rk}] 完成{tag} {tpl} {dev_num} → 回到设备池1 (执行{now_ts - task['created_at']:.1f}s)")
                            else:
                                if rk not in region_devices:
                                    region_devices[rk] = {}
                                region_devices[rk][dev_num] = dev_code
                                tag = "来负载" if is_load else "来空车"
                                log(f"  [{rk}] 完成{tag} {tpl} {dev_num} → 到达区域 (执行{now_ts - task['created_at']:.1f}s)")
            except Exception as e:
                pass
    
    threading.Thread(target=done_loop, daemon=True).start()
    
    # ========== 空车检查独立线程：每0.1s检查一次 ==========
    def empty_check_loop():
        """独立线程：高频检查空车任务下发和接取"""
        while True:
            time.sleep(0.1)
            try:
                # 随机选一个区域执行计算（触发空车下发）
                rk_exec = random.choice(list(REGIONS.keys()))
                r = execute(rk_exec)
                if r.get('success'):
                    total_ops['exec'] += 1
                    dc = r.get('dispatch_count', 0)
                    if dc > 0:
                        log(f"  [{rk_exec}] 执行计算: {'模拟' if r.get('simulated',True) else '真实'}下发{dc}台")
                    
                    # 拉取后端文件中的空车任务
                    empty_tasks = get_backend_empty_tasks(REGIONS)
                    for et in empty_tasks:
                        oid = et.get('order_id', '')
                        if not oid or oid in completed_empty_orders:
                            continue
                        with pending_lock:
                            already = any(
                                t.get('order_id') == oid and not t.get('is_load')
                                for t in pending_tasks
                            )
                        if already:
                            continue
                        
                        et_rk = et['region_key']
                        et_tpl = et['template']
                        et_task_type = et.get('task_type', '')
                        is_incoming = et_task_type in ('empty_in', 'load_in')
                        
                        if is_incoming:
                            with pool_lock:
                                dev_num, dev_code = pool.take()
                        else:
                            with region_devices_lock:
                                if et_rk in region_devices and region_devices[et_rk]:
                                    dev_num = random.choice(list(region_devices[et_rk].keys()))
                                    dev_code = region_devices[et_rk].pop(dev_num)
                                else:
                                    continue
                        
                        r6 = report(et_tpl, dev_num, 6, et_rk, device_code=dev_code, order_id=oid)
                        if r6.get('code') != 1000:
                            if is_incoming:
                                with pool_lock:
                                    pool.put_back(dev_num, dev_code)
                            else:
                                with region_devices_lock:
                                    if et_rk not in region_devices:
                                        region_devices[et_rk] = {}
                                    region_devices[et_rk][dev_num] = dev_code
                            continue
                        
                        exec_dur = random.uniform(empty_dur_min, empty_dur_max)
                        now_ts = time.time()
                        with pending_lock:
                            pending_tasks.append({
                                'type': 'empty', 'is_load': False,
                                'region_key': et_rk, 'template': et_tpl,
                                'task_type': et_task_type,
                                'deviceNum': dev_num, 'deviceCode': dev_code,
                                'order_id': oid,
                                'created_at': now_ts, 'done_at': now_ts + exec_dur
                            })
                        completed_empty_orders.add(oid)
                        tag = "来空车" if is_incoming else "回空车"
                        log(f"  [{et_rk}] {tag} {et_tpl} {dev_num} status=6已上报 ({exec_dur:.1f}s后完成)")
                elif r.get('error'):
                    pass  # 静默跳过（如互斥、平衡等）
            except Exception as e:
                pass
    
    threading.Thread(target=empty_check_loop, daemon=True).start()
    
    # ========== 预热阶段：快速跑20轮主循环（临时加速） ==========
    log("预热: 快速下发约20个任务...")
    saved_interval_min = args.load_interval_min
    saved_interval_max = args.load_interval_max
    args.load_interval_min = 0.05
    args.load_interval_max = 0.05
    warmup_start = time.time()
    warmup_rounds = 20
    for _ in range(warmup_rounds):
        # 复用主循环逻辑（通过下面的 while True 循环）
        # 这里直接调用一轮主循环的核心逻辑
        elapsed = time.time() - start_time
        if args.duration > 0 and elapsed >= args.duration:
            break
        round_num += 1
        wave = math.sin(round_num * math.pi / 60)
        in_prob = 0.5 + wave * 0.4
        is_batch = random.random() < 0.2
        batch_count = random.randint(2, 10) if is_batch else 1
        for _ in range(batch_count):
            rk = random.choice(list(REGIONS.keys()))
            region = REGIONS[rk]
            is_in = random.random() < in_prob
            if is_in and region['in_tpls']:
                load_in = [t for t in region['in_tpls'] if t not in EMPTY_TPL]
                if load_in:
                    with pool_lock:
                        dev_num, dev_code = pool.take()
                    tpl = random.choice(load_in)
                    order_id = f"pad_html{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_{random.randint(100,999)}_{random.randint(1000,9999)}"
                    r = report(tpl, dev_num, 6, rk, device_code=dev_code, order_id=order_id)
                    if r.get('code') == 1000:
                        total_ops['load_in'] += 1
                        exec_dur = random.uniform(load_dur_min, load_dur_max)
                        now_ts = time.time()
                        with pending_lock:
                            pending_tasks.append({
                                'type': 'load', 'is_load': True,
                                'region_key': rk, 'template': tpl, 'task_type': 'load_in',
                                'deviceNum': dev_num, 'deviceCode': dev_code,
                                'order_id': order_id,
                                'created_at': now_ts, 'done_at': now_ts + exec_dur
                            })
                        log(f"  [预热] 来负载 {tpl} {dev_num} (池→任务, {exec_dur:.1f}s后完成)")
            elif not is_in and region['out_tpls']:
                load_out = [t for t in region['out_tpls'] if t not in EMPTY_TPL]
                if load_out:
                    with region_devices_lock:
                        if rk in region_devices and region_devices[rk]:
                            dev_num = random.choice(list(region_devices[rk].keys()))
                            dev_code = region_devices[rk].pop(dev_num)
                        else:
                            continue
                    tpl = random.choice(load_out)
                    order_id = f"pad_html{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_{random.randint(100,999)}_{random.randint(1000,9999)}"
                    r = report(tpl, dev_num, 6, rk, device_code=dev_code, order_id=order_id)
                    if r.get('code') == 1000:
                        total_ops['load_out'] += 1
                        exec_dur = random.uniform(load_dur_min, load_dur_max)
                        now_ts = time.time()
                        with pending_lock:
                            pending_tasks.append({
                                'type': 'load', 'is_load': True,
                                'region_key': rk, 'template': tpl, 'task_type': 'load_out',
                                'deviceNum': dev_num, 'deviceCode': dev_code,
                                'order_id': order_id,
                                'created_at': now_ts, 'done_at': now_ts + exec_dur
                            })
                        log(f"  [预热] 回负载 {tpl} {dev_num} (区域→任务, {exec_dur:.1f}s后完成)")
        time.sleep(random.uniform(args.load_interval_min, args.load_interval_max))
    # 恢复原始间隔
    args.load_interval_min = saved_interval_min
    args.load_interval_max = saved_interval_max
    log(f"预热完成: 耗时{time.time()-warmup_start:.1f}s, 恢复间隔 {saved_interval_min}~{saved_interval_max}s")
    
    try:
        while True:
            elapsed = time.time() - start_time
            if args.duration > 0 and elapsed >= args.duration:
                log(f"\n达到运行时长 {args.duration}s，自动停止")
                break
            
            round_num += 1
            
            # 潮汐效应：正弦波决定来/回方向概率
            wave = math.sin(round_num * math.pi / 60)
            in_prob = 0.5 + wave * 0.4
            
            # 随机触发批量下发（约20%概率），1s内批量发送2~10条
            is_batch = random.random() < 0.2
            batch_count = random.randint(2, 10) if is_batch else 1
            
            for _ in range(batch_count):
                rk = random.choice(list(REGIONS.keys()))
                region = REGIONS[rk]
                is_in = random.random() < in_prob
                
                if is_in and region['in_tpls']:
                    load_in = [t for t in region['in_tpls'] if t not in EMPTY_TPL]
                    if load_in:
                        with pool_lock:
                            dev_num, dev_code = pool.take()
                        tpl = random.choice(load_in)
                        order_id = f"pad_html{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_{random.randint(100,999)}_{random.randint(1000,9999)}"
                        r = report(tpl, dev_num, 6, rk, device_code=dev_code, order_id=order_id)
                        if r.get('code') == 1000:
                            total_ops['load_in'] += 1
                            exec_dur = random.uniform(load_dur_min, load_dur_max)
                            now_ts = time.time()
                            with pending_lock:
                                pending_tasks.append({
                                    'type': 'load', 'is_load': True,
                                    'region_key': rk, 'template': tpl, 'task_type': 'load_in',
                                    'deviceNum': dev_num, 'deviceCode': dev_code,
                                    'order_id': order_id,
                                    'created_at': now_ts, 'done_at': now_ts + exec_dur
                                })
                            log(f"  [{rk}] 来负载 {tpl} {dev_num} (池→任务, {exec_dur:.1f}s后完成)")
                
                elif not is_in and region['out_tpls']:
                    load_out = [t for t in region['out_tpls'] if t not in EMPTY_TPL]
                    if load_out:
                        with region_devices_lock:
                            if rk in region_devices and region_devices[rk]:
                                dev_num = random.choice(list(region_devices[rk].keys()))
                                dev_code = region_devices[rk].pop(dev_num)
                            else:
                                continue
                        tpl = random.choice(load_out)
                        order_id = f"pad_html{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_{random.randint(100,999)}_{random.randint(1000,9999)}"
                        r = report(tpl, dev_num, 6, rk, device_code=dev_code, order_id=order_id)
                        if r.get('code') == 1000:
                            total_ops['load_out'] += 1
                            exec_dur = random.uniform(load_dur_min, load_dur_max)
                            now_ts = time.time()
                            with pending_lock:
                                pending_tasks.append({
                                    'type': 'load', 'is_load': True,
                                    'region_key': rk, 'template': tpl, 'task_type': 'load_out',
                                    'deviceNum': dev_num, 'deviceCode': dev_code,
                                    'order_id': order_id,
                                    'created_at': now_ts, 'done_at': now_ts + exec_dur
                                })
                            log(f"  [{rk}] 回负载 {tpl} {dev_num} (区域→任务, {exec_dur:.1f}s后完成)")
            
            # 每10轮打印统计
            if round_num % 10 == 0:
                elapsed_s = time.time() - start_time
                with pool_lock, region_devices_lock, pending_lock:
                    pool_stat = pool.stats()
                    region_total = sum(len(v) for v in region_devices.values())
                    pending_count = len(pending_tasks)
                log(f"轮{round_num} | 负载来:{total_ops['load_in']} 负载回:{total_ops['load_out']} 负载完成:{total_ops['done_load']} 空车完成:{total_ops['done_empty']} 执行:{total_ops['exec']} | {pool_stat} 区域中:{region_total} 进行中:{pending_count} | 耗时:{elapsed_s:.0f}s")
                print_summary(REGIONS)
            
            time.sleep(random.uniform(args.load_interval_min, args.load_interval_max))
    except KeyboardInterrupt:
        log("\n手动停止")
    
    # 最终统计
    elapsed_s = time.time() - start_time
    log(f"\n=== 最终统计 ===")
    log(f"运行 {round_num} 轮, 耗时 {elapsed_s:.0f}s")
    log(f"负载来:{total_ops['load_in']} 负载回:{total_ops['load_out']} 负载完成:{total_ops['done_load']} 空车完成:{total_ops['done_empty']} 执行:{total_ops['exec']}")
    with pool_lock, region_devices_lock, pending_lock:
        log(f"最终设备池: {pool.stats()}")
        region_total = sum(len(v) for v in region_devices.values())
        log(f"区域中设备: {region_total}  进行中任务: {len(pending_tasks)}")
    log(f"操作日志:")
    gl = glog().get('logs',[])
    log(f"  共 {len(gl)} 条")
    for l in gl[:5]:
        log(f"    [{l.get('time','')[11:19]}] [{l.get('region_key','?')}] {l.get('action','')}: {l.get('detail','')[:80]}")
    
    log("清理所有区域")
    for rk in REGIONS: reset_all(rk)
    
    print(f"\n{'='*60}\n  完成!\n{'='*60}")

if __name__=="__main__":
    main()
