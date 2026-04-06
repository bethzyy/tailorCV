"""
模板处理器单元测试

测试 core/template_processor.py — 初始化、_build_context、_flatten_context、
check_template_compatibility、get_stats、_generate_template_id。
"""

import pytest
from unittest.mock import MagicMock, patch
from core.template_processor import TemplateProcessor


@pytest.fixture
def processor():
    return TemplateProcessor()


# ==================== 测试数据 ====================

SAMPLE_TAILORED_RESUME = {
    'basic_info': {'name': 'Zhang San', 'phone': '13800138000', 'email': 'zs@test.com'},
    'summary': '5 years backend experience',
    'education': [
        {'time': '2016-2020', 'school': 'Tsinghua', 'major': 'CS', 'degree': 'Bachelor'},
    ],
    'work_experience': [
        {'time': '2020-2023', 'company': 'ByteDance', 'position': 'SWE', 'content': 'Built API'},
    ],
    'projects': [
        {'time': '2021', 'name': 'API Gateway', 'role': 'Developer', 'content': 'Microservice'},
    ],
    'skills': [{'name': 'Python'}, {'name': 'Go'}],
    'awards': ['ACM Gold'],
    'certificates': ['AWS SAA'],
    'self_evaluation': 'Strong problem solver',
}


# ==================== 初始化 ====================

class TestTemplateProcessorInit:
    """初始化"""

    def test_create_processor(self, processor):
        assert processor is not None

    def test_has_detector(self, processor):
        assert processor.detector is not None

    def test_has_inserter(self, processor):
        assert processor.inserter is not None

    def test_template_dir_exists(self, processor):
        assert processor.template_dir.exists()

    def test_stats_initialized(self, processor):
        assert 'preprocessed' in processor.stats
        assert 'rendered' in processor.stats
        assert 'fallback_used' in processor.stats
        assert 'failed' in processor.stats


# ==================== 统计信息 ====================

class TestGetStats:
    """get_stats"""

    def test_returns_dict(self, processor):
        stats = processor.get_stats()
        assert isinstance(stats, dict)

    def test_includes_own_stats(self, processor):
        stats = processor.get_stats()
        assert 'preprocessed' in stats
        assert 'rendered' in stats

    def test_includes_sub_stats(self, processor):
        stats = processor.get_stats()
        assert 'detector_stats' in stats
        assert 'inserter_stats' in stats


# ==================== 上下文构建 ====================

class TestBuildContext:
    """_build_context"""

    def test_basic_info_preserved(self, processor):
        ctx = processor._build_context(SAMPLE_TAILORED_RESUME)
        assert ctx['basic_info']['name'] == 'Zhang San'
        assert ctx['basic_info']['phone'] == '13800138000'

    def test_summary_preserved(self, processor):
        ctx = processor._build_context(SAMPLE_TAILORED_RESUME)
        assert ctx['summary'] == '5 years backend experience'

    def test_self_evaluation_preserved(self, processor):
        ctx = processor._build_context(SAMPLE_TAILORED_RESUME)
        assert ctx['self_evaluation'] == 'Strong problem solver'

    def test_education_list_format(self, processor):
        ctx = processor._build_context(SAMPLE_TAILORED_RESUME)
        edu = ctx['education']
        assert isinstance(edu, list)
        assert len(edu) == 1
        assert edu[0]['school'] == 'Tsinghua'

    def test_work_experience_list_format(self, processor):
        ctx = processor._build_context(SAMPLE_TAILORED_RESUME)
        we = ctx['work_experience']
        assert isinstance(we, list)
        assert len(we) == 1
        assert we[0]['company'] == 'ByteDance'

    def test_flat_format_generated(self, processor):
        """验证扁平格式变量生成（如 work_experience_0_company）"""
        ctx = processor._build_context(SAMPLE_TAILORED_RESUME)
        assert 'work_experience_0_company' in ctx
        assert ctx['work_experience_0_company'] == 'ByteDance'
        assert 'work_experience_0_position' in ctx
        assert 'education_0_school' in ctx
        assert ctx['education_0_school'] == 'Tsinghua'

    def test_skills_as_list(self, processor):
        ctx = processor._build_context(SAMPLE_TAILORED_RESUME)
        skills = ctx['skills']
        assert isinstance(skills, list)
        assert len(skills) == 2

    def test_string_items_in_flat_format(self, processor):
        """awards/certificates 是字符串列表，flat 格式应为 xxx_0_name"""
        ctx = processor._build_context(SAMPLE_TAILORED_RESUME)
        assert 'awards_0_name' in ctx
        assert ctx['awards_0_name'] == 'ACM Gold'
        assert 'certificates_0_name' in ctx
        assert ctx['certificates_0_name'] == 'AWS SAA'

    def test_empty_resume(self, processor):
        """空简历返回默认值"""
        ctx = processor._build_context({})
        assert ctx['basic_info'] == {}
        assert ctx['summary'] == ''
        assert ctx['education'] == []
        assert ctx['work_experience'] == []
        assert ctx['self_evaluation'] == ''

    def test_missing_sections_default_to_empty(self, processor):
        """缺少某些章节时使用空列表"""
        partial = {'basic_info': {'name': 'Test'}}
        ctx = processor._build_context(partial)
        assert ctx['education'] == []
        assert ctx['projects'] == []
        assert ctx['skills'] == []


