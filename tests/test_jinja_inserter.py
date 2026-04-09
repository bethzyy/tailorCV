"""
Jinja2 标记插入器单元测试

测试 core/jinja_inserter.py — JinjaTagInserter 的所有公开和关键私有方法。
使用 mock Document 对象，不依赖真实 .docx 文件。

覆盖范围：
1. 基础信息插入（姓名、联系方式）
2. 静态章节处理（个人简介、自我评价）
3. 动态章节处理（工作经历、项目经历、教育背景）
4. 段落清理（从 XML 中彻底删除多余段落）
5. 边界条件（空文档、无结构、无条目等）
"""

import pytest
from unittest.mock import MagicMock, patch
from core.structure_detector import (
    StructureMap, SectionType, SectionInfo, EntryInfo
)
from core.jinja_inserter import JinjaTagInserter, TemplateMetadata


# ==================== 工具函数 ====================


def _make_run(text="", bold=None, italic=None, underline=None,
              font_name=None, font_size=None, font_color=None):
    """创建 mock Run 对象"""
    run = MagicMock()
    run.text = text
    run.font.name = font_name
    run.font.size = font_size
    run.font.bold = bold
    run.font.italic = italic
    run.font.underline = underline
    if font_color is not None:
        run.font.color.rgb = font_color
    else:
        run.font.color.rgb = None
    return run


def _make_paragraph(text="", runs=None, bold=False):
    """创建 mock Paragraph 对象，支持 clear/add_run/_element"""
    para = MagicMock()
    para.text = text
    if runs is None:
        para.runs = [_make_run(text, bold=bold)]
    else:
        para.runs = runs

    def clear_side_effect():
        para.runs = []
        para.text = ""
    para.clear.side_effect = clear_side_effect

    def add_run_side_effect(run_text):
        new_run = _make_run(run_text)
        para.runs.append(new_run)
        return new_run
    para.add_run.side_effect = add_run_side_effect
    para.paragraph_format.alignment = None
    para.paragraph_format.space_before = None
    para.paragraph_format.space_after = None
    para.paragraph_format.line_spacing = None
    para.style = None
    element_mock = MagicMock()
    para._element = element_mock
    return para


def _make_doc(paragraphs):
    """创建 mock Document 对象"""
    doc = MagicMock()
    doc.paragraphs = paragraphs
    return doc


def _make_structure(name_idx=None, contact_idx=None, sections=None, entries=None,
                    confidence=0.8):
    """创建 StructureMap 测试数据"""
    return StructureMap(
        name_paragraph_index=name_idx,
        contact_paragraph_index=contact_idx,
        sections=sections or [],
        entries=entries or [],
        confidence=confidence,
    )


@pytest.fixture
def inserter():
    """创建 JinjaTagInserter 实例"""
    return JinjaTagInserter()

# ==================== 1. Basic info insertion tests ====================


class TestInsertNameTag:
    """Name variable insertion"""

    @pytest.mark.unit
    def test_insert_name_with_default_value(self, inserter):
        """Name paragraph should be replaced with Jinja2 variable with default filter"""
        para = _make_paragraph("张三")
        doc = _make_doc([para])
        inserter._insert_name_tag(doc, 0)
        assert len(para.runs) == 1
        assert "{{ basic_info.name" in para.runs[0].text
        # default filter with original name
        assert "default(" in para.runs[0].text
        assert "张三" in para.runs[0].text

    @pytest.mark.unit
    def test_insert_name_preserves_font_format(self, inserter):
        """Name insertion should preserve original font format"""
        run = _make_run("张三", bold=True, font_name="微软雅黑", font_size=240000)
        para = _make_paragraph("张三", runs=[run])
        doc = _make_doc([para])
        inserter._insert_name_tag(doc, 0)
        new_run = para.runs[0]
        assert new_run.font.bold is True
        assert new_run.font.name == "微软雅黑"
        assert new_run.font.size == 240000

    @pytest.mark.unit
    def test_insert_name_preserves_font_color(self, inserter):
        """Name insertion should preserve font color"""
        color_mock = MagicMock()
        run = _make_run("张三", font_color=color_mock)
        para = _make_paragraph("张三", runs=[run])
        doc = _make_doc([para])
        inserter._insert_name_tag(doc, 0)
        assert para.runs[0].font.color.rgb == color_mock

    @pytest.mark.unit
    def test_insert_name_no_runs(self, inserter):
        """Paragraph without runs should get a new Jinja2 variable run"""
        para = _make_paragraph("")
        para.runs = []
        doc = _make_doc([para])
        inserter._insert_name_tag(doc, 0)
        assert len(para.runs) == 1
        assert "{{ basic_info.name }}" in para.runs[0].text

    @pytest.mark.unit
    def test_insert_name_clears_original_runs(self, inserter):
        """Name insertion should clear all original runs"""
        run1 = _make_run("张")
        run2 = _make_run("三")
        para = _make_paragraph("张三", runs=[run1, run2])
        doc = _make_doc([para])
        inserter._insert_name_tag(doc, 0)
        assert len(para.runs) == 1

