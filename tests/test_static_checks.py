"""
前端静态分析测试：自动检测 HTML/JS 中的命名冲突和引用错误

覆盖问题类型：
1. HTML id 重复（同 id 多个元素 → getElementById 行为不确定）
2. JS function 声明重复（后者会覆盖前者）
3. getElementById / querySelector 引用不存在的 id
4. inline 事件处理器（onclick 等）引用不存在的函数
5. addEventListener 绑定到不存在的元素 id

运行：pytest tests/test_static_checks.py -v
"""
import re
import pytest
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent / 'web/templates'
HTML_FILES = sorted(TEMPLATES_DIR.rglob('*.html'))

# JS 内置对象/方法/关键字（不是用户定义的函数）
JS_BUILTINS = {
    # 语句
    'if', 'else', 'for', 'while', 'switch', 'case', 'return', 'break', 'continue',
    'try', 'catch', 'finally', 'throw', 'new', 'delete', 'typeof', 'instanceof',
    'class', 'extends', 'super', 'import', 'export', 'default', 'async', 'await', 'yield',
    # 类型/值
    'true', 'false', 'null', 'undefined', 'NaN', 'Infinity',
    'this', 'self', 'arguments',
    # 全局对象
    'document', 'window', 'localStorage', 'sessionStorage', 'navigator',
    'console', 'history', 'location', 'screen',
    'JSON', 'Math', 'Date', 'Object', 'Array', 'String', 'Number',
    'Boolean', 'RegExp', 'Error', 'Promise', 'Map', 'Set', 'Symbol',
    'Proxy', 'Reflect', 'Intl', 'WeakMap', 'WeakSet',
    'parseInt', 'parseFloat', 'isNaN', 'isFinite', 'encodeURI', 'decodeURI',
    'encodeURIComponent', 'decodeURIComponent',
    'atob', 'btoa',
    # DOM 方法（常用）
    'alert', 'confirm', 'prompt',
    'setTimeout', 'setInterval', 'clearTimeout', 'clearInterval',
    'requestAnimationFrame', 'cancelAnimationFrame',
    'fetch', 'XMLHttpRequest', 'FormData', 'Headers', 'Response', 'Request',
    'URL', 'URLSearchParams',
    'getElementById', 'getElementsByClassName', 'getElementsByTagName',
    'querySelector', 'querySelectorAll',
    'createElement', 'createTextNode', 'appendChild', 'removeChild', 'remove',
    'click', 'focus', 'blur', 'submit', 'reset',
    'insertBefore', 'replaceChild', 'cloneNode',
    'setAttribute', 'getAttribute', 'removeAttribute', 'hasAttribute',
    'classList', 'style', 'innerHTML', 'outerHTML', 'textContent', 'innerText',
    'addEventListener', 'removeEventListener',
    'dispatchEvent', 'preventDefault', 'stopPropagation', 'stopImmediatePropagation',
    'matches', 'closest', 'contains',
    'scrollTo', 'scrollBy', 'scrollIntoView',
    'getComputedStyle',
    'parse', 'stringify',
    'assign', 'freeze', 'keys', 'values', 'entries', 'from',
    'push', 'pop', 'shift', 'unshift', 'splice', 'slice', 'concat',
    'map', 'filter', 'reduce', 'forEach', 'find', 'findIndex', 'some', 'every',
    'includes', 'indexOf', 'lastIndexOf', 'join', 'reverse', 'sort', 'flat',
    'fill', 'copyWithin',
    'split', 'replace', 'replaceAll', 'match', 'matchAll', 'search',
    'substring', 'substr', 'slice', 'trim', 'trimStart', 'trimEnd',
    'toUpperCase', 'toLowerCase', 'charAt', 'charCodeAt', 'codePointAt',
    'startsWith', 'endsWith', 'repeat', 'padStart', 'padEnd',
    'toString', 'valueOf', 'toFixed', 'toPrecision', 'toExponential',
    'isNaN', 'isInteger', 'isSafeInteger', 'isFinite',
    'abs', 'ceil', 'floor', 'round', 'max', 'min', 'pow', 'sqrt', 'random',
    'log', 'info', 'warn', 'error', 'debug', 'table', 'time', 'timeEnd', 'group', 'groupEnd',
    'then', 'catch', 'finally',
    'next', 'return', 'throw',
    # CSS 函数（出现在 style 属性值中）
    'rgba', 'rgb', 'hsla', 'hsl', 'calc', 'var', 'linear', 'url',
    'translateX', 'translateY', 'translateZ', 'scale', 'rotate', 'skew',
    'min', 'max', 'clamp',
    # jQuery / 其他库
    '$', 'jQuery', 'ajax',
}


