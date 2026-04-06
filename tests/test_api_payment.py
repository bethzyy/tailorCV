"""
支付 API 测试
"""
import pytest


class TestPaymentPlans:
    """套餐列表"""

    def test_get_plans(self, client):
        resp = client.get('/api/payment/plans')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success']
        plans = data['plans']
        assert len(plans) == 4
        plan_types = [p['type'] for p in plans]
        assert 'free' in plan_types
        assert 'pack5' in plan_types
        assert 'monthly' in plan_types
        assert 'quarterly' in plan_types

    def test_plan_prices(self, client):
        resp = client.get('/api/payment/plans')
        data = resp.get_json()
        plans = {p['type']: p for p in data['plans']}
        assert plans['free']['price'] == 0
        assert plans['pack5']['price'] == 9.9
        assert plans['monthly']['price'] == 29.9


class TestPaymentCreate:
    """创建支付订单（需要登录 — 测试未登录返回 401）"""

    def test_create_unauthorized(self, client):
        resp = client.post('/api/payment/create', json={'plan_type': 'pack5'})
        assert resp.status_code == 401


class TestPaymentLogic:
    """支付核心逻辑（直接测试，不需要登录）"""

    def test_create_pack5_direct(self, test_user):
        from core.payment import create_payment
        client, user_id = test_user
        if user_id is None:
            pytest.skip("User creation failed")
        result = create_payment(user_id, 'pack5')
        assert 'order_no' in result
        assert result['amount'] == 9.9
        assert result['plan_type'] == 'pack5'

    def test_create_invalid_plan_direct(self, test_user):
        from core.payment import create_payment
        client, user_id = test_user
        if user_id is None:
            pytest.skip("User creation failed")
        with pytest.raises(ValueError):
            create_payment(user_id, 'nonexistent')

    def test_create_free_plan_direct(self, test_user):
        from core.payment import create_payment
        client, user_id = test_user
        if user_id is None:
            pytest.skip("User creation failed")
        with pytest.raises(ValueError):
            create_payment(user_id, 'free')

    def test_simulate_full_flow(self, test_user):
        """完整模拟支付流程"""
        from core.payment import create_payment, simulate_payment
        from core.quota import get_quota_display
        client, user_id = test_user
        if user_id is None:
            pytest.skip("User creation failed")

        # 创建订单
        order = create_payment(user_id, 'pack5')
        order_no = order['order_no']

        # 模拟支付
        assert simulate_payment(order_no) is True

        # 验证配额更新
        info = get_quota_display(user_id)
        assert info['plan_type'] == 'pack5'
        assert info['remaining'] == 8  # 3 (free) + 5 (pack5)

    def test_query_order(self, test_user):
        from core.payment import create_payment, query_payment
        client, user_id = test_user
        if user_id is None:
            pytest.skip("User creation failed")

        order = create_payment(user_id, 'pack5')
        result = query_payment(order['order_no'])
        assert result['status'] == 'pending'
        assert result['plan_type'] == 'pack5'

    def test_simulate_nonexistent(self):
        from core.payment import simulate_payment
        assert simulate_payment('nonexistent') is False
