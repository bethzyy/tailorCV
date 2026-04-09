"""
UI 重构回归测试 — 覆盖界面重构后发现的所有问题

每次大的前端/后端修改后，运行：
    pytest tests/test_ui_regression.py -v

问题清单（2026-04-08 UI 重构回归）：
1. classList.add('show') 缺少对应 CSS 规则 → 模态框不弹出
2. document('id') 误用 → "document is not a function" 运行时报错
3. parentElement.querySelector 嵌套错误 → 返回 null
4. .file-info.show / .preview-content.show CSS 缺失 → 显示/隐藏失效
5. 模态框 show/hide 方式不一致（classList vs style.display）
6. 提取模板时 preprocessed 缓存未清理 → 复用旧文件
7. AI 校验同步阻塞 → 提取速度慢
8. 同文件重提取被哈希去重阻挡
9. 提取/上传按钮无 loading 状态
10. para.clear() 不移除 XML 元素 → 空行残留
"""
import re
import ast
import pytest
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent / 'web/templates'
CSS_DIR = Path(__file__).parent.parent / 'web/static/css'
HTML_FILES = sorted(TEMPLATES_DIR.rglob('*.html'))
CSS_FILES = sorted(CSS_DIR.rglob('*.css'))

# 所有 HTML 内容缓存
HTML_CONTENTS = {}
for f in HTML_FILES:
    HTML_CONTENTS[str(f)] = f.read_text(encoding='utf-8')

# 所有 CSS 内容缓存
CSS_CONTENTS = {}
for f in CSS_FILES:
    CSS_CONTENTS[str(f)] = f.read_text(encoding='utf-8')

ALL_CSS = '\n'.join(CSS_CONTENTS.values())


def _get_css_classes(css_text):
    """提取 CSS 中所有定义的 class 选择器"""
    # 匹配 .classname { 或 .classname.show { 等
    classes = set(re.findall(r'\.([a-zA-Z_][\w-]*)', css_text))
    return classes


def _get_css_rules_with_show(css_text):
    """提取所有包含 .show 的 CSS 规则"""
    return set(re.findall(r'\.([\w-]+)\.show', css_text))


# ============================================================
# 回归 #1: classList.add('show') 必须有对应 CSS 规则
# ============================================================
class TestClassListShowHasCSS:
    """
    BUG: classList.add('show') / remove('show') 控制显隐，
    但 CSS 中没有 .xxx.show { display: flex/block; } 规则，
    导致模态框永远不弹出。

    修复: 要么添加 CSS 规则，要么改用 style.display 控制。
    此测试确保每个 classList('show') 操作都有对应的 CSS 规则。
    """

    @pytest.mark.parametrize('html_file', HTML_FILES, ids=lambda f: f.relative_to(TEMPLATES_DIR))
    def test_classlist_show_has_css_rule(self, html_file):
        html = HTML_CONTENTS[str(html_file)]

        # 提取所有 classList.add('show') 和 classList.remove('show') 的目标元素
        # 模式1: getElementById('xxx').classList.add('show')
        id_refs = re.findall(
            r"getElementById\(['\"]([^'\"]+)['\"]\)\.classList\.(?:add|remove|toggle)\(['\"]show['\"]\)",
            html
        )
        # 模式2: xxx.classList.add('show')（变量引用，无法静态检查，跳过）

        if not id_refs:
            return  # 没有使用 classList.show 模式，跳过

        # 获取这些 id 对应元素的 class
        missing_css = []
        for ref_id in id_refs:
            # 查找该 id 元素的 class 属性
            class_match = re.search(rf'id="{re.escape(ref_id)}"[^>]*class="([^"]*)"', html)
            if not class_match:
                # 可能 class 在 id 前面
                class_match = re.search(rf'class="([^"]*)"[^>]*id="{re.escape(ref_id)}"', html)
            if class_match:
                classes = class_match.group(1).split()
                for cls in classes:
                    if f'.{cls}.show' not in ALL_CSS and f'.{cls}.show' not in html:
                        missing_css.append(f"id='{ref_id}' class='{cls}'")

        # 也检查 modal-overlay 特殊情况
        if 'classList' in html and '.show' in html:
            # 检查是否有 modal-overlay.show 规则
            if 'modal-overlay' in html and '.modal-overlay.show' not in ALL_CSS:
                # 如果使用了 classList.show 模式但 CSS 没有 .modal-overlay.show
                if re.search(r"classList\.(?:add|remove|toggle)\(['\"]show['\"]\)", html):
                    has_modal_show = '.modal-overlay' in ALL_CSS and 'display: none' in ALL_CSS
                    if has_modal_show and '.modal-overlay.show' not in ALL_CSS:
                        missing_css.append("modal-overlay (classList.show 模式需要 .modal-overlay.show 规则)")

        assert not missing_css, (
            f"\n{html_file.relative_to(TEMPLATES_DIR)}: "
            f"classList.add/remove('show') 缺少对应 CSS 规则:\n" +
            "\n".join(f"  {m}" for m in missing_css) +
            "\n修复: 添加 CSS 规则或改用 element.style.display = 'flex'/'none'"
        )


