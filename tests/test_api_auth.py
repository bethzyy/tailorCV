"""
认证 API 测试
"""


class TestAuthSendCode:
    """发送验证码"""

    def test_send_code_empty_email(self, client):
        resp = client.post('/api/auth/send-code', json={'email': ''})
        assert resp.status_code == 400
        data = resp.get_json()
        assert not data['success']

    def test_send_code_no_body(self, client):
        resp = client.post('/api/auth/send-code', json={})
        assert resp.status_code == 400

    def test_send_code_invalid_email(self, client):
        resp = client.post('/api/auth/send-code', json={'email': 'not-an-email'})
        assert resp.status_code == 400

    def test_send_code_valid_email(self, client):
        """测试发送验证码（开发模式不需要 SMTP）"""
        import core.auth as auth_module
        auth_module._verification_codes.clear()

        resp = client.post('/api/auth/send-code', json={'email': 'test@example.com'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success']

    def test_send_code_rate_limit(self, client):
        """短时间内重复发送应失败"""
        import core.auth as auth_module
        auth_module._verification_codes.clear()

        resp1 = client.post('/api/auth/send-code', json={'email': 'ratelimit@example.com'})
        assert resp1.status_code == 200

        resp2 = client.post('/api/auth/send-code', json={'email': 'ratelimit@example.com'})
        assert resp2.status_code == 400


class TestAuthLogin:
    """登录/注册"""

    def test_login_empty_fields(self, client):
        resp = client.post('/api/auth/login', json={})
        assert resp.status_code == 400

    def test_login_wrong_code(self, client):
        resp = client.post('/api/auth/login', json={
            'email': 'test@example.com',
            'code': '000000'
        })
        assert resp.status_code == 401

    def test_login_success(self, client):
        """测试完整登录流程：发送验证码 → 使用验证码登录"""
        import core.auth as auth_module
        auth_module._verification_codes.clear()

        test_email = 'logintest@example.com'

        # 1. 发送验证码
        resp = client.post('/api/auth/send-code', json={'email': test_email})
        assert resp.status_code == 200

        # 2. 获取发送的验证码（开发模式存在内存中）
        code = auth_module._verification_codes[test_email]['code']

        # 3. 使用验证码登录
        resp = client.post('/api/auth/login', json={
            'email': test_email,
            'code': code,
            'duration': 'session'
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success']
        assert 'user' in data
        assert data['user']['email'] == test_email
        assert data['user']['is_new_user'] is True

    def test_login_existing_user(self, client):
        """已注册用户再次登录应返回 is_new_user=False"""
        import core.auth as auth_module
        import uuid
        auth_module._verification_codes.clear()

        test_email = f'relogin_{uuid.uuid4().hex[:8]}@example.com'

        # 第一次登录（注册）
        resp = client.post('/api/auth/send-code', json={'email': test_email})
        assert resp.status_code == 200
        code1 = auth_module._verification_codes[test_email]['code']
        resp = client.post('/api/auth/login', json={'email': test_email, 'code': code1})
        assert resp.status_code == 200
        assert resp.get_json()['user']['is_new_user'] is True

        # 第二次登录（已注册用户）
        auth_module._verification_codes.clear()
        resp = client.post('/api/auth/send-code', json={'email': test_email})
        assert resp.status_code == 200
        code2 = auth_module._verification_codes[test_email]['code']
        resp = client.post('/api/auth/login', json={'email': test_email, 'code': code2})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['user']['is_new_user'] is False


class TestAuthLogout:
    """退出登录"""

    def test_logout(self, client):
        """验证退出登录清除 session"""
        resp = client.post('/api/auth/logout')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success']

    def test_get_current_user_none_when_not_logged_in(self, client):
        """未登录时 /api/auth/me 返回 401"""
        resp = client.get('/api/auth/me')
        assert resp.status_code == 401


class TestAuthMe:
    """获取当前用户"""

    def test_me_unauthorized(self, client):
        resp = client.get('/api/auth/me')
        assert resp.status_code == 401