# ==================== 扁平化上下文 ====================

class TestFlattenContext:
    """_flatten_context"""

    def test_flatten_simple_dict(self, processor):
        ctx = {'name': 'Zhang', 'age': 30}
        flat = processor._flatten_context(ctx)
        assert flat == {'name': 'Zhang', 'age': 30}

    def test_flatten_nested_dict(self, processor):
        ctx = {'basic_info': {'name': 'Zhang', 'phone': '138'}}
        flat = processor._flatten_context(ctx)
        assert 'basic_info_name' in flat
        assert flat['basic_info_name'] == 'Zhang'
        assert 'basic_info_phone' in flat

    def test_flatten_list(self, processor):
        ctx = {'skills': ['Python', 'Go']}
        flat = processor._flatten_context(ctx)
        assert 'skills' in flat
        assert isinstance(flat['skills'], list)

    def test_flatten_list_of_dicts(self, processor):
        ctx = {'education': [{'school': 'THU'}, {'school': 'PKU'}]}
        flat = processor._flatten_context(ctx)
        assert 'education_0_school' in flat
        assert flat['education_0_school'] == 'THU'
        assert 'education_1_school' in flat
        assert flat['education_1_school'] == 'PKU'


# ==================== 模板兼容性 ====================

class TestCheckCompatibility:
    """check_template_compatibility"""

    @patch('core.template_manager.template_manager')
    def test_nonexistent_template(self, mock_tm, processor):
        mock_tm.get_template.return_value = None
        compatible, missing = processor.check_template_compatibility('nonexistent', {})
        assert compatible is False
        assert '模板不存在' in missing

    @patch('core.template_manager.template_manager')
    def test_empty_context_with_requirements(self, mock_tm, processor):
        """模板需要变量但上下文为空时返回缺失列表"""
        mock_tm.get_template.return_value = {
            'variables': ['basic_info', 'work_experience', 'education']
        }
        compatible, missing = processor.check_template_compatibility('tpl1', {})
        assert compatible is False
        assert 'basic_info' in missing
        assert 'work_experience' in missing

    @patch('core.template_manager.template_manager')
    def test_full_context_compatible(self, mock_tm, processor):
        """列表类型上下文（如 work_experience）保持为顶层 key"""
        mock_tm.get_template.return_value = {
            'variables': ['work_experience', 'education']
        }
        ctx = {'work_experience': [], 'education': []}
        compatible, missing = processor.check_template_compatibility('tpl1', ctx)
        assert compatible is True
        assert missing == []


# ==================== 模板 ID 生成 ====================

class TestGenerateTemplateId:
    """_generate_template_id"""

    def test_from_content_hash(self, processor):
        """基于内容生成固定哈希 ID"""
        content = b'hello world'
        id1 = processor._generate_template_id(None, content)
        id2 = processor._generate_template_id(None, content)
        assert id1 == id2  # 相同内容生成相同 ID
        assert len(id1) == 16  # MD5 前 16 位

    def test_different_content_different_id(self, processor):
        content_a = b'content a'
        content_b = b'content b'
        id_a = processor._generate_template_id(None, content_a)
        id_b = processor._generate_template_id(None, content_b)
        assert id_a != id_b

    def test_no_content_uses_timestamp(self, processor):
        """无内容时使用时间戳+UUID"""
        id1 = processor._generate_template_id(None, None)
        assert '_' in id1  # 格式: timestamp_uuid


# ==================== 动态字段配置 ====================

class TestDynamicSectionFields:
    """DYNAMIC_SECTION_FIELDS 配置"""

    def test_has_expected_sections(self, processor):
        fields = TemplateProcessor.DYNAMIC_SECTION_FIELDS
        assert 'education' in fields
        assert 'work_experience' in fields
        assert 'projects' in fields
        assert 'skills' in fields
        assert 'awards' in fields
        assert 'certificates' in fields

    def test_work_experience_fields(self, processor):
        fields = TemplateProcessor.DYNAMIC_SECTION_FIELDS['work_experience']
        assert 'time' in fields
        assert 'company' in fields
        assert 'position' in fields
        assert 'content' in fields
        assert 'tailored' in fields
