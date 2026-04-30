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

from flask_caching import Cache

# 全局缓存实例
cache = Cache()


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