def _find_duplicates(items, label='item'):
    """通用重复检测，返回 {name: count}"""
    counts = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return {k: v for k, v in counts.items() if v > 1}


def _is_dynamic_ref(ref):
    """判断引用是否为动态拼接"""
    dynamic_patterns = ['+', '${', '(', '..']
    return any(p in ref for p in dynamic_patterns)


def _extract_js_blocks(html):
    """提取 HTML 中所有 <script> 块的内容"""
    return re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)


def _collect_defined_functions(html):
    """收集所有已定义的函数名（function 声明 + const/let/var 赋值函数）"""
    funcs = set(re.findall(r'\bfunction\s+(\w+)\s*\(', html))
    # const xxx = function(...)  或  const xxx = (...) => ...
    funcs |= set(re.findall(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:function|\([^)]*\)\s*=>)', html))
    return funcs


# ============================================================
# 1. HTML id 唯一性
# ============================================================
class TestHTMLIDDuplicates:
    """同 id 多个元素 → getElementById 始终返回第一个"""

    @pytest.mark.parametrize('html_file', HTML_FILES, ids=lambda f: f.relative_to(TEMPLATES_DIR))
    def test_no_duplicate_ids(self, html_file):
        html = html_file.read_text(encoding='utf-8')
        ids = re.findall(r'id="([^"]+)"', html)
        dups = _find_duplicates(ids)
        assert not dups, (
            f"\n{html_file.relative_to(TEMPLATES_DIR)}: "
            f"发现 {len(dups)} 个重复的 HTML id:\n" +
            "\n".join(f"  '{name}' × {count}" for name, count in dups.items())
        )


# ============================================================
# 2. JS function 声明唯一性
# ============================================================
class TestJSDuplicates:
    """同名 function 声明会静默覆盖"""

    @pytest.mark.parametrize('html_file', HTML_FILES, ids=lambda f: f.relative_to(TEMPLATES_DIR))
    def test_no_duplicate_function_declarations(self, html_file):
        html = html_file.read_text(encoding='utf-8')
        funcs = re.findall(r'\bfunction\s+(\w+)\s*\(', html)
        dups = _find_duplicates(funcs)
        assert not dups, (
            f"\n{html_file.relative_to(TEMPLATES_DIR)}: "
            f"发现 {len(dups)} 个重复的 function 声明:\n" +
            "\n".join(f"  function {name}() × {count}" for name, count in dups.items())
        )


# ============================================================
# 3. getElementById / querySelector 引用完整性
# ============================================================
class TestElementReferences:
    """引用不存在的 id → 返回 null，后续操作报错"""

    @pytest.mark.parametrize('html_file', HTML_FILES, ids=lambda f: f.relative_to(TEMPLATES_DIR))
    def test_getElementById_targets_exist(self, html_file):
        html = html_file.read_text(encoding='utf-8')
        html_ids = set(re.findall(r'id="([^"]+)"', html))
        refs = re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)", html)
        refs = [r for r in refs if not _is_dynamic_ref(r)]
        missing = [r for r in refs if r not in html_ids]
        assert not missing, (
            f"\n{html_file.relative_to(TEMPLATES_DIR)}: "
            f"发现 {len(missing)} 个 getElementById 引用了不存在的 id:\n" +
            "\n".join(f"  getElementById('{m}')" for m in missing)
        )

    @pytest.mark.parametrize('html_file', HTML_FILES, ids=lambda f: f.relative_to(TEMPLATES_DIR))
    def test_querySelector_id_targets_exist(self, html_file):
        html = html_file.read_text(encoding='utf-8')
        html_ids = set(re.findall(r'id="([^"]+)"', html))
        refs = re.findall(r"querySelector\(['\"]#([^'\"]+)['\"]\)", html)
        refs = [r for r in refs if not _is_dynamic_ref(r)]
        missing = [r for r in refs if r not in html_ids]
        assert not missing, (
            f"\n{html_file.relative_to(TEMPLATES_DIR)}: "
            f"发现 {len(missing)} 个 querySelector('#xxx') 引用了不存在的 id:\n" +
            "\n".join(f"  querySelector('#{m}')" for m in missing)
        )