# ============================================================
# 回归 #2: document() 不能作为函数调用
# ============================================================
class TestDocumentNotFunction:
    """
    BUG: document('templateEditContent') 误用，
    应为 document.getElementById('templateEditContent')。
    运行时报 TypeError: document is not a function。
    """

    @pytest.mark.parametrize('html_file', HTML_FILES, ids=lambda f: f.relative_to(TEMPLATES_DIR))
    def test_document_not_called_as_function(self, html_file):
        html = HTML_CONTENTS[str(html_file)]
        # 排除合法的 document.createElement 等
        illegal_calls = re.findall(r'(?<!\.)document\s*\(\s*[\'"]', html)
        # 过滤掉 document.querySelector/All 等（这些是方法调用，不是直接调用）
        illegal_calls = [c for c in illegal_calls if not re.search(
            r'document\.(?:querySelector|querySelectorAll|getElementById|getElementsBy)',
            html[:html.index(c)]
        )]

        assert not illegal_calls, (
            f"\n{html_file.relative_to(TEMPLATES_DIR)}: "
            f"发现 document() 被当作函数直接调用:\n" +
            "\n".join(f"  {c}..." for c in illegal_calls) +
            "\n修复: 改为 document.getElementById('id')"
        )


# ============================================================
# 回归 #3: parentElement.querySelector 嵌套不返回 null
# ============================================================
class TestDOMNavigationSafety:
    """
    BUG: document.getElementById('A').parentElement.querySelector('.B')
    当 A 的 parentElement 就是 .B 时，在其后代中找不到嵌套的 .B，返回 null。
    """

    @pytest.mark.parametrize('html_file', HTML_FILES, ids=lambda f: f.relative_to(TEMPLATES_DIR))
    def test_parentElement_querySelector_not_self(self, html_file):
        html = HTML_CONTENTS[str(html_file)]

        # 匹配 xxx.parentElement.querySelector('.yyy') 模式
        pattern = r"getElementById\(['\"]([^'\"]+)['\"]\)\.parentElement\.querySelector\(['\"]\.([^'\"]+)['\"]\)"
        matches = re.findall(pattern, html)

        problematic = []
        for elem_id, selector_class in matches:
            # 查找该元素的父元素的 class
            elem_match = re.search(
                rf'<\w+[^>]*id="{re.escape(elem_id)}"[^>]*>',
                html
            )
            if elem_match:
                # 检查父元素是否就是目标 class
                # 简化检查：如果元素的直接包裹元素有这个 class，就有问题
                problematic.append(
                    f"getElementById('{elem_id}').parentElement.querySelector('.{selector_class}')"
                )

        # 这个测试是警告性质的，记录已知问题模式
        if problematic:
            # 不直接 fail，而是检查这些路径后面是否有 null 保护
            for match_str in matches:
                full_pattern = rf"{re.escape(match_str[0])}.parentElement\.querySelector\('{re.escape(match_str[1])}'\)"
                idx = html.find(full_pattern)
                if idx >= 0:
                    # 检查后面是否有 ?. 或 if null 保护
                    after = html[idx + len(full_pattern):idx + len(full_pattern) + 50]
                    if '?' not in after and 'if ' not in after and '||' not in after:
                        pytest.fail(
                            f"\n{html_file.relative_to(TEMPLATES_DIR)}: "
                            f"DOM 导航可能返回 null 且无保护:\n"
                            f"  {match_str[0]}.parentElement.querySelector('.{match_str[1]}')\n"
                            f"修复: 使用 document.querySelector('#parentId .className') 替代"
                        )


