#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路由蓝图注册模块
将所有功能蓝图注册到 Flask 应用，支持按模块开关禁用
"""


def register_blueprints(app, modules=None):
    """注册蓝图到 Flask 应用，modules 为模块开关字典
    
    modules 键名:
      config_module  - 跨环境配置（template/join_qr/custom_table）
      dispatch       - 调车调度
      task           - 任务下发
      system         - 系统管理（始终启用，不可禁）
    """
    if modules is None:
        modules = {}

    # 始终启用
    from routes.auth_routes import auth_bp

    def _enabled(key, default=True):
        return modules.get(key, default)

    # ── 系统管理（始终启用） ──
    from routes.system_routes import system_bp
    from routes.docs_routes import docs_bp
    from routes.monitor_routes import monitor_bp
    from routes.system_upgrade_routes import upgrade_bp

    # ── 跨环境配置 ──
    if _enabled("config_module"):
        from routes.template_routes import template_bp
        from routes.join_qr_routes import join_qr_bp
        from routes.custom_table_routes import custom_table_bp
        from routes.config_routes import config_bp
        from routes.stats_routes import stats_bp
        from routes.platform_switch_routes import platform_switch_bp

    # ── 调车调度 ──
    if _enabled("dispatch"):
        from routes.dispatch_routes import dispatch_bp

    # ── 任务下发 ──
    if _enabled("task"):
        from routes.task_routes import task_bp

    # 注册：始终启用
    app.register_blueprint(auth_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(monitor_bp)
    app.register_blueprint(upgrade_bp)

    # 注册：条件启用
    if _enabled("config_module"):
        app.register_blueprint(template_bp)
        app.register_blueprint(join_qr_bp)
        app.register_blueprint(custom_table_bp)
        app.register_blueprint(config_bp)
        app.register_blueprint(stats_bp)
        app.register_blueprint(platform_switch_bp)
        print("[Routes] config_module 已注册 (含数据统计/平台切换)")

    if _enabled("dispatch"):
        app.register_blueprint(dispatch_bp)
        print("[Routes] dispatch 已注册")

    if _enabled("task"):
        app.register_blueprint(task_bp)
        print("[Routes] task 已注册")

    print("[Routes] 系统蓝图已注册 (system/upgrade/monitor/stats/docs/auth)")