# ============================================================
# 4. inline 事件处理器引用的函数必须存在
# ============================================================
class TestInlineEventHandlerReferences:
    """onclick="xxx()" 引用的函数如果不存在 → 点击时 ReferenceError"""

    @pytest.mark.parametrize('html_file', HTML_FILES, ids=lambda f: f.relative_to(TEMPLATES_DIR))
    def test_inline_handlers_reference_existing_functions(self, html_file):
        html = html_file.read_text(encoding='utf-8')

        # 提取内联事件处理器内容
        inline_calls = re.findall(
            r'\bon(?:click|change|submit|input|keyup|keydown|focus|blur|mouseover|mouseout|load|error)'
            r'="([^"]*)"',
            html
        )

        # 从处理器内容中提取函数调用名
        handler_funcs = set()
        for content in inline_calls:
            for m in re.findall(r'\b([a-zA-Z_]\w*)\s*\(', content):
                if m not in JS_BUILTINS and len(m) > 2:
                    handler_funcs.add(m)

        # 收集所有已定义的函数
        all_defined = _collect_defined_functions(html)
        missing = handler_funcs - all_defined

        assert not missing, (
            f"\n{html_file.relative_to(TEMPLATES_DIR)}: "
            f"发现 {len(missing)} 个内联事件调用了未定义的函数:\n" +
            "\n".join(f"  {f}()" for f in sorted(missing))
        )


# ============================================================
# 5. addEventListener 绑定的元素 id 必须存在
# ============================================================
class TestEventListenerTargets:
    """addEventListener 前的 getElementById 引用的 id 必须存在"""

    @pytest.mark.parametrize('html_file', HTML_FILES, ids=lambda f: f.relative_to(TEMPLATES_DIR))
    def test_addEventListener_on_existing_ids(self, html_file):
        html = html_file.read_text(encoding='utf-8')
        html_ids = set(re.findall(r'id="([^"]+)"', html))

        # 匹配 xxx.getElementById('yyy').addEventListener
        refs = re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)\.addEventListener", html)
        missing = [r for r in refs if r not in html_ids and not _is_dynamic_ref(r)]

        assert not missing, (
            f"\n{html_file.relative_to(TEMPLATES_DIR)}: "
            f"发现 {len(missing)} 个 addEventListener 绑定到不存在的 id:\n" +
            "\n".join(f"  getElementById('{m}').addEventListener(...)" for m in missing)
        )


# ============================================================
# 6. classList 操作引用的元素 id 必须存在
# ============================================================
class TestClassListOperations:
    """getElementById('xxx').classList → xxx 必须存在"""

    @pytest.mark.parametrize('html_file', HTML_FILES, ids=lambda f: f.relative_to(TEMPLATES_DIR))
    def test_classList_on_existing_ids(self, html_file):
        html = html_file.read_text(encoding='utf-8')
        html_ids = set(re.findall(r'id="([^"]+)"', html))

        refs = re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)\.classList", html)
        missing = [r for r in refs if r not in html_ids and not _is_dynamic_ref(r)]

        assert not missing, (
            f"\n{html_file.relative_to(TEMPLATES_DIR)}: "
            f"发现 {len(missing)} 个 classList 操作引用了不存在的 id:\n" +
            "\n".join(f"  getElementById('{m}').classList" for m in missing)
        )


# ============================================================
# 7. .style 操作引用的元素 id 必须存在
# ============================================================
class TestStyleOperations:
    """getElementById('xxx').style → xxx 必须存在"""

    @pytest.mark.parametrize('html_file', HTML_FILES, ids=lambda f: f.relative_to(TEMPLATES_DIR))
    def test_style_on_existing_ids(self, html_file):
        html = html_file.read_text(encoding='utf-8')
        html_ids = set(re.findall(r'id="([^"]+)"', html))

        # 匹配 xxx.getElementById('yyy').style.zzz = 模式（赋值操作）
        refs = re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)\.style\.\w+\s*=", html)
        missing = [r for r in refs if r not in html_ids and not _is_dynamic_ref(r)]

        assert not missing, (
            f"\n{html_file.relative_to(TEMPLATES_DIR)}: "
            f"发现 {len(missing)} 个 style 操作引用了不存在的 id:\n" +
            "\n".join(f"  getElementById('{m}').style" for m in missing)
        )
