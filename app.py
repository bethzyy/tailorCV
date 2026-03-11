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
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

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

# 任务状态存储（简单实现，生产环境应使用 Redis）
task_status: Dict[str, Dict[str, Any]] = {}


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
        parsed_resume = parser.parse(
            file_content=resume_content,
            filename=resume_file.filename
        )

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
        word_bytes = generator.generate_bytes(generation.tailored_resume)

        task_status[session_id]['progress'] = 100
        task_status[session_id]['status'] = 'completed'
        task_status[session_id]['message'] = '完成'

        # 构建响应
        result = {
            'session_id': session_id,
            'status': 'completed',
            'processing_time': 0,  # TODO: 计算实际时间
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
        cache_manager.set(parsed_resume.raw_text, jd_content, result)

        return jsonify(result)

    except Exception as e:
        logger.error(f"文件定制失败: {e}")
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

        # 生成文档
        word_bytes = generator.generate_bytes(generation.tailored_resume)

        task_status[session_id]['progress'] = 100
        task_status[session_id]['status'] = 'completed'
        task_status[session_id]['message'] = '完成'

        # 构建响应
        result = {
            'session_id': session_id,
            'status': 'completed',
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

        return jsonify(result)

    except Exception as e:
        logger.error(f"表单定制失败: {e}")
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

    TODO: 实现数据库存储
    """
    return jsonify({
        'history': [],
        'message': '历史记录功能开发中'
    })


@app.route('/api/history/<history_id>', methods=['GET'])
def get_history_item(history_id: str):
    """
    获取特定历史记录

    TODO: 实现数据库存储
    """
    return jsonify({
        'error': '历史记录功能开发中'
    }), 404


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