class TestInsertContactTag:
    """Contact variable insertion"""

    @pytest.mark.unit
    def test_insert_contact_with_separator(self, inserter):
        """Detected separator should be preserved in output"""
        para = _make_paragraph("13800138000 | zs@test.com | 北京")
        doc = _make_doc([para])
        inserter._insert_contact_tag(doc, 0)
        assert len(para.runs) == 1
        text = para.runs[0].text
        assert "{{ basic_info.phone }}" in text
        assert "{{ basic_info.email }}" in text
        assert "{{ basic_info.location }}" in text
        assert "|" in text

    @pytest.mark.unit
    def test_insert_contact_without_separator(self, inserter):
        """No separator should use default format with labels"""
        para = _make_paragraph("13800138000 zs@test.com 北京")
        doc = _make_doc([para])
        inserter._insert_contact_tag(doc, 0)
        text = para.runs[0].text
        # Chinese labels should be present
        assert "{{ basic_info.phone }}" in text
        assert "{{ basic_info.email }}" in text
        assert "{{ basic_info.location }}" in text

    @pytest.mark.unit
    def test_insert_contact_preserves_format(self, inserter):
        """Contact insertion should preserve original font format"""
        run = _make_run("13800138000 | zs@test.com", font_name="宋体", font_size=180000)
        para = _make_paragraph("13800138000 | zs@test.com", runs=[run])
        doc = _make_doc([para])
        inserter._insert_contact_tag(doc, 0)
        new_run = para.runs[0]
        assert new_run.font.name == "宋体"
        assert new_run.font.size == 180000

    @pytest.mark.unit
    def test_insert_contact_clears_paragraph(self, inserter):
        """Contact insertion should clear original runs"""
        run1 = _make_run("13800138000")
        run2 = _make_run(" | ")
        run3 = _make_run("zs@test.com")
        para = _make_paragraph("13800138000 | zs@test.com", runs=[run1, run2, run3])
        doc = _make_doc([para])
        inserter._insert_contact_tag(doc, 0)
        assert len(para.runs) == 1


class TestDetectContactSeparator:
    """Contact separator detection"""

    @pytest.mark.unit
    def test_pipe_separator(self, inserter):
        """Half-width pipe separator"""
        assert inserter._detect_contact_separator("13800138000 | zs@test.com") == "|"

    @pytest.mark.unit
    def test_fullwidth_pipe_separator(self, inserter):
        """Full-width pipe separator"""
        assert inserter._detect_contact_separator("13800138000 ｜ zs@test.com") == "｜"

    @pytest.mark.unit
    def test_slash_separator(self, inserter):
        """Slash separator"""
        assert inserter._detect_contact_separator("13800138000 / zs@test.com") == "/"

    @pytest.mark.unit
    def test_dash_separator(self, inserter):
        """Dash separator"""
        assert inserter._detect_contact_separator("13800138000 - zs@test.com") == "-"

    @pytest.mark.unit
    def test_em_dash_separator(self, inserter):
        """Em-dash separator"""
        assert inserter._detect_contact_separator("13800138000 — zs@test.com") == "—"

    @pytest.mark.unit
    def test_no_separator(self, inserter):
        """No separator returns None"""
        assert inserter._detect_contact_separator("13800138000 zs@test.com") is None

    @pytest.mark.unit
    def test_dot_bullet_separator(self, inserter):
        """Middle-dot bullet separator"""
        assert inserter._detect_contact_separator("13800138000 · zs@test.com") == "·"

# ==================== 2. Static section tests ====================


