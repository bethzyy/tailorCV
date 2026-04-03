"""
前端一致性检查（静态分析）

检查 HTML 中的 JS 函数引用、ID 引用、API 端点是否与后端匹配。
不需要运行 Flask app。
"""

import re
import pytest
from pathlib import Path


HTML_PATH = Path(__file__).parent.parent / 'web' / 'templates' / 'simple' / 'index.html'
APP_PATH = Path(__file__).parent.parent / 'apps' / 'simple_app.py'


@pytest.fixture(scope='module')
def html_content():
    return HTML_PATH.read_text(encoding='utf-8')


@pytest.fixture(scope='module')
def app_content():
    return APP_PATH.read_text(encoding='utf-8')


# JavaScript 内置方法，不应被当作自定义函数
JS_BUILTINS = {
    'stopPropagation', 'preventDefault', 'addEventListener', 'removeEventListener',
    'querySelector', 'querySelectorAll', 'getElementById', 'createElement',
    'appendChild', 'removeChild', 'classList', 'setAttribute', 'getAttribute',
    'setTimeout', 'setInterval', 'clearTimeout', 'clearInterval',
    'JSON', 'Math', 'Date', 'console', 'window', 'document', 'fetch',
    'parseInt', 'parseFloat', 'isNaN', 'alert', 'confirm', 'prompt',
    'push', 'pop', 'shift', 'unshift', 'splice', 'slice', 'map', 'filter',
    'reduce', 'forEach', 'find', 'indexOf', 'includes', 'join', 'keys',
    'values', 'entries', 'length', 'toString', 'hasOwnProperty',
    'open', 'close', 'write', 'focus', 'blur', 'click', 'submit',
    'location', 'reload', 'assign', 'replace', 'href',
    'innerWidth', 'innerHeight', 'outerWidth', 'outerHeight',
    'getBoundingClientRect', 'scrollIntoView',
}


class TestJSFunctionReferences:
    """检查 onclick 引用的函数是否都存在"""

    @pytest.fixture(scope='class')
    def js_functions(self, html_content):
        """提取所有 function 定义"""
        patterns = [
            r'function\s+(\w+)\s*\(',
            r'(?:const|let|var)\s+(\w+)\s*=\s*(?:function|\()',
        ]
        functions = set()
        for pattern in patterns:
            for match in re.finditer(pattern, html_content):
                functions.add(match.group(1))
        return functions

    @pytest.fixture(scope='class')
    def onclick_functions(self, html_content):
        """提取所有 onclick 中引用的函数（排除内置方法）"""
        pattern = r'onclick="[^"]*?(\w+)\s*\('
        return set(m.group(1) for m in re.finditer(pattern, html_content)) - JS_BUILTINS

    def test_all_onclick_functions_exist(self, js_functions, onclick_functions):
        missing = onclick_functions - js_functions
        assert not missing, f"onclick 引用了不存在的函数: {missing}"


class TestElementIdReferences:
    """检查 getElementById 引用的 ID 是否都存在"""

    @pytest.fixture(scope='class')
    def html_ids(self, html_content):
        return set(m.group(1) for m in re.finditer(r'id="([^"]+)"', html_content))

    @pytest.fixture(scope='class')
    def referenced_ids(self, html_content):
        return set(m.group(1) for m in re.finditer(r"getElementById\(['\"]([^'\"]+)['\"]\)", html_content))

    def test_all_referenced_ids_exist(self, html_ids, referenced_ids):
        missing = referenced_ids - html_ids
        assert not missing, f"getElementById 引用了不存在的 ID: {missing}"


class TestAPIEndpointsMatch:
    """检查前端 fetch 调用的端点是否在后端定义"""

    @pytest.fixture(scope='class')
    def frontend_endpoints(self, html_content):
        """提取前端 fetch 的 API 路径"""
        # 匹配各种模板字符串中的 API 路径
        patterns = [
            r"fetch\(['\"](/api/[^'\"]+)['\"]",
            r"fetch\(`([^`]+)`",
        ]
        endpoints = set()
        for pattern in patterns:
            for m in re.finditer(pattern, html_content):
                endpoint = m.group(1)
                # 标准化路径参数：${xxx} → <param>
                endpoint = re.sub(r'\$\{[^}]+\}', '<param>', endpoint)
                endpoint = re.sub(r'\{[^}]+\}', '<param>', endpoint)
                endpoint = endpoint.split('?')[0]
                endpoints.add(endpoint)
        return endpoints

    @pytest.fixture(scope='class')
    def backend_routes(self, app_content):
        """提取后端定义的 API 路由"""
        routes = set()
        for m in re.finditer(r"@app\.route\(['\"]([^'\"]+)['\"]", app_content):
            route = m.group(1)
            route = re.sub(r'<[^>]+>', '<param>', route)
            routes.add(route)
        return routes

    def test_all_frontend_endpoints_exist(self, frontend_endpoints, backend_routes):
        missing = frontend_endpoints - backend_routes
        assert not missing, f"前端调用了后端不存在的 API: {missing}"


class TestModalDisplayConsistency:
    """检查带 inline display:none 的 modal 使用 style.display 而非 classList"""

    def test_no_classlist_show_on_inline_hidden_modals(self, html_content):
        """带 inline style="display:none" 的 modal 不应使用 classList（会被 inline 覆盖）"""
        # 找出所有带 inline display:none 的 modal
        problematic_modals = set()
        for m in re.finditer(r'<div[^>]*class="modal-overlay"[^>]*style="[^"]*display\s*:\s*none[^"]*"[^>]*id="([^"]+)"', html_content):
            problematic_modals.add(m.group(1))
        for m in re.finditer(r'<div[^>]*id="([^"]+)"[^>]*class="modal-overlay"[^>]*style="[^"]*display\s*:\s*none[^"]*"', html_content):
            problematic_modals.add(m.group(1))
        # 也匹配 id 在 style 之前的
        for m in re.finditer(r'<div[^>]*id="([^"]+)"[^>]*style="[^"]*display\s*:\s*none[^"]*"[^>]*class="modal-overlay"', html_content):
            problematic_modals.add(m.group(1))

        # 查找所有 classList.add/remove('show') 调用
        for match in re.finditer(r"classList\.(?:add|remove)\(['\"]show['\"]\)", html_content):
            line_start = html_content.rfind('\n', 0, match.start()) + 1
            line_end = html_content.find('\n', match.start())
            line = html_content[line_start:line_end]
            for mid in problematic_modals:
                if mid in line:
                    pytest.fail(
                        f"Modal '{mid}' has inline display:none but uses classList at: {line.strip()}. "
                        f"Use style.display='flex'/'none' instead."
                    )


class TestHTMLStructure:
    """基础 HTML 结构检查"""

    def test_html_has_login_modal(self, html_content):
        assert 'id="loginModal"' in html_content

    def test_html_has_payment_modal(self, html_content):
        assert 'id="paymentModal"' in html_content

    def test_html_has_user_center_modal(self, html_content):
        assert 'id="userCenterModal"' in html_content

    def test_html_has_template_preview_modal(self, html_content):
        assert 'id="templatePreviewModal"' in html_content

    def test_html_has_login_guide(self, html_content):
        assert 'id="loginGuide"' in html_content

    def test_html_has_quota_badge(self, html_content):
        assert 'id="userQuotaBadge"' in html_content

    def test_html_has_bfcache_prevention(self, html_content):
        assert 'pageshow' in html_content
