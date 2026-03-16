"""
简版工具 Flask 应用

单模型（智谱）快速生成简历定制工具。
独立启动入口，端口 5001。
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

# 添加父目录到路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import config
from core.providers.zhipu_provider import ZhipuProvider
from core.model_manager import ModelManager
from core.resume_parser import ResumeParser, ParsedResume
from core.resume_builder import ResumeBuilder
from core.expert_team import ExpertTeam, AnalysisResult, GenerationResult
from core.evidence_tracker import EvidenceTracker
from core.resume_generator import ResumeGenerator
from core.cache_manager import CacheManager
from core.template_processor import TemplateProcessor
from core.database import db

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """创建简版工具 Flask 应用"""
    app = Flask(__name__,
                template_folder='../web/templates/simple',
                static_folder='../web/static')

    app.config['SECRET_KEY'] = config.SECRET_KEY
    app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH
    CORS(app)

    # 初始化组件
    provider = ZhipuProvider()
    model_manager = ModelManager(provider)
    parser = ResumeParser()
    builder = ResumeBuilder()
    expert_team = ExpertTeam(model_manager)
    generator = ResumeGenerator()
    cache_manager = CacheManager()
    template_processor = TemplateProcessor()

    # 任务状态存储
    task_status: Dict[str, Dict[str, Any]] = {}

    # ==================== 辅助函数 ====================

    def save_uploaded_file(file, session_id: str) -> str:
        upload_dir = Path('storage/uploads') / session_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        ext = Path(file.filename).suffix.lower()
        file_path = upload_dir / f'original{ext}'
        file.save(str(file_path))
        return str(file_path)

    def save_uploaded_bytes(content: bytes, filename: str, session_id: str) -> str:
        upload_dir = Path('storage/uploads') / session_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        ext = Path(filename).suffix.lower()
        file_path = upload_dir / f'original{ext}'
        with open(file_path, 'wb') as f:
            f.write(content)
        return str(file_path)

    def save_tailored_file(content: bytes, session_id: str) -> str:
        output_dir = Path('storage/tailored') / session_id
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / 'tailored.docx'
        with open(file_path, 'wb') as f:
            f.write(content)
        return str(file_path)

    def parse_jd_info(jd_content: str) -> Tuple[str, str]:
        job_title = ''
        company = ''
        lines = jd_content.strip().split('\n')
        for line in lines[:10]:
            line = line.strip()
            if not line:
                continue
            if any(kw in line for kw in ['职位', '岗位', '招聘', 'Job Title']):
                if '：' in line:
                    job_title = line.split('：')[-1].strip()
                elif ':' in line:
                    job_title = line.split(':')[-1].strip()
            if any(kw in line for kw in ['公司', '企业', 'Company']):
                if '：' in line:
                    company = line.split('：')[-1].strip()
        if not job_title and lines:
            first_line = lines[0].strip()
            if len(first_line) < 100:
                job_title = first_line
        return job_title[:100] if job_title else '', company[:50] if company else ''

    def allowed_file(filename: str) -> bool:
        allowed_extensions = {'.pdf', '.docx', '.doc', '.txt', '.md'}
        return Path(filename).suffix.lower() in allowed_extensions

    # ==================== 路由 ====================

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/guided')
    def guided_input():
        return render_template('guided_input.html')

    @app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({
            'status': 'healthy',
            'version': '1.0.0',
            'mode': 'simple',
            'provider': 'zhipu',
            'timestamp': datetime.now().isoformat()
        })

    @app.route('/api/shutdown', methods=['POST'])
    def shutdown():
        """关闭服务（由主服务器调用）"""
        import threading
        import os

        def do_shutdown():
            time.sleep(1)
            os._exit(0)

        logger.info("Received shutdown request")
        threading.Thread(target=do_shutdown, daemon=True).start()
        return jsonify({'status': 'shutting_down'})

    @app.route('/api/tailor/file', methods=['POST'])
    def tailor_file():
        try:
            start_time = time.time()

            if 'resume' not in request.files:
                return jsonify({'error': '未上传简历文件'}), 400

            resume_file = request.files['resume']
            if resume_file.filename == '':
                return jsonify({'error': '未选择简历文件'}), 400

            if not allowed_file(resume_file.filename):
                return jsonify({'error': '不支持的简历格式'}), 400

            jd_content = ''
            if 'jd' in request.files and request.files['jd'].filename != '':
                jd_file = request.files['jd']
                if allowed_file(jd_file.filename):
                    jd_content = jd_file.read().decode('utf-8', errors='ignore')
            elif request.form.get('jd_text'):
                jd_content = request.form.get('jd_text', '')

            if not jd_content:
                return jsonify({'error': '未提供职位JD'}), 400

            session_id = str(uuid.uuid4())
            task_status[session_id] = {'status': 'processing', 'progress': 0, 'message': '正在解析简历...'}

            resume_content = resume_file.read()
            save_uploaded_bytes(resume_content, resume_file.filename, session_id)

            parsed_resume = parser.parse(
                file_content=resume_content,
                filename=resume_file.filename
            )

            template_result = None
            original_doc = None
            if parsed_resume.source_format == 'word':
                task_status[session_id]['progress'] = 10
                task_status[session_id]['message'] = '正在提取模板样式...'
                try:
                    from docx import Document
                    original_doc = Document(io.BytesIO(resume_content))
                    template_result = template_processor.preprocess(
                        original_doc,
                        resume_file.filename,
                        original_content=resume_content
                    )
                except Exception as e:
                    logger.warning(f"模板预处理异常: {e}")

            task_status[session_id]['progress'] = 20
            task_status[session_id]['message'] = '正在分析JD需求...'

            cached_result = cache_manager.get(parsed_resume.raw_text, jd_content)
            if cached_result:
                task_status[session_id]['progress'] = 100
                task_status[session_id]['status'] = 'completed'
                return jsonify(cached_result)

            task_status[session_id]['message'] = '正在AI分析...'
            analysis, generation = expert_team.tailor(
                parsed_resume.raw_text,
                jd_content
            )

            task_status[session_id]['progress'] = 60
            task_status[session_id]['message'] = '正在验证依据...'

            evidence_tracker = EvidenceTracker(model_manager)
            evidence_report = evidence_tracker.validate_resume(
                parsed_resume.raw_text,
                generation.tailored_resume
            )

            task_status[session_id]['progress'] = 80
            task_status[session_id]['message'] = '正在生成文档...'

            style = request.form.get('style', 'original')
            style_preserved = False

            if template_result and template_result.success and original_doc:
                try:
                    word_bytes, used_template = template_processor.render_with_fallback(
                        original_doc,
                        generation.tailored_resume,
                        parsed_resume.style_metadata,
                        resume_file.filename
                    )
                    style_preserved = used_template
                except Exception as e:
                    logger.warning(f"模板渲染失败: {e}")
                    word_bytes = generator.generate_bytes(
                        generation.tailored_resume,
                        style_metadata=parsed_resume.style_metadata
                    )
            else:
                word_bytes = generator.generate_bytes(
                    generation.tailored_resume,
                    style_metadata=parsed_resume.style_metadata
                )

            task_status[session_id]['progress'] = 100
            task_status[session_id]['status'] = 'completed'

            processing_time_ms = int((time.time() - start_time) * 1000)
            result = {
                'session_id': session_id,
                'status': 'completed',
                'processing_time': processing_time_ms,
                'tailored_word': base64.b64encode(word_bytes).decode('utf-8'),
                'evidence_report': evidence_report.to_dict(),
                'validation_result': 'pass' if evidence_report.coverage >= 0.9 else 'pass_with_review',
                'style_preserved': style_preserved,
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

            cache_manager.set(parsed_resume.raw_text, jd_content, result)
            save_tailored_file(word_bytes, session_id)

            job_title, company = parse_jd_info(jd_content)
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
                'optimization_summary': {'style_preserved': style_preserved},
                'model_used': model_manager.current_model,
                'tokens_used': 0,
                'processing_time_ms': processing_time_ms
            })

            return jsonify(result)

        except Exception as e:
            logger.error(f"文件定制失败: {e}", exc_info=True)
            error_str = str(e)
            if "resume_analysis" in error_str or "{" in error_str:
                return jsonify({'error': 'AI响应解析失败，请重试'}), 500
            return jsonify({'error': str(e)}), 500

    @app.route('/api/tailor/form', methods=['POST'])
    def tailor_form():
        try:
            start_time = time.time()

            data = request.get_json()
            if not data:
                return jsonify({'error': '未提供表单数据'}), 400

            jd_content = data.get('jd', '')
            if not jd_content:
                return jsonify({'error': '未提供职位JD'}), 400

            session_id = str(uuid.uuid4())
            task_status[session_id] = {'status': 'processing', 'progress': 0, 'message': '正在构建简历...'}

            resume_text = builder.build_from_form(data)

            task_status[session_id]['progress'] = 20
            task_status[session_id]['message'] = '正在分析JD需求...'

            cached_result = cache_manager.get(resume_text, jd_content)
            if cached_result:
                task_status[session_id]['progress'] = 100
                task_status[session_id]['status'] = 'completed'
                return jsonify(cached_result)

            task_status[session_id]['message'] = '正在AI分析...'
            analysis, generation = expert_team.tailor(resume_text, jd_content)

            task_status[session_id]['progress'] = 60
            task_status[session_id]['message'] = '正在验证依据...'

            evidence_tracker = EvidenceTracker(model_manager)
            evidence_report = evidence_tracker.validate_resume(
                resume_text,
                generation.tailored_resume
            )

            task_status[session_id]['progress'] = 80
            task_status[session_id]['message'] = '正在生成文档...'

            word_bytes = generator.generate_bytes(generation.tailored_resume)

            task_status[session_id]['progress'] = 100
            task_status[session_id]['status'] = 'completed'

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

            cache_manager.set(resume_text, jd_content, result)
            save_tailored_file(word_bytes, session_id)

            job_title, company = parse_jd_info(jd_content)
            basic_info = builder.build_structured(data).get('basic_info', {})
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
                'optimization_summary': {'input_mode': 'guided'},
                'model_used': model_manager.current_model,
                'tokens_used': 0,
                'processing_time_ms': processing_time_ms
            })

            return jsonify(result)

        except Exception as e:
            logger.error(f"表单定制失败: {e}", exc_info=True)
            error_str = str(e)
            if "resume_analysis" in error_str or "{" in error_str:
                return jsonify({'error': 'AI响应解析失败，请重试'}), 500
            return jsonify({'error': str(e)}), 500

    @app.route('/api/status/<task_id>', methods=['GET'])
    def get_status(task_id: str):
        if task_id not in task_status:
            return jsonify({'error': '任务不存在'}), 404
        return jsonify(task_status[task_id])

    @app.route('/api/preview', methods=['POST'])
    def preview():
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': '未提供数据'}), 400
            resume_text = builder.build_from_form(data)
            return jsonify({'preview_text': resume_text})
        except Exception as e:
            logger.error(f"预览失败: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/stats', methods=['GET'])
    def get_stats():
        return jsonify({
            'model_stats': expert_team.get_stats(),
            'cache_stats': cache_manager.get_stats(),
            'parser_stats': parser.get_stats()
        })

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=config.SIMPLE_APP_PORT, debug=True)
