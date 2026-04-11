"""
生成模板预览图

从 .docx 模板文件生成 PNG 预览图，展示模板的结构和样式。
"""

import os
import sys
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from docx import Document
    HAS_PYTHON_DOCX = True
except ImportError:
    HAS_PYTHON_DOCX = False
    logging.error("请先安装 python-docx: pip install python-docx")
    sys.exit(1)

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    logging.error("请先安装 Pillow: pip install Pillow")
    sys.exit(1)


# 颜色方案
COLOR_SCHEMES = {
    'classic_professional': {
        'bg': '#FFFFFF',
        'header': '#1a365d',
        'section': '#2c5282',
        'text': '#2d3748',
        'accent': '#4299e1'
    },
    'modern_minimal': {
        'bg': '#FAFAFA',
        'header': '#1a202c',
        'section': '#4a5568',
        'text': '#2d3748',
        'accent': '#667eea'
    },
    'creative_design': {
        'bg': '#FFF5F5',
        'header': '#9f1239',
        'section': '#be185d',
        'text': '#1f2937',
        'accent': '#ec4899'
    },
    'executive_senior': {
        'bg': '#FFFFFF',
        'header': '#1e3a5f',
        'section': '#0f172a',
        'text': '#334155',
        'accent': '#0ea5e9'
    },
    'academic_research': {
        'bg': '#FFFFFF',
        'header': '#1e40af',
        'section': '#1e3a8a',
        'text': '#1f2937',
        'accent': '#3b82f6'
    },
    'tech_engineer': {
        'bg': '#0f172a',
        'header': '#22d3ee',
        'section': '#38bdf8',
        'text': '#e2e8f0',
        'accent': '#06b6d4'
    }
}


def hex_to_rgb(hex_color):
    """将十六进制颜色转换为 RGB"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def get_font(size, bold=False):
    """获取字体 - 使用 Windows 系统字体绝对路径"""
    # Windows 系统字体路径（按优先级排序）
    font_paths = [
        'C:/Windows/Fonts/msyh.ttc',      # 微软雅黑
        'C:/Windows/Fonts/msyhbd.ttc',    # 微软雅黑粗体
        'C:/Windows/Fonts/simhei.ttf',    # 黑体
        'C:/Windows/Fonts/simsun.ttc',    # 宋体
    ]

    # 如果需要粗体，优先尝试粗体字体
    if bold:
        font_paths = [
            'C:/Windows/Fonts/msyhbd.ttc',    # 微软雅黑粗体
            'C:/Windows/Fonts/simhei.ttf',    # 黑体（本身就是粗体风格）
        ] + font_paths

    for path in font_paths:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue

    # 回退：尝试通过字体名称查找
    font_names = [
        'Microsoft YaHei',
        'SimHei',
        'Arial Unicode MS',
        'DejaVu Sans',
    ]
    for name in font_names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue

    # 最后回退到默认字体
    return ImageFont.load_default()


def _read_template_content(template_path):
    """读取模板文件内容"""
    try:
        doc = Document(str(template_path))
        return [p.text for p in doc.paragraphs if p.text.strip()]
    except Exception as e:
        logging.warning(f"无法读取模板文件 {template_path}: {e}")
        return []


def _draw_wrapped_text(draw, text, x, y, max_width, font, color, line_height=16):
    """绘制自动换行的文本"""
    words = text
    char_width = 10  # 估算字符宽度
    chars_per_line = max_width // char_width
    
    while words:
        if len(words) <= chars_per_line:
            draw.text((x, y), words, fill=color, font=font)
            y += line_height
            break
        else:
            draw.text((x, y), words[:chars_per_line], fill=color, font=font)
            words = words[chars_per_line:]
            y += line_height
    
    return y


def _draw_resume_sections(draw, width, colors, fonts):
    """绘制简历的各个部分"""
    y = 75  # 起始 Y 坐标
    height = 560  # 画布高度
    
    sections = [
        ('个人简介', '资深专业人士，具有丰富的工作经验和专业技能...'),
        ('教育背景', 'XX大学 | 计算机科学 | 硕士\n2015-2018'),
        ('工作经历', 'ABC公司 | 高级工程师\n2018-至今\n负责核心系统开发...'),
        ('项目经历', '项目名称 | 核心成员\n主要技术栈和成果...'),
        ('专业技能', 'Python, JavaScript, 项目管理...'),
    ]

    for section_title, section_content in sections:
        # 章节标题
        draw.text((20, y), section_title, fill=hex_to_rgb(colors['section']), font=fonts['section'])
        y += 22

        # 章节内容
        lines = section_content.split('\n')
        for line in lines:
            y = _draw_wrapped_text(
                draw, line, 25, y, width - 40,
                fonts['small'], hex_to_rgb(colors['text'])
            )

        y += 10

        # 检查是否超出画布
        if y > height - 30:
            break
    
    return y


def generate_preview(template_id: str, template_path: Path, output_path: Path):
    """生成单个模板的预览图"""
    colors = COLOR_SCHEMES.get(template_id, COLOR_SCHEMES['classic_professional'])

    # 创建画布
    width, height = 400, 560
    img = Image.new('RGB', (width, height), hex_to_rgb(colors['bg']))
    draw = ImageDraw.Draw(img)

    # 字体
    fonts = {
        'name': get_font(20, bold=True),
        'section': get_font(14, bold=True),
        'text': get_font(11),
        'small': get_font(9)
    }

    # 读取模板内容
    paragraphs = _read_template_content(template_path)

    # 绘制模板名称
    template_names = {
        'classic_professional': '经典专业',
        'modern_minimal': '现代简约',
        'creative_design': '创意设计',
        'executive_senior': '高管资深',
        'academic_research': '学术研究',
        'tech_engineer': '技术工程师'
    }
    name = template_names.get(template_id, template_id)
    draw.text((20, 20), name, fill=hex_to_rgb(colors['header']), font=fonts['name'])

    # 绘制分隔线
    draw.line([(20, 55), (width - 20, 55)], fill=hex_to_rgb(colors['accent']), width=2)

    # 绘制简历内容
    _draw_resume_sections(draw, width, colors, fonts)

    # 添加底部边框装饰
    draw.rectangle([(0, height-5), (width, height)], fill=hex_to_rgb(colors['accent']))

    # 保存
    img.save(str(output_path), 'PNG')
    logging.info(f'  Generated: {output_path.name}')


def main():
    """生成所有模板的预览图"""
    builtin_dir = Path(__file__).parent.parent / 'templates' / 'builtin'
    previews_dir = Path(__file__).parent.parent / 'templates' / 'previews'
    previews_dir.mkdir(parents=True, exist_ok=True)

    logging.info('Generating template previews...')
    logging.info(f'Source: {builtin_dir}')
    logging.info(f'Output: {previews_dir}')
    logging.info('')

    templates = [
        'classic_professional',
        'modern_minimal',
        'creative_design',
        'executive_senior',
        'academic_research',
        'tech_engineer',
    ]

    for template_id in templates:
        template_path = builtin_dir / f'{template_id}.docx'
        output_path = previews_dir / f'{template_id}.png'

        if not template_path.exists():
            logging.warning(f'  Skipped: {template_id} (file not found)')
            continue

        generate_preview(template_id, template_path, output_path)

    logging.info('')
    logging.info('Done!')


if __name__ == '__main__':
    main()
