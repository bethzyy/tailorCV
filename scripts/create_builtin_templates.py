"""
创建内置简历模板

运行此脚本生成 6 个内置模板 .docx 文件。
每个模板包含 Jinja2 标记，用于动态渲染。
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.style import WD_STYLE_TYPE
    HAS_PYTHON_DOCX = True
except ImportError:
    print("请先安装 python-docx: pip install python-docx")
    HAS_PYTHON_DOCX = False
    sys.exit(1)


def set_style(paragraph, font_name='微软雅黑', font_size=11, bold=False, color=None):
    """设置段落样式"""
    for run in paragraph.runs:
        run.font.name = font_name
        run.font.size = Pt(font_size)
        run.font.bold = bold
        if color:
            run.font.color.rgb = RGBColor(*color)


def create_classic_professional():
    """经典专业模板 - 传统正式风格"""
    doc = Document()

    # 标题
    title = doc.add_paragraph()
    title.add_run('{{ basic_info.name }}')
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # 联系方式
    contact = doc.add_paragraph()
    contact.add_run('{{ basic_info.phone }} | {{ basic_info.email }}')
    contact.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()

    # 个人简介
    doc.add_paragraph('个人简介')
    doc.add_paragraph('{{ summary }}')

    # 教育背景
    doc.add_paragraph('教育背景')
    doc.add_paragraph('{% for edu in education %}')
    doc.add_paragraph('{{ edu.school }} | {{ edu.major }} | {{ edu.degree }} | {{ edu.time }}')
    doc.add_paragraph('{{ edu.tailored or "" }}')
    doc.add_paragraph('{% endfor %}')

    # 工作经历
    doc.add_paragraph('工作经历')
    doc.add_paragraph('{% for work in work_experience %}')
    doc.add_paragraph('{{ work.company }} | {{ work.position }} | {{ work.time }}')
    doc.add_paragraph('{{ work.tailored or work.content }}')
    doc.add_paragraph('{% endfor %}')

    # 项目经历
    doc.add_paragraph('项目经历')
    doc.add_paragraph('{% for proj in projects %}')
    doc.add_paragraph('{{ proj.name }} | {{ proj.role }} | {{ proj.time }}')
    doc.add_paragraph('{{ proj.tailored or proj.content }}')
    doc.add_paragraph('{% endfor %}')

    # 技能特长
    doc.add_paragraph('技能特长')
    doc.add_paragraph('{% for skill in skills %}')
    doc.add_paragraph('{{ skill.name }}{% if skill.tailored_description %}: {{ skill.tailored_description }}{% endif %}')
    doc.add_paragraph('{% endfor %}')

    # 荣誉证书
    doc.add_paragraph('荣誉证书')
    doc.add_paragraph('{% for award in awards %}{{ award.name }}{% if not loop.last %}、{% endif %}{% endfor %}')

    # 自我评价
    doc.add_paragraph('自我评价')
    doc.add_paragraph('{{ self_evaluation }}')

    return doc


def create_modern_minimal():
    """现代简约模板 - 简洁清爽风格"""
    doc = Document()

    # 标题
    title = doc.add_paragraph()
    title.add_run('{{ basic_info.name }}')
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT

    # 联系方式
    contact = doc.add_paragraph()
    contact.add_run('📧 {{ basic_info.email }} | 📱 {{ basic_info.phone }}')

    doc.add_paragraph('─' * 40)

    # 个人简介
    doc.add_paragraph('◆ 关于我')
    doc.add_paragraph('{{ summary }}')

    # 教育背景
    doc.add_paragraph('◆ 教育背景')
    doc.add_paragraph('{% for edu in education %}')
    doc.add_paragraph('• {{ edu.school }} - {{ edu.major }} ({{ edu.degree }}) | {{ edu.time }}')
    doc.add_paragraph('{% endfor %}')

    # 工作经历
    doc.add_paragraph('◆ 工作经历')
    doc.add_paragraph('{% for work in work_experience %}')
    doc.add_paragraph('• {{ work.company }} - {{ work.position }} | {{ work.time }}')
    doc.add_paragraph('  {{ work.tailored or work.content }}')
    doc.add_paragraph('{% endfor %}')

    # 项目经历
    doc.add_paragraph('◆ 项目经历')
    doc.add_paragraph('{% for proj in projects %}')
    doc.add_paragraph('• {{ proj.name }} - {{ proj.role }} | {{ proj.time }}')
    doc.add_paragraph('  {{ proj.tailored or proj.content }}')
    doc.add_paragraph('{% endfor %}')

    # 技能
    doc.add_paragraph('◆ 技能')
    doc.add_paragraph('{% for skill in skills %}{{ skill.name }}{% if not loop.last %} | {% endif %}{% endfor %}')

    return doc


def create_creative_design():
    """创意设计模板 - 个性化风格"""
    doc = Document()

    # 标题
    title = doc.add_paragraph()
    title.add_run('★ {{ basic_info.name }} ★')
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    contact = doc.add_paragraph()
    contact.add_run('📞 {{ basic_info.phone }} | ✉️ {{ basic_info.email }}')
    contact.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph('═' * 50)

    # 个人简介
    doc.add_paragraph('【 个人简介 】')
    doc.add_paragraph('{{ summary }}')

    # 教育背景
    doc.add_paragraph('【 教育背景 】')
    doc.add_paragraph('{% for edu in education %}')
    doc.add_paragraph('🎓 {{ edu.school }} | {{ edu.major }} | {{ edu.degree }}')
    doc.add_paragraph('   {{ edu.time }}{% if edu.highlights %} | {{ edu.highlights }}{% endif %}')
    doc.add_paragraph('{% endfor %}')

    # 工作经历
    doc.add_paragraph('【 工作经历 】')
    doc.add_paragraph('{% for work in work_experience %}')
    doc.add_paragraph('💼 {{ work.company }} | {{ work.position }}')
    doc.add_paragraph('   {{ work.time }}')
    doc.add_paragraph('   {{ work.tailored or work.content }}')
    doc.add_paragraph('{% endfor %}')

    # 项目经历
    doc.add_paragraph('【 项目经历 】')
    doc.add_paragraph('{% for proj in projects %}')
    doc.add_paragraph('🚀 {{ proj.name }} | {{ proj.role }}')
    doc.add_paragraph('   {{ proj.tailored or proj.content }}')
    doc.add_paragraph('{% endfor %}')

    # 技能
    doc.add_paragraph('【 专业技能 】')
    doc.add_paragraph('{% for skill in skills %}')
    doc.add_paragraph('⭐ {{ skill.name }}{% if skill.tailored_description %}: {{ skill.tailored_description }}{% endif %}')
    doc.add_paragraph('{% endfor %}')

    return doc


def create_executive_senior():
    """高管资深模板 - 大气稳重风格"""
    doc = Document()

    # 标题
    title = doc.add_paragraph()
    title.add_run('{{ basic_info.name }}')
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    subtitle = doc.add_paragraph()
    subtitle.add_run('资深专业人士')
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER

    contact = doc.add_paragraph()
    contact.add_run('{{ basic_info.phone }} | {{ basic_info.email }}')
    contact.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()

    # 职业概述
    doc.add_paragraph('职业概述')
    doc.add_paragraph('{{ summary }}')

    # 核心能力
    doc.add_paragraph('核心能力')
    doc.add_paragraph('{% for skill in skills %}• {{ skill.name }}{% if not loop.last %}  {% endif %}{% endfor %}')

    # 工作经历
    doc.add_paragraph('工作经历')
    doc.add_paragraph('{% for work in work_experience %}')
    doc.add_paragraph('━━━━━━━━━━━━━━━━━━━━')
    doc.add_paragraph('{{ work.company }} | {{ work.position }}')
    doc.add_paragraph('{{ work.time }}')
    doc.add_paragraph()
    doc.add_paragraph('{{ work.tailored or work.content }}')
    doc.add_paragraph('{% endfor %}')

    # 教育背景
    doc.add_paragraph('教育背景')
    doc.add_paragraph('{% for edu in education %}')
    doc.add_paragraph('{{ edu.school }} | {{ edu.degree }} | {{ edu.major }} | {{ edu.time }}')
    doc.add_paragraph('{% endfor %}')

    # 项目经历
    doc.add_paragraph('主要项目')
    doc.add_paragraph('{% for proj in projects %}')
    doc.add_paragraph('• {{ proj.name }} ({{ proj.role }}) - {{ proj.time }}')
    doc.add_paragraph('  {{ proj.tailored or proj.content }}')
    doc.add_paragraph('{% endfor %}')

    return doc


def create_academic_research():
    """学术研究模板 - 规范学术风格"""
    doc = Document()

    # 标题
    title = doc.add_paragraph()
    title.add_run('{{ basic_info.name }}')
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    contact = doc.add_paragraph()
    contact.add_run('联系邮箱: {{ basic_info.email }} | 电话: {{ basic_info.phone }}')
    contact.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()

    # 研究兴趣
    doc.add_paragraph('研究兴趣')
    doc.add_paragraph('{{ summary }}')

    # 教育背景
    doc.add_paragraph('教育背景')
    doc.add_paragraph('{% for edu in education %}')
    doc.add_paragraph('{{ edu.time }} | {{ edu.school }} | {{ edu.degree }} | {{ edu.major }}')
    doc.add_paragraph('{% endfor %}')

    # 研究经历/工作经历
    doc.add_paragraph('研究/工作经历')
    doc.add_paragraph('{% for work in work_experience %}')
    doc.add_paragraph('{{ work.time }} | {{ work.company }} | {{ work.position }}')
    doc.add_paragraph('{{ work.tailored or work.content }}')
    doc.add_paragraph('{% endfor %}')

    # 项目经历
    doc.add_paragraph('研究项目')
    doc.add_paragraph('{% for proj in projects %}')
    doc.add_paragraph('【{{ proj.name }}】 {{ proj.role }} | {{ proj.time }}')
    doc.add_paragraph('{{ proj.tailored or proj.content }}')
    doc.add_paragraph('{% endfor %}')

    # 技能
    doc.add_paragraph('专业技能')
    doc.add_paragraph('{% for skill in skills %}• {{ skill.name }}{% if skill.tailored_description %}: {{ skill.tailored_description }}{% endif %}{% if not loop.last %}{{ "\\n" }}{% endif %}{% endfor %}')

    # 荣誉奖项
    doc.add_paragraph('荣誉奖项')
    doc.add_paragraph('{% for award in awards %}• {{ award.name }}{% if not loop.last %}{{ "\\n" }}{% endif %}{% endfor %}')

    return doc


def create_tech_engineer():
    """技术工程师模板 - 结构化清晰风格"""
    doc = Document()

    # 标题
    title = doc.add_paragraph()
    title.add_run('{{ basic_info.name }}')
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT

    contact = doc.add_paragraph()
    contact.add_run('📱 {{ basic_info.phone }} | 📧 {{ basic_info.email }}')

    doc.add_paragraph('─────────────────────────────────')

    # 个人简介
    doc.add_paragraph('> 个人简介')
    doc.add_paragraph('{{ summary }}')

    # 技术栈
    doc.add_paragraph('> 技术栈')
    doc.add_paragraph('{% for skill in skills %}• {{ skill.name }}{% if skill.tailored_description %}: {{ skill.tailored_description }}{% endif %}{{ "\\n" }}{% endfor %}')

    # 工作经历
    doc.add_paragraph('> 工作经历')
    doc.add_paragraph('{% for work in work_experience %}')
    doc.add_paragraph('┌─ {{ work.company }} | {{ work.position }}')
    doc.add_paragraph('│  {{ work.time }}')
    doc.add_paragraph('│  {{ work.tailored or work.content }}')
    doc.add_paragraph('└────────────────────')
    doc.add_paragraph('{% endfor %}')

    # 项目经历
    doc.add_paragraph('> 项目经历')
    doc.add_paragraph('{% for proj in projects %}')
    doc.add_paragraph('• {{ proj.name }}')
    doc.add_paragraph('  角色: {{ proj.role }} | 时间: {{ proj.time }}')
    doc.add_paragraph('  {{ proj.tailored or proj.content }}')
    doc.add_paragraph('{% endfor %}')

    # 教育背景
    doc.add_paragraph('> 教育背景')
    doc.add_paragraph('{% for edu in education %}• {{ edu.school }} | {{ edu.major }} | {{ edu.degree }} | {{ edu.time }}{% if not loop.last %}{{ "\\n" }}{% endif %}{% endfor %}')

    return doc


def main():
    """生成所有内置模板"""
    output_dir = Path(__file__).parent.parent / 'templates' / 'builtin'
    output_dir.mkdir(parents=True, exist_ok=True)

    templates = [
        ('classic_professional', create_classic_professional, '经典专业'),
        ('modern_minimal', create_modern_minimal, '现代简约'),
        ('creative_design', create_creative_design, '创意设计'),
        ('executive_senior', create_executive_senior, '高管资深'),
        ('academic_research', create_academic_research, '学术研究'),
        ('tech_engineer', create_tech_engineer, '技术工程师'),
    ]

    for template_id, creator_func, name in templates:
        doc = creator_func()
        output_path = output_dir / f'{template_id}.docx'
        doc.save(str(output_path))
        print(f'Created: {name} ({output_path.name})')

    print(f'\nAll templates saved to: {output_dir}')


if __name__ == '__main__':
    main()