class TestInsertStaticSection:
    """Static section processing (summary, self-evaluation)"""

    @pytest.mark.unit
    def test_summary_replaced_with_variable(self, inserter):
        """Summary section should be replaced with {{ summary }} variable"""
        para_title = _make_paragraph("个人简介")
        para_content = _make_paragraph("5年后端开发经验")
        paras = [para_title, para_content]
        section = SectionInfo(
            section_type=SectionType.SUMMARY,
            title="个人简介",
            paragraph_index=0,
            content_start=1,
            content_end=1,
            is_dynamic=False,
        )
        doc = _make_doc(paras)
        result = inserter._insert_static_section(doc, section)
        assert result == "summary"
        assert "{{ summary }}" in paras[1].runs[0].text

    @pytest.mark.unit
    def test_self_evaluation_replaced_with_variable(self, inserter):
        """Self-evaluation should be replaced with {{ self_evaluation }} variable"""
        para_title = _make_paragraph("自我评价")
        para_content = _make_paragraph("责任心强，善于沟通")
        paras = [para_title, para_content]
        section = SectionInfo(
            section_type=SectionType.SELF_EVALUATION,
            title="自我评价",
            paragraph_index=0,
            content_start=1,
            content_end=1,
            is_dynamic=False,
        )
        doc = _make_doc(paras)
        result = inserter._insert_static_section(doc, section)
        assert result == "self_evaluation"
        assert "{{ self_evaluation }}" in paras[1].runs[0].text

    @pytest.mark.unit
    def test_static_section_extra_paragraphs_cleared(self, inserter):
        """Extra content paragraphs in static section should be cleared"""
        para_title = _make_paragraph("个人简介")
        para_c1 = _make_paragraph("5年后端开发经验")
        para_c2 = _make_paragraph("擅长 Python 和 Go")
        paras = [para_title, para_c1, para_c2]
        section = SectionInfo(
            section_type=SectionType.SUMMARY,
            title="个人简介",
            paragraph_index=0,
            content_start=1,
            content_end=2,
            is_dynamic=False,
        )
        doc = _make_doc(paras)
        inserter._insert_static_section(doc, section)
        assert "{{ summary }}" in paras[1].runs[0].text
        assert len(paras[2].runs) == 0

    @pytest.mark.unit
    def test_static_section_empty_content_returns_none(self, inserter):
        """Empty content paragraphs should return None"""
        para_title = _make_paragraph("个人简介")
        para_empty = _make_paragraph("")
        paras = [para_title, para_empty]
        section = SectionInfo(
            section_type=SectionType.SUMMARY,
            title="个人简介",
            paragraph_index=0,
            content_start=1,
            content_end=1,
            is_dynamic=False,
        )
        doc = _make_doc(paras)
        result = inserter._insert_static_section(doc, section)
        assert result is None

    @pytest.mark.unit
    def test_static_section_unknown_type_returns_none(self, inserter):
        """Unknown section type should return None"""
        section = SectionInfo(
            section_type=SectionType.UNKNOWN,
            title="unknown",
            paragraph_index=0,
            content_start=1,
            content_end=1,
            is_dynamic=False,
        )
        result = inserter._insert_static_section([], section)
        assert result is None

    @pytest.mark.unit
    def test_static_section_skips_empty_paragraphs(self, inserter):
        """Should skip empty paragraphs, insert variable in first non-empty one"""
        para_title = _make_paragraph("个人简介")
        para_empty = _make_paragraph("")
        para_content = _make_paragraph("实际内容")
        paras = [para_title, para_empty, para_content]
        section = SectionInfo(
            section_type=SectionType.SUMMARY,
            title="个人简介",
            paragraph_index=0,
            content_start=1,
            content_end=2,
            is_dynamic=False,
        )
        doc = _make_doc(paras)
        result = inserter._insert_static_section(doc, section)
        assert result == "summary"
        assert "{{ summary }}" in paras[2].runs[0].text

# ==================== 3. Dynamic section tests ====================


