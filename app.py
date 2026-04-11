"""
tailorCV Flask 主入口

提供 Web 界面和 REST API。
"""

import os
import io
import json
import base64
import uuid
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Tuple

from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

from core.config import config
from core.resume_parser import ResumeParser, ParsedResume
from core.resume_builder import ResumeBuilder
from core.expert_team import ExpertTeam, AnalysisResult, GenerationResult
from core.evidence_tracker import EvidenceTracker
from core.resume_generator import ResumeGenerator
from core.cache_manager import CacheManager
from core.auth import login_required
from core.template_processor import TemplateProcessor
from core.database import db

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建 Flask 应用
app = Flask(__name__,
            template_folder='web/templates',
            static_folder='web/static')

app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH
CORS(app)

# 初始化组件
parser = ResumeParser()
builder = ResumeBuilder()
expert_team = ExpertTeam()
generator = ResumeGenerator()
cache_manager = CacheManager()
template_processor = TemplateProcessor()

# 任务状态存储（简单实现，生产环境应使用 Redis）
task_status: Dict[str, Dict[str, Any]] = {}


# ==================== 文件保存辅助函数 ====================

def save_uploaded_file(file, session_id: str) -> str:
    """
    保存上传的原始文件

    Args:
        file: Flask 文件对象
        session_id: 会话ID

    Returns:
        str: 保存的文件路径
    """
    upload_dir = Path('storage/uploads') / session_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    # 保留原始扩展名
    ext = Path(file.filename).suffix.lower()
    file_path = upload_dir / f'original{ext}'
    file.save(str(file_path))

    logger.info(f"原始文件已保存: {file_path}")
    return str(file_path)


def save_uploaded_bytes(content: bytes, filename: str, session_id: str) -> str:
    """
    保存上传的原始文件内容（字节形式）

    Args:
        content: 文件内容（字节）
        filename: 原始文件名
        session_id: 会话ID

    Returns:
        str: 保存的文件路径
    """
    upload_dir = Path('storage/uploads') / session_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    # 保留原始扩展名
    ext = Path(filename).suffix.lower()
    file_path = upload_dir / f'original{ext}'

    with open(file_path, 'wb') as f:
        f.write(content)

    logger.info(f"原始文件已保存: {file_path}")
    return str(file_path)


def save_tailored_file(content: bytes, session_id: str) -> str:
    """
    保存定制后的文件

    Args:
        content: 文件内容（字节）
        session_id: 会话ID

    Returns:
        str: 保存的文件路径
    """
    output_dir = Path('storage/tailored') / session_id
    output_dir.mkdir(parents=True, exist_ok=True)

    file_path = output_dir / 'tailored.docx'
    with open(file_path, 'wb') as f:
        f.write(content)

    logger.info(f"定制文件已保存: {file_path}")
    return str(file_path)


def parse_jd_info(jd_content: str) -> Tuple[str, str]:
    """
    从 JD 内容中提取职位名称和公司名称

    Args:
        jd_content: JD 文本内容

    Returns:
        Tuple[str, str]: (职位名称, 公司名称)
    """
    job_title = ''
    company = ''

    lines = jd_content.strip().split('\n')
    for line in lines[:10]:  # 只检查前10行
        line = line.strip()
        if not line:
            continue

        # 常见的职位标识
        if any(kw in line for kw in ['职位', '岗位', '招聘', 'Job Title']):
            # 尝试提取职位名称
            if '：' in line:
                job_title = line.split('：')[-1].strip()
            elif ':' in line:
                job_title = line.split(':')[-1].strip()
            elif not job_title and len(line) < 50:
                job_title = line

        # 常见的公司标识
        if any(kw in line for kw in ['公司', '企业', 'Company', '招聘方']):
            if '：' in line:
                company = line.split('：')[-1].strip()
            elif ':' in line:
                company = line.split(':')[-1].strip()

    # 如果没有提取到，使用第一行作为职位（通常是标题）
    if not job_title and lines:
        first_line = lines[0].strip()
        if len(first_line) < 100:  # 避免使用太长的行
            job_title = first_line

    return job_title[:100] if job_title else '', company[:50] if company else ''


def allowed_file(filename: str) -> bool:
    """检查文件类型是否允许"""
    allowed_extensions = {'.pdf', '.docx', '.doc', '.txt', '.md'}
    return Path(filename).suffix.lower() in allowed_extensions


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/guided')
def guided_input():
    """引导输入页面"""
    return render_template('guided_input.html')


