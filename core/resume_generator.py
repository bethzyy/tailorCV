"""
简历生成器模块

负责生成定制后的简历文档，支持 Word 格式输出。
"""

import io
import os
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

from docx import Document
from docx.shared import Pt, Inches, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from .config import config

logger = logging.getLogger(__name__)


class ResumeGenerator:
    """简历生成器 - Word 文档输出"""

    def __init__(self):
        self.template_dir = config.BASE_DIR / 'templates'
        self.output_dir = config.BASE_DIR / 'output'
        self.output_dir.mkdir(exist_ok=True)

    def generate_word(self, tailored_resume: Dict[str, Any],
                      output_path: Optional[str] = None,
                      style: str = 'original') -> str:
        """
        生成 Word 文档

        Args:
            tailored_resume: 定制后的简历数据
            output_path: 输出路径（可选）
            style: 样式（MVP仅支持 'original'）

        Returns:
            str: 生成的文件路径
        """
        logger.info(f"开始生成 Word 文档: style={style}")

        # 创建文档
        doc = Document()

        # 设置页面边距
        sections = doc.sections
        for section in sections:
            section.top_margin = Cm(2.5)
            section.bottom_margin = Cm(2.5)
            section.left_margin = Cm(2)
            section.right_margin = Cm(2)

        # 设置默认字体
        self._set_document_font(doc)

        # 添加内容
        self._add_basic_info(doc, tailored_resume.get('basic_info', {}))
        self._add_summary(doc, tailored_resume.get('summary', ''))
        self._add_education(doc, tailored_resume.get('education', []))
        self._add_work_experience(doc, tailored_resume.get('work_experience', []))
        self._add_projects(doc, tailored_resume.get('projects', []))
        self._add_skills(doc, tailored_resume.get('skills', []))
        self._add_awards(doc, tailored_resume.get('awards', []))
        self._add_certificates(doc, tailored_resume.get('certificates', []))
        self._add_self_evaluation(doc, tailored_resume.get('self_evaluation', ''))

        # 生成输出路径
        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            name = tailored_resume.get('basic_info', {}).get('name', '简历')
            output_path = str(self.output_dir / f'{name}_定制简历_{timestamp}.docx')

        # 保存文档
        doc.save(output_path)
        logger.info(f"Word 文档生成完成: {output_path}")

        return output_path

    def generate_pdf(self, tailored_resume: Dict[str, Any],
                     output_path: Optional[str] = None) -> str:
        """
        生成 PDF 文档（先 Word 后转换）

        Args:
            tailored_resume: 定制后的简历数据
            output_path: 输出路径（可选）

        Returns:
            str: 生成的 PDF 文件路径
        """
        # 先生成 Word
        word_path = self.generate_word(tailored_resume)

        # 转换为 PDF
        pdf_path = word_path.replace('.docx', '.pdf')

        try:
            from docx2pdf import convert
            convert(word_path, pdf_path)
            logger.info(f"PDF 文档生成完成: {pdf_path}")
            return pdf_path
        except ImportError:
            logger.warning("docx2pdf 未安装，跳过 PDF 生成")
            return word_path
        except Exception as e:
            logger.error(f"PDF 转换失败: {e}")
            return word_path

    def generate_bytes(self, tailored_resume: Dict[str, Any],
                       format: str = 'word') -> bytes:
        """
        生成文档字节流

        Args:
            tailored_resume: 定制后的简历数据
            format: 格式 ('word' 或 'pdf')

        Returns:
            bytes: 文档字节流
        """
        # 生成到内存
        doc = self._create_document(tailored_resume)

        # 保存到字节流
        bio = io.BytesIO()
        doc.save(bio)
        bio.seek(0)

        if format == 'pdf':
            # TODO: 实现 PDF 字节流转换
            pass

        return bio.read()

    def _create_document(self, tailored_resume: Dict[str, Any]) -> Document:
        """创建文档对象"""
        doc = Document()

        # 设置页面边距
        for section in doc.sections:
            section.top_margin = Cm(2.5)
            section.bottom_margin = Cm(2.5)
            section.left_margin = Cm(2)
            section.right_margin = Cm(2)

        self._set_document_font(doc)

        # 添加内容
        self._add_basic_info(doc, tailored_resume.get('basic_info', {}))
        self._add_summary(doc, tailored_resume.get('summary', ''))
        self._add_education(doc, tailored_resume.get('education', []))
        self._add_work_experience(doc, tailored_resume.get('work_experience', []))
        self._add_projects(doc, tailored_resume.get('projects', []))
        self._add_skills(doc, tailored_resume.get('skills', []))
        self._add_awards(doc, tailored_resume.get('awards', []))
        self._add_certificates(doc, tailored_resume.get('certificates', []))
        self._add_self_evaluation(doc, tailored_resume.get('self_evaluation', ''))

        return doc

    def _set_document_font(self, doc: Document):
        """设置文档默认字体"""
        # 设置正文样式
        style = doc.styles['Normal']
        font = style.font
        font.name = 'Microsoft YaHei'
        font.size = Pt(10.5)

        # 设置中文字体
        style._element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')

    def _add_basic_info(self, doc: Document, basic_info: Dict[str, Any]):
        """添加基本信息"""
        name = basic_info.get('name', '')
        if not name:
            return

        # 姓名（标题）
        title = doc.add_paragraph()
        title_run = title.add_run(name)
        title_run.bold = True
        title_run.font.size = Pt(18)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # 联系方式（一行）
        contact_parts = []
        if basic_info.get('phone'):
            contact_parts.append(f"电话: {basic_info['phone']}")
        if basic_info.get('email'):
            contact_parts.append(f"邮箱: {basic_info['email']}")
        if basic_info.get('location'):
            contact_parts.append(f"现居: {basic_info['location']}")
        if basic_info.get('age'):
            contact_parts.append(f"年龄: {basic_info['age']}岁")
        if basic_info.get('gender'):
            contact_parts.append(f"性别: {basic_info['gender']}")

        if contact_parts:
            contact = doc.add_paragraph()
            contact_run = contact.add_run(' | '.join(contact_parts))
            contact_run.font.size = Pt(10)
            contact.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # 分隔线
        doc.add_paragraph('─' * 40)

    def _add_summary(self, doc: Document, summary: str):
        """添加个人简介"""
        if not summary:
            return

        self._add_section_title(doc, '个人简介')
        p = doc.add_paragraph(summary)
        p.paragraph_format.first_line_indent = Cm(0.74)  # 两字符缩进

    def _add_education(self, doc: Document, education: List[Dict[str, Any]]):
        """添加教育背景"""
        if not education:
            return

        self._add_section_title(doc, '教育背景')

        for edu in education:
            p = doc.add_paragraph()

            # 时间
            time = edu.get('time', '')
            if time:
                run = p.add_run(time + '  ')
                run.font.size = Pt(10)

            # 学校和专业
            school = edu.get('school', '')
            major = edu.get('major', '')
            degree = edu.get('degree', '')

            if school:
                run = p.add_run(school)
                run.bold = True
            if major:
                p.add_run(f'  {major}')
            if degree:
                run = p.add_run(f'  [{degree}]')
                run.font.size = Pt(9)

    def _add_work_experience(self, doc: Document, work_experience: List[Dict[str, Any]]):
        """添加工作经历"""
        if not work_experience:
            return

        self._add_section_title(doc, '工作经历')

        for exp in work_experience:
            # 标题行：时间 公司 职位
            p = doc.add_paragraph()

            time = exp.get('time', '')
            if time:
                run = p.add_run(time + '  ')
                run.font.size = Pt(10)

            company = exp.get('company', '')
            if company:
                run = p.add_run(company)
                run.bold = True

            position = exp.get('position', '')
            if position:
                p.add_run(f'  |  {position}')

            # 工作内容
            content = exp.get('tailored', exp.get('content', ''))
            if content:
                # 按行分割并添加
                lines = content.split('\n')
                for line in lines:
                    line = line.strip()
                    if line:
                        p = doc.add_paragraph(line, style='List Bullet')
                        p.paragraph_format.left_indent = Cm(0.5)

    def _add_projects(self, doc: Document, projects: List[Dict[str, Any]]):
        """添加项目经历"""
        if not projects:
            return

        self._add_section_title(doc, '项目经历')

        for proj in projects:
            # 标题行
            p = doc.add_paragraph()

            time = proj.get('time', '')
            if time:
                run = p.add_run(time + '  ')
                run.font.size = Pt(10)

            name = proj.get('name', '')
            if name:
                run = p.add_run(name)
                run.bold = True

            role = proj.get('role', '')
            if role:
                p.add_run(f'  |  {role}')

            # 项目内容
            content = proj.get('tailored', proj.get('content', ''))
            if content:
                lines = content.split('\n')
                for line in lines:
                    line = line.strip()
                    if line:
                        p = doc.add_paragraph(line, style='List Bullet')
                        p.paragraph_format.left_indent = Cm(0.5)

    def _add_skills(self, doc: Document, skills: List[Any]):
        """添加专业技能"""
        if not skills:
            return

        self._add_section_title(doc, '专业技能')

        # 处理不同的技能格式
        if isinstance(skills, list):
            skill_names = []
            for skill in skills:
                if isinstance(skill, dict):
                    name = skill.get('name', '')
                    desc = skill.get('tailored_description', '')
                    if name:
                        if desc:
                            skill_names.append(f"{name}: {desc}")
                        else:
                            skill_names.append(name)
                elif isinstance(skill, str):
                    skill_names.append(skill)

            if skill_names:
                p = doc.add_paragraph(' | '.join(skill_names))

    def _add_awards(self, doc: Document, awards: List[str]):
        """添加奖项荣誉"""
        if not awards:
            return

        self._add_section_title(doc, '奖项荣誉')

        for award in awards:
            if award:
                p = doc.add_paragraph(award, style='List Bullet')

    def _add_certificates(self, doc: Document, certificates: List[str]):
        """添加证书资质"""
        if not certificates:
            return

        self._add_section_title(doc, '证书资质')

        for cert in certificates:
            if cert:
                p = doc.add_paragraph(cert, style='List Bullet')

    def _add_self_evaluation(self, doc: Document, self_evaluation: str):
        """添加自我评价"""
        if not self_evaluation:
            return

        self._add_section_title(doc, '自我评价')
        p = doc.add_paragraph(self_evaluation)
        p.paragraph_format.first_line_indent = Cm(0.74)

    def _add_section_title(self, doc: Document, title: str):
        """添加章节标题"""
        p = doc.add_paragraph()
        run = p.add_run(title)
        run.bold = True
        run.font.size = Pt(12)
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(6)

        # 添加下划线
        p.add_run('\n' + '─' * 20)
