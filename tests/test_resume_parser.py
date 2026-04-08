"""
简历解析器单元测试

测试 core/resume_parser.py — TXT/MD 解析、信息提取、置信度计算、格式支持。
"""

import pytest
from core.resume_parser import ResumeParser, ParsedResume, StyleMetadata


@pytest.fixture
def parser():
    return ResumeParser()


# ==================== 基础解析 ====================

class TestParseTxt:
    """TXT 文件解析"""

    def test_parse_txt_content(self, parser):
        """解析纯文本简历"""
        content = "张三\n13800138000\nzhangsan@example.com\n\n教育背景\n清华大学 计算机科学 本科\n\n专业技能\nPython、Java、Go\n\n工作经历\n2020-2023 字节跳动 后端工程师\n负责API开发和微服务架构设计\n\n项目经历\n2021 API网关系统\n负责核心模块开发\n\n自我评价\n5年后端开发经验，擅长高并发系统设计".encode('utf-8')
        result = parser.parse(file_content=content, filename='resume.txt')
        assert result is not None
        assert result.source_format == 'text'

    def test_parse_md_content(self, parser):
        """解析 Markdown 简历"""
        content = "# 张三简历\n\n## 联系方式\n13800138000\n\n## 工作经历\n\n- 字节跳动 后端工程师 2020-2023\n\n## 专业技能\nPython、Java".encode('utf-8')
        result = parser.parse(file_content=content, filename='resume.md')
        assert result is not None

    def test_parse_text_too_short_raises(self, parser):
        """内容过少时抛 ValueError"""
        content = "short".encode('utf-8')
        with pytest.raises(ValueError, match="内容过少"):
            parser.parse(file_content=content, filename='resume.txt')


class TestParseUnsupportedFormat:
    """不支持的格式"""

    def test_unsupported_extension(self, parser):
        content = b'some content'
        with pytest.raises(ValueError, match="不支持的文件格式"):
            parser.parse(file_content=content, filename='resume.exe')

    def test_no_args_raises(self, parser):
        """不提供参数时抛 ValueError"""
        with pytest.raises(ValueError, match="必须提供"):
            parser.parse()


# ==================== 信息提取 ====================

class TestExtractBasicInfo:
    """_extract_basic_info"""

    def test_extract_name(self, parser):
        text = "张三\n13800138000\nzhangsan@example.com"
        info = parser._extract_basic_info(text)
        assert info['name'] == '张三'

    def test_extract_phone(self, parser):
        text = "张三\n13800138000\nzhangsan@example.com"
        info = parser._extract_basic_info(text)
        assert info['phone'] == '13800138000'

    def test_extract_email(self, parser):
        text = "张三\n13800138000\nzhangsan@test.com"
        info = parser._extract_basic_info(text)
        assert info['email'] == 'zhangsan@test.com'

    def test_extract_age(self, parser):
        text = "张三 25岁\n13800138000"
        info = parser._extract_basic_info(text)
        assert info['age'] == 25

    def test_extract_gender(self, parser):
        text = "张三 男\n13800138000"
        info = parser._extract_basic_info(text)
        assert info['gender'] == '男'

    def test_extract_location(self, parser):
        text = "张三\n现居：北京市海淀区\n13800138000"
        info = parser._extract_basic_info(text)
        assert info['location'] == '北京市海淀区'

    def test_partial_info(self, parser):
        """部分信息缺失时返回可用部分"""
        text = "just some random text without contact info"
        info = parser._extract_basic_info(text)
        assert isinstance(info, dict)
        # 没有姓名、电话、邮箱
        assert 'name' not in info or info.get('name') is None


class TestExtractSkills:
    """_extract_skills"""

    def test_extract_skills_with_chinese_comma(self, parser):
        text = "专业技能\nPython、Java、Go、Docker"
        skills = parser._extract_skills(text)
        assert 'Python' in skills
        assert 'Java' in skills
        assert 'Go' in skills

    def test_extract_skills_no_section(self, parser):
        """没有技能章节时返回空列表"""
        text = "张三\n13800138000\n教育背景\n清华大学"
        skills = parser._extract_skills(text)
        assert skills == []

    def test_extract_skills_dedup(self, parser):
        """技能去重"""
        text = "专业技能\nPython、Java、Python"
        skills = parser._extract_skills(text)
        assert len(skills) == len(set(skills))


