"""
简历结构检测器模块

检测 Word 文档中的简历结构，定位姓名、联系方式、章节标题、
工作经历条目等关键位置，为 Jinja2 标记插入提供依据。
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

# Word 文档处理
try:
    from docx import Document
    from docx.text.paragraph import Paragraph
    from docx.table import Table
    HAS_PYTHON_DOCX = True
except ImportError:
    HAS_PYTHON_DOCX = False

logger = logging.getLogger(__name__)


class SectionType(Enum):
    """章节类型枚举"""
    BASIC_INFO = "basic_info"        # 基本信息（姓名、联系方式）
    SUMMARY = "summary"              # 个人简介
    EDUCATION = "education"          # 教育背景
    WORK = "work"                    # 工作经历
    PROJECT = "project"              # 项目经历
    SKILLS = "skills"                # 专业技能
    AWARDS = "awards"                # 奖项荣誉
    CERTIFICATES = "certificates"    # 证书资质
    SELF_EVALUATION = "self_evaluation"  # 自我评价
    UNKNOWN = "unknown"              # 未知类型


@dataclass
class SectionInfo:
    """章节信息"""
    section_type: SectionType
    title: str                       # 章节标题文本
    paragraph_index: int             # 标题段落在文档中的索引
    content_start: int               # 内容起始段落索引
    content_end: int                 # 内容结束段落索引
    is_dynamic: bool = False         # 是否是动态内容（需要循环渲染）


@dataclass
class EntryInfo:
    """动态条目信息（工作经历、项目经历等）"""
    entry_type: SectionType          # 所属章节类型
    paragraph_index: int             # 条目标题段落在文档中的索引
    time: str = ""                   # 时间
    organization: str = ""           # 公司/学校/项目名
    role: str = ""                   # 职位/角色
    content_paragraphs: List[int] = field(default_factory=list)  # 内容段落索引列表


@dataclass
class StructureMap:
    """简历结构映射"""
    # 基本信息位置
    name_paragraph_index: Optional[int] = None      # 姓名段落索引
    contact_paragraph_index: Optional[int] = None   # 联系方式段落索引

    # 章节列表
    sections: List[SectionInfo] = field(default_factory=list)

    # 动态条目（工作经历、项目经历、教育背景等）
    entries: List[EntryInfo] = field(default_factory=list)

    # 检测置信度
    confidence: float = 0.0

    # 原始文本内容（用于调试）
    raw_text_preview: str = ""


class StructureDetector:
    """
    简历结构检测器

    检测策略：
    1. 姓名检测：文档开头短文本（2-10字符，纯中文）
    2. 联系方式检测：正则匹配电话/邮箱
    3. 章节标题检测：关键词匹配 + 格式特征（加粗、字号）
    4. 动态条目检测：时间-公司-职位模式
    """

    # 章节关键词映射
    SECTION_KEYWORDS = {
        SectionType.SUMMARY: ['个人简介', '简介', '个人介绍', '个人总结', '求职意向', 'summary'],
        SectionType.EDUCATION: ['教育背景', '教育经历', '学历', '院校背景', 'education'],
        SectionType.WORK: ['工作经历', '工作经验', '职业经历', '工作背景', 'work experience'],
        SectionType.PROJECT: ['项目经历', '项目经验', '项目背景', 'project'],
        SectionType.SKILLS: ['专业技能', '技能特长', '技术栈', '掌握技能', '核心技能', '核心能力', 'skills'],
        SectionType.AWARDS: ['奖项荣誉', '获奖情况', '荣誉证书', '所获荣誉', 'awards'],
        SectionType.CERTIFICATES: ['证书资质', '资格证书', '执业资格', '专业证书', '证书与语言', 'certificates'],
        SectionType.SELF_EVALUATION: ['自我评价', '个人评价', '自我介绍', 'self evaluation'],
    }

    # 时间格式正则
    TIME_PATTERN = re.compile(
        r'(\d{4}[.\-/年]\d{1,2}[.\-/月]?\d{0,2}[至~\-–到]*\d{0,4}[.\-/年]?\d{0,2}[.\-/月]?\d{0,2})|'
        r'(\d{4}[.\-/]\d{1,2}[至~\-–到]*至今)|'
        r'(\d{4}年\d{1,2}月[至~\-–到]*(至今|\d{4}年\d{1,2}月))'
    )

    # 时间在末尾的条目格式正则（如 "公司名 | 职位 | 2006.3 – 2025.12"）
    # 匹配以 | 分隔、最后一个字段是时间的格式
    TRAILING_TIME_PATTERN = re.compile(
        r'^(.+?)\s*\|\s*(.+?)\s*\|\s*'
        r'('
        r'\d{4}[.\-/年]\d{1,2}[.\-/月]?\d{0,2}\s*[至~\-–到]\s*\d{0,4}[.\-/年]?\d{0,2}[.\-/月]?\d{0,2}'
        r'|\d{4}[.\-/]\d{1,2}\s*[至~\-–到]\s*至今'
        r'|\d{4}年\d{1,2}月\s*[至~\-–到]\s*(?:至今|\d{4}年\d{1,2}月)'
        r'|\d{4}\s*[至~\-–到]\s*\d{4}'
        r')'
        r'\s*$'
    )

    # 编号列表正则（如 "1. 项目名 —— 角色描述"）
    NUMBERED_LIST_PATTERN = re.compile(r'^(\d+)\.\s+(.+)')

    # 联系方式正则
    PHONE_PATTERN = re.compile(r'1[3-9]\d{9}')
    EMAIL_PATTERN = re.compile(r'[\w.-]+@[\w.-]+\.\w+')

    def __init__(self):
        self.detection_stats = {
            'name_detected': 0,
            'contact_detected': 0,
            'sections_detected': 0,
            'entries_detected': 0,
            'failed': 0
        }

    def detect_structure(self, doc: 'Document') -> StructureMap:
        """
        检测文档结构

        Args:
            doc: python-docx Document 对象

        Returns:
            StructureMap: 结构映射
        """
        if not HAS_PYTHON_DOCX:
            raise ImportError("未安装 python-docx")

        structure = StructureMap()

        # 获取所有段落
        paragraphs = list(doc.paragraphs)

        # 1. 检测姓名（通常在前几行）
        structure.name_paragraph_index = self._detect_name(paragraphs)

        # 2. 检测联系方式
        structure.contact_paragraph_index = self._detect_contact(paragraphs)

        # 3. 检测章节标题
        structure.sections = self._detect_sections(paragraphs)

        # 4. 检测动态条目
        structure.entries = self._detect_entries(paragraphs, structure.sections)

        # 5. 计算置信度
        structure.confidence = self._calculate_confidence(structure)

        # 6. 生成预览文本
        structure.raw_text_preview = '\n'.join(
            p.text[:50] + '...' if len(p.text) > 50 else p.text
            for p in paragraphs[:10]
        )

        logger.info(f"结构检测完成: 置信度 {structure.confidence:.2f}, "
                   f"章节 {len(structure.sections)}, 条目 {len(structure.entries)}")

        return structure

    def _detect_name(self, paragraphs: List['Paragraph']) -> Optional[int]:
        """
        检测姓名段落

        策略：文档开头（前5行）的短文本，2-10字符，纯中文
        """
        for i, para in enumerate(paragraphs[:5]):
            text = para.text.strip()
            # 检查是否是纯中文，长度2-10
            if 2 <= len(text) <= 10 and re.match(r'^[\u4e00-\u9fa5]+$', text):
                # 检查不是章节标题
                if not any(kw in text for kw_list in self.SECTION_KEYWORDS.values()
                          for kw in kw_list):
                    self.detection_stats['name_detected'] += 1
                    logger.debug(f"检测到姓名: {text} (段落 {i})")
                    return i
        return None

    def _detect_contact(self, paragraphs: List['Paragraph']) -> Optional[int]:
        """
        检测联系方式段落

        策略：包含电话或邮箱的段落
        """
        for i, para in enumerate(paragraphs[:10]):  # 通常在前10行
            text = para.text
            if self.PHONE_PATTERN.search(text) or self.EMAIL_PATTERN.search(text):
                self.detection_stats['contact_detected'] += 1
                logger.debug(f"检测到联系方式 (段落 {i}): {text[:30]}...")
                return i
        return None

    def _detect_sections(self, paragraphs: List['Paragraph']) -> List[SectionInfo]:
        """
        检测章节标题

        策略：
        1. 关键词匹配
        2. 格式特征（加粗、字号较大）
        """
        sections = []
        current_section = None

        for i, para in enumerate(paragraphs):
            text = para.text.strip()
            if not text:
                continue

            # 检查是否是章节标题
            detected_type = self._match_section_title(text, para)

            if detected_type != SectionType.UNKNOWN:
                # 保存上一个章节
                if current_section:
                    current_section.content_end = max(i - 1, current_section.content_start)
                    sections.append(current_section)

                # 创建新章节
                content_start = min(i + 1, len(paragraphs) - 1)
                current_section = SectionInfo(
                    section_type=detected_type,
                    title=text,
                    paragraph_index=i,
                    content_start=content_start,
                    content_end=len(paragraphs) - 1,  # 默认到文档末尾
                    is_dynamic=detected_type in [
                        SectionType.EDUCATION,
                        SectionType.WORK,
                        SectionType.PROJECT
                    ]
                )
                self.detection_stats['sections_detected'] += 1
                logger.debug(f"检测到章节: {text} (类型: {detected_type.value}, 段落 {i})")

        # 添加最后一个章节（确保 content_end >= content_start）
        if current_section:
            current_section.content_end = max(current_section.content_end, current_section.content_start)
            sections.append(current_section)

        return sections

    def _match_section_title(self, text: str, para: 'Paragraph') -> SectionType:
        """
        匹配章节标题

        Args:
            text: 段落文本
            para: 段落对象

        Returns:
            SectionType: 检测到的类型，或 UNKNOWN
        """
        text_lower = text.lower()

        # 跳过包含 Jinja2 语法的段落（预处理后的模板变量）
        if '{{' in text or '{%' in text:
            return SectionType.UNKNOWN

        for section_type, keywords in self.SECTION_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in text_lower:
                    return section_type

        # 检查格式特征（加粗）
        # if para.runs and para.runs[0].bold:
        #     # 可能是未知的章节标题
        #     pass

        return SectionType.UNKNOWN

    def _detect_entries(self, paragraphs: List['Paragraph'],
                       sections: List[SectionInfo]) -> List[EntryInfo]:
        """
        检测动态条目（工作经历、项目经历、教育背景）

        策略：在动态章节中，检测时间-组织-角色模式
        """
        entries = []

        for section in sections:
            if not section.is_dynamic:
                continue

            # 在章节范围内检测条目
            current_entry = None

            for i in range(section.content_start, section.content_end + 1):
                if i >= len(paragraphs):
                    break

                para = paragraphs[i]
                text = para.text.strip()
                if not text:
                    continue

                # 检测时间开头的行（新条目标志）
                time_match = self.TIME_PATTERN.match(text)
                # 检测时间在末尾的行（如 "公司 | 职位 | 2006.3 – 2025.12"）
                trailing_match = self.TRAILING_TIME_PATTERN.match(text) if not time_match else None
                # 检测编号列表开头的行（如 "1. 项目名 —— 描述"）
                numbered_match = self.NUMBERED_LIST_PATTERN.match(text) if not time_match and not trailing_match else None

                if time_match or trailing_match or numbered_match:
                    # 保存上一个条目
                    if current_entry:
                        entries.append(current_entry)

                    # 解析新条目
                    if time_match:
                        time_str = time_match.group(0)
                        rest = text[time_match.end():].strip()
                        org, role = self._parse_entry_header(rest)
                    elif trailing_match:
                        # 时间在末尾格式: "公司 | 职位 | 时间"
                        time_str = trailing_match.group(3).strip()
                        org = trailing_match.group(1).strip()
                        role = trailing_match.group(2).strip()
                    else:
                        # 编号列表格式: "1. 项目名 —— 描述"
                        time_str = ''
                        rest = numbered_match.group(2).strip()
                        org, role = self._parse_entry_header(rest)

                    current_entry = EntryInfo(
                        entry_type=section.section_type,
                        paragraph_index=i,
                        time=time_str,
                        organization=org,
                        role=role,
                        content_paragraphs=[]
                    )
                    self.detection_stats['entries_detected'] += 1
                    logger.debug(f"检测到条目: {time_str} {org} {role} (段落 {i})")

                elif current_entry:
                    # 添加到当前条目的内容
                    current_entry.content_paragraphs.append(i)

            # 添加最后一个条目
            if current_entry:
                entries.append(current_entry)

        return entries

    def _parse_entry_header(self, text: str) -> Tuple[str, str]:
        """
        解析条目标题行，分离组织和角色

        Args:
            text: 时间之后的文本，如 "字节跳动  高级工程师"

        Returns:
            Tuple[str, str]: (组织, 角色)
        """
        # 常见分隔符
        separators = ['|', '｜', '/', '  ', '\t', '——', '—']

        for sep in separators:
            if sep in text:
                parts = text.split(sep, 1)
                org = parts[0].strip()
                role = parts[1].strip() if len(parts) > 1 else ''
                return org, role

        # 没有分隔符，整体作为组织名
        return text.strip(), ''

    def _calculate_confidence(self, structure: StructureMap) -> float:
        """
        计算检测置信度

        Args:
            structure: 结构映射

        Returns:
            float: 置信度 0.0-1.0
        """
        score = 0.0

        # 姓名检测（权重25%）
        if structure.name_paragraph_index is not None:
            score += 0.25

        # 联系方式检测（权重25%）
        if structure.contact_paragraph_index is not None:
            score += 0.25

        # 章节检测（权重30%）
        if structure.sections:
            score += min(0.30, len(structure.sections) * 0.10)

        # 动态条目检测（权重20%）
        if structure.entries:
            score += min(0.20, len(structure.entries) * 0.05)

        return min(1.0, score)

    def get_stats(self) -> Dict[str, int]:
        """获取检测统计信息"""
        return self.detection_stats.copy()