# ============================================================
# 回归 #4: 所有模态框使用一致的 show/hide 方式
# ============================================================
class TestModalConsistency:
    """
    BUG: 部分模态框用 classList.add('show')，部分用 style.display='flex'，
    导致维护困难，容易遗漏 CSS 规则。

    规范: 所有模态框统一使用 style.display 方式。
    """

    @pytest.mark.parametrize('html_file', HTML_FILES, ids=lambda f: f.relative_to(TEMPLATES_DIR))
    def test_modal_show_uses_style_display(self, html_file):
        html = HTML_CONTENTS[str(html_file)]

        # 查找所有 modal-overlay 元素
        modal_ids = re.findall(r'class="modal-overlay"[^>]*id="([^"]+)"', html)
        if not modal_ids:
            modal_ids = re.findall(r'id="([^"]+)"[^>]*class="modal-overlay"', html)

        if not modal_ids:
            return  # 没有模态框，跳过

        # 检查每个模态框的 show/hide 函数
        issues = []
        for modal_id in modal_ids:
            # 查找 classList.add('show') 用于此模态框
            show_pattern = rf"getElementById\(['\"]{re.escape(modal_id)}['\"]\)\.classList\.add\(['\"]show['\"]\)"
            hide_pattern = rf"getElementById\(['\"]{re.escape(modal_id)}['\"]\)\.classList\.remove\(['\"]show['\"]\)"
            if re.search(show_pattern, html) or re.search(hide_pattern, html):
                issues.append(
                    f"  modal '#{modal_id}' 使用 classList.show 模式，应改用 style.display"
                )

        assert not issues, (
            f"\n{html_file.relative_to(TEMPLATES_DIR)}: "
            f"模态框 show/hide 方式不一致:\n" +
            "\n".join(issues) +
            "\n规范: 统一使用 element.style.display = 'flex' / 'none'"
        )


# ============================================================
# 回归 #5: 提取/上传按钮应有 loading 状态
# ============================================================
class TestAsyncButtonsHaveLoadingState:
    """
    BUG: 提取模板按钮点击后无 loading 反馈，用户以为无响应。
    异步操作按钮应在请求期间禁用并显示加载状态。
    """

    @pytest.mark.parametrize('html_file', HTML_FILES, ids=lambda f: f.relative_to(TEMPLATES_DIR))
    def test_extract_button_has_loading_state(self, html_file):
        html = HTML_CONTENTS[str(html_file)]
        # 查找 extractTemplate 函数
        if 'async function extractTemplate' not in html:
            return
        # 应该有 disabled 和加载文字
        # 搜索函数定义后的 10000 字符（覆盖整个函数体）
        func_start = html.index('async function extractTemplate')
        func_body = html[func_start:func_start + 10000]
        has_disabled = 'disabled' in func_body
        has_loading_text = '⏳' in func_body or '加载中' in func_body
        assert has_disabled and has_loading_text, (
            f"\n{html_file.relative_to(TEMPLATES_DIR)}: "
            f"extractTemplate() 缺少 loading 状态\n"
            f"  disabled: {has_disabled}, loading文字: {has_loading_text}\n"
            f"修复: 按钮应在 fetch 期间禁用并显示 '⏳ 提取中...'"
        )


# ============================================================
# 回归 #6: AI 校验不应阻塞主流程
# ============================================================
class TestAIVvalidationNonBlocking:
    """
    BUG: template_processor._ai_validate_structure 同步调用 AI API，
    阻塞模板提取响应数秒。

    修复: 应使用 threading.Thread(daemon=True) 异步执行。
    """

    def test_ai_validate_runs_in_thread(self):
        processor_file = Path(__file__).parent.parent / 'core/template_processor.py'
        if not processor_file.exists():
            pytest.skip('template_processor.py not found')

        source = processor_file.read_text(encoding='utf-8')

        # 检查 AI 校验调用是否在 threading.Thread 中
        if '_ai_validate_structure' not in source:
            pytest.skip('AI validation not implemented')

        # 查找 _ai_validate_structure 的调用（排除 def 定义行）
        validate_call_pattern = r'_ai_validate_structure\s*\('
        matches = list(re.finditer(validate_call_pattern, source))

        for match in matches:
            # 跳过函数定义行
            line_start = source.rfind('\n', 0, match.start()) + 1
            line = source[line_start:source.find('\n', match.start())]
            if 'def ' in line:
                continue
            # 检查前后 500 字符是否有 Thread
            context = source[max(0, match.start() - 500):match.start() + 200]
            if 'Thread' not in context and 'thread' not in context:
                pytest.fail(
                    f"\ncore/template_processor.py: "
                    f"_ai_validate_structure() 未在后台线程中运行 (位置 {match.start()})\n"
                    f"修复: 使用 threading.Thread(target=..., daemon=True).start()"
                )


