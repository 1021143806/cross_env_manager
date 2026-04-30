#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路由蓝图注册模块
将所有功能蓝图注册到 Flask 应用
"""


def register_blueprints(app):
    """注册所有蓝图到 Flask 应用"""
    from routes.template_routes import template_bp
    from routes.task_routes import task_bp
    from routes.config_routes import config_bp
    from routes.auth_routes import auth_bp
    from routes.stats_routes import stats_bp
    from routes.system_routes import system_bp
    from routes.docs_routes import docs_bp
    from routes.join_qr_routes import join_qr_bp
    from routes.dispatch_routes import dispatch_bp
    
    app.register_blueprint(template_bp)
    app.register_blueprint(task_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(join_qr_bp)
    app.register_blueprint(dispatch_bp)
    
    print("[Routes] 所有蓝图已注册")