class TestInsertDynamicSection:
    """Dynamic section processing (work, project, education)"""

    @pytest.mark.unit
    def test_work_entry_simple_variables(self, inserter):
        """Work entry should use indexed variable replacement"""
        para = _make_paragraph("2020-2023 字节跳动  高级工程师")
        content_para = _make_paragraph("负责后端服务开发")
        paras = [para, content_para]
        section = SectionInfo(
            section_type=SectionType.WORK,
            title="工作经历",
            paragraph_index=0,
            content_start=1,
            content_end=1,
            is_dynamic=True,
        )
        entry = EntryInfo(
            entry_type=SectionType.WORK,
            paragraph_index=0,
            time="2020-2023",
            organization="字节跳动",
            role="高级工程师",
            content_paragraphs=[1],
        )
        doc = _make_doc(paras)
        result = inserter._insert_dynamic_section(doc, section, [entry])
        assert "work_experience" in result
        header_text = paras[0].runs[0].text
        assert "{{ work_experience_0_time }}" in header_text
        assert "{{ work_experience_0_company }}" in header_text
        assert "{{ work_experience_0_position }}" in header_text

    @pytest.mark.unit
    def test_project_entry_with_time(self, inserter):
        """Project entry with time should generate numbered+time+name+role variables"""
        para = _make_paragraph("2021 API Gateway  开发者")
        content_para = _make_paragraph("微服务架构")
        paras = [para, content_para]
        section = SectionInfo(
            section_type=SectionType.PROJECT,
            title="项目经历",
            paragraph_index=0,
            content_start=1,
            content_end=1,
            is_dynamic=True,
        )
        entry = EntryInfo(
            entry_type=SectionType.PROJECT,
            paragraph_index=0,
            time="2021",
            organization="API Gateway",
            role="开发者",
            content_paragraphs=[1],
        )
        doc = _make_doc(paras)
        inserter._insert_dynamic_section(doc, section, [entry])
        header_text = paras[0].runs[0].text
        assert "{{ projects_0_time }}" in header_text
        assert "{{ projects_0_name }}" in header_text
        assert "{{ projects_0_role }}" in header_text
        assert "1." in header_text

    @pytest.mark.unit
    def test_project_entry_without_time(self, inserter):
        """Project entry without time should use detected separator"""
        para = _make_paragraph("API Gateway —— 开发者")
        content_para = _make_paragraph("微服务架构")
        paras = [para, content_para]
        section = SectionInfo(
            section_type=SectionType.PROJECT,
            title="项目经历",
            paragraph_index=0,
            content_start=1,
            content_end=1,
            is_dynamic=True,
        )
        entry = EntryInfo(
            entry_type=SectionType.PROJECT,
            paragraph_index=0,
            time="",
            organization="API Gateway",
            role="开发者",
            content_paragraphs=[1],
        )
        doc = _make_doc(paras)
        inserter._insert_dynamic_section(doc, section, [entry])
        header_text = paras[0].runs[0].text
        assert "{{ projects_0_name }}" in header_text
        assert "{{ projects_0_role }}" in header_text
        assert "——" in header_text

    @pytest.mark.unit
    def test_project_entry_default_separator(self, inserter):
        """Project entry without separator should use default | separator"""
        para = _make_paragraph("API Gateway 开发者")
        content_para = _make_paragraph("微服务架构")
        paras = [para, content_para]
        section = SectionInfo(
            section_type=SectionType.PROJECT,
            title="项目经历",
            paragraph_index=0,
            content_start=1,
            content_end=1,
            is_dynamic=True,
        )
        entry = EntryInfo(
            entry_type=SectionType.PROJECT,
            paragraph_index=0,
            time="",
            organization="API Gateway",
            role="开发者",
            content_paragraphs=[1],
        )
        doc = _make_doc(paras)
        inserter._insert_dynamic_section(doc, section, [entry])
        header_text = paras[0].runs[0].text
        assert "|" in header_text
    @pytest.mark.unit
    def test_education_entry_variables(self, inserter):
        """Education entry should generate time+school+major variables"""
        para = _make_paragraph("2016-2020 清华大学 计算机科学")
        content_para = _make_paragraph("GPA 3.8")
        paras = [para, content_para]
        section = SectionInfo(
            section_type=SectionType.EDUCATION,
            title="教育背景",
            paragraph_index=0,
            content_start=1,
            content_end=1,
            is_dynamic=True,
        )
        entry = EntryInfo(
            entry_type=SectionType.EDUCATION,
            paragraph_index=0,
            time="2016-2020",
            organization="清华大学",
            role="计算机科学",
            content_paragraphs=[1],
        )
        doc = _make_doc(paras)
        inserter._insert_dynamic_section(doc, section, [entry])
        header_text = paras[0].runs[0].text
        assert "{{ education_0_time }}" in header_text
        assert "{{ education_0_school }}" in header_text
        assert "{{ education_0_major }}" in header_text

    @pytest.mark.unit
    def test_entry_content_replaced_with_tailored(self, inserter):
        """Entry content paragraph should be replaced with tailored variable"""
        para = _make_paragraph("2020-2023 字节跳动  工程师")
        content_para = _make_paragraph("负责后端开发")
        paras = [para, content_para]
        section = SectionInfo(
            section_type=SectionType.WORK,
            title="工作经历",
            paragraph_index=0,
            content_start=1,
            content_end=1,
            is_dynamic=True,
        )
        entry = EntryInfo(
            entry_type=SectionType.WORK,
            paragraph_index=0,
            content_paragraphs=[1],
        )
        doc = _make_doc(paras)
        inserter._insert_dynamic_section(doc, section, [entry])
        assert "{{ work_experience_0_tailored }}" in paras[1].runs[0].text

    @pytest.mark.unit
    def test_multiple_entries_indexed_correctly(self, inserter):
        """Multiple entries should use correct indices"""
        para0 = _make_paragraph("2020-2023 字节跳动  工程师")
        content0 = _make_paragraph("后端开发")
        para1 = _make_paragraph("2018-2020 腾讯  工程师")
        content1 = _make_paragraph("前端开发")
        paras = [para0, content0, para1, content1]
        section = SectionInfo(
            section_type=SectionType.WORK,
            title="工作经历",
            paragraph_index=0,
            content_start=1,
            content_end=3,
            is_dynamic=True,
        )
        entry0 = EntryInfo(entry_type=SectionType.WORK, paragraph_index=0, content_paragraphs=[1])
        entry1 = EntryInfo(entry_type=SectionType.WORK, paragraph_index=2, content_paragraphs=[3])
        doc = _make_doc(paras)
        inserter._insert_dynamic_section(doc, section, [entry0, entry1])
        assert "{{ work_experience_0_company }}" in paras[0].runs[0].text
        assert "{{ work_experience_1_company }}" in paras[2].runs[0].text
        assert "{{ work_experience_0_tailored }}" in paras[1].runs[0].text
        assert "{{ work_experience_1_tailored }}" in paras[3].runs[0].text

    @pytest.mark.unit
    def test_no_entries_triggers_simple_template(self, inserter):
        """No entries should generate simple template entry"""
        para = _make_paragraph("")
        content_para = _make_paragraph("一些内容")
        paras = [para, content_para]
        section = SectionInfo(
            section_type=SectionType.WORK,
            title="工作经历",
            paragraph_index=0,
            content_start=0,
            content_end=1,
            is_dynamic=True,
        )
        doc = _make_doc(paras)
        result = inserter._insert_dynamic_section(doc, section, [])
        assert "work_experience" in result
        text = paras[0].runs[0].text
        has_time = "{{ work_experience_0_time }}" in text
        has_company = "{{ work_experience_0_company }}" in text
        assert has_time or has_company

    @pytest.mark.unit
    def test_unknown_dynamic_type_returns_empty(self, inserter):
        """Unknown dynamic section type should return empty variable list"""
        section = SectionInfo(
            section_type=SectionType.UNKNOWN,
            title="unknown",
            paragraph_index=0,
            content_start=1,
            content_end=1,
            is_dynamic=True,
        )
        result = inserter._insert_dynamic_section([], section, [])
        assert result == []

    @pytest.mark.unit
    def test_skills_entry_simple_variable(self, inserter):
        """Skills entry should use simple variable replacement"""
        para = _make_paragraph("Python")
        paras = [para]
        section = SectionInfo(
            section_type=SectionType.SKILLS,
            title="专业技能",
            paragraph_index=0,
            content_start=1,
            content_end=1,
            is_dynamic=True,
        )
        entry = EntryInfo(entry_type=SectionType.SKILLS, paragraph_index=0)
        doc = _make_doc(paras)
        inserter._insert_dynamic_section(doc, section, [entry])
        assert "{{ skills_0_name }}" in paras[0].runs[0].text

