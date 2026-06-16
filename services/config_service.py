#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理服务
统一管理调度配置：存储为 JSON（真实来源），自动生成 JS 文件供前端旧版兼容
"""

import os
import json
import re
import datetime
import shutil


class ConfigService:
    """配置管理服务"""

    CONFIG_FILENAME = 'dispatch_config.json'
    JS_OUTPUT_FILENAME = 'config.js'
    BACKUP_DIRNAME = 'backups'

    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # ─── 路径 ───────────────────────────────────────────────

    def _get_config_dir(self):
        """配置存储目录（JSON 源文件）"""
        return os.path.join(self.base_dir, 'config')

    def _get_config_path(self):
        return os.path.join(self._get_config_dir(), self.CONFIG_FILENAME)

    def _get_js_output_path(self):
        """前端兼容 JS 文件路径"""
        return os.path.join(self.base_dir, 'static', 'js', self.JS_OUTPUT_FILENAME)

    def _get_backup_dir(self):
        return os.path.join(self._get_config_dir(), self.BACKUP_DIRNAME)

    # ─── 读取 / 写入 JSON ────────────────────────────────────

    def load_config(self):
        """读取 JSON 配置，返回 dict"""
        path = self._get_config_path()
        if not os.path.exists(path):
            # 兼容升级：从旧 static/js/config.js 迁移
            migrated = self._migrate_from_old_js()
            if migrated is not None:
                return migrated
            return self._default_config()
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            raise RuntimeError(f'配置解析失败: {e}')

    def _migrate_from_old_js(self):
        """
        从旧版 static/js/config.js 迁移配置到 config/dispatch_config.json
        当 JSON 源文件不存在但旧 JS 文件存在时自动迁移。
        返回迁移后的 dict，如果无法迁移返回 None。
        """
        old_js_path = self._get_js_output_path()
        if not os.path.exists(old_js_path):
            return None

        try:
            with open(old_js_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 解析 const config = {...};
            match = re.search(r'const config\s*=\s*(\{[\s\S]*?\});', content)
            if not match:
                print('[Config] 旧 config.js 格式不匹配，跳过迁移')
                return None

            config_dict = json.loads(match[1])

            # 确保 _version 字段
            if '_version' not in config_dict:
                config_dict['_version'] = 0

            # 写入新的 JSON 源文件
            config_dir = self._get_config_dir()
            os.makedirs(config_dir, exist_ok=True)
            json_path = self._get_config_path()
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
                f.write('\n')

            # 同步更新 JS 文件（生成带标准头部的新版本）
            self._sync_js_file(config_dict)

            print(f'[Config] 已从旧版 {old_js_path} 自动迁移配置到 {json_path}')
            return config_dict
        except Exception as e:
            print(f'[Config] 从旧 config.js 迁移失败: {e}')
            return None

    def save_config(self, config_dict: dict, commit_message: str = ''):
        """
        保存配置（JSON 源文件 + 自动生成 JS 兼容文件 + 自动备份）
        :param config_dict: 完整配置字典
        :param commit_message: 提交说明（可选）
        :return: dict {new_version, backup_name, parent_version}
        """
        # 1. 读取当前版本
        current = self.load_config() if os.path.exists(self._get_config_path()) else {}
        current_version = current.get('_version', 0)

        # 2a. 自动补全：确保 _features 字段存在（辊筒任务等新功能依赖此开关）
        if '_features' not in config_dict or not isinstance(config_dict['_features'], dict):
            config_dict['_features'] = {}
        if 'enable_roller_task' not in config_dict['_features']:
            config_dict['_features']['enable_roller_task'] = True

        # 2b. 版本递增
        new_version = current_version + 1
        config_dict['_version'] = new_version

        # 3. 自动备份
        backup_name = self._create_backup_file(current, current_version, commit_message)

        # 4. 写入 JSON
        config_dir = self._get_config_dir()
        os.makedirs(config_dir, exist_ok=True)
        json_path = self._get_config_path()
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)
            f.write('\n')

        # 5. 同步生成 JS 兼容文件（供 addtask.js 等旧版使用）
        self._sync_js_file(config_dict)

        return {
            'new_version': new_version,
            'backup_name': backup_name,
            'parent_version': current_version,
            'message': commit_message or '(no message)'
        }

    # ─── JS 兼容文件生成 ─────────────────────────────────────

    def _sync_js_file(self, config_dict: dict):
        """从 JSON dict 生成 static/js/config.js"""
        js_dir = os.path.dirname(self._get_js_output_path())
        os.makedirs(js_dir, exist_ok=True)

        js_content = (
            '// 此文件由系统自动生成，请勿手动编辑\n'
            '// 请通过 API 修改 config/dispatch_config.json\n\n'
            f'const config = {json.dumps(config_dict, indent=2, ensure_ascii=False)};\n'
        )
        with open(self._get_js_output_path(), 'w', encoding='utf-8') as f:
            f.write(js_content)

    # ─── 默认配置 ────────────────────────────────────────────

    def _default_config(self):
        return {
            '_version': 0,
            '_features': {
                'enable_roller_task': True
            },
            'general': {
                'title': 'AGV 跨环境任务下发系统',
                'footer_text': '任务下发系统 © 2025 | 运营 AGV 组提供技术支持'
            },
            'areas': {}
        }

    # ─── 备份管理 ────────────────────────────────────────────

    def _create_backup_file(self, config_dict: dict, version: int, message: str = '') -> str:
        """创建备份文件"""
        backup_dir = self._get_backup_dir()
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f'config_v{version}_{timestamp}.json'
        backup_path = os.path.join(backup_dir, backup_name)

        # 备份内容增加元信息注释
        meta = {
            '__meta__': {
                'backup_time': datetime.datetime.now().isoformat(),
                'version': version,
                'message': message or '(no message)'
            }
        }
        backup_data = {**meta, **config_dict}

        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)

        return backup_name

    def list_backups(self):
        """列出所有备份"""
        backup_dir = self._get_backup_dir()
        os.makedirs(backup_dir, exist_ok=True)

        backups = []
        for filename in sorted(os.listdir(backup_dir), reverse=True):
            if not filename.endswith('.json'):
                continue
            filepath = os.path.join(backup_dir, filename)
            stat = os.stat(filepath)
            meta = self._read_backup_meta(filepath)

            backups.append({
                'name': filename,
                'version': meta.get('version', 0),
                'message': meta.get('message', ''),
                'timestamp': stat.st_mtime * 1000,
                'size': stat.st_size
            })
        return backups

    def _read_backup_meta(self, filepath: str) -> dict:
        """读取备份文件的元信息"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('__meta__', {})
        except Exception:
            return {}

    def get_backup_content(self, backup_name: str):
        """获取备份内容（原始 JSON 字符串）"""
        path = os.path.join(self._get_backup_dir(), backup_name)
        if not os.path.exists(path):
            return None
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def restore_backup(self, backup_name: str) -> bool:
        """从备份恢复"""
        backup_path = os.path.join(self._get_backup_dir(), backup_name)
        if not os.path.exists(backup_path):
            return False

        with open(backup_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 去除 __meta__ 字段
        if '__meta__' in data:
            del data['__meta__']

        # 恢复（会自动生成 JS 兼容文件）
        self.save_config(data, commit_message=f'从备份恢复: {backup_name}')
        return True

    def delete_backup(self, backup_name: str) -> bool:
        """删除备份"""
        path = os.path.join(self._get_backup_dir(), backup_name)
        if not os.path.exists(path):
            return False
        os.remove(path)
        return True

    # ─── 版本对比 ────────────────────────────────────────────

    def diff_versions(self, v1: int, v2: int) -> dict:
        """
        对比两个版本的对象级差异
        返回: {v1, v2, added, modified, removed}
        """
        data1 = self._load_version(v1)
        data2 = self._load_version(v2)
        if data1 is None or data2 is None:
            return None

        areas1 = data1.get('areas', {})
        areas2 = data2.get('areas', {})

        added = []      # {area, task, path}
        modified = []   # {area, task, path, old_value, new_value}
        removed = []    # {area, task, path}

        all_areas = sorted(set(list(areas1.keys()) + list(areas2.keys())))

        for area in all_areas:
            tasks1 = areas1.get(area, {}).get('tasks', {})
            tasks2 = areas2.get(area, {}).get('tasks', {})

            if area not in areas1:
                # 整个区域是新增
                for task in sorted(tasks2.keys()):
                    added.append({'area': area, 'task': task, 'path': f'areas.{area}.tasks.{task}'})
                continue
            if area not in areas2:
                # 整个区域被删除
                for task in sorted(tasks1.keys()):
                    removed.append({'area': area, 'task': task, 'path': f'areas.{area}.tasks.{task}'})
                continue

            all_tasks = sorted(set(list(tasks1.keys()) + list(tasks2.keys())))
            for task in all_tasks:
                t1 = tasks1.get(task)
                t2 = tasks2.get(task)
                prefix = f'areas.{area}.tasks.{task}'

                if t1 is None:
                    added.append({'area': area, 'task': task, 'path': prefix})
                elif t2 is None:
                    removed.append({'area': area, 'task': task, 'path': prefix})
                elif t1 != t2:
                    # 任务级别修改：列出变化的字段
                    all_fields = set(list(t1.keys()) + list(t2.keys()))
                    for field in sorted(all_fields):
                        v1_val = t1.get(field)
                        v2_val = t2.get(field)
                        if v1_val != v2_val:
                            modified.append({
                                'area': area, 'task': task,
                                'path': f'{prefix}.{field}',
                                'old_value': v1_val,
                                'new_value': v2_val
                            })

        return {
            'v1': v1,
            'v2': v2,
            'added': added,
            'modified': modified,
            'removed': removed
        }

    def _load_version(self, version: int) -> dict:
        """加载指定版本的配置"""
        current = self.load_config()
        if current.get('_version') == version:
            return current

        # 从备份中查找
        backup_dir = self._get_backup_dir()
        if os.path.exists(backup_dir):
            for filename in sorted(os.listdir(backup_dir), reverse=True):
                if not filename.endswith('.json'):
                    continue
                try:
                    with open(os.path.join(backup_dir, filename), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if data.get('_version') == version or data.get('__meta__', {}).get('version') == version:
                        if '__meta__' in data:
                            del data['__meta__']
                        return data
                except Exception:
                    continue
        return None

    # ─── 增量升级 ────────────────────────────────────────────

    def apply_upgrade(self, patch: dict, message: str = '') -> dict:
        """
        应用增量补丁
        :param patch: {title, changes: [{path, value}], removals: [path]}
        :param message: 提交说明
        :return: {new_version, backup_name, applied: {added, modified, removed, errors}}
        """
        config = self.load_config()
        result = {'added': 0, 'modified': 0, 'removed': 0, 'errors': []}

        # 处理 changes
        for item in patch.get('changes', []):
            path = item.get('path', '')
            value = item.get('value')
            if not path:
                result['errors'].append('missing path in change item')
                continue
            try:
                self._set_nested(config, path, value, result)
            except Exception as e:
                result['errors'].append(f'{path}: {str(e)}')

        # 处理 removals
        for path in patch.get('removals', []):
            try:
                self._remove_nested(config, path, result)
            except Exception as e:
                result['errors'].append(f'{path}: {str(e)}')

        # 保存
        save_result = self.save_config(config, commit_message=message or patch.get('title', '增量升级'))
        result.update(save_result)
        return result

    def _set_nested(self, config: dict, path: str, value, result: dict):
        """按路径设置嵌套值，自动创建中间节点"""
        parts = path.split('.')
        if not parts:
            return

        # 按 parts 深入
        current = config
        for i, part in enumerate(parts[:-1]):
            if isinstance(current, dict) and part not in current:
                current[part] = {}
            current = current[part]
            if current is None:
                raise ValueError(f'中间路径 {parts[:i+1]} 为 null')

        last = parts[-1]
        if isinstance(current, dict):
            if last in current:
                result['modified'] += 1
            else:
                result['added'] += 1
            current[last] = value
        else:
            raise ValueError(f'目标路径不可写')

    def _remove_nested(self, config: dict, path: str, result: dict):
        """按路径删除嵌套值"""
        parts = path.split('.')
        if not parts:
            return

        current = config
        for i, part in enumerate(parts[:-1]):
            current = current.get(part, {})
            if not isinstance(current, dict):
                return  # 路径不存在，忽略

        last = parts[-1]
        if isinstance(current, dict) and last in current:
            del current[last]
            result['removed'] += 1