@app.route('/history')
def history():
    """历史记录页面"""
    return render_template('history.html')


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        'status': 'healthy',
        'version': '1.0.0',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/tailor/file', methods=['POST'])
def tailor_file():
    """
    文件上传模式定制简历

    请求:
        - resume: 简历文件
        - jd: JD 文件或文本
        - style: 输出样式（可选，默认 'original'）

    响应:
        - session_id: 会话ID
        - status: 状态
        - tailored_word: Word 文件（base64）
        - tailored_pdf: PDF 文件（base64，可选）
        - evidence_report: 依据报告
    """
    try:
        # 记录开始时间
        start_time = time.time()

        # 检查文件
        if 'resume' not in request.files:
            return jsonify({'error': '未上传简历文件'}), 400

        resume_file = request.files['resume']
        if resume_file.filename == '':
            return jsonify({'error': '未选择简历文件'}), 400

        if not allowed_file(resume_file.filename):
            return jsonify({'error': '不支持的简历格式'}), 400

        # 获取 JD
        jd_content = ''
        if 'jd' in request.files and request.files['jd'].filename != '':
            jd_file = request.files['jd']
            if allowed_file(jd_file.filename):
                jd_content = jd_file.read().decode('utf-8', errors='ignore')
        elif request.form.get('jd_text'):
            jd_content = request.form.get('jd_text', '')

        if not jd_content:
            return jsonify({'error': '未提供职位JD'}), 400

        # 生成会话ID
        session_id = str(uuid.uuid4())
        task_status[session_id] = {
            'status': 'processing',
            'progress': 0,
            'message': '正在解析简历...'
        }

        # 解析简历
        resume_content = resume_file.read()

        # 保存原始文件
        save_uploaded_bytes(resume_content, resume_file.filename, session_id)

        parsed_resume = parser.parse(
            file_content=resume_content,
            filename=resume_file.filename
        )

        # 模板预处理（仅 Word 格式）
        template_result = None
        original_doc = None
        if parsed_resume.source_format == 'word':
            task_status[session_id]['progress'] = 10
            task_status[session_id]['message'] = '正在提取模板样式...'
            try:
                from docx import Document
                import io as docx_io
                original_doc = Document(docx_io.BytesIO(resume_content))
                template_result = template_processor.preprocess(
                    original_doc,
                    resume_file.filename,
                    original_content=resume_content  # 传递原始内容用于去重
                )
                if template_result.success:
                    logger.info(f"模板预处理成功: {template_result.template_id}")
                else:
                    logger.warning(f"模板预处理失败: {template_result.error_message}")
            except Exception as e:
                logger.warning(f"模板预处理异常: {e}")

        task_status[session_id]['progress'] = 20
        task_status[session_id]['message'] = '正在分析JD需求...'

        # 检查缓存
        cached_result = cache_manager.get(parsed_resume.raw_text, jd_content)
        if cached_result:
            task_status[session_id]['progress'] = 80
            task_status[session_id]['message'] = '使用缓存结果...'
            logger.info(f"使用缓存结果: {session_id}")
            return jsonify(cached_result)

        # AI 定制
        task_status[session_id]['message'] = '正在AI分析...'
        analysis, generation = expert_team.tailor(
            parsed_resume.raw_text,
            jd_content
        )

        task_status[session_id]['progress'] = 60
        task_status[session_id]['message'] = '正在生成定制简历...'

        # 验证依据
        evidence_tracker = EvidenceTracker(expert_team.model_manager)
        evidence_report = evidence_tracker.validate_resume(
            parsed_resume.raw_text,
            generation.tailored_resume
        )

        task_status[session_id]['progress'] = 80
        task_status[session_id]['message'] = '正在生成文档...'

        # 生成文档
        style = request.form.get('style', 'original')
        output_format = request.form.get('format', 'word')  # word / ats_pdf
        style_preserved = False

        # ATS PDF 模式：使用 career-ops 风格的 ATS 优化输出
        if output_format == 'ats_pdf':
            task_status[session_id]['message'] = '正在生成 ATS 优化简历...'
            try:
                # Extract JD keywords for competency tags
                jd_keywords = analysis.matching_strategy.get('must_have_skills', [])
                if not jd_keywords:
                    jd_keywords = analysis.matching_strategy.get('strengths', [])

                ats_html_path = generator.generate_ats_html(
                    generation.tailored_resume,
                    jd_keywords=jd_keywords
                )
                ats_pdf_path = ats_html_path.replace('.html', '.pdf')

                # Use generate-pdf.mjs
                import subprocess as _subprocess
                pdf_tool = Path('tools/generate-pdf.mjs')
                if pdf_tool.exists():
                    proc = _subprocess.run(
                        ['node', str(pdf_tool), ats_html_path, ats_pdf_path, '--format=letter'],
                        capture_output=True, text=True, timeout=30
                    )
                    if proc.returncode == 0:
                        with open(ats_pdf_path, 'rb') as f:
                            ats_pdf_bytes = f.read()
                        task_status[session_id]['progress'] = 100
                        task_status[session_id]['status'] = 'completed'
                        task_status[session_id]['message'] = 'ATS 简历生成完成'

                        result = {
                            'session_id': session_id,
                            'status': 'completed',
                            'processing_time': int((time.time() - start_time) * 1000),
                            'tailored_word': '',  # ATS mode doesn't produce Word
                            'tailored_ats_pdf': base64.b64encode(ats_pdf_bytes).decode('utf-8'),
                            'evidence_report': evidence_report.to_dict(),
                            'validation_result': 'pass' if evidence_report.coverage >= 0.9 else 'pass_with_review',
                            'output_format': 'ats_pdf',
                            'style_preserved': False,
                            'analysis': {
                                'match_score': analysis.matching_strategy.get('match_score', 0),
                                'match_level': analysis.matching_strategy.get('match_level', ''),
                                'strengths': analysis.matching_strategy.get('strengths', []),
                                'gaps': analysis.matching_strategy.get('gaps', [])
                            }
                        }
                        cache_manager.set(parsed_resume.raw_text, jd_content, result)
                        return jsonify(result)
                    else:
                        logger.error(f"ATS PDF 生成失败: {proc.stderr}")
                else:
                    logger.warning("generate-pdf.mjs 不存在，回退到 Word 格式")
            except Exception as e:
                logger.error(f"ATS PDF 生成异常: {e}")
                logger.warning("回退到 Word 格式")

        # 优先使用模板渲染（Word 格式）
        if template_result and template_result.success and original_doc:
            task_status[session_id]['message'] = '正在应用原简历样式...'
            try:
                word_bytes, used_template = template_processor.render_with_fallback(
                    original_doc,
                    generation.tailored_resume,
                    parsed_resume.style_metadata,
                    resume_file.filename,
                    preprocess_result=template_result,
                    original_content=resume_content
                )
                style_preserved = used_template
                logger.info(f"文档生成完成，使用模板: {used_template}")
            except Exception as e:
                logger.warning(f"模板渲染失败，降级到样式方案: {e}")
                word_bytes = generator.generate_bytes(
                    generation.tailored_resume,
                    style_metadata=parsed_resume.style_metadata
                )
        else:
            # PDF/文本：使用样式元数据提取（已实现）
            word_bytes = generator.generate_bytes(
                generation.tailored_resume,
                style_metadata=parsed_resume.style_metadata
            )

        task_status[session_id]['progress'] = 100
        task_status[session_id]['status'] = 'completed'
        task_status[session_id]['message'] = '完成'

        # 构建响应
        processing_time_ms = int((time.time() - start_time) * 1000)
        result = {
            'session_id': session_id,
            'status': 'completed',
            'processing_time': processing_time_ms,
            'tailored_word': base64.b64encode(word_bytes).decode('utf-8'),
            'evidence_report': evidence_report.to_dict(),
            'validation_result': 'pass' if evidence_report.coverage >= 0.9 else 'pass_with_review',
            'style_preserved': style_preserved,  # 是否保留了原简历样式
            'style_info': {
                'font': parsed_resume.style_metadata.primary_font,
                'font_size': parsed_resume.style_metadata.body_font_size,
                'source': parsed_resume.style_metadata.source
            },
            'analysis': {
                'match_score': analysis.matching_strategy.get('match_score', 0),
                'match_level': analysis.matching_strategy.get('match_level', ''),
                'strengths': analysis.matching_strategy.get('strengths', []),
                'gaps': analysis.matching_strategy.get('gaps', [])
            }
        }

        # 缓存结果
        cache_manager.set(parsed_resume.raw_text, jd_content, result)

        # 保存定制后的文件
        save_tailored_file(word_bytes, session_id)

        # 保存历史记录
        job_title, company = parse_jd_info(jd_content)
        # 判断候选人类型：有工作经验为 experienced，否则为 entry_level
        has_experience = bool(parsed_resume.sections.get('work_experience'))
        db.save_history(session_id, {
            'candidate_name': parsed_resume.basic_info.get('name', ''),
            'candidate_type': 'experienced' if has_experience else 'entry_level',
            'job_title': job_title,
            'company': company,
            'match_score': analysis.matching_strategy.get('match_score', 0),
            'match_level': analysis.matching_strategy.get('match_level', ''),
            'original_resume': parsed_resume.raw_text,
            'tailored_resume': generation.tailored_resume,
            'jd_content': jd_content,
            'evidence_report': evidence_report.to_dict(),
            'optimization_summary': {
                'style_preserved': style_preserved,
                'source_format': parsed_resume.source_format
            },
            'model_used': expert_team.model_manager.current_model,
            'tokens_used': 0,  # TODO: 从模型响应中获取
            'processing_time_ms': processing_time_ms
        })

        return jsonify(result)

    except Exception as e:
        logger.error(f"文件定制失败: {e}", exc_info=True)  # 添加完整堆栈
        # 不要直接显示技术错误给用户
        error_str = str(e)
        if "resume_analysis" in error_str or "{" in error_str or "JSON" in error_str.upper():
            return jsonify({'error': 'AI响应解析失败，请重试'}), 500
        return jsonify({'error': str(e)}), 500


