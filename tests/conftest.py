"""
tailorCV 测试配置

提供 Flask app fixture、临时数据库、测试客户端。
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 全局计数器，确保每个测试用唯一邮箱
_email_counter = 0


def _next_email(prefix='test'):
    global _email_counter
    _email_counter += 1
    import time
    return f'{prefix}_{_email_counter}_{int(time.time()*1000)}@test.example.com'


@pytest.fixture(scope='session')
def db_path():
    """创建临时数据库路径（session 级别共享）"""
    fd, path = tempfile.mkstemp(suffix='.db', prefix='tailorcv_test_')
    os.close(fd)
    yield path
    try:
        if os.path.exists(path):
            os.unlink(path)
    except PermissionError:
        pass  # Windows 文件锁定


@pytest.fixture(scope='session')
def app(db_path):
    """创建测试用 Flask app"""
    os.environ['TESTING'] = 'true'
    os.environ['DATABASE_PATH'] = db_path
    os.environ['WECHAT_SANDBOX'] = 'true'
    os.environ['RATE_LIMIT_ANON'] = '10000 per minute'
    os.environ['RATE_LIMIT_DEFAULT'] = '10000 per minute'
    os.environ['SECRET_KEY'] = 'test-secret-key-for-tailorcv'

    # 重建数据库单例，使用测试数据库
    from core.database import Database
    from core import database as db_module
    test_db = Database(db_path=db_path)
    db_module.db = test_db

    # 覆盖 config 的 SECRET_KEY
    from core import config as cfg
    cfg.SECRET_KEY = 'test-secret-key-for-tailorcv'

    # 导入 app（这会导入所有依赖模块，它们此时会获取 test_db）
    from apps.simple_app import create_app
    application = create_app()
    application.config['TESTING'] = True

    # 修补所有已导入 db 的模块（包括 create_app 内部导入的模块）
    import core.auth
    import core.quota
    import core.payment
    import core.template_manager
    import apps.simple_app as simple_app_mod
    for mod in [core.auth, core.quota, core.payment, core.template_manager, simple_app_mod]:
        if hasattr(mod, 'db'):
            mod.db = test_db

    # 禁用限流
    limiter_entry = application.extensions.get('limiter')
    if isinstance(limiter_entry, set) and limiter_entry:
        limiter_obj = next(iter(limiter_entry))
        if hasattr(limiter_obj, 'enabled'):
            limiter_obj.enabled = False

    return application


@pytest.fixture
def client(app):
    """Flask 测试客户端"""
    return app.test_client()


@pytest.fixture
def test_user(client, app):
    """创建测试用户，返回 (client, user_id)"""
    from core.database import db
    email = _next_email('user')
    phone = _next_email('phone').replace('@', '').replace('.', '')
    user_id = db.create_user(email=email, phone=phone)
    return client, user_id