# ==================== 4. Paragraph cleanup tests ====================


class TestParagraphCleanup:
    """Extra paragraphs should be removed from XML (not just cleared)"""

    @pytest.mark.unit
    def test_content_paragraphs_removed_from_xml(self, inserter):
        """Extra content_paragraphs should be removed from XML"""
        para = _make_paragraph("2020-2023 字节跳动  工程师")
        content0 = _make_paragraph("后端开发")
        content1 = _make_paragraph("微服务架构")
        content2 = _make_paragraph("团队管理")
        paras = [para, content0, content1, content2]

        parent_mock = MagicMock()
        content1._element.getparent.return_value = parent_mock
        content2._element.getparent.return_value = parent_mock

        section = SectionInfo(
            section_type=SectionType.WORK,
            title="工作经历",
            paragraph_index=0,
            content_start=1,
            content_end=3,
            is_dynamic=True,
        )
        entry = EntryInfo(
            entry_type=SectionType.WORK,
            paragraph_index=0,
            content_paragraphs=[1, 2, 3],
        )
        doc = _make_doc(paras)
        inserter._insert_dynamic_section(doc, section, [entry])
        assert "{{ work_experience_0_tailored }}" in paras[1].runs[0].text
        parent_mock.remove.assert_any_call(content1._element)
        parent_mock.remove.assert_any_call(content2._element)

    @pytest.mark.unit
    def test_fallback_content_scan_removes_extra_paras(self, inserter):
        """Fallback scan when content_paragraphs is empty should remove extras"""
        para = _make_paragraph("2020-2023 字节跳动  工程师")
        content0 = _make_paragraph("后端开发")
        content1 = _make_paragraph("微服务架构")
        content2 = _make_paragraph("")
        paras = [para, content0, content1, content2]

        parent_mock = MagicMock()
        content1._element.getparent.return_value = parent_mock

        section = SectionInfo(
            section_type=SectionType.WORK,
            title="工作经历",
            paragraph_index=0,
            content_start=1,
            content_end=3,
            is_dynamic=True,
        )
        entry = EntryInfo(entry_type=SectionType.WORK, paragraph_index=0, content_paragraphs=[])
        doc = _make_doc(paras)
        inserter._insert_dynamic_section(doc, section, [entry])
        assert "{{ work_experience_0_tailored }}" in paras[1].runs[0].text
        parent_mock.remove.assert_called_with(content1._element)

    @pytest.mark.unit
    def test_fallback_stops_at_numbered_list(self, inserter):
        """Fallback scan should stop at numbered list items"""
        para = _make_paragraph("2020-2023 字节跳动  工程师")
        content0 = _make_paragraph("后端开发")
        content1 = _make_paragraph("微服务架构")
        content2 = _make_paragraph("2. 新条目")
        paras = [para, content0, content1, content2]

        parent_mock = MagicMock()
        content1._element.getparent.return_value = parent_mock
        content2._element.getparent.return_value = parent_mock

        section = SectionInfo(
            section_type=SectionType.WORK,
            title="工作经历",
            paragraph_index=0,
            content_start=1,
            content_end=3,
            is_dynamic=True,
        )
        entry = EntryInfo(entry_type=SectionType.WORK, paragraph_index=0, content_paragraphs=[])
        doc = _make_doc(paras)
        inserter._insert_dynamic_section(doc, section, [entry])
        # content1 removed, content2 (numbered list) not removed
        parent_mock.remove.assert_called_once_with(content1._element)

    @pytest.mark.unit
    def test_no_parent_does_not_crash(self, inserter):
        """Paragraph without parent should not crash"""
        para = _make_paragraph("2020-2023 字节跳动  工程师")
        content0 = _make_paragraph("后端开发")
        content1 = _make_paragraph("微服务架构")
        paras = [para, content0, content1]

        content1._element.getparent.return_value = None

        section = SectionInfo(
            section_type=SectionType.WORK,
            title="工作经历",
            paragraph_index=0,
            content_start=1,
            content_end=2,
            is_dynamic=True,
        )
        entry = EntryInfo(
            entry_type=SectionType.WORK,
            paragraph_index=0,
            content_paragraphs=[1, 2],
        )
        doc = _make_doc(paras)
        # Should not raise exception
        inserter._insert_dynamic_section(doc, section, [entry])