@app.route('/api/tailor/form', methods=['POST'])
def tailor_form():
    """
    引导输入模式定制简历

    请求:
        - JSON 格式的表单数据

    响应:
        - session_id: 会话ID
        - status: 状态
        - tailored_word: Word 文件（base64）
        - evidence_report: 依据报告
    """
    try:
        # 记录开始时间
        start_time = time.time()

        data = request.get_json()
        if not data:
            return jsonify({'error': '未提供表单数据'}), 400

        # 获取 JD
        jd_content = data.get('jd', '')
        if not jd_content:
            return jsonify({'error': '未提供职位JD'}), 400

        # 生成会话ID
        session_id = str(uuid.uuid4())
        task_status[session_id] = {
            'status': 'processing',
            'progress': 0,
            'message': '正在构建简历...'
        }

        # 构建简历
        resume_text = builder.build_from_form(data)

        task_status[session_id]['progress'] = 20
        task_status[session_id]['message'] = '正在分析JD需求...'

        # 检查缓存
        cached_result = cache_manager.get(resume_text, jd_content)
        if cached_result:
            task_status[session_id]['progress'] = 100
            task_status[session_id]['status'] = 'completed'
            logger.info(f"使用缓存结果: {session_id}")
            return jsonify(cached_result)

        # AI 定制
        task_status[session_id]['message'] = '正在AI分析...'
        analysis, generation = expert_team.tailor(resume_text, jd_content)

        task_status[session_id]['progress'] = 60
        task_status[session_id]['message'] = '正在验证依据...'

        # 验证依据
        evidence_tracker = EvidenceTracker(expert_team.model_manager)
        evidence_report = evidence_tracker.validate_resume(
            resume_text,
            generation.tailored_resume
        )

        task_status[session_id]['progress'] = 80
        task_status[session_id]['message'] = '正在生成文档...'

        # 生成文档（引导输入模式使用默认样式）
        word_bytes = generator.generate_bytes(generation.tailored_resume)

        task_status[session_id]['progress'] = 100
        task_status[session_id]['status'] = 'completed'
        task_status[session_id]['message'] = '完成'

        # 构建响应
        processing_time_ms = int((time.time() - start_time) * 1000)
        result = {
            'session_id': session_id,
            'status': 'completed',
            'processing_time': processing_time_ms,
            'tailored_word': base64.b64encode(word_bytes).decode('utf-8'),
            'evidence_report': evidence_report.to_dict(),
            'validation_result': 'pass' if evidence_report.coverage >= 0.9 else 'pass_with_review',
            'analysis': {
                'match_score': analysis.matching_strategy.get('match_score', 0),
                'match_level': analysis.matching_strategy.get('match_level', ''),
                'strengths': analysis.matching_strategy.get('strengths', []),
                'gaps': analysis.matching_strategy.get('gaps', [])
            }
        }

        # 缓存结果
        cache_manager.set(resume_text, jd_content, result)

        # 保存定制后的文件
        save_tailored_file(word_bytes, session_id)

        # 保存历史记录
        job_title, company = parse_jd_info(jd_content)
        # 从表单数据中获取基本信息
        basic_info = builder.build_structured(data).get('basic_info', {})
        # 判断候选人类型：有工作经验为 experienced，否则为 entry_level
        has_experience = bool(data.get('work_experience') or data.get('work_count', 0) > 0)
        db.save_history(session_id, {
            'candidate_name': basic_info.get('name', ''),
            'candidate_type': 'experienced' if has_experience else 'entry_level',
            'job_title': job_title,
            'company': company,
            'match_score': analysis.matching_strategy.get('match_score', 0),
            'match_level': analysis.matching_strategy.get('match_level', ''),
            'original_resume': resume_text,
            'tailored_resume': generation.tailored_resume,
            'jd_content': jd_content,
            'evidence_report': evidence_report.to_dict(),
            'optimization_summary': {
                'input_mode': 'guided'
            },
            'model_used': expert_team.model_manager.current_model,
            'tokens_used': 0,  # TODO: 从模型响应中获取
            'processing_time_ms': processing_time_ms
        })

        return jsonify(result)

    except Exception as e:
        logger.error(f"表单定制失败: {e}", exc_info=True)  # 添加完整堆栈
        # 不要直接显示技术错误给用户
        error_str = str(e)
        if "resume_analysis" in error_str or "{" in error_str or "JSON" in error_str.upper():
            return jsonify({'error': 'AI响应解析失败，请重试'}), 500
        return jsonify({'error': str(e)}), 500


