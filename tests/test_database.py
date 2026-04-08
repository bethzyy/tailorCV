"""
数据库操作单元测试

测试 core/database.py — CRUD 操作、唯一约束、级联操作。
使用临时 SQLite 文件，不污染生产数据库。
"""

import pytest
import time
from core.database import Database


@pytest.fixture
def db(tmp_path):
    """创建临时数据库"""
    db_path = str(tmp_path / 'test.db')
    return Database(db_path=db_path)


class TestUserCRUD:
    """用户 CRUD"""

    def test_create_user(self, db):
        """创建用户"""
        user_id = db.create_user(email='test1@example.com', phone='13800000001')
        assert user_id is not None
        assert isinstance(user_id, int)

    def test_create_user_duplicate_email(self, db):
        """重复邮箱返回 None"""
        db.create_user(email='test@example.com', phone='13800000001')
        result = db.create_user(email='test@example.com', phone='13800000002')
        assert result is None

    def test_get_user_by_email(self, db):
        """按邮箱查询"""
        user_id = db.create_user(email='find@example.com', phone='13800000003')
        user = db.get_user_by_email('find@example.com')
        assert user is not None
        assert user['id'] == user_id

    def test_get_user_by_email_not_found(self, db):
        """查询不存在的邮箱"""
        user = db.get_user_by_email('nonexistent@example.com')
        assert user is None

    def test_get_user_by_id(self, db):
        """按 ID 查询"""
        user_id = db.create_user(email='id@example.com', phone='13800000004')
        user = db.get_user_by_id(user_id)
        assert user is not None
        assert user['email'] == 'id@example.com'

    def test_get_user_by_id_not_found(self, db):
        """查询不存在的 ID"""
        user = db.get_user_by_id(999999)
        assert user is None


class TestTaskCRUD:
    """任务 CRUD"""

    def test_create_task(self, db):
        """创建任务"""
        success = db.create_task('task_001', 'session_001', input_mode='file')
        assert success is True

    def test_get_task(self, db):
        """查询任务"""
        db.create_task('task_002', 'session_002')
        task = db.get_task('task_002')
        assert task is not None
        assert task['status'] == 'pending'

    def test_update_task_status(self, db):
        """更新任务状态"""
        db.create_task('task_003', 'session_003')
        db.update_task_status('task_003', 'processing')
        task = db.get_task('task_003')
        assert task['status'] == 'processing'

    def test_update_task_completed(self, db):
        """完成任务"""
        db.create_task('task_004', 'session_004')
        success = db.update_task_status('task_004', 'completed')
        assert success is True
        task = db.get_task('task_004')
        assert task['status'] == 'completed'


class TestOrderCRUD:
    """订单 CRUD"""

    def test_create_order(self, db):
        """创建订单"""
        user_id = db.create_user(email='order@example.com', phone='13800000010')
        success = db.create_order(
            order_no='ORD001', user_id=user_id,
            plan_type='pack5', plan_name='按次包',
            amount=9.9, provider='alipay'
        )
        assert success is True

    def test_get_order(self, db):
        """查询订单"""
        user_id = db.create_user(email='order2@example.com', phone='13800000011')
        db.create_order(
            order_no='ORD002', user_id=user_id,
            plan_type='pack5', plan_name='按次包',
            amount=9.9
        )
        order = db.get_order('ORD002')
        assert order is not None
        assert order['plan_type'] == 'pack5'

    def test_get_user_orders(self, db):
        """查询用户订单列表"""
        user_id = db.create_user(email='order3@example.com', phone='13800000012')
        db.create_order('ORD003', user_id, 'pack5', '按次包', 9.9)
        db.create_order('ORD004', user_id, 'monthly', '月卡', 29.9)
        orders = db.get_user_orders(user_id)
        assert len(orders) == 2

    def test_update_order_paid(self, db):
        """更新订单为已支付"""
        user_id = db.create_user(email='order4@example.com', phone='13800000013')
        db.create_order('ORD005', user_id, 'pack5', '按次包', 9.9)
        db.update_order_paid('ORD005', 'tx_001')
        order = db.get_order('ORD005')
        assert order['status'] == 'paid'
        assert order['transaction_id'] == 'tx_001'


class TestHistoryCRUD:
    """历史记录 CRUD"""

    def test_save_and_get_history(self, db):
        """保存和查询历史"""
        session_id = f'test_session_{int(time.time()*1000)}'
        db.save_history(session_id=session_id, data={
            'candidate_name': '张三',
            'job_title': 'Python工程师',
            'match_score': 85,
            'original_resume': '原始简历内容',
            'tailored_resume': '定制简历内容',
            'jd_content': '职位描述内容'
        })
        history = db.get_history(session_id)
        assert history is not None
        assert history['candidate_name'] == '张三'
        assert history['match_score'] == 85

    def test_get_history_list(self, db):
        """查询历史列表"""
        for i in range(3):
            db.save_history(
                session_id=f'session_list_{i}_{int(time.time()*1000)}',
                data={'candidate_name': f'候选人{i}', 'job_title': '工程师'}
            )
        history_list = db.get_history_list(limit=10)
        assert len(history_list) >= 3


class TestAnalysisCache:
    """分析缓存"""

    def test_save_and_get_cache(self, db):
        """保存和读取缓存"""
        db.save_analysis_cache(
            cache_key='test_cache_key',
            resume_hash='hash1',
            jd_hash='hash2',
            analysis_result={'score': 85, 'level': 'good'}
        )
        cached = db.get_analysis_cache('test_cache_key')
        assert cached is not None
        assert cached['score'] == 85

    def test_cache_not_found(self, db):
        """缓存未命中"""
        cached = db.get_analysis_cache('nonexistent_key')
        assert cached is None


class TestConfigCRUD:
    """配置 CRUD"""

    def test_save_and_get_config(self, db):
        """保存和读取配置"""
        db.save_config('test_key', 'test_value')
        value = db.get_config('test_key')
        assert value == 'test_value'

    def test_get_config_default(self, db):
        """读取不存在的配置返回默认值"""
        value = db.get_config('nonexistent_key', default='default_val')
        assert value == 'default_val'

    def test_delete_config(self, db):
        """删除配置"""
        db.save_config('del_key', 'del_val')
        db.delete_config('del_key')
        value = db.get_config('del_key')
        assert value == ''
