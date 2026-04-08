"""
简历构建器单元测试

测试 core/resume_builder.py — 表单数据 → 结构化简历的纯数据转换逻辑。
无外部依赖，不需要 mock。
"""

import pytest
from core.resume_builder import ResumeBuilder, GuidedInputData


@pytest.fixture
def builder():
    return ResumeBuilder()


@pytest.fixture
def full_form_data():
    """包含所有字段的完整表单数据"""
    return {
        'name': '张三',
        'gender': '男',
        'age': 28,
        'phone': '13800138000',
        'email': 'zhangsan@example.com',
        'location': '北京',
        'political_status': '中共党员',
        'edu_count': 2,
        'edu_school_0': '清华大学',
        'edu_major_0': '计算机科学',
        'edu_degree_0': '硕士',
        'edu_time_0': '2018-2021',
        'edu_school_1': '北京大学',
        'edu_major_1': '软件工程',
        'edu_degree_1': '本科',
        'edu_time_1': '2014-2018',
        'work_count': 2,
        'work_company_0': '字节跳动',
        'work_position_0': '高级工程师',
        'work_time_0': '2021-至今',
        'work_content_0': '负责核心系统开发',
        'work_company_1': '腾讯',
        'work_position_1': '工程师',
        'work_time_1': '2018-2021',
        'work_content_1': '参与后端服务开发',
        'proj_count': 1,
        'proj_name_0': '智能推荐系统',
        'proj_role_0': '技术负责人',
        'proj_time_0': '2022-2023',
        'proj_content_0': '设计并实现推荐引擎',
        'skills': 'Python、Java、Go、Kubernetes',
        'awards': 'ACM金牌、优秀毕业生',
        'certificates': 'PMP、AWS架构师',
        'self_evaluation': '5年后端开发经验，热爱技术',
    }


class TestBuildFromForm:
    """build_from_form: 表单 → 简历文本"""

    def test_full_form(self, builder, full_form_data):
        result = builder.build_from_form(full_form_data)
        assert '张三' in result
        assert '13800138000' in result
        assert 'zhangsan@example.com' in result
        assert '清华大学' in result
        assert '字节跳动' in result
        assert '智能推荐系统' in result
        assert 'Python' in result
        assert 'ACM金牌' in result
        assert 'PMP' in result
        assert '5年后端开发经验' in result

    def test_empty_form(self, builder):
        result = builder.build_from_form({})
        # 空表单应该返回空字符串或只有空白
        assert isinstance(result, str)

    def test_name_only(self, builder):
        result = builder.build_from_form({'name': '李四'})
        assert '李四' in result

    def test_missing_work_experience(self, builder):
        form = {
            'name': '王五',
            'phone': '13900139000',
            'email': 'wangwu@example.com',
        }
        result = builder.build_from_form(form)
        assert '王五' in result
        # 不应崩溃，工作经历部分应被跳过
        assert isinstance(result, str)

    def test_missing_education(self, builder):
        form = {
            'name': '赵六',
            'work_count': 1,
            'work_company_0': '某公司',
            'work_position_0': '工程师',
        }
        result = builder.build_from_form(form)
        assert '赵六' in result
        assert '某公司' in result
        assert isinstance(result, str)

    def test_multiple_work_experiences(self, builder):
        form = {
            'name': '孙七',
            'work_count': 3,
            'work_company_0': '公司A',
            'work_position_0': '职位A',
            'work_company_1': '公司B',
            'work_position_1': '职位B',
            'work_company_2': '公司C',
            'work_position_2': '职位C',
        }
        result = builder.build_from_form(form)
        assert '公司A' in result
        assert '公司B' in result
        assert '公司C' in result

    def test_skills_with_various_separators(self, builder):
        """技能支持多种分隔符"""
        for sep, skills_str in [
            ('\n', 'Python\nJava\nGo'),
            ('、', 'Python、Java、Go'),
            ('，', 'Python，Java，Go'),
            (',', 'Python,Java,Go'),
        ]:
            form = {'name': '测试', 'skills': skills_str}
            result = builder.build_from_form(form)
            assert 'Python' in result
            assert 'Java' in result
            assert 'Go' in result

    def test_special_characters(self, builder):
        """特殊字符不应导致崩溃"""
        form = {
            'name': '测试<script>',
            'self_evaluation': '熟悉 "引号" & 特殊字符 <tag>',
        }
        result = builder.build_from_form(form)
        assert isinstance(result, str)
        assert len(result) > 0


class TestBuildStructured:
    """build_structured: 表单 → 结构化 JSON"""

    def test_full_form(self, builder, full_form_data):
        result = builder.build_structured(full_form_data)
        assert isinstance(result, dict)
        assert result['basic_info']['name'] == '张三'
        assert result['basic_info']['phone'] == '13800138000'
        assert len(result['education']) == 2
        assert len(result['work_experience']) == 2
        assert len(result['projects']) == 1
        assert len(result['skills']) == 4

    def test_empty_form(self, builder):
        result = builder.build_structured({})
        assert isinstance(result, dict)
        assert result['basic_info']['name'] == ''
        assert result['education'] == []
        assert result['work_experience'] == []
        assert result['skills'] == []

    def test_basic_info_fields(self, builder):
        form = {
            'name': '测试',
            'gender': '女',
            'age': 25,
            'phone': '13800000000',
            'email': 'test@test.com',
            'location': '上海',
            'political_status': '团员',
        }
        result = builder.build_structured(form)
        info = result['basic_info']
        assert info['name'] == '测试'
        assert info['gender'] == '女'
        assert info['age'] == 25
        assert info['phone'] == '13800000000'
        assert info['email'] == 'test@test.com'
        assert info['location'] == '上海'
        assert info['political_status'] == '团员'

    def test_single_education_fallback(self, builder):
        """没有 edu_count 时使用单条字段"""
        form = {
            'name': '测试',
            'school': '复旦大学',
            'major': '数学',
            'degree': '博士',
        }
        result = builder.build_structured(form)
        assert len(result['education']) == 1
        assert result['education'][0]['school'] == '复旦大学'
        assert result['education'][0]['degree'] == '博士'

    def test_single_work_fallback(self, builder):
        """没有 work_count 时使用单条字段"""
        form = {
            'name': '测试',
            'company': '阿里巴巴',
            'position': 'P7',
        }
        result = builder.build_structured(form)
        assert len(result['work_experience']) == 1
        assert result['work_experience'][0]['company'] == '阿里巴巴'