@app.route('/api/status/<task_id>', methods=['GET'])
def get_status(task_id: str):
    """
    查询任务进度

    Args:
        task_id: 任务ID

    Returns:
        任务状态和进度
    """
    if task_id not in task_status:
        return jsonify({'error': '任务不存在'}), 404

    return jsonify(task_status[task_id])


@app.route('/api/preview', methods=['POST'])
def preview():
    """
    实时预览简历

    请求:
        - JSON 格式的表单数据

    响应:
        - preview_text: 预览文本
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '未提供数据'}), 400

        resume_text = builder.build_from_form(data)

        return jsonify({
            'preview_text': resume_text
        })

    except Exception as e:
        logger.error(f"预览失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/history', methods=['GET'])
def get_history():
    """
    获取历史记录列表

    查询参数:
        - limit: 返回数量限制（默认50）
        - offset: 偏移量（默认0）

    响应:
        - history: 历史记录列表
        - total: 总数
    """
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)

        history_list = db.get_history_list(limit=limit, offset=offset)
        total = db.get_history_count()

        return jsonify({
            'history': history_list,
            'total': total
        })

    except Exception as e:
        logger.error(f"获取历史记录失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/history/<history_id>', methods=['GET'])
def get_history_item(history_id: str):
    """
    获取特定历史记录详情

    参数:
        - history_id: 会话ID（session_id）

    响应:
        - 完整的历史记录详情
    """
    try:
        item = db.get_history(history_id)
        if item:
            return jsonify(item)
        return jsonify({'error': '记录不存在'}), 404

    except Exception as e:
        logger.error(f"获取历史记录详情失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/history/<history_id>', methods=['DELETE'])
def delete_history_item(history_id: str):
    """
    删除历史记录

    参数:
        - history_id: 会话ID（session_id）

    响应:
        - success: 是否成功
    """
    try:
        success = db.delete_history(history_id)
        if success:
            return jsonify({'success': True})
        return jsonify({'error': '删除失败，记录不存在'}), 404

    except Exception as e:
        logger.error(f"删除历史记录失败: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== 用户配置 API ====================

@app.route('/api/config', methods=['GET'])
def get_config():
    """
    获取用户配置

    响应:
        - 配置字典
    """
    try:
        config_data = db.get_all_config()
        return jsonify(config_data)

    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/config', methods=['POST'])
def save_config():
    """
    保存用户配置

    请求:
        - JSON 格式的配置键值对

    响应:
        - success: 是否成功
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '未提供配置数据'}), 400

        for key, value in data.items():
            db.save_config(key, str(value) if value is not None else '')

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"保存配置失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/config/<key>', methods=['DELETE'])
@login_required
def delete_config(key: str):
    """
    删除用户配置

    参数:
        - key: 配置键

    响应:
        - success: 是否成功
    """
    try:
        success = db.delete_config(key)
        return jsonify({'success': success})

    except Exception as e:
        logger.error(f"删除配置失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """
    获取系统统计信息
    """
    return jsonify({
        'model_stats': expert_team.get_stats(),
        'cache_stats': cache_manager.get_stats(),
        'parser_stats': parser.get_stats()
    })


if __name__ == '__main__':
    # 验证配置
    try:
        config.validate()
    except ValueError as e:
        logger.error(f"配置验证失败: {e}")
        print(f"错误: {e}")
        print("请确保已设置 ZHIPU_API_KEY 环境变量或 .env 文件")
        exit(1)

    # 启动服务
    app.run(host='0.0.0.0', port=5000, debug=True)
