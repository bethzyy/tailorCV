"""
应用入口模块测试

测试 apps/__init__.py 模块的导入和导出。
"""

import pytest

from apps import create_simple_app, create_multi_app
from apps import __all__


class TestAppsInit:
    """测试 apps 模块初始化"""

    def test_create_simple_app_importable(self):
        """测试 create_simple_app 可正常导入"""
        assert callable(create_simple_app)

    def test_create_multi_app_importable(self):
        """测试 create_multi_app 可正常导入"""
        assert callable(create_multi_app)

    def test_all_exports(self):
        """测试 __all__ 包含所有导出项"""
        assert 'create_simple_app' in __all__
        assert 'create_multi_app' in __all__

    def test_all_exports_count(self):
        """测试 __all__ 导出项数量"""
        assert len(__all__) == 2