# ==================== 5. Edge case tests ====================


class TestEdgeCases:
    """Edge cases and boundary conditions"""

    @pytest.mark.unit
    @patch("core.jinja_inserter.Document")
    def test_insert_tags_empty_structure(self, MockDocument, inserter):
        """Empty structure should return metadata without modifying document"""
        mock_doc = MagicMock()
        MockDocument.return_value = mock_doc

        doc = MagicMock()
        structure = _make_structure()
        tagged_doc, metadata = inserter.insert_tags(doc, structure, "test_empty")

        assert isinstance(metadata, TemplateMetadata)
        assert metadata.template_id == "test_empty"
        assert metadata.sections_detected == 0
        assert metadata.entries_detected == 0
        assert metadata.has_dynamic_content is False
        assert metadata.variables == []

    @pytest.mark.unit
    @patch("core.jinja_inserter.Document")
    def test_insert_tags_name_only(self, MockDocument, inserter):
        """Document with only name should generate name variable"""
        mock_doc = MagicMock()
        MockDocument.return_value = mock_doc

        para = _make_paragraph("张三")
        mock_doc.paragraphs = [para]

        doc = MagicMock()
        structure = _make_structure(name_idx=0)
        tagged_doc, metadata = inserter.insert_tags(doc, structure, "test_name")

        assert "basic_info.name" in metadata.variables
        assert metadata.has_dynamic_content is False

    @pytest.mark.unit
    @patch("core.jinja_inserter.Document")
    def test_insert_tags_full_structure(self, MockDocument, inserter):
        """Full structure should generate all variables"""
        mock_doc = MagicMock()
        MockDocument.return_value = mock_doc

        paras = [
            _make_paragraph("张三"),
            _make_paragraph("13800138000 | zs@test.com | 北京"),
            _make_paragraph("个人简介"),
            _make_paragraph("5年经验"),
            _make_paragraph("工作经历"),
            _make_paragraph("2020-2023 字节跳动  工程师"),
            _make_paragraph("后端开发"),
        ]
        mock_doc.paragraphs = paras

        doc = MagicMock()
        section_summary = SectionInfo(
            section_type=SectionType.SUMMARY,
            title="个人简介",
            paragraph_index=2,
            content_start=3,
            content_end=3,
            is_dynamic=False,
        )
        section_work = SectionInfo(
            section_type=SectionType.WORK,
            title="工作经历",
            paragraph_index=4,
            content_start=5,
            content_end=6,
            is_dynamic=True,
        )
        entry = EntryInfo(
            entry_type=SectionType.WORK,
            paragraph_index=5,
            content_paragraphs=[6],
        )
        structure = _make_structure(
            name_idx=0,
            contact_idx=1,
            sections=[section_summary, section_work],
            entries=[entry],
            confidence=0.9,
        )
        tagged_doc, metadata = inserter.insert_tags(doc, structure, "test_full")

        assert "basic_info.name" in metadata.variables
        assert "basic_info.phone" in metadata.variables
        assert "summary" in metadata.variables
        assert "work_experience" in metadata.variables
        assert metadata.has_dynamic_content is True
        assert metadata.sections_detected == 2
        assert metadata.entries_detected == 1
        assert metadata.structure_confidence == 0.9

    @pytest.mark.unit
    @patch("core.jinja_inserter.Document")
    def test_insert_tags_saves_and_reloads(self, MockDocument, inserter):
        """insert_tags should perform deep copy via save/reload"""
        mock_doc = MagicMock()
        MockDocument.return_value = mock_doc

        doc = MagicMock()
        structure = _make_structure()
        inserter.insert_tags(doc, structure, "test_copy")

        doc.save.assert_called_once()
        MockDocument.assert_called_once()
    @pytest.mark.unit
    def test_replace_paragraph_text_preserves_paragraph_format(self, inserter):
        """_replace_paragraph_text should preserve paragraph format"""
        para = _make_paragraph("原始文本")
        para.paragraph_format.alignment = 1
        para.paragraph_format.space_before = 200
        para.paragraph_format.space_after = 100
        para.paragraph_format.line_spacing = 1.5

        inserter._replace_paragraph_text(para, "新文本")

        assert "{{" not in para.runs[0].text
        assert para.runs[0].text == "新文本"
        assert para.paragraph_format.alignment == 1
        assert para.paragraph_format.space_before == 200
        assert para.paragraph_format.space_after == 100
        assert para.paragraph_format.line_spacing == 1.5

    @pytest.mark.unit
    def test_replace_paragraph_text_no_runs_uses_style(self, inserter):
        """No runs should fall back to paragraph style font"""
        para = _make_paragraph("")
        para.runs = []
        para.style = MagicMock()
        para.style.font.name = "仿宋"
        para.style.font.size = 240000
        para.style.font.bold = True

        inserter._replace_paragraph_text(para, "{{ test }}")

        new_run = para.runs[0]
        assert new_run.font.name == "仿宋"
        assert new_run.font.size == 240000
        assert new_run.font.bold is True

    @pytest.mark.unit
    def test_replace_paragraph_text_preserves_run_formats(self, inserter):
        """_replace_paragraph_text should preserve run-level font formats"""
        run = _make_run("原始", bold=True, italic=True, underline=True)
        para = _make_paragraph("原始", runs=[run])

        inserter._replace_paragraph_text(para, "替换后")

        new_run = para.runs[0]
        assert new_run.font.bold is True
        assert new_run.font.italic is True
        assert new_run.font.underline is True

    @pytest.mark.unit
    def test_stats_tracking(self, inserter):
        """Stats should accumulate correctly"""
        inserter.insertion_stats = {
            "static_variables": 0,
            "dynamic_loops": 0,
            "conditional_blocks": 0,
            "failed": 0,
        }
        assert inserter.get_stats()["static_variables"] == 0
        inserter.insertion_stats["static_variables"] += 2
        inserter.insertion_stats["dynamic_loops"] += 1
        stats = inserter.get_stats()
        assert stats["static_variables"] == 2
        assert stats["dynamic_loops"] == 1

    @pytest.mark.unit
    def test_metadata_defaults(self):
        """TemplateMetadata default values"""
        meta = TemplateMetadata(
            template_id="test",
            original_filename="test.docx",
            structure_confidence=0.5,
        )
        assert meta.variables == []
        assert meta.has_dynamic_content is False
        assert meta.sections_detected == 0
        assert meta.entries_detected == 0

    @pytest.mark.unit
    @patch("core.jinja_inserter.Document")
    def test_insert_tags_variables_deduplicated(self, MockDocument, inserter):
        """Duplicate variables should be deduplicated"""
        mock_doc = MagicMock()
        MockDocument.return_value = mock_doc

        paras = [
            _make_paragraph("张三"),
            _make_paragraph("13800138000 | zs@test.com"),
        ]
        mock_doc.paragraphs = paras

        doc = MagicMock()
        structure = _make_structure(name_idx=0, contact_idx=1)
        tagged_doc, metadata = inserter.insert_tags(doc, structure, "test_dedup")

        name_count = metadata.variables.count("basic_info.name")
        assert name_count == 1

