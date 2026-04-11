"""
多模型工具 Flask 应用

多模型并行生成，结果对比。
独立启动入口，端口 5002。
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
from typing import Dict, Any, Tuple, List

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

# 添加父目录到路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import config
from core.multi_model_manager import MultiModelManager
from core.multi_expert_team import MultiExpertTeam, MultiModelAnalysisResult, MultiModelGenerationResult
from core.resume_parser import ResumeParser
from core.resume_builder import ResumeBuilder
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
    """创建多模型工具 Flask 应用"""
    app = Flask(__name__,
                template_folder='../web/templates/multi',
                static_folder='../web/static')

    app.config['SECRET_KEY'] = config.SECRET_KEY
    app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH
    CORS(app)

    # 初始化组件
    multi_manager = MultiModelManager()
    multi_team = MultiExpertTeam(multi_manager)
    parser = ResumeParser()
    builder = ResumeBuilder()
    generator = ResumeGenerator()
    cache_manager = CacheManager()
    template_processor = TemplateProcessor()

    # 任务状态存储
    task_status: Dict[str, Dict[str, Any]] = {}

    # ==================== 辅助函数 ====================

    def save_uploaded_bytes(content: bytes, filename: str, session_id: str) -> str:
        upload_dir = Path('storage/uploads') / session_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        ext = Path(filename).suffix.lower()
        file_path = upload_dir / f'original{ext}'
        try:
            with open(file_path, 'wb') as f:
                f.write(content)
        except IOError as e:
            logger.error(f"保存上传文件失败: {e}")
            raise
        return str(file_path)

    def save_multi_result(content: bytes, session_id: str, provider_id: str) -> str:
        output_dir = Path('storage/multi_results') / session_id
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / f'{provider_id}_tailored.docx'
        try:
            with open(file_path, 'wb') as f:
                f.write(content)
        except IOError as e:
            logger.error(f"保存多模型结果失败: {e}")
            raise
        return str(file_path)

    def allowed_file(filename: str) -> bool:
        allowed_extensions = {'.pdf', '.docx', '.doc', '.txt', '.md'}
        return Path(filename).suffix.lower() in allowed_extensions

    # ==================== 路由 ====================

    @app.route('/')
    def index():
        """多模型工具主页"""
        providers = multi_manager.available_providers
        models = multi_manager.available_models
        return render_template('index.html', providers=providers, models=models)

    @app.route('/compare')
    def compare():
        """结果对比页面"""
        return render_template('compare.html')

    @app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({
            'status': 'healthy',
            'version': '1.0.0',
            'mode': 'multi',
            'providers': multi_manager.available_providers,
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

    @app.route('/api/providers', methods=['GET'])
    def get_providers():
        """获取可用的模型提供者"""
        return jsonify({
            'providers': multi_manager.available_providers,
            'models': multi_manager.available_models
        })

    @app.route('/api/tailor/file', methods=['POST'])
    def tailor_file():
        """
        文件上传模式 - 多模型并行

        请求:
            - resume: 简历文件
            - jd: JD 文件或文本
            - providers: 要使用的提供者列表（可选，JSON数组）
        """
        try:
            start_time = time.time()

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

            # 获取要使用的提供者
            provider_ids = None
            if request.form.get('providers'):
                try:
                    provider_ids = json.loads(request.form.get('providers'))
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"providers 参数 JSON 解析失败: {request.form.get('providers')[:100]}")

            session_id = str(uuid.uuid4())
            task_status[session_id] = {
                'status': 'processing',
                'progress': 0,
                'message': '正在解析简历...'
            }

            # 解析简历
            resume_content = resume_file.read()
            save_uploaded_bytes(resume_content, resume_file.filename, session_id)

            parsed_resume = parser.parse(
                file_content=resume_content,
                filename=resume_file.filename
            )

            task_status[session_id]['progress'] = 20
            task_status[session_id]['message'] = '正在多模型并行分析...'

            # 多模型并行定制
            analysis_result, generation_result = multi_team.tailor_parallel(
                parsed_resume.raw_text,
                jd_content,
                provider_ids=provider_ids
            )

            if not generation_result.success:
                return jsonify({'error': '所有模型生成失败'}), 500

            task_status[session_id]['progress'] = 80
            task_status[session_id]['message'] = '正在生成文档...'

            # 生成各模型的结果文档
            results = {}
            for provider_id, gen_result in generation_result.results.items():
                word_bytes = generator.generate_bytes(
                    gen_result.tailored_resume,
                    style_metadata=parsed_resume.style_metadata
                )

                save_multi_result(word_bytes, session_id, provider_id)

                # 修复: 仅返回文件引用，不返回 base64 编码的文件内容
                results[provider_id] = {
                    'model_used': gen_result.model_used,
                    'provider_id': provider_id,
                    'file_path': f'/api/download/{session_id}/{provider_id}',
                    'analysis': {
                        'match_score': analysis_result.results.get(provider_id, {}).matching_strategy.get('match_score', 0) if provider_id in analysis_result.results else 0,
                        'match_level': analysis_result.results.get(provider_id, {}).matching_strategy.get('match_level', '') if provider_id in analysis_result.results else '',
                    },
                    'tokens_used': gen_result.tokens_used
                }

            task_status[session_id]['progress'] = 100
            task_status[session_id]['status'] = 'completed'

            processing_time_ms = int((time.time() - start_time) * 1000)

            return jsonify({
                'session_id': session_id,
                'status': 'completed',
                'processing_time': processing_time_ms,
                'providers_used': list(results.keys()),
                'results': results,
                'best_provider': list(results.keys())[0] if results else None
            })

        except Exception as e:
            logger.error(f"多模型定制失败: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    @app.route('/api/tailor/single', methods=['POST'])
    def tailor_single():
        """
        单模型定制（指定提供者）

        请求:
            - resume: 简历文件
            - jd: JD 文件或文本
            - provider_id: 提供者ID
        """
        try:
            start_time = time.time()

            if 'resume' not in request.files:
                return jsonify({'error': '未上传简历文件'}), 400

            resume_file = request.files['resume']
            provider_id = request.form.get('provider_id', 'zhipu')

            jd_content = ''
            if 'jd' in request.files and request.files['jd'].filename != '':
                jd_content = request.files['jd'].read().decode('utf-8', errors='ignore')
            elif request.form.get('jd_text'):
                jd_content = request.form.get('jd_text', '')

            if not jd_content:
                return jsonify({'error': '未提供职位JD'}), 400

            session_id = str(uuid.uuid4())

            # 解析简历
            resume_content = resume_file.read()
            parsed_resume = parser.parse(
                file_content=resume_content,
                filename=resume_file.filename
            )

            # 单模型定制
            analysis, generation = multi_team.tailor_single(
                parsed_resume.raw_text,
                jd_content,
                provider_id=provider_id
            )

            # 生成文档
            word_bytes = generator.generate_bytes(
                generation.tailored_resume,
                style_metadata=parsed_resume.style_metadata
            )

            save_multi_result(word_bytes, session_id, provider_id)

            processing_time_ms = int((time.time() - start_time) * 1000)

            # 修复: 仅返回文件引用，不返回 base64 编码的文件内容
            return jsonify({
                'session_id': session_id,
                'status': 'completed',
                'processing_time': processing_time_ms,
                'provider_id': provider_id,
                'model_used': generation.model_used,
                'file_path': f'/api/download/{session_id}/{provider_id}',
                'analysis': {
                    'match_score': analysis.matching_strategy.get('match_score', 0),
                    'match_level': analysis.matching_strategy.get('match_level', ''),
                    'strengths': analysis.matching_strategy.get('strengths', []),
                    'gaps': analysis.matching_strategy.get('gaps', [])
                }
            })

        except Exception as e:
            logger.error(f"单模型定制失败: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    @app.route('/api/status/<task_id>', methods=['GET'])
    def get_status(task_id: str):
        if task_id not in task_status:
            return jsonify({'error': '任务不存在'}), 404
        return jsonify(task_status[task_id])

    @app.route('/api/stats', methods=['GET'])
    def get_stats():
        return jsonify({
            'multi_team_stats': multi_team.get_stats(),
            'manager_stats': multi_manager.get_stats(),
            'cache_stats': cache_manager.get_stats()
        })

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=config.MULTI_APP_PORT, debug=True)
