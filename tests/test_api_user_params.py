"""
用户参数 API 测试

测试 /api/user_params GET 和 POST 端点。
"""

import json
import pytest


class TestGetUserParams:
    """GET /api/user_params"""

    def test_returns_json_when_no_file(self, client):
        """未保存时返回空 JSON 对象"""
        resp = client.get('/api/user_params')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)


class TestSaveUserParams:
    """POST /api/user_params"""

    def test_save_success(self, client):
        """保存参数成功"""
        params = {'name': 'Zhang San', 'target_position': 'Python Engineer'}
        resp = client.post('/api/user_params',
                          data=json.dumps(params),
                          content_type='application/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_save_and_retrieve(self, client):
        """保存后读取"""
        params = {'key1': 'value1', 'key2': 'value2'}
        client.post('/api/user_params',
                    data=json.dumps(params),
                    content_type='application/json')
        resp = client.get('/api/user_params')
        data = resp.get_json()
        assert data['key1'] == 'value1'
        assert data['key2'] == 'value2'

    def test_overwrite_params(self, client):
        """覆盖已保存的参数"""
        client.post('/api/user_params',
                    data=json.dumps({'v': 1}),
                    content_type='application/json')
        client.post('/api/user_params',
                    data=json.dumps({'v': 2}),
                    content_type='application/json')
        resp = client.get('/api/user_params')
        assert resp.get_json()['v'] == 2
