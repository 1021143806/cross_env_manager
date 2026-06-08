#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Service 层 - 业务逻辑封装
"""

from services.auth_service import AuthService
from services.stats_service import StatsService
from services.template_service import TemplateService
from services.config_service import ConfigService
from services.platform_switch_service import PlatformSwitchService, PlatformSwitchError

__all__ = [
    'AuthService', 'StatsService', 'TemplateService', 'ConfigService',
    'PlatformSwitchService', 'PlatformSwitchError',
]