# ==================== 6. Simple template entry tests ====================


class TestAddSimpleTemplateEntry:
    """Simple template entry generation (fallback when no entries detected)"""

    @pytest.mark.unit
    def test_work_simple_template(self, inserter):
        """Work simple template should include time/company/position"""
        para = _make_paragraph("")
        content_para = _make_paragraph("内容")
        paras = [para, content_para]
        section = SectionInfo(
            section_type=SectionType.WORK,
            title="工作经历",
            paragraph_index=0,
            content_start=0,
            content_end=1,
            is_dynamic=True,
        )
        doc = _make_doc(paras)
        inserter._add_simple_template_entry(doc, section, "exp", "work_experience")
        text = paras[0].runs[0].text
        assert "{{ work_experience_0_time }}" in text
        assert "{{ work_experience_0_company }}" in text
        assert "{{ work_experience_0_position }}" in text

    @pytest.mark.unit
    def test_project_simple_template(self, inserter):
        """Project simple template should include time/name/role"""
        para = _make_paragraph("")
        content_para = _make_paragraph("内容")
        paras = [para, content_para]
        section = SectionInfo(
            section_type=SectionType.PROJECT,
            title="项目经历",
            paragraph_index=0,
            content_start=0,
            content_end=1,
            is_dynamic=True,
        )
        doc = _make_doc(paras)
        inserter._add_simple_template_entry(doc, section, "proj", "projects")
        text = paras[0].runs[0].text
        assert "{{ projects_0_time }}" in text
        assert "{{ projects_0_name }}" in text
        assert "{{ projects_0_role }}" in text

    @pytest.mark.unit
    def test_education_simple_template(self, inserter):
        """Education simple template should include time/school/major"""
        para = _make_paragraph("")
        content_para = _make_paragraph("内容")
        paras = [para, content_para]
        section = SectionInfo(
            section_type=SectionType.EDUCATION,
            title="教育背景",
            paragraph_index=0,
            content_start=0,
            content_end=1,
            is_dynamic=True,
        )
        doc = _make_doc(paras)
        inserter._add_simple_template_entry(doc, section, "edu", "education")
        text = paras[0].runs[0].text
        assert "{{ education_0_time }}" in text
        assert "{{ education_0_school }}" in text
        assert "{{ education_0_major }}" in text

    @pytest.mark.unit
    def test_skills_simple_template(self, inserter):
        """Skills simple template should include name"""
        para = _make_paragraph("")
        paras = [para]
        section = SectionInfo(
            section_type=SectionType.SKILLS,
            title="专业技能",
            paragraph_index=0,
            content_start=0,
            content_end=0,
            is_dynamic=True,
        )
        doc = _make_doc(paras)
        inserter._add_simple_template_entry(doc, section, "skill", "skills")
        text = paras[0].runs[0].text
        assert "{{ skills_0_name }}" in text

    @pytest.mark.unit
    def test_simple_template_out_of_range(self, inserter):
        """insert_idx beyond document range should not crash"""
        paras = [_make_paragraph("唯一段落")]
        section = SectionInfo(
            section_type=SectionType.WORK,
            title="工作经历",
            paragraph_index=0,
            content_start=5,
            content_end=5,
            is_dynamic=True,
        )
        doc = _make_doc(paras)
        inserter._add_simple_template_entry(doc, section, "exp", "work_experience")

# ==================== 7. Configuration validation ====================


class TestConfiguration:
    """Class-level configuration validation"""

    @pytest.mark.unit
    def test_basic_info_mapping_keys(self, inserter):
        """BASIC_INFO mapping should contain common fields"""
        mapping = inserter.VARIABLE_MAPPING[SectionType.BASIC_INFO]
        assert "name" in mapping
        assert "phone" in mapping
        assert "email" in mapping
        assert "location" in mapping

    @pytest.mark.unit
    def test_loop_variables_sections(self, inserter):
        """LOOP_VARIABLES should cover all dynamic section types"""
        for section_type in [SectionType.EDUCATION, SectionType.WORK,
                             SectionType.PROJECT, SectionType.SKILLS,
                             SectionType.AWARDS, SectionType.CERTIFICATES]:
            assert section_type in inserter.LOOP_VARIABLES

    @pytest.mark.unit
    def test_loop_variable_fields(self, inserter):
        """Each loop config should have loop_var, list_var, fields"""
        for section_type, config in inserter.LOOP_VARIABLES.items():
            assert "loop_var" in config
            assert "list_var" in config
            assert "fields" in config
            assert isinstance(config["fields"], list)
            assert len(config["fields"]) > 0