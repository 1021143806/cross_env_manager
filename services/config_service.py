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
            return self._default_config()
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            raise RuntimeError(f'配置解析失败: {e}')

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

        # 2. 版本递增
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
