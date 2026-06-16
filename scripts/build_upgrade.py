#!/usr/bin/env python3
"""
构建增量升级包

从生产服务器获取当前版本信息 → 本地 git diff 打包变更文件 → 生成 version.json

用法:
  # 完整流程（查服务器 → diff → 打包 → 上传）
  python scripts/build_upgrade.py \
    --server http://10.68.2.40:5000 \
    --notes "修复: xxx; 新增: xxx" \
    --upload

  # 仅打包（指定基线版本，不连服务器）
  python scripts/build_upgrade.py \
    --from v2.4.2 \
    --to 2.4.3 \
    --notes "修复: xxx; 新增: xxx"
"""

import os
import sys
import json
import zipfile
import subprocess
import tempfile
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_git(*args):
    """执行 git 命令，返回 (returncode, stdout, stderr)"""
    result = subprocess.run(
        ['git'] + list(args),
        capture_output=True, text=True, cwd=BASE_DIR, timeout=30,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def get_current_commit():
    """获取本地 HEAD commit"""
    rc, out, _ = run_git('rev-parse', 'HEAD')
    return out if rc == 0 else ''


def get_current_branch():
    """获取本地当前分支名"""
    rc, out, _ = run_git('rev-parse', '--abbrev-ref', 'HEAD')
    return out if rc == 0 else 'unknown'


def get_changed_files(from_commit, to_ref='HEAD'):
    """获取 from_commit 到 to_ref 的变更文件列表
    返回: {'A': [path, ...], 'M': [path, ...], 'D': [path, ...]}
    """
    rc, out, _ = run_git('diff', '--name-status', from_commit, to_ref)
    if rc != 0:
        return {}
    
    files = {'A': [], 'M': [], 'D': []}
    for line in out.split('\n'):
        if not line.strip():
            continue
        parts = line.split('\t', 1)
        if len(parts) != 2:
            continue
        status, path = parts
        # 去除 git 对特殊字符路径的引号包裹
        path = path.strip('"').strip()
        # 只保留第一位的变更类型 (M, A, D 等)
        status_code = status[0]
        if status_code in files:
            files[status_code].append(path)
    return files


def fetch_server_info(server_url, session_cookie=''):
    """从服务器获取版本信息"""
    import urllib.request
    
    url = f'{server_url.rstrip("/")}/api/system/version-info'
    headers = {}
    if session_cookie:
        headers['Cookie'] = f'session={session_cookie}'
    elif server_url != 'http://localhost:5000':
        # 如果没有提供 cookie，提示登录
        print(f"  [!] 需要登录 {server_url}")
        print(f"      请先通过浏览器登录后，在 Cookie 中获取 session 值")
        print(f"      或用 --session 参数传入")
        print()
        return None
    
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data.get('success'):
                return data['info']
            else:
                print(f"  [!] 服务器返回错误: {data}")
                return None
    except Exception as e:
        print(f"  [!] 连接服务器失败: {e}")
        return None


def find_baseline_commit(server_version, server_commit=''):
    """查找对应版本的基线 commit"""
    
    # 1. 如果有 server_commit 且在本地存在，直接使用
    if server_commit:
        rc, _, _ = run_git('cat-file', '-e', server_commit)
        if rc == 0:
            print(f"  ✓ 使用服务器提供的 commit: {server_commit[:12]}")
            return server_commit
    
    # 2. 搜索 git log 找到设置该版本的 commit
    rc, log, _ = run_git('log', '--all', '--oneline', '--grep', 
                          f"APP_VERSION.*{server_version}")
    if rc == 0 and log:
        commit = log.split('\n')[0].split()[0]
        print(f"  ✓ 从 git log 找到 v{server_version} 的 commit: {commit[:12]}")
        return commit
    
    # 3. 搜索 version bump 的 commit message
    rc, log, _ = run_git('log', '--all', '--oneline', '--grep',
                          f"v{server_version}")
    if rc == 0 and log:
        commit = log.split('\n')[0].split()[0]
        print(f"  ✓ 从 git log 找到 v{server_version} 对应 commit: {commit[:12]}")
        return commit
    
    # 4. 搜索 APP_VERSION 文本变更
    rc, log, _ = run_git('log', '--all', '--oneline', '-S', 
                          f"'{server_version}'", '--', 'app.py')
    if rc == 0 and log:
        # 取最新的一个（可能是写入该版本的 commit）
        commits = []
        for line in log.split('\n'):
            c = line.split()[0]
            commits.append(c)
        # 查找最先设置该版本的 commit（即最旧的）
        # 按时间正向排序
        rc2, sorted_log, _ = run_git('log', '--reverse', '--oneline', '-S',
                                       f"'{server_version}'", '--', 'app.py')
        if rc2 == 0 and sorted_log:
            first = sorted_log.split('\n')[0].split()[0]
            print(f"  ✓ 从 app.py 版本搜索找到基线 commit: {first[:12]}")
            return first
    
    print(f"  [!] 无法在本地 git 历史中找到 v{server_version} 对应的 commit")
    print(f"      请确认本地仓库包含服务器的所有提交历史")
    print(f"      可手动指定: --from COMMIT_HASH")
    return ''


def build_upgrade_package(from_commit, to_version, notes, output_dir, export_commit=None, is_rollback=False):
    """构建增量升级包
    
    export_commit: 导出文件的 commit（默认 HEAD，回退时为回退目标 commit）
    is_rollback: True 时为回退模式，version.json type='rollback'
    """
    if not export_commit:
        export_commit = 'HEAD'
    
    # 获取当前 commit（提前，供 diff 使用）
    current_commit = get_current_commit()
    
    # 1. 获取变更文件
    # 回退模式：diff 回退目标 vs 当前服务器 commit
    if is_rollback:
        changed_files = get_changed_files(export_commit, from_commit)
    else:
        changed_files = get_changed_files(from_commit)
    all_changed = changed_files.get('A', []) + changed_files.get('M', []) + changed_files.get('D', [])
    
    if not all_changed:
        print("  [!] 没有发现变更文件，无需打包")
        return None
    
    print(f"\n  ├─ 新增: {len(changed_files.get('A', []))} 个文件")
    print(f"  ├─ 修改: {len(changed_files.get('M', []))} 个文件")
    print(f"  └─ 删除: {len(changed_files.get('D', []))} 个文件")
    
    # 2. 读取排除规则（复用服务端的 EXCLUDE_PATTERNS 概念）
    exclude_patterns = [
        'venv/', '.git/', 'logs/', 'backup/', 'dev/', 'config/env.toml',
        'config/dispatch_config.json', 'config/postlook_servers.json',
        'config/old/', 'deploy_iraypleos/', 'Plugin/postlook/deploy/',
        'Plugin/postlook/venv/', '__pycache__/', '*.pyc', '.gitignore',
        'skill.md', 'README.md', 'plans/', 'test/', 'doc/old/', '.DS_Store',
    ]
    
    def should_exclude(path):
        path = path.replace('\\', '/')
        for pat in exclude_patterns:
            if pat.endswith('/'):
                if path.startswith(pat):
                    return True
            elif pat.startswith('*'):
                if path.endswith(pat[1:]):
                    return True
            else:
                if path == pat:
                    return True
        return False
    
    # 3. 获取目标版本号
    if not to_version:
        to_version = _read_app_version('HEAD')
    
    # 回退模式：目标版本从回退 commit 读取
    if is_rollback:
        to_version = _read_app_version(export_commit)
    
    # 4. 获取 from_commit 对应的版本号
    from_version = _read_app_version(from_commit)
    
    # 6. 创建临时目录
    tmpdir = tempfile.mkdtemp(prefix='cem_upgrade_')
    
    try:
        # 7. 从 git 导出变更文件
        export_count = 0
        delete_list = []  # 回退模式：需要删除的文件（新增的）
        restore_list = []  # 回退模式：需要恢复的文件（已删除的）
        
        # 确定导出源
        export_ref = export_commit
        
        if is_rollback:
            # 回退模式：M 和 D 文件从回退目标导出，A 文件加入删除清单
            for path in changed_files.get('A', []):
                if not should_exclude(path):
                    delete_list.append(path)
            
            export_paths = changed_files.get('M', []) + changed_files.get('D', [])
        else:
            export_paths = changed_files.get('A', []) + changed_files.get('M', [])
        
        for path in export_paths:
            if should_exclude(path):
                print(f"  ⏭ 跳过排除文件: {path}")
                continue
            
            dst = os.path.join(tmpdir, path)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            
            rc, content, err = run_git('show', f'{export_ref}:{path}')
            if rc == 0:
                with open(dst, 'w', encoding='utf-8') as f:
                    f.write(content)
                export_count += 1
            else:
                # 可能是二进制文件
                rc2 = subprocess.run(
                    ['git', 'show', f'{export_ref}:{path}'],
                    capture_output=True, cwd=BASE_DIR, timeout=30,
                )
                if rc2.returncode == 0:
                    with open(dst, 'wb') as f:
                        f.write(rc2.stdout)
                    export_count += 1
        
        # D 文件也需要导出（回退时用于恢复），但已包含在 export_paths 中
        if is_rollback and changed_files.get('D', []):
            # 标记回退模式中恢复的删除文件
            restore_list = [p for p in changed_files.get('D', []) if not should_exclude(p)]
        
        if export_count == 0 and not (is_rollback and delete_list):
            print("  [!] 所有变更文件均被排除规则过滤，无需打包")
            return None
        
        if is_rollback and delete_list:
            print(f"  ├─ 回退将删除: {len(delete_list)} 个文件")
        if is_rollback and restore_list:
            print(f"  ├─ 回退将恢复: {len(restore_list)} 个文件")
        print(f"  ├─ 导出: {export_count} 个文件到临时目录")
        
        # 8. 生成 version.json
        changes_list = [n.strip() for n in notes.split(';') if n.strip()] if notes else []
        version_data = {
            'from_version': from_version,
            'from_commit': from_commit,
            'to_version': to_version,
            'to_commit': current_commit,
            'type': 'rollback' if is_rollback else 'incremental',
            'title': f'回退到 v{from_version}' if is_rollback else f'v{to_version} 更新',
            'changes': changes_list,
            'files_changed': {
                'A': changed_files.get('A', []),
                'M': changed_files.get('M', []),
                'D': changed_files.get('D', []),
            },
            'file_count': export_count,
        }
        if is_rollback and delete_list:
            version_data['delete_list'] = delete_list
        
        vj_path = os.path.join(tmpdir, 'version.json')
        with open(vj_path, 'w', encoding='utf-8') as f:
            json.dump(version_data, f, ensure_ascii=False, indent=2)
        
        # 9. 打包
        prefix = 'rollback' if is_rollback else 'upgrade'
        output_name = f'{prefix}_v{from_version}_to_v{to_version}.zip'
        output_path = os.path.join(output_dir, output_name)
        
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(tmpdir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, tmpdir)
                    zf.write(file_path, arcname)
        
        # 10. 打印摘要
        print(f"\n  ──────────────────────────────────────")
        print(f"  升级包: {output_path}")
        print(f"  版本:   v{from_version} → v{to_version}")
        print(f"  大小:   {os.path.getsize(output_path) / 1024:.1f} KB")
        print(f"  文件数: {export_count} (+ 1 version.json)")
        print(f"  变更详情:")
        for path in changed_files.get('A', []):
            print(f"    + {path}")
        for path in changed_files.get('M', []):
            print(f"    ~ {path}")
        for path in changed_files.get('D', []):
            print(f"    - {path}")
        print(f"  ──────────────────────────────────────")
        
        return output_path
    
    finally:
        # 清理临时目录
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


def upload_upgrade_package(server_url, package_path, session_cookie='', notes=''):
    """上传升级包到服务器"""
    import urllib.request
    import uuid
    
    boundary = f'----WebKitFormBoundary{uuid.uuid4().hex[:16]}'
    
    # 构建 multipart/form-data
    body = []
    
    # file 字段
    file_data = open(package_path, 'rb').read()
    filename = os.path.basename(package_path)
    body.append(f'--{boundary}\r\n'.encode())
    body.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode())
    body.append(f'Content-Type: application/zip\r\n\r\n'.encode())
    body.append(file_data)
    body.append(b'\r\n')
    
    # remark 字段
    if notes:
        body.append(f'--{boundary}\r\n'.encode())
        body.append(b'Content-Disposition: form-data; name="remark"\r\n\r\n')
        body.append(notes.encode())
        body.append(b'\r\n')
    
    body.append(f'--{boundary}--\r\n'.encode())
    
    data = b''.join(body)
    
    url = f'{server_url.rstrip("/")}/api/system/upgrade'
    headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary}',
    }
    if session_cookie:
        headers['Cookie'] = f'session={session_cookie}'
    
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
            return result
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return json.loads(body)
        except Exception:
            return {'success': False, 'error': f'HTTP {e.code}: {body}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _read_app_version(ref='HEAD'):
    """从指定 ref 的 app.py 读取 APP_VERSION"""
    try:
        rc, content, _ = run_git('show', f'{ref}:app.py')
        if rc == 0:
            for line in content.split('\n'):
                if line.strip().startswith('APP_VERSION'):
                    return line.split('=')[1].strip().strip("'\"")
    except Exception:
        pass
    return 'unknown'


def get_app_version_from_file():
    """从 app.py 文件读取当前版本"""
    try:
        app_path = os.path.join(BASE_DIR, 'app.py')
        with open(app_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('APP_VERSION'):
                    return line.split('=')[1].strip().strip("'\"")
    except Exception:
        pass
    return 'unknown'


def main():
    parser = argparse.ArgumentParser(
        description='构建增量升级包',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 完整流程
  python scripts/build_upgrade.py --server http://10.68.2.40:5000 --notes "修复xxx;新增xxx" --upload
  
  # 仅打包
  python scripts/build_upgrade.py --from v2.4.2 --to 2.4.3 --notes "修复xxx"
  
  # 指定 session
  python scripts/build_upgrade.py --server http://10.68.2.40:5000 --session "YOUR_COOKIE" --upload
        """,
    )
    parser.add_argument('--server', help='生产服务器地址，如 http://10.68.2.40:5000')
    parser.add_argument('--session', help='服务器 session cookie（从浏览器复制）')
    parser.add_argument('--from', dest='from_ref', help='基线版本号或 commit hash（如 v2.4.2）')
    parser.add_argument('--to', dest='to_version', help='目标版本号（默认从 app.py 读取）')
    parser.add_argument('--rollback-to', dest='rollback_to', help='回退到指定版本（如 v2.4.5）')
    parser.add_argument('--notes', default='', help='升级说明，用分号分隔多条')
    parser.add_argument('--upload', action='store_true', help='打包后自动上传到服务器')
    parser.add_argument('--output', default=BASE_DIR, help='升级包输出目录（默认项目根目录）')
    
    args = parser.parse_args()
    
    print("=" * 55)
    print("  CEM 增量升级包构建工具")
    print("=" * 55)
    
    from_ref = args.from_ref
    rollback_commit = ''
    server_commit = ''
    server_version = ''
    
    # 1. 如果提供了 --server，先查服务器
    if args.server:
        print(f"\n[1/4] 查询服务器 {args.server} ...")
        info = fetch_server_info(args.server, args.session)
        if info:
            server_version = info.get('app_version', '')
            server_commit = info.get('git_commit', '')
            branch = info.get('git_branch', '')
            print(f"  ├─ 版本: v{server_version}")
            print(f"  ├─ commit: {server_commit[:16] if server_commit else 'unknown'}")
            if branch:
                print(f"  └─ 分支: {branch}")
            
            # 回退模式：查找目标版本的 commit
            if args.rollback_to:
                candidates = info.get('rollback_candidates', [])
                for c in candidates:
                    if c.get('version') == args.rollback_to.lstrip('v') or c.get('version') == args.rollback_to:
                        rollback_commit = c.get('commit', '')
                        print(f"  ✓ 从服务器找到回退目标: v{c.get('version')} (commit {rollback_commit[:12]})")
                        break
                if not rollback_commit:
                    print(f"  [!] 服务器未找到可回退版本: {args.rollback_to}")
                    print(f"  可用版本: {[c.get('version') for c in candidates]}")
                    sys.exit(1)
            else:
                # 用服务器版本作为基线
                from_ref = from_ref or f'v{server_version}'
        else:
            print("  [!] 无法获取服务器信息，请重试")
            sys.exit(1)
    
    # 2. 确定基线 commit
    print(f"\n[2/4] 确定基线 commit ...")
    local_commit = get_current_commit()
    print(f"  ├─ 本地 HEAD: {local_commit[:12]}")
    
    if rollback_commit:
        # 回退模式：基线=服务器当前commit, 导出源=回退目标commit
        base_commit = server_commit
        export_commit = rollback_commit
        is_rollback = True
        print(f"  ├─ 回退起点 (当前): {base_commit[:12]}")
        print(f"  └─ 回退目标 (导出): {export_commit[:12]}")
    elif from_ref and len(from_ref) >= 7:
        # 检查是否是直接的 commit hash
        rc, _, _ = run_git('cat-file', '-e', from_ref)
        if rc == 0:
            base_commit = from_ref
            print(f"  └─ 使用指定 commit: {base_commit[:12]}")
        else:
            # 尝试 tag / 版本号搜索
            base_commit = find_baseline_commit(
                from_ref.lstrip('v'),
                server_commit,
            )
            if not base_commit:
                sys.exit(1)
        export_commit = local_commit
        is_rollback = False
    elif server_commit:
        base_commit = server_commit
        export_commit = local_commit
        is_rollback = False
        print(f"  └─ 使用服务器 commit: {base_commit[:12]}")
    else:
        print("  [!] 无法确定基线，请指定 --from 或 --server")
        sys.exit(1)
    
    # 3. 检查本地是否有未提交的改动
    rc, status, _ = run_git('status', '--porcelain')
    if status:
        print(f"\n  [!] 警告: 工作区有未提交的修改")
        for line in status.split('\n')[:5]:
            print(f"      {line}")
        if status.count('\n') >= 4:
            print(f"      ... (共 {status.count(chr(10))+1} 项)")
        confirm = input("      继续打包？未提交的修改不会被包含 [y/N] ").strip().lower()
        if confirm != 'y':
            print("  已取消")
            sys.exit(0)
    
    # 4. 构建升级包
    print(f"\n[3/4] 构建增量升级包 ...")
    pkg_path = build_upgrade_package(
        from_commit=base_commit,
        to_version=args.to_version,
        notes=args.notes,
        output_dir=args.output,
        export_commit=export_commit,
        is_rollback=is_rollback,
    )
    
    if not pkg_path:
        print("\n  升级包构建失败")
        sys.exit(1)
    
    # 5. 上传
    if args.upload and args.server:
        print(f"\n[4/4] 上传到服务器 ...")
        result = upload_upgrade_package(
            server_url=args.server,
            package_path=pkg_path,
            session_cookie=args.session or '',
            notes=args.notes,
        )
        if result.get('success'):
            print(f"  ✅ {result['message']}")
        else:
            print(f"  ❌ 上传失败: {result.get('error', '未知错误')}")
    elif args.upload:
        print(f"\n[4/4] 跳过上传（未指定 --server）")
        print(f"  请手动上传: {pkg_path}")
    else:
        print(f"\n  如需自动上传，添加 --upload 参数")
    
    print(f"\n  {'=' * 55}")


if __name__ == '__main__':
    main()
