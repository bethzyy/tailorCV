"""
用户中心 API 测试
"""
import pytest


class TestUserHistory:
    """使用历史"""

    def test_history_unauthorized(self, client):
        resp = client.get('/api/user/history')
        assert resp.status_code == 401


class TestUserLogic:
    """用户中心核心逻辑（直接测试，不需要 session）"""

    def test_record_usage(self, test_user):
        from core.database import db
        client, user_id = test_user
        if user_id is None:
            pytest.skip("User creation failed")

        db.record_usage(user_id, session_id='test_1')
        db.record_usage(user_id, session_id='test_2')

        records = db.get_user_usage_history(user_id, limit=20)
        assert len(records) >= 2

    def test_get_user_orders(self, test_user):
        from core.payment import create_payment
        from core.database import db
        client, user_id = test_user
        if user_id is None:
            pytest.skip("User creation failed")

        order = create_payment(user_id, 'pack5')

        orders = db.get_user_orders(user_id)
        assert len(orders) >= 1
        assert orders[0]['plan_type'] == 'pack5'
