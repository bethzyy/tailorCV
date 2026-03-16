"""
应用入口模块

提供简版工具和多模型工具的独立应用入口。
"""

from .simple_app import create_app as create_simple_app
from .multi_app import create_app as create_multi_app

__all__ = [
    'create_simple_app',
    'create_multi_app',
]
