"""
简历结构检测器单元测试

测试 core/structure_detector.py — 姓名检测、联系方式检测、章节识别。
使用 mock Document 对象，不依赖真实 .docx 文件。
"""

import pytest
from unittest.mock import MagicMock
from core.structure_detector import (
    StructureDetector, StructureMap, SectionType, SectionInfo, EntryInfo
)


@pytest.fixture
def detector():
    return StructureDetector()


def _make_paragraph(text, bold=False):
    """创建 mock Paragraph 对象"""
    para = MagicMock()
    para.text = text
    runs = [MagicMock()]
    runs[0].bold = bold
    para.runs = runs
    return para


def _make_doc(paragraphs):
    """创建 mock Document 对象"""
    doc = MagicMock()
    doc.paragraphs = paragraphs
    return doc


class TestDetectName:
    """姓名检测"""

    def test_chinese_name_detected(self, detector):
        """纯中文短文本应被识别为姓名"""
        paras = [
            _make_paragraph('张三'),
            _make_paragraph('电话: 13800138000'),
        ]
        doc = _make_doc(paras)
        structure = detector.detect_structure(doc)
        assert structure.name_paragraph_index == 0

    def test_name_not_section_title(self, detector):
        """章节关键词不应被识别为姓名"""
        paras = [
            _make_paragraph('教育背景'),
            _make_paragraph('计算机科学与技术专业'),  # 9个字符，超过阈值但不含关键词 → 会被检测为姓名
        ]
        doc = _make_doc(paras)
        structure = detector.detect_structure(doc)
        # "教育背景" 是章节标题，第二行被检测为姓名（合法行为）
        # 关键断言：第一行（index 0）不是姓名
        assert structure.name_paragraph_index != 0

    def test_name_too_long(self, detector):
        """过长的文本不应被识别为姓名"""
        paras = [
            _make_paragraph('这是一个很长的自我介绍文本超过十个字符'),
            _make_paragraph('13800138000'),
        ]
        doc = _make_doc(paras)
        structure = detector.detect_structure(doc)
        assert structure.name_paragraph_index is None

    def test_name_after_five_lines(self, detector):
        """5行之后的姓名不应被检测"""
        paras = [_make_paragraph(f'第{i}行内容') for i in range(6)]
        paras.append(_make_paragraph('张三'))
        doc = _make_doc(paras)
        structure = detector.detect_structure(doc)
        # 只检查前5行
        assert structure.name_paragraph_index is None

    def test_no_name(self, detector):
        """无姓名"""
        paras = [
            _make_paragraph('13800138000'),
            _make_paragraph('test@example.com'),
        ]
        doc = _make_doc(paras)
        structure = detector.detect_structure(doc)
        assert structure.name_paragraph_index is None


class TestDetectContact:
    """联系方式检测"""

    def test_phone_detected(self, detector):
        """手机号检测"""
        paras = [
            _make_paragraph('张三'),
            _make_paragraph('13800138000'),
        ]
        doc = _make_doc(paras)
        structure = detector.detect_structure(doc)
        assert structure.contact_paragraph_index == 1

    def test_email_detected(self, detector):
        """邮箱检测"""
        paras = [
            _make_paragraph('张三'),
            _make_paragraph('zhangsan@example.com'),
        ]
        doc = _make_doc(paras)
        structure = detector.detect_structure(doc)
        assert structure.contact_paragraph_index == 1

    def test_no_contact(self, detector):
        """无联系方式"""
        paras = [
            _make_paragraph('张三'),
            _make_paragraph('自我评价内容'),
        ]
        doc = _make_doc(paras)
        structure = detector.detect_structure(doc)
        assert structure.contact_paragraph_index is None


class TestDetectSections:
    """章节检测"""

    def test_work_section(self, detector):
        """工作经历章节"""
        paras = [
            _make_paragraph('张三'),
            _make_paragraph('13800138000'),
            _make_paragraph('工作经历'),
            _make_paragraph('2020-2023 字节跳动 工程师'),
        ]
        doc = _make_doc(paras)
        structure = detector.detect_structure(doc)
        types = [s.section_type for s in structure.sections]
        assert SectionType.WORK in types

    def test_education_section(self, detector):
        """教育背景章节"""
        paras = [
            _make_paragraph('张三'),
            _make_paragraph('教育背景'),
            _make_paragraph('2016-2020 清华大学 计算机科学'),
        ]
        doc = _make_doc(paras)
        structure = detector.detect_structure(doc)
        types = [s.section_type for s in structure.sections]
        assert SectionType.EDUCATION in types

    def test_multiple_sections(self, detector):
        """多个章节"""
        paras = [
            _make_paragraph('张三'),
            _make_paragraph('13800138000'),
            _make_paragraph('教育背景'),
            _make_paragraph('清华大学'),
            _make_paragraph('工作经历'),
            _make_paragraph('字节跳动'),
            _make_paragraph('专业技能'),
            _make_paragraph('Python'),
        ]
        doc = _make_doc(paras)
        structure = detector.detect_structure(doc)
        types = [s.section_type for s in structure.sections]
        assert SectionType.EDUCATION in types
        assert SectionType.WORK in types
        assert SectionType.SKILLS in types

    def test_no_sections(self, detector):
        """无章节"""
        paras = [
            _make_paragraph('张三'),
            _make_paragraph('13800138000'),
            _make_paragraph('一些普通文本'),
        ]
        doc = _make_doc(paras)
        structure = detector.detect_structure(doc)
        assert len(structure.sections) == 0


class TestDetectEntries:
    """动态条目检测"""

    def test_work_entries(self, detector):
        """工作经历条目检测"""
        paras = [
            _make_paragraph('张三'),
            _make_paragraph('13800138000'),
            _make_paragraph('工作经历'),
            _make_paragraph('2020-2023 字节跳动  高级工程师'),  # 双空格分隔
            _make_paragraph('负责后端服务开发'),
            _make_paragraph('2018-2020 腾讯  工程师'),
            _make_paragraph('参与微服务开发'),
        ]
        doc = _make_doc(paras)
        structure = detector.detect_structure(doc)
        work_entries = [e for e in structure.entries if e.entry_type == SectionType.WORK]
        assert len(work_entries) == 2
        assert work_entries[0].organization == '字节跳动'
        assert work_entries[1].organization == '腾讯'


class TestConfidence:
    """置信度计算"""

    def test_high_confidence(self, detector):
        """高置信度"""
        paras = [
            _make_paragraph('张三'),
            _make_paragraph('13800138000'),
            _make_paragraph('教育背景'),
            _make_paragraph('工作经历'),
            _make_paragraph('专业技能'),
        ]
        doc = _make_doc(paras)
        structure = detector.detect_structure(doc)
        assert structure.confidence >= 0.5

    def test_low_confidence(self, detector):
        """低置信度"""
        paras = [
            _make_paragraph('Some random text'),
            _make_paragraph('More random content'),
        ]
        doc = _make_doc(paras)
        structure = detector.detect_structure(doc)
        assert structure.confidence < 0.5

    def test_empty_document(self, detector):
        """空文档"""
        doc = _make_doc([])
        structure = detector.detect_structure(doc)
        assert structure.confidence == 0.0
        assert structure.name_paragraph_index is None
        assert structure.sections == []