# ============================================================
# 回归 #7: 删除模板时应清理 preprocessed 缓存
# ============================================================
class TestTemplateCacheCleanup:
    """
    BUG: 删除旧模板（DB记录）后，templates/preprocessed/{id}.docx 仍存在，
    template_processor.preprocess() 会复用旧文件，导致代码修改不生效。
    """

    def test_extract_deletes_preprocessed_cache(self):
        manager_file = Path(__file__).parent.parent / 'core/template_manager.py'
        if not manager_file.exists():
            pytest.skip('template_manager.py not found')

        source = manager_file.read_text(encoding='utf-8')

        # 查找 extract_template_from_resume 中的 delete_template 调用
        if 'delete_template' not in source:
            pytest.skip('delete_template not found')

        # 在 delete_template 调用附近应有无 unlink() 或 preprocessed 清理
        extract_start = source.find('extract_template_from_resume')
        if extract_start < 0:
            pytest.skip('extract_template_from_resume not found')

        # 找函数结尾（下一个 def 或文件末尾）
        next_def = source.find('\n    def ', extract_start + 10)
        func_body = source[extract_start:next_def] if next_def > 0 else source[extract_start:]

        has_delete = 'delete_template' in func_body
        has_unlink = 'unlink' in func_body or 'remove' in func_body or 'preprocessed' in func_body

        if has_delete:
            assert has_unlink, (
                "\ncore/template_manager.py: "
                "extract_template_from_resume() 删除旧模板后未清理 preprocessed 缓存\n"
                "修复: 添加 preprocessed_path.unlink() 清理缓存文件"
            )


# ============================================================
# 回归 #8: para.clear() vs XML 元素删除
# ============================================================
class TestParagraphCleanupMethod:
    """
    BUG: jinja_inserter 中使用 para.clear() 清除多余段落，
    只清除文本但保留 <w:p> 元素，导致渲染时出现空行。

    修复: 应从 XML 中彻底移除段落元素 (parent.remove(para._element))。
    """

    def test_entry_cleanup_removes_xml_element(self):
        inserter_file = Path(__file__).parent.parent / 'core/jinja_inserter.py'
        if not inserter_file.exists():
            pytest.skip('jinja_inserter.py not found')

        source = inserter_file.read_text(encoding='utf-8')

        # 在 _insert_entry_simple 中，清除剩余内容段落不应只用 clear()
        if '_insert_entry_simple' not in source:
            pytest.skip('_insert_entry_simple not found')

        func_start = source.find('def _insert_entry_simple')
        next_def = source.find('\n    def ', func_start + 10)
        func_body = source[func_start:next_def] if next_def > 0 else source[func_start:]

        # 检查是否有 content_paragraphs 清除逻辑
        if 'content_paragraphs' in func_body:
            # 如果有 .clear() 调用，检查是否同时有 XML 移除
            has_clear = '.clear()' in func_body
            has_xml_remove = 'getparent' in func_body and 'remove' in func_body

            if has_clear and not has_xml_remove:
                pytest.fail(
                    "\ncore/jinja_inserter.py: "
                    "_insert_entry_simple() 使用 para.clear() 但未从 XML 中移除元素\n"
                    "修复: 使用 parent.remove(para._element) 彻底删除段落"
                )

    def test_no_orphan_numbering_cleaner(self):
        """
        回归: _clean_section_residuals / _is_orphan_numbering 方法
        因 O(n²) 性能和索引失效问题已被移除。
        不应再引入类似的全量段落遍历清理方法。
        """
        inserter_file = Path(__file__).parent.parent / 'core/jinja_inserter.py'
        if not inserter_file.exists():
            pytest.skip('jinja_inserter.py not found')

        source = inserter_file.read_text(encoding='utf-8')

        # 这些方法已被确认有问题，不应再出现
        forbidden = ['_clean_section_residuals', '_is_orphan_numbering']
        for name in forbidden:
            assert name not in source, (
                f"\ncore/jinja_inserter.py: "
                f"方法 {name} 已被移除（O(n²)性能+索引失效），不应再引入\n"
                f"原因: 倒序遍历删除 XML 元素后 doc.paragraphs[idx] 索引失效"
            )


# ============================================================
# 回归 #9: 同文件允许重提取
# ============================================================
class TestTemplateReExtraction:
    """
    BUG: 上传同一文件提取模板时，content_hash 相同直接返回旧模板，
    即使用户指定了不同的名称。
    """

    def test_reextract_allows_new_name(self):
        manager_file = Path(__file__).parent.parent / 'core/template_manager.py'
        if not manager_file.exists():
            pytest.skip('template_manager.py not found')

        source = manager_file.read_text(encoding='utf-8')

        func_start = source.find('def extract_template_from_resume')
        next_def = source.find('\n    def ', func_start + 10)
        func_body = source[func_start:next_def] if next_def > 0 else source[func_start:]

        # 检查哈希去重逻辑
        if 'get_template_by_hash' in func_body:
            # 不应该无条件返回旧模板
            # 应该在名称不同时删除旧模板并继续
            has_delete_branch = 'delete_template' in func_body

            assert has_delete_branch, (
                "\ncore/template_manager.py: "
                "extract_template_from_resume() 哈希去重逻辑不允许重提取\n"
                "修复: 同文件不同名称时应删除旧模板并重新提取"
            )