class TestExtractAwards:
    """_extract_awards"""

    def test_extract_awards(self, parser):
        text = "奖项荣誉\nACM区域赛金牌\n全国数学竞赛一等奖\n工作经历"
        awards = parser._extract_awards(text)
        assert len(awards) >= 1
        assert any('ACM' in a for a in awards)

    def test_extract_awards_no_section(self, parser):
        text = "张三\n13800138000\n教育背景\n清华大学"
        awards = parser._extract_awards(text)
        assert awards == []


class TestExtractSelfEvaluation:
    """_extract_self_evaluation"""

    def test_extract_self_evaluation(self, parser):
        text = "自我评价\n5年后端开发经验\n擅长高并发系统设计\n工作经历"
        evaluation = parser._extract_self_evaluation(text)
        assert '5年' in evaluation

    def test_extract_self_evaluation_no_section(self, parser):
        text = "张三\n13800138000"
        evaluation = parser._extract_self_evaluation(text)
        assert evaluation == ''


# ==================== 置信度 ====================

class TestCalculateConfidence:
    """_calculate_confidence"""

    def test_empty_resume_low_confidence(self, parser):
        """空简历置信度为 0"""
        parsed = ParsedResume(raw_text='')
        confidence = parser._calculate_confidence(parsed)
        assert confidence == 0.0

    def test_full_resume_high_confidence(self, parser):
        """完整简历高置信度"""
        parsed = ParsedResume(raw_text='full resume')
        parsed.basic_info = {'name': '张三', 'phone': '13800138000', 'age': 25}
        parsed.education = [{'school': '清华大学', 'major': 'CS', 'degree': '本科'}]
        parsed.work_experience = [{'company': '字节跳动', 'position': 'SWE', 'content': '开发'}]
        parsed.projects = [{'name': 'API网关', 'content': '开发'}]
        parsed.skills = ['Python', 'Go', 'Docker']
        confidence = parser._calculate_confidence(parsed)
        assert 0.5 <= confidence <= 1.0

    def test_fresh_grad_weighting(self, parser):
        """应届生：教育背景和项目权重更高"""
        parsed = ParsedResume(raw_text='fresh grad')
        parsed.basic_info = {'name': '李四', 'phone': '13800138000'}
        parsed.education = [{'school': '清华大学', 'major': 'CS', 'degree': '本科'}]
        parsed.projects = [{'name': '毕业设计', 'content': 'ML模型'}]
        parsed.skills = ['Python']
        confidence = parser._calculate_confidence(parsed)
        # 应届生无工作经历但教育+项目加分
        assert confidence > 0.3

    def test_confidence_capped_at_1(self, parser):
        """置信度不超过 1.0"""
        parsed = ParsedResume(raw_text='super resume')
        parsed.basic_info = {'name': 'A', 'phone': '1', 'age': 30, 'gender': '男'}
        parsed.education = [{'school': 'A'}, {'school': 'B'}, {'school': 'C'}]
        parsed.work_experience = [{'company': 'A'}, {'company': 'B'}, {'company': 'C'}]
        parsed.projects = [{'name': 'A'}, {'name': 'B'}]
        parsed.skills = ['A', 'B', 'C', 'D', 'E']
        parsed.awards = ['A', 'B']
        parsed.certificates = ['A', 'B']
        confidence = parser._calculate_confidence(parsed)
        assert confidence <= 1.0


# ==================== 统计 ====================

class TestParseStats:
    """解析统计"""

    def test_get_stats(self, parser):
        stats = parser.get_stats()
        assert isinstance(stats, dict)
        assert 'pdfplumber' in stats
        assert 'pypdf2' in stats
        assert 'docx' in stats
        assert 'text' in stats
        assert 'failed' in stats


# ==================== StyleMetadata ====================

class TestStyleMetadata:
    """样式元数据"""

    def test_default_values(self):
        sm = StyleMetadata()
        assert sm.primary_font == "Microsoft YaHei"
        assert sm.body_font_size == 10.5

    def test_name_font_size(self):
        sm = StyleMetadata()
        assert sm.get_name_font_size() == round(10.5 * 1.7, 1)

    def test_section_title_font_size(self):
        sm = StyleMetadata()
        assert sm.get_section_title_font_size() == round(10.5 * 1.14, 1)

    def test_custom_body_size(self):
        sm = StyleMetadata(body_font_size=12.0)
        assert sm.get_name_font_size() == round(12.0 * 1.7, 1)
