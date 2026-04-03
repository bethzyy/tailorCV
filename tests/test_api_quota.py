"""
配额 API 测试
"""
import pytest


class TestQuotaAPI:
    """配额查询（需要登录 — 测试核心逻辑）"""

    def test_quota_unauthorized(self, client):
        resp = client.get('/api/quota')
        assert resp.status_code == 401


class TestQuotaLogic:
    """配额业务逻辑（直接测试核心模块）"""

    def test_check_quota_free_user_can_use(self, test_user):
        from core.quota import check_quota
        client, user_id = test_user
        if user_id is None:
            pytest.skip("User creation failed (duplicate email)")
        can_use, info = check_quota(user_id)
        assert can_use is True
        assert info['plan_type'] == 'free'

    def test_check_quota_exhausted(self, test_user):
        from core.quota import check_quota
        from core.database import db
        client, user_id = test_user
        if user_id is None:
            pytest.skip("User creation failed")
        db.record_usage(user_id, session_id='test_1')

        can_use, info = check_quota(user_id)
        assert can_use is False
        assert 'reason' in info

    def test_activate_pack5(self, test_user):
        from core.quota import activate_plan, check_quota
        client, user_id = test_user
        if user_id is None:
            pytest.skip("User creation failed")
        assert activate_plan(user_id, 'pack5') is True

        can_use, info = check_quota(user_id)
        assert can_use is True
        assert info['plan_type'] == 'pack5'
        assert info['quota_remaining'] == 6  # 1 (free) + 5 (pack5)

    def test_get_quota_display(self, test_user):
        from core.quota import get_quota_display
        client, user_id = test_user
        if user_id is None:
            pytest.skip("User creation failed")
        info = get_quota_display(user_id)
        assert info['plan_type'] == 'free'
        assert info['remaining'] == 1
        assert info['plan_name'] == '免费体验'
