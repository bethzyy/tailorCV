"""
健康检查和基础 API 测试
"""


class TestHealth:
    """基础健康检查"""

    def test_index_returns_html(self, client):
        resp = client.get('/')
        assert resp.status_code == 200
        assert 'text/html' in resp.content_type

    def test_index_no_cache_headers(self, client):
        resp = client.get('/')
        assert 'no-cache' in resp.headers.get('Cache-Control', '')

    def test_health_check(self, client):
        resp = client.get('/api/health')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'status' in data
