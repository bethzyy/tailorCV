"""
模板管理 API 测试
"""


class TestTemplateList:
    """模板列表"""

    def test_get_templates(self, client):
        resp = client.get('/api/templates')
        assert resp.status_code == 200
        data = resp.get_json()
        templates = data.get('templates', [])
        # 应至少有 6 个内置模板
        assert len(templates) >= 6

    def test_builtin_templates_exist(self, client):
        resp = client.get('/api/templates')
        data = resp.get_json()
        templates = data.get('templates', [])
        # 检查内置模板 source
        builtin = [t for t in templates if t.get('source') == 'builtin']
        assert len(builtin) >= 6


class TestTemplateDetail:
    """模板详情"""

    def test_get_template_detail(self, client):
        resp = client.get('/api/templates')
        templates = resp.get_json()['templates']
        if templates:
            template_id = templates[0]['template_id']
            detail_resp = client.get(f'/api/templates/{template_id}')
            assert detail_resp.status_code == 200
            detail = detail_resp.get_json()
            assert detail['template_id'] == template_id
            assert 'name' in detail

    def test_get_nonexistent_template(self, client):
        resp = client.get('/api/templates/nonexistent_id')
        assert resp.status_code == 404


class TestTemplateDelete:
    """模板删除"""

    def test_delete_builtin_forbidden(self, client):
        resp = client.get('/api/templates')
        templates = resp.get_json()['templates']
        builtin = [t for t in templates if t['source'] == 'builtin']
        if builtin:
            template_id = builtin[0]['template_id']
            del_resp = client.delete(f'/api/templates/{template_id}')
            # 内置模板不能删除（400 或 403 都算通过）
            assert del_resp.status_code in (400, 403)


class TestTemplatePreview:
    """模板预览"""

    def test_html_preview(self, client):
        resp = client.get('/api/templates')
        templates = resp.get_json()['templates']
        if templates:
            template_id = templates[0]['template_id']
            preview_resp = client.get(f'/api/templates/{template_id}/preview/html')
            assert preview_resp.status_code == 200
            data = preview_resp.get_json()
            assert data.get('success') is True
            assert 'html' in data


class TestTemplateRecommend:
    """模板推荐"""

    def test_recommend(self, client):
        resp = client.post('/api/templates/recommend',
                           json={'jd_content': '招聘高级Java开发工程师，5年以上经验'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'recommendations' in data


class TestTemplateCompatibility:
    """兼容性检查"""

    def test_compatibility(self, client):
        resp = client.get('/api/templates')
        templates = resp.get_json()['templates']
        if templates:
            template_id = templates[0]['template_id']
            sample_resume = {
                'basic_info': {'name': '测试'},
                'work_experience': [{'company': 'ABC'}],
            }
            compat_resp = client.post(
                f'/api/templates/{template_id}/compatibility',
                json={'resume_data': sample_resume}
            )
            assert compat_resp.status_code == 200
            data = compat_resp.get_json()
            assert 'is_compatible' in data or 'compatible' in data
