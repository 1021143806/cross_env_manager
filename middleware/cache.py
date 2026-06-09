#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缓存中间件 - 基于 Flask-Caching 的内存缓存

使用方式:
    from middleware.cache import cache
    
    # 在 Service 方法上加装饰器
    @cache.cached(timeout=300, key_prefix='stats_overview')
    def get_overview(self):
        ...
    
    # 在写操作后清除缓存
    cache.clear()
"""

# 全局缓存实例
# flask_caching 可选依赖 - 若未安装则使用 NoOpCache 降级

class _NoOpCache:
    """当 flask_caching 不可用时的空缓存降级"""
    def __init__(self):
        self._app = None

    def init_app(self, app, config=None):
        self._app = app

    def cached(self, timeout=None, key_prefix=None):
        """装饰器：不做实际缓存，直接执行原函数"""
        def decorator(f):
            def wrapper(*args, **kwargs):
                return f(*args, **kwargs)
            return wrapper
        return decorator

    def clear(self):
        pass

    def get(self, key):
        return None

    def set(self, key, value, timeout=None):
        return True

try:
    from flask_caching import Cache
    cache = Cache()
except ImportError:
    cache = _NoOpCache()


def init_cache(app):
    """
    初始化缓存
    
    使用 SimpleCache（内存缓存），不需要 Redis
    配置:
    - CACHE_TYPE: simple（内存缓存）
    - CACHE_DEFAULT_TIMEOUT: 300秒（5分钟）
    - CACHE_THRESHOLD: 100（最多缓存100个键）
    """
    cache.init_app(app, config={
        'CACHE_TYPE': 'SimpleCache',
        'CACHE_DEFAULT_TIMEOUT': 300,
        'CACHE_THRESHOLD': 100,
        'CACHE_IGNORE_ERRORS': True,
    })
    print(f"[Cache] 内存缓存已初始化 (timeout=300s, max_keys=100)")
    return cache
