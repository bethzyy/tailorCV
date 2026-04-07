"""
AI 专家团队模块

支持两种架构：
1. ExpertTeam: 两阶段调用（兼容旧版）
2. ExpertTeamV2: 五阶段调用（新版，提升定制质量）

五阶段流程：
- 阶段0: 简历结构解析 (parse_resume)
- 阶段1: JD深度解码 (decode_jd)
- 阶段2: 匹配度分析 (match_analysis)
- 阶段3: 内容深度改写 (rewrite_content)
- 阶段4: 质量验证 (quality_check)

支持依赖注入，可接受不同的模型管理器。
"""

import json
import logging
import re
import threading
import time
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional, Tuple, List, Callable, TYPE_CHECKING
from pathlib import Path
from dataclasses import dataclass, field

from .config import config
from .match_scorer import MatchScorer, MatchScoreResult
from . import response_parser

if TYPE_CHECKING:
    from .model_manager import ModelManager

logger = logging.getLogger(__name__)


# ==================== 旧版数据类（兼容） ====================

@dataclass
class AnalysisResult:
    """分析阶段结果（旧版兼容）"""
    resume_analysis: Dict[str, Any] = field(default_factory=dict)
    jd_requirements: Dict[str, Any] = field(default_factory=dict)
    matching_strategy: Dict[str, Any] = field(default_factory=dict)
    raw_response: str = ""
    model_used: str = ""
    tokens_used: int = 0


@dataclass
class GenerationResult:
    """生成阶段结果（旧版兼容）"""
    tailored_resume: Dict[str, Any] = field(default_factory=dict)
    evidence_report: Dict[str, Any] = field(default_factory=dict)
    optimization_summary: Dict[str, Any] = field(default_factory=dict)
    raw_response: str = ""
    model_used: str = ""
    tokens_used: int = 0


# ==================== 新版数据类（五阶段） ====================

@dataclass
class StageResult:
    """单个阶段结果基类"""
    raw_response: str = ""
    model_used: str = ""
    tokens_used: int = 0
    success: bool = True
    error: str = ""


@dataclass
class ParseResumeResult(StageResult):
    """阶段0: 简历结构解析结果"""
    basic_info: Dict[str, Any] = field(default_factory=dict)
    education: List[Dict[str, Any]] = field(default_factory=list)
    work_experience: List[Dict[str, Any]] = field(default_factory=list)
    projects: List[Dict[str, Any]] = field(default_factory=list)
    skills: Dict[str, Any] = field(default_factory=dict)
    awards: List[str] = field(default_factory=list)           # 新增: 奖项
    certificates: List[str] = field(default_factory=list)     # 新增: 证书
    self_evaluation: str = ""                                  # 新增: 自我评价
    raw_materials: Dict[str, Any] = field(default_factory=dict)
    parsing_confidence: float = 0.0


@dataclass
class DecodeJdResult(StageResult):
    """阶段1: JD深度解码结果"""
    job_title: str = ""
    company_overview: str = ""
    salary_range: str = ""  # 新增: 薪资范围
    must_have: Dict[str, Any] = field(default_factory=dict)
    nice_to_have: Dict[str, Any] = field(default_factory=dict)
    implicit_requirements: List[Dict[str, Any]] = field(default_factory=list)
    keyword_weights: Dict[str, int] = field(default_factory=dict)
    success_indicators: List[str] = field(default_factory=list)
    red_flags: List[str] = field(default_factory=list)
    pain_points: List[Dict[str, Any]] = field(default_factory=list)
    competitor_profile: Dict[str, Any] = field(default_factory=dict)  # 新增: 竞争者画像


@dataclass
class MatchAnalysisResult(StageResult):
    """阶段2: 匹配度分析结果"""
    match_score: int = 0
    match_level: str = ""
    rewrite_intensity: str = "L1"
    strengths: List[Dict[str, Any]] = field(default_factory=list)
    gaps: List[Dict[str, Any]] = field(default_factory=list)
    fatal_flaws: List[Dict[str, Any]] = field(default_factory=list)
    highlight_opportunities: List[Dict[str, Any]] = field(default_factory=list)
    rewrite_strategy: Dict[str, Any] = field(default_factory=dict)
    content_to_emphasize: List[str] = field(default_factory=list)
    content_to_weaken: List[str] = field(default_factory=list)
    recruiter_tips: List[str] = field(default_factory=list)
    differentiation_strategy: Dict[str, Any] = field(default_factory=dict)
    # 新增：分数计算详情
    score_breakdown: Dict[str, int] = field(default_factory=dict)
    requirements_analysis: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RewriteContentResult(StageResult):
    """阶段3: 内容深度改写结果"""
    tailored_resume: Dict[str, Any] = field(default_factory=dict)
    change_log: List[Dict[str, Any]] = field(default_factory=list)
    keyword_coverage: Dict[str, Any] = field(default_factory=dict)
    jd_keyword_coverage: Dict[str, Any] = field(default_factory=dict)  # JD关键词覆盖率验证结果
    # Writer-Reviewer 闭环元数据
    review_iterations: int = 0
    review_scores: List[Dict[str, Any]] = field(default_factory=list)
    review_feedback_summary: str = ""
    review_stop_reason: str = ""


@dataclass
class QualityCheckResult(StageResult):
    """阶段4: 质量验证结果"""
    overall_score: int = 0
    score_breakdown: Dict[str, int] = field(default_factory=dict)
    keyword_coverage: Dict[str, Any] = field(default_factory=dict)
    authenticity_check: Dict[str, Any] = field(default_factory=dict)
    improvement_analysis: Dict[str, Any] = field(default_factory=dict)
    recruiter_feedback: Dict[str, Any] = field(default_factory=dict)
    evidence_validation: List[Dict[str, Any]] = field(default_factory=list)
    final_verdict: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TailorResultV2:
    """五阶段完整定制结果"""
    # 各阶段结果
    parse_result: ParseResumeResult = None
    decode_result: DecodeJdResult = None
    match_result: MatchAnalysisResult = None
    rewrite_result: RewriteContentResult = None
    quality_result: QualityCheckResult = None

    # 汇总信息
    total_tokens: int = 0
    total_latency_ms: int = 0
    models_used: List[str] = field(default_factory=list)

    # 最终输出（兼容旧版接口）
    tailored_resume: Dict[str, Any] = field(default_factory=dict)
    evidence_report: Dict[str, Any] = field(default_factory=dict)
    optimization_summary: Dict[str, Any] = field(default_factory=dict)

    # 新增分析信息
    analysis: Dict[str, Any] = field(default_factory=dict)


# ==================== 旧版 ExpertTeam（兼容） ====================

class ExpertTeam:
    """AI 专家团队 - 两阶段调用（旧版兼容）"""

    def __init__(self, model_manager: 'ModelManager' = None):
        """
        初始化专家团队

        Args:
            model_manager: 模型管理器（可选，默认自动创建）
        """
        if model_manager is None:
            from .model_manager import ModelManager
            model_manager = ModelManager()

        self.model_manager = model_manager

        # 加载 Prompt 模板
        self.prompts_dir = config.BASE_DIR / 'prompts'
        self.analyze_prompt = self._load_prompt('analyze_prompt.txt')
        self.generate_prompt = self._load_prompt('generate_prompt.txt')

        # 调用统计
        self.stats = {
            'analyze_calls': 0,
            'generate_calls': 0,
            'total_tokens': 0,
            'total_latency_ms': 0
        }

    def _load_prompt(self, filename: str) -> str:
        """加载 Prompt 模板"""
        filepath = self.prompts_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Prompt 文件不存在: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()

    def analyze(self, resume_content: str, jd_content: str) -> AnalysisResult:
        """
        阶段1: 分析+策略

        Args:
            resume_content: 原版简历内容
            jd_content: 职位JD内容

        Returns:
            AnalysisResult: 分析结果
        """
        self.stats['analyze_calls'] += 1
        logger.info("开始阶段1: 分析+策略")

        # 构建 Prompt
        prompt = self.analyze_prompt.format(
            resume_content=resume_content,
            jd_content=jd_content
        )

        # 调用模型
        response = self.model_manager.call(
            prompt=prompt,
            task_type='analyze',
            max_tokens=4096,
            temperature=0.3  # 分析任务使用较低温度
        )

        if not response.success:
            raise RuntimeError(f"分析阶段失败: {response.error_message}")

        self.stats['total_tokens'] += response.tokens_used
        self.stats['total_latency_ms'] += response.latency_ms

        # 解析结果
        result = self._parse_analysis_response(response.content)
        result.raw_response = response.content
        result.model_used = response.model_id
        result.tokens_used = response.tokens_used

        logger.info(f"阶段1完成: model={response.model_id}, tokens={response.tokens_used}")
        return result

    def generate(self, analysis_result: AnalysisResult,
                 original_resume: str, jd_content: str) -> GenerationResult:
        """
        阶段2: 生成+自验证

        Args:
            analysis_result: 阶段1分析结果
            original_resume: 原版简历
            jd_content: 职位JD

        Returns:
            GenerationResult: 生成结果
        """
        self.stats['generate_calls'] += 1
        logger.info("开始阶段2: 生成+自验证")

        # 序列化分析结果
        analysis_json = json.dumps({
            'resume_analysis': analysis_result.resume_analysis,
            'jd_requirements': analysis_result.jd_requirements,
            'matching_strategy': analysis_result.matching_strategy
        }, ensure_ascii=False, indent=2)

        # 构建 Prompt
        prompt = self.generate_prompt.format(
            analysis_result=analysis_json,
            original_resume=original_resume,
            jd_content=jd_content
        )

        # 调用模型
        response = self.model_manager.call(
            prompt=prompt,
            task_type='generate',
            max_tokens=6144,  # 生成任务需要更多 token
            temperature=0.5
        )

        if not response.success:
            raise RuntimeError(f"生成阶段失败: {response.error_message}")

        self.stats['total_tokens'] += response.tokens_used
        self.stats['total_latency_ms'] += response.latency_ms

        # 解析结果
        result = self._parse_generation_response(response.content)
        result.raw_response = response.content
        result.model_used = response.model_id
        result.tokens_used = response.tokens_used

        logger.info(f"阶段2完成: model={response.model_id}, tokens={response.tokens_used}")
        return result

    def tailor(self, resume_content: str, jd_content: str) -> Tuple[AnalysisResult, GenerationResult]:
        """
        完整定制流程

        Args:
            resume_content: 原版简历
            jd_content: 职位JD

        Returns:
            Tuple[AnalysisResult, GenerationResult]: 分析结果和生成结果
        """
        logger.info("开始完整定制流程")

        # 阶段1: 分析
        analysis = self.analyze(resume_content, jd_content)

        # 阶段2: 生成
        generation = self.generate(analysis, resume_content, jd_content)

        logger.info(f"定制流程完成: 总tokens={self.stats['total_tokens']}")
        return analysis, generation

    def _parse_analysis_response(self, response: str) -> AnalysisResult:
        """解析分析阶段响应 - 增强版fallback机制

        确保所有异常都被捕获，永远返回有效的 AnalysisResult 对象
        """
        result = AnalysisResult()

        try:
            # 多级JSON提取策略
            json_str = None
            extraction_method = None

            # Level 1: 尝试匹配 ```json ... ``` 格式
            json_pattern = r'```json\s*([\s\S]*?)\s*```'
            match = re.search(json_pattern, response)
            if match:
                json_str = match.group(1)
                extraction_method = 'code_block'

            # Level 2: 尝试匹配 { ... } 格式（非贪婪）
            if not json_str:
                # 使用栈匹配来正确处理嵌套JSON
                json_str = self._extract_balanced_json(response)
                if json_str:
                    extraction_method = 'balanced'

            # Level 3: 尝试正则匹配（兜底）
            if not json_str:
                json_pattern = r'\{[\s\S]*\}'
                match = re.search(json_pattern, response)
                if match:
                    json_str = match.group(0)
                    extraction_method = 'regex'

            if json_str:
                try:
                    data = json.loads(json_str)
                    logger.info(f"JSON解析成功 (方法: {extraction_method})")

                    # 安全获取各字段，带完整默认值
                    result.resume_analysis = self._safe_get_dict(data, 'resume_analysis')
                    result.jd_requirements = self._safe_get_dict(data, 'jd_requirements')
                    result.matching_strategy = self._safe_get_dict(data, 'matching_strategy')

                    # 验证关键字段
                    self._validate_analysis_result(result)

                except json.JSONDecodeError as e:
                    logger.error(f"JSON解析失败: {e}, 尝试修复...")
                    # 尝试修复常见JSON错误
                    fixed_json = self._repair_json(json_str)
                    if fixed_json:
                        try:
                            data = json.loads(fixed_json)
                            result.resume_analysis = self._safe_get_dict(data, 'resume_analysis')
                            result.jd_requirements = self._safe_get_dict(data, 'jd_requirements')
                            result.matching_strategy = self._safe_get_dict(data, 'matching_strategy')
                            logger.info("JSON修复成功")
                        except json.JSONDecodeError:
                            logger.error("JSON修复失败，使用默认结构")
                            result = self._create_fallback_analysis_result(response)
                    else:
                        result = self._create_fallback_analysis_result(response)
            else:
                logger.warning("未找到JSON响应，尝试从文本提取关键信息")
                result = self._extract_from_text(response)

        except Exception as e:
            # 捕获所有异常，确保不会传播到调用方
            logger.error(f"解析响应时发生异常: {e}")
            logger.debug(f"原始响应前200字符: {response[:200] if response else 'empty'}")
            result = self._create_fallback_analysis_result(response)

        return result

    def _extract_balanced_json(self, text: str) -> Optional[str]:
        """使用栈匹配提取平衡的JSON"""
        result = response_parser.extract_balanced_json(text)
        if result is None:
            return self._try_complete_json(text)
        return result

    def _try_complete_json(self, text: str) -> Optional[str]:
        """尝试补全不完整的JSON（缺少外层{}）"""
        return response_parser.try_complete_json(text)

    def _repair_json(self, json_str: str) -> Optional[str]:
        """尝试修复常见的JSON错误"""
        return response_parser.repair_json(json_str)

    def _safe_get_dict(self, data: dict, key: str) -> dict:
        """安全获取字典字段"""
        return response_parser.safe_get_dict(data, key, default={}, convert_list=True)

    def _safe_get_list(self, data: dict, key: str) -> list:
        """安全获取列表字段"""
        return response_parser.safe_get_list(data, key, default=[])

    def _validate_analysis_result(self, result: AnalysisResult) -> None:
        """验证分析结果的关键字段"""
        result.matching_strategy = response_parser.validate_analysis_fields(
            result.matching_strategy
        )

    def _create_fallback_analysis_result(self, response: str) -> AnalysisResult:
        """创建兜底分析结果"""
        result = AnalysisResult()
        result.matching_strategy = {
            'match_score': 50,
            'match_level': '未知',
            'strengths': ['无法解析AI响应'],
            'gaps': ['请检查原始输入'],
            'error': 'JSON解析失败',
            'raw_response_preview': response[:500] if response else ''
        }
        return result

    def _extract_from_text(self, response: str) -> AnalysisResult:
        """从纯文本响应中提取关键信息（最后兜底）"""
        result = AnalysisResult()

        # 尝试提取分数
        score_match = re.search(r'(\d{1,3})\s*[分%]', response)
        if score_match:
            score = int(score_match.group(1))
            if score > 100:
                score = 50
            result.matching_strategy['match_score'] = score

        # 尝试提取优势
        strengths = re.findall(r'优势[：:]\s*([^\n]+)', response)
        if strengths:
            result.matching_strategy['strengths'] = [s.strip() for s in strengths]

        # 尝试提取差距
        gaps = re.findall(r'差距[：:]\s*([^\n]+)', response)
        if gaps:
            result.matching_strategy['gaps'] = [g.strip() for g in gaps]

        # 设置默认值
        if not result.matching_strategy.get('match_score'):
            result.matching_strategy['match_score'] = 50
        if not result.matching_strategy.get('strengths'):
            result.matching_strategy['strengths'] = ['无法从响应中提取']
        if not result.matching_strategy.get('gaps'):
            result.matching_strategy['gaps'] = []

        result.matching_strategy['match_level'] = self._get_match_level(
            result.matching_strategy['match_score']
        )
        result.matching_strategy['extraction_method'] = 'text_fallback'

        return result

    def _get_match_level(self, score: int) -> str:
        """根据分数获取匹配等级"""
        if score >= 90:
            return '优秀'
        elif score >= 75:
            return '良好'
        elif score >= 60:
            return '一般'
        else:
            return '较低'

    def _parse_generation_response(self, response: str) -> GenerationResult:
        """解析生成阶段响应 - 增强版fallback机制

        确保所有异常都被捕获，永远返回有效的 GenerationResult 对象
        """
        result = GenerationResult()

        try:
            # 多级JSON提取策略
            json_str = None
            extraction_method = None

            # Level 1: 尝试匹配 ```json ... ``` 格式
            json_pattern = r'```json\s*([\s\S]*?)\s*```'
            match = re.search(json_pattern, response)
            if match:
                json_str = match.group(1)
                extraction_method = 'code_block'

            # Level 2: 使用栈匹配提取平衡JSON
            if not json_str:
                json_str = self._extract_balanced_json(response)
                if json_str:
                    extraction_method = 'balanced'

            # Level 3: 正则匹配（兜底）
            if not json_str:
                json_pattern = r'\{[\s\S]*\}'
                match = re.search(json_pattern, response)
                if match:
                    json_str = match.group(0)
                    extraction_method = 'regex'

            if json_str:
                try:
                    data = json.loads(json_str)
                    logger.info(f"生成JSON解析成功 (方法: {extraction_method})")

                    # 安全获取各字段，带完整默认值
                    result.tailored_resume = self._safe_get_dict(data, 'tailored_resume')
                    result.evidence_report = self._safe_get_dict(data, 'evidence_report')
                    result.optimization_summary = self._safe_get_dict(data, 'optimization_summary')

                    # 验证和补全关键字段
                    self._validate_generation_result(result)

                except json.JSONDecodeError as e:
                    logger.error(f"生成JSON解析失败: {e}, 尝试修复...")
                    fixed_json = self._repair_json(json_str)
                    if fixed_json:
                        try:
                            data = json.loads(fixed_json)
                            result.tailored_resume = self._safe_get_dict(data, 'tailored_resume')
                            result.evidence_report = self._safe_get_dict(data, 'evidence_report')
                            result.optimization_summary = self._safe_get_dict(data, 'optimization_summary')
                            self._validate_generation_result(result)
                            logger.info("生成JSON修复成功")
                        except json.JSONDecodeError:
                            logger.error("生成JSON修复失败，使用默认结构")
                            result = self._create_fallback_generation_result(response)
                    else:
                        result = self._create_fallback_generation_result(response)
            else:
                logger.warning("未找到生成JSON响应")
                result = self._create_fallback_generation_result(response)

        except Exception as e:
            # 捕获所有异常，确保不会传播到调用方
            logger.error(f"解析生成响应时发生异常: {e}")
            logger.debug(f"原始响应前200字符: {response[:200] if response else 'empty'}")
            result = self._create_fallback_generation_result(response)

        return result

    def _validate_generation_result(self, result: GenerationResult) -> None:
        """验证生成结果的关键字段"""
        result.tailored_resume = response_parser.validate_generation_fields(
            result.tailored_resume
        )

        # 确保evidence_report有基本结构
        if not result.evidence_report:
            result.evidence_report = {
                'total_items': 0,
                'validated': 0,
                'needs_review': 0,
                'coverage': 0.0
            }

        # 确保optimization_summary有基本结构
        if not result.optimization_summary:
            result.optimization_summary = {
                'jd_match_improvement': 'N/A',
                'key_changes': []
            }

    def _create_fallback_generation_result(self, response: str) -> GenerationResult:
        """创建兜底生成结果"""
        result = GenerationResult()
        result.tailored_resume = {
            'basic_info': {},
            'education': [],
            'work_experience': [],
            'projects': [],
            'skills': [],
            'awards': [],
            'certificates': [],
            'self_evaluation': '',
            'error': 'JSON解析失败',
            'raw_response_preview': response[:500] if response else ''
        }
        result.evidence_report = {
            'total_items': 0,
            'validated': 0,
            'needs_review': 0,
            'rejected': 0,
            'coverage': 0.0,
            'error': '无法生成依据报告'
        }
        result.optimization_summary = {
            'jd_match_improvement': 'N/A',
            'key_changes': ['无法解析AI响应'],
            'error': 'JSON解析失败'
        }
        return result

    def _extract_json(self, text: str) -> Optional[str]:
        """从文本中提取 JSON"""
        # 尝试匹配 ```json ... ``` 格式
        json_pattern = r'```json\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, text)
        if match:
            return match.group(1)

        # 尝试匹配 { ... } 格式
        json_pattern = r'\{[\s\S]*\}'
        match = re.search(json_pattern, text)
        if match:
            return match.group(0)

        return None

    def get_stats(self) -> Dict[str, Any]:
        """获取调用统计"""
        stats = self.stats.copy()
        model_stats = self.model_manager.get_stats()
        stats.update(model_stats)
        return stats


# ==================== 新版 ExpertTeamV2（五阶段） ====================

class ExpertTeamV2:
    """AI 专家团队 V2 - 五阶段调用

    五阶段流程：
    1. 阶段0: 简历结构解析 (parse_resume)
    2. 阶段1: JD深度解码 (decode_jd)
    3. 阶段2: 匹配度分析 (match_analysis)
    4. 阶段3: 内容深度改写 (rewrite_content)
    5. 阶段4: 质量验证 (quality_check)
    """

    def __init__(self, model_manager: 'ModelManager' = None):
        """
        初始化专家团队 V2

        Args:
            model_manager: 模型管理器（可选，默认自动创建）
        """
        if model_manager is None:
            from .model_manager import ModelManager
            model_manager = ModelManager()

        self.model_manager = model_manager

        # 加载 Prompt 模板
        self.prompts_dir = config.BASE_DIR / 'prompts'
        self.prompts = {
            'parse_resume': self._load_prompt('parse_resume_prompt.txt'),
            'decode_jd': self._load_prompt('decode_jd_prompt.txt'),
            'match_analysis': self._load_prompt('match_analysis_prompt.txt'),
            'rewrite_content': self._load_prompt('rewrite_content_prompt.txt'),
            'quality_check': self._load_prompt('quality_check_prompt.txt'),
        }

        # 调用统计
        self.stats = {
            'stage_calls': {stage: 0 for stage in self.prompts.keys()},
            'total_tokens': 0,
            'total_latency_ms': 0
        }

        # Writer-Reviewer 闭环初始化
        self._reviewer_providers = {}  # {model_id: provider_instance}
        if config.WRITER_REVIEWER_ENABLED:
            try:
                self.prompts['review_content'] = self._load_prompt('review_content_prompt.txt')
                self.prompts['revise_content'] = self._load_prompt('revise_content_prompt.txt')
                self._init_reviewer_providers()
                if self._reviewer_providers:
                    logger.info(f"Writer-Reviewer 闭环已启用，审阅模型: {list(self._reviewer_providers.keys())}")
                else:
                    logger.warning("Writer-Reviewer 闭环启用但无可用审阅模型，降级为单次改写")
            except FileNotFoundError as e:
                logger.warning(f"Writer-Reviewer prompt 文件缺失，降级为单次改写: {e}")

    def _load_prompt(self, filename: str) -> str:
        """加载 Prompt 模板"""
        filepath = self.prompts_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Prompt 文件不存在: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()

    def _call_model(self, prompt: str, stage: str, max_tokens: int = 4096,
                    temperature: float = 0.3) -> Tuple[str, str, int]:
        """调用模型的通用方法"""
        response = self.model_manager.call(
            prompt=prompt,
            task_type=stage,
            max_tokens=max_tokens,
            temperature=temperature
        )

        if not response.success:
            raise RuntimeError(f"{stage}阶段失败: {response.error_message}")

        self.stats['stage_calls'][stage] = self.stats['stage_calls'].get(stage, 0) + 1
        self.stats['total_tokens'] += response.tokens_used
        self.stats['total_latency_ms'] += response.latency_ms

        return response.content, response.model_id, response.tokens_used

    def _extract_json(self, text: str) -> Optional[str]:
        """从文本中提取 JSON"""
        if not text:
            logger.warning("📝 _extract_json: 输入文本为空")
            return None

        # 尝试匹配 ```json ... ``` 格式
        json_pattern = r'```json\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, text)
        if match:
            json_str = match.group(1)
            try:
                json.loads(json_str)
                logger.info("📝 _extract_json: 使用 ```json 模式成功提取")
                return json_str
            except json.JSONDecodeError as e:
                logger.warning(f"📝 _extract_json: ```json 模式提取内容不是有效JSON: {e}")

        # 尝试使用栈匹配提取平衡JSON
        stack = []
        start_idx = None
        for i, char in enumerate(text):
            if char == '{':
                if not stack:
                    start_idx = i
                stack.append(char)
            elif char == '}':
                if stack:
                    stack.pop()
                    if not stack and start_idx is not None:
                        json_str = text[start_idx:i+1]
                        try:
                            json.loads(json_str)
                            logger.info("📝 _extract_json: 使用栈匹配模式成功提取")
                            return json_str
                        except json.JSONDecodeError as e:
                            logger.warning(f"📝 _extract_json: 栈匹配提取内容不是有效JSON: {e}")
                            continue

        logger.warning(f"📝 _extract_json: 所有模式都失败，响应前200字符: {text[:200]}")
        return None

    def _safe_get_dict(self, data: dict, key: str, default=None) -> dict:
        """安全获取字典字段"""
        return response_parser.safe_get_dict(data, key, default=default)

    def _safe_get_list(self, data: dict, key: str, default=None) -> list:
        """安全获取列表字段"""
        return response_parser.safe_get_list(data, key, default=default)

    def _protect_time_fields(self, tailored_resume: Dict[str, Any],
                              parsed_resume: ParseResumeResult) -> int:
        """
        保护时间字段：AI 改写可能错误修改 work_experience/projects 的 time 字段。
        将 AI 返回的 time 与原始解析结果对比，不一致时强制还原。
        返回被修正的条目数。
        """
        fixed_count = 0

        # 构建原始时间映射（按 index 对应）
        original_work_times = {}
        for i, exp in enumerate(parsed_resume.work_experience or []):
            t = exp.get('time', '') if isinstance(exp, dict) else ''
            if t:
                original_work_times[i] = t

        original_project_times = {}
        for i, proj in enumerate(parsed_resume.projects or []):
            t = proj.get('time', '') if isinstance(proj, dict) else ''
            if t:
                original_project_times[i] = t

        # 修正 work_experience 的 time
        work_exp = tailored_resume.get('work_experience', [])
        if isinstance(work_exp, list):
            for i, exp in enumerate(work_exp):
                if isinstance(exp, dict) and i in original_work_times:
                    ai_time = exp.get('time', '')
                    original_time = original_work_times[i]
                    if ai_time and ai_time != original_time:
                        logger.warning(f"⏰ 时间字段保护: work_experience[{i}] time 被AI修改 "
                                       f"'{original_time}' -> '{ai_time}'，已还原")
                        exp['time'] = original_time
                        fixed_count += 1

        # 修正 projects 的 time
        projects = tailored_resume.get('projects', [])
        if isinstance(projects, list):
            for i, proj in enumerate(projects):
                if isinstance(proj, dict) and i in original_project_times:
                    ai_time = proj.get('time', '')
                    original_time = original_project_times[i]
                    if ai_time and ai_time != original_time:
                        logger.warning(f"⏰ 时间字段保护: projects[{i}] time 被AI修改 "
                                       f"'{original_time}' -> '{ai_time}'，已还原")
                        proj['time'] = original_time
                        fixed_count += 1

        # 修正 education 的 time
        education = tailored_resume.get('education', [])
        if isinstance(education, list):
            original_edu_times = {}
            for i, edu in enumerate(parsed_resume.education or []):
                t = edu.get('time', '') if isinstance(edu, dict) else ''
                if t:
                    original_edu_times[i] = t
            for i, edu in enumerate(education):
                if isinstance(edu, dict) and i in original_edu_times:
                    ai_time = edu.get('time', '')
                    original_time = original_edu_times[i]
                    if ai_time and ai_time != original_time:
                        logger.warning(f"⏰ 时间字段保护: education[{i}] time 被AI修改 "
                                       f"'{original_time}' -> '{ai_time}'，已还原")
                        edu['time'] = original_time
                        fixed_count += 1

        if fixed_count > 0:
            logger.info(f"⏰ 时间字段保护: 共修正 {fixed_count} 个时间字段")
        return fixed_count

    def _convert_tailored_format(self, resume: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换 AI 返回的嵌套格式为扁平格式

        AI 可能返回:
        - work_experience[].tailored_bullets: [{content: "...", evidence: {...}}]
        - projects[].tailored_description: "..."

        代码期望:
        - work_experience[].tailored: "..."
        - projects[].tailored: "..."
        """
        if not resume:
            return resume

        # 处理 work_experience: tailored_bullets -> tailored
        work_exp = resume.get('work_experience', [])
        if isinstance(work_exp, list):
            for exp in work_exp:
                if isinstance(exp, dict) and 'tailored_bullets' in exp and 'tailored' not in exp:
                    bullets = exp.get('tailored_bullets', [])
                    if isinstance(bullets, list) and bullets:
                        contents = []
                        for b in bullets:
                            if isinstance(b, dict):
                                c = b.get('content', '')
                                if c:
                                    contents.append(c.strip())
                            elif isinstance(b, str) and b.strip():
                                contents.append(b.strip())
                        merged = '\n'.join(filter(None, contents))
                        if merged:
                            exp['tailored'] = merged
                            logger.info(f"📊 格式转换: work_experience {len(bullets)} bullets -> tailored ({len(merged)} 字符)")

        # 处理 projects: tailored_description -> tailored
        projects = resume.get('projects', [])
        if isinstance(projects, list):
            for proj in projects:
                if isinstance(proj, dict) and 'tailored_description' in proj and 'tailored' not in proj:
                    desc = proj.get('tailored_description', '')
                    if desc:
                        proj['tailored'] = desc
                        logger.info(f"📊 格式转换: projects tailored_description -> tailored ({len(desc)} 字符)")

        # 处理 education: tailored_highlights -> tailored
        education = resume.get('education', [])
        if isinstance(education, list):
            for edu in education:
                if isinstance(edu, dict) and 'tailored_highlights' in edu and 'tailored' not in edu:
                    highlights = edu.get('tailored_highlights', [])
                    if isinstance(highlights, list) and highlights:
                        merged = '\n'.join(filter(None, highlights))
                        if merged:
                            edu['tailored'] = merged
                            logger.info(f"📊 格式转换: education {len(highlights)} highlights -> tailored ({len(merged)} 字符)")

        # 处理 summary: dict(title, highlights, evidence) -> string
        summary = resume.get('summary')
        if isinstance(summary, dict) and summary:
            title = summary.get('title', '')
            highlights = summary.get('highlights', [])
            parts = []
            if title:
                parts.append(title)
            if isinstance(highlights, list) and highlights:
                for h in highlights:
                    text = h.get('content', h) if isinstance(h, dict) else h
                    if text:
                        parts.append(f"- {text}")
            if parts:
                resume['summary'] = '\n'.join(parts)
                logger.info(f"📊 格式转换: summary dict -> string ({len(resume['summary'])} 字符)")

        # 处理 skills: 嵌套 dict -> 扁平列表
        # AI 可能返回: {"ordered_by_jd_relevance": [...], "other_skills": [...]}
        # 也可能返回: 纯字符串（来自 revise prompt）
        # 代码期望: [{"name": "Python", "tailored_description": "精通 — 5年经验"}, ...]
        skills = resume.get('skills')
        if isinstance(skills, dict) and not isinstance(skills, list):
            skill_list = []
            for key in ['ordered_by_jd_relevance', 'other_skills', 'items', 'technical']:
                items = skills.get(key, [])
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            skill_name = item.get('skill', item.get('name', ''))
                            level = item.get('level', '')
                            context = item.get('context', '')
                            description = f"{level} — {context}" if level and context else (level or context or '')
                            skill_list.append({'name': skill_name, 'tailored_description': description.strip()})
                        elif isinstance(item, str) and item.strip():
                            skill_list.append({'name': item.strip(), 'tailored_description': ''})
            if skill_list:
                resume['skills'] = skill_list
                logger.info(f"📊 格式转换: skills dict -> list ({len(skill_list)} 项技能)")
        elif isinstance(skills, str) and skills.strip():
            # 纯字符串格式：按换行拆分
            lines = [l.strip() for l in skills.strip().split('\n') if l.strip()]
            if lines:
                resume['skills'] = [{'name': line, 'tailored_description': ''} for line in lines]
                logger.info(f"📊 格式转换: skills string -> list ({len(lines)} 项技能)")

        # 清洗 tailored 内容中的结构性标记和重复信息
        self._sanitize_tailored_content(resume)

        return resume

    def _sanitize_tailored_content(self, resume: Dict[str, Any]) -> int:
        """
        清洗 tailored 字段中的结构性标记和重复信息

        AI 可能输出 【关键行动】、【成果】、**Situation:** 等结构性标记，
        以及在 tailored 中重复 time/company 等已有字段的信息。
        此方法在格式转换后调用，清洗这些不需要的内容。

        Returns:
            int: 清洗的字段数量
        """
        sanitized = 0

        for section_key in ['work_experience', 'projects', 'education']:
            items = resume.get(section_key, [])
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                tailored = item.get('tailored', '')
                if not tailored:
                    continue

                original = tailored

                # 1. 移除 【xxx】 标记（保留标记后的内容）
                tailored = re.sub(r'【[^】]*】\s*', '', tailored)

                # 2. 移除 [xxx] 标记（保留内容）
                tailored = re.sub(r'\[[^\]]*\]\s*', '', tailored)

                # 3. 移除 **xxx:** 或 *xxx:* 粗体/斜体标记行（整行删除）
                tailored = re.sub(r'\*{1,2}[^*]+\*{1,2}\s*[:：]\s*\n?', '', tailored)

                # 4. 清理多余空行（连续3+换行→2个换行）
                tailored = re.sub(r'\n{3,}', '\n\n', tailored)

                # 5. 移除行首重复的时间信息（字符串开头或行首）
                time_val = item.get('time', '')
                if time_val:
                    # 尝试多种时间前缀格式
                    prefixes_to_check = [time_val]
                    for sep_char in ['-', '–', '~', '至', '—']:
                        if sep_char in time_val:
                            prefixes_to_check.append(time_val.split(sep_char)[0].strip())
                    for t_prefix in prefixes_to_check:
                        if not t_prefix:
                            continue
                        # 字符串开头
                        if tailored.startswith(t_prefix):
                            tailored = tailored[len(t_prefix):].lstrip(' ,，、:：')
                            break
                        # 行首（多行内容中某行以时间开头）
                        escaped = re.escape(t_prefix)
                        tailored = re.sub(
                            r'\n' + escaped + r'\s*',
                            '\n', tailored, count=1
                        )

                # 6. 移除行首重复的公司/组织名
                org_val = item.get('company', '') or item.get('school', '') or item.get('name', '')
                if org_val and len(org_val) >= 2:
                    for org_prefix in [org_val, org_val + ' ']:
                        if tailored.startswith(org_prefix):
                            tailored = tailored[len(org_prefix):].lstrip(' ,，、:：')
                            break

                if tailored != original:
                    item['tailored'] = tailored.strip()
                    sanitized += 1
                    logger.info(f"🧹 清洗 tailored ({section_key}): 移除结构性标记或重复信息")

        # 清洗 summary
        summary = resume.get('summary', '')
        if summary and isinstance(summary, str):
            original = summary
            summary = re.sub(r'【[^】]*】\s*', '', summary)
            summary = re.sub(r'\*{1,2}[^*]+\*{1,2}\s*[:：]\s*\n?', '', summary)
            summary = re.sub(r'\n{3,}', '\n\n', summary)
            if summary != original:
                resume['summary'] = summary.strip()
                sanitized += 1
                logger.info(f"🧹 清洗 summary: 移除结构性标记")

        return sanitized

    def _build_jd_core_requirements(self, jd_analysis: DecodeJdResult,
                                       match_result: MatchAnalysisResult = None) -> Dict[str, Any]:
        """
        从 JD 解析结果提取必须覆盖的核心要求

        用于：
        1. 传递给 rewrite_content 阶段作为强制约束
        2. 增强降级机制中生成 JD 定向内容
        3. 质量验证阶段计算覆盖率
        """
        # 提取 must_have 技能（包含具体要求描述）
        must_have_skills = []
        jd_specific_requirements = []
        if jd_analysis.must_have:
            skills_data = jd_analysis.must_have.get('skills', [])
            if isinstance(skills_data, list):
                for s in skills_data:
                    if isinstance(s, dict):
                        skill_name = s.get('skill', '')
                        must_have_skills.append(skill_name)
                        # 提取具体要求描述（不只是技能名）
                        requirement_detail = skill_name
                        if s.get('requirement'):
                            requirement_detail = f"{skill_name}: {s['requirement']}"
                        elif s.get('level'):
                            requirement_detail = f"{skill_name}（{s['level']}）"
                        elif s.get('experience'):
                            requirement_detail = f"{skill_name}（{s['experience']}经验）"
                        jd_specific_requirements.append(requirement_detail)
                    else:
                        must_have_skills.append(s)
                        jd_specific_requirements.append(s)

        # 提取 must_have 经验要求
        must_have_experience = jd_analysis.must_have.get('experience', []) if jd_analysis.must_have else []

        # 提取前 10 个关键词
        top_keywords = list(jd_analysis.keyword_weights.keys())[:10]

        # 提取核心能力要求
        core_abilities = []
        if jd_analysis.must_have:
            core_abilities = jd_analysis.must_have.get('abilities', [])

        # 提取改写强度
        rewrite_intensity = 'L2'  # 默认
        if match_result and hasattr(match_result, 'rewrite_intensity') and match_result.rewrite_intensity:
            rewrite_intensity = match_result.rewrite_intensity

        result = {
            'job_title': jd_analysis.job_title,
            'must_have_skills': must_have_skills,
            'jd_specific_requirements': jd_specific_requirements,
            'must_have_experience': must_have_experience,
            'top_keywords': top_keywords,
            'core_abilities': core_abilities,
            'rewrite_intensity': rewrite_intensity,
            'target_coverage': 0.8  # 目标覆盖率 80%
        }

        logger.info(f"📋 JD核心要求提取: 职位={jd_analysis.job_title}, 必备技能={must_have_skills}, "
                    f"具体要求={jd_specific_requirements}, 改写强度={rewrite_intensity}")
        return result

    def _create_fallback_tailored_resume(self, parsed_resume: ParseResumeResult) -> Dict[str, Any]:
        """创建降级定制简历（当AI改写失败时使用）"""
        logger.info("📝 启用降级方案：使用原始简历数据")
        return {
            'basic_info': parsed_resume.basic_info or {},
            'summary': '',
            'education': parsed_resume.education or [],
            'work_experience': parsed_resume.work_experience or [],
            'projects': parsed_resume.projects or [],
            'skills': parsed_resume.skills or {},
            'awards': parsed_resume.awards or [],
            'certificates': parsed_resume.certificates or [],
            'self_evaluation': parsed_resume.self_evaluation or ''
        }

    def _create_enhanced_fallback_tailored_resume(
        self,
        parsed_resume: ParseResumeResult,
        jd_analysis: DecodeJdResult,
        match_result: MatchAnalysisResult
    ) -> Dict[str, Any]:
        """
        增强降级：执行规则化轻量定制

        当 AI 改写失败时，不是简单返回原始数据，而是：
        1. 生成 JD 定向的 summary（包含职位名称）
        2. 在原始内容中标记 JD 关键词
        3. 按匹配分析调整技能顺序
        """
        logger.info("📝 启用增强降级方案：规则化轻量定制")

        jd_requirements = self._build_jd_core_requirements(jd_analysis)
        jd_keywords = jd_requirements['top_keywords']
        job_title = jd_analysis.job_title or "求职者"

        # 1. 生成 JD 定向的 summary
        strengths_text = ""
        if match_result.strengths:
            strengths_text = match_result.strengths[0].get('item', '') if isinstance(match_result.strengths[0], dict) else str(match_result.strengths[0])

        enhanced_summary = {
            'title': f"{job_title} | {strengths_text}" if strengths_text else job_title,
            'highlights': [
                s.get('item', str(s)) if isinstance(s, dict) else str(s)
                for s in match_result.strengths[:3]
            ] if match_result.strengths else []
        }

        # 2. 在工作经历中标记 JD 关键词
        enhanced_work = self._mark_jd_keywords(
            parsed_resume.work_experience or [],
            jd_keywords
        )

        # 3. 按 JD 相关性重排技能
        enhanced_skills = self._reorder_skills(
            parsed_resume.skills or {},
            jd_keywords
        )

        return {
            'basic_info': parsed_resume.basic_info or {},
            'summary': enhanced_summary,
            'education': parsed_resume.education or [],
            'work_experience': enhanced_work,
            'projects': self._mark_jd_keywords(parsed_resume.projects or [], jd_keywords),
            'skills': enhanced_skills,
            'awards': parsed_resume.awards or [],
            'certificates': parsed_resume.certificates or [],
            'self_evaluation': self._generate_jd_aligned_self_evaluation(
                parsed_resume.self_evaluation or '',
                job_title,
                jd_keywords
            )
        }

    def _mark_jd_keywords(self, items: List[Dict], jd_keywords: List[str]) -> List[Dict]:
        """在内容中标记 JD 关键词（用【】标记）"""
        if not jd_keywords or not items:
            return items

        enhanced_items = []
        for item in items:
            if not isinstance(item, dict):
                enhanced_items.append(item)
                continue

            enhanced_item = dict(item)

            # 处理 responsibilities 或 description 字段
            for field in ['responsibilities', 'description', 'tailored']:
                if field in enhanced_item and enhanced_item[field]:
                    text = enhanced_item[field]
                    if isinstance(text, str):
                        # 标记关键词
                        marked_text = text
                        for kw in jd_keywords:
                            if kw.lower() in marked_text.lower() and f'【{kw}】' not in marked_text:
                                # 不区分大小写替换，保留原文大小写
                                import re
                                pattern = re.compile(re.escape(kw), re.IGNORECASE)
                                marked_text = pattern.sub(f'【{kw}】', marked_text, count=1)
                        enhanced_item[field] = marked_text

            enhanced_items.append(enhanced_item)

        return enhanced_items

    def _reorder_skills(self, skills: Dict, jd_keywords: List[str]) -> Dict:
        """按 JD 相关性重排技能"""
        if not jd_keywords or not skills:
            return skills

        # 获取技能列表
        skill_items = skills.get('items', skills.get('technical', []))
        if not isinstance(skill_items, list):
            return skills

        # 计算每个技能与 JD 的相关性分数
        scored_skills = []
        for skill in skill_items:
            if isinstance(skill, dict):
                skill_name = skill.get('skill', skill.get('name', ''))
            else:
                skill_name = str(skill)

            # 计算匹配分数
            score = 0
            skill_lower = skill_name.lower()
            for kw in jd_keywords:
                if kw.lower() in skill_lower or skill_lower in kw.lower():
                    score += 1

            scored_skills.append((score, skill))

        # 按分数降序排列
        scored_skills.sort(key=lambda x: x[0], reverse=True)

        # 重建技能字典
        reordered = [s[1] for s in scored_skills]

        result = dict(skills)
        if 'items' in result:
            result['items'] = reordered
        elif 'technical' in result:
            result['technical'] = reordered
        else:
            result['ordered_by_jd_relevance'] = reordered

        result['_jd_relevance_sorted'] = True
        return result

    def _generate_jd_aligned_self_evaluation(
        self,
        original: str,
        job_title: str,
        jd_keywords: List[str]
    ) -> str:
        """生成 JD 对齐的自我评价"""
        if not original:
            return f"专注{job_title}领域，期待在新的岗位中发挥价值。"

        # 如果原文已经包含职位关键词，直接返回
        if job_title and job_title in original:
            return original

        # 否则在开头加上职位定位
        if job_title:
            return f"作为{job_title}，{original}"

        return original

    def _validate_jd_keyword_coverage(
        self,
        tailored_resume: Dict[str, Any],
        jd_keywords: List[str]
    ) -> Dict[str, Any]:
        """
        验证 JD 关键词覆盖率，目标 >= 80%

        返回:
        - total: 关键词总数
        - covered: 已覆盖数
        - coverage_rate: 覆盖率
        - missing: 未覆盖的关键词列表
        """
        if not jd_keywords:
            return {
                'total': 0,
                'covered': 0,
                'coverage_rate': 1.0,
                'missing': [],
                'status': 'no_keywords'
            }

        # 将整个简历转为文本进行搜索
        all_text = json.dumps(tailored_resume, ensure_ascii=False).lower()

        covered = []
        missing = []

        for kw in jd_keywords:
            kw_lower = kw.lower()
            # 支持多种匹配方式
            if kw_lower in all_text or f'【{kw}】'.lower() in all_text:
                covered.append(kw)
            else:
                missing.append(kw)

        coverage_rate = len(covered) / len(jd_keywords) if jd_keywords else 0

        result = {
            'total': len(jd_keywords),
            'covered': len(covered),
            'coverage_rate': round(coverage_rate, 2),
            'missing': missing,
            'status': 'pass' if coverage_rate >= 0.8 else 'fail'
        }

        logger.info(f"📊 JD关键词覆盖: {len(covered)}/{len(jd_keywords)} = {coverage_rate:.0%}, 缺失: {missing}")

        return result

    # ==================== 各阶段实现 ====================

    def parse_resume(self, resume_content: str) -> ParseResumeResult:
        """阶段0: 简历结构解析"""
        logger.info("开始阶段0: 简历结构解析")

        prompt = self.prompts['parse_resume'].format(
            resume_content=resume_content
        )

        response, model_id, tokens = self._call_model(
            prompt, 'parse_resume', max_tokens=4096, temperature=0.2
        )

        result = ParseResumeResult()
        result.raw_response = response
        result.model_used = model_id
        result.tokens_used = tokens

        try:
            json_str = self._extract_json(response)
            if json_str:
                data = json.loads(json_str)
                result.basic_info = self._safe_get_dict(data, 'basic_info')
                result.education = self._safe_get_list(data, 'education')
                result.work_experience = self._safe_get_list(data, 'work_experience')
                result.projects = self._safe_get_list(data, 'projects')
                result.skills = self._safe_get_dict(data, 'skills')
                result.awards = self._safe_get_list(data, 'awards')           # 新增
                result.certificates = self._safe_get_list(data, 'certificates')  # 新增
                result.self_evaluation = data.get('self_evaluation', '')      # 新增
                result.raw_materials = self._safe_get_dict(data, 'raw_materials')
                result.parsing_confidence = data.get('parsing_confidence', 0.0)
                result.success = True
            else:
                result.success = False
                result.error = "无法从响应中提取JSON"
        except Exception as e:
            logger.error(f"解析简历结构失败: {e}")
            result.success = False
            result.error = str(e)

        logger.info(f"阶段0完成: success={result.success}")
        return result

    def decode_jd(self, jd_content: str) -> DecodeJdResult:
        """阶段1: JD深度解码"""
        logger.info("开始阶段1: JD深度解码")

        prompt = self.prompts['decode_jd'].format(
            jd_content=jd_content
        )

        response, model_id, tokens = self._call_model(
            prompt, 'decode_jd', max_tokens=4096, temperature=0.2
        )

        result = DecodeJdResult()
        result.raw_response = response
        result.model_used = model_id
        result.tokens_used = tokens

        try:
            json_str = self._extract_json(response)
            if json_str:
                data = json.loads(json_str)
                result.job_title = data.get('job_title', '')
                result.company_overview = data.get('company_overview', '')
                result.salary_range = data.get('salary_range', '')  # 新增
                result.must_have = self._safe_get_dict(data, 'must_have')
                result.nice_to_have = self._safe_get_dict(data, 'nice_to_have')
                result.implicit_requirements = self._safe_get_list(data, 'implicit_requirements')
                result.keyword_weights = self._safe_get_dict(data, 'keyword_weights')
                result.success_indicators = self._safe_get_list(data, 'success_indicators')
                result.red_flags = self._safe_get_list(data, 'red_flags')
                result.pain_points = self._safe_get_list(data, 'pain_points')
                result.competitor_profile = self._safe_get_dict(data, 'competitor_profile')  # 新增
                result.success = True
            else:
                result.success = False
                result.error = "无法从响应中提取JSON"
        except Exception as e:
            logger.error(f"JD解码失败: {e}")
            result.success = False
            result.error = str(e)

        logger.info(f"阶段1完成: success={result.success}")
        return result

    def match_analysis(self, parsed_resume: ParseResumeResult,
                       jd_analysis: DecodeJdResult) -> MatchAnalysisResult:
        """阶段2: 匹配度分析"""
        logger.info("开始阶段2: 匹配度分析")

        prompt = self.prompts['match_analysis'].format(
            parsed_resume=json.dumps({
                'basic_info': parsed_resume.basic_info,
                'education': parsed_resume.education,
                'work_experience': parsed_resume.work_experience,
                'projects': parsed_resume.projects,
                'skills': parsed_resume.skills,
                'awards': parsed_resume.awards,                       # 新增
                'certificates': parsed_resume.certificates,           # 新增
                'self_evaluation': parsed_resume.self_evaluation,     # 新增
                'raw_materials': parsed_resume.raw_materials
            }, ensure_ascii=False, indent=2),
            jd_analysis=json.dumps({
                'job_title': jd_analysis.job_title,
                'company_overview': jd_analysis.company_overview,
                'salary_range': jd_analysis.salary_range,             # 新增
                'must_have': jd_analysis.must_have,
                'nice_to_have': jd_analysis.nice_to_have,
                'keyword_weights': jd_analysis.keyword_weights,
                'implicit_requirements': jd_analysis.implicit_requirements,
                'success_indicators': jd_analysis.success_indicators,
                'red_flags': jd_analysis.red_flags,
                'pain_points': jd_analysis.pain_points,
                'competitor_profile': jd_analysis.competitor_profile  # 新增
            }, ensure_ascii=False, indent=2)
        )

        response, model_id, tokens = self._call_model(
            prompt, 'match_analysis', max_tokens=4096, temperature=0.3
        )

        result = MatchAnalysisResult()
        result.raw_response = response
        result.model_used = model_id
        result.tokens_used = tokens

        try:
            json_str = self._extract_json(response)
            if json_str:
                data = json.loads(json_str)

                # 使用分数计算器计算匹配分数
                jd_checklist = data.get('jd_requirements_checklist', [])
                if jd_checklist:
                    scorer = MatchScorer()
                    resume_dict = {
                        'basic_info': parsed_resume.basic_info,
                        'education': parsed_resume.education,
                        'work_experience': parsed_resume.work_experience,
                        'projects': parsed_resume.projects,
                        'skills': parsed_resume.skills,
                    }
                    ai_analysis = {
                        'strengths': data.get('strengths', []),
                        'gaps': data.get('gaps', []),
                    }
                    score_result = scorer.calculate_score(jd_checklist, resume_dict, ai_analysis)
                    result.match_score = score_result.score
                    result.match_level = score_result.level
                    result.score_breakdown = score_result.breakdown
                    result.requirements_analysis = score_result.to_dict()
                    logger.info(f"分数计算器结果: score={score_result.score}, level={score_result.level}")
                    logger.info(f"分数明细: {score_result.breakdown}")
                else:
                    # 降级：使用 AI 返回的分数
                    result.match_score = data.get('match_score', 50)
                    result.match_level = data.get('match_level', '未知')
                    logger.info(f"使用AI原始分数: score={result.match_score}")

                result.rewrite_intensity = data.get('rewrite_intensity', 'L1')
                result.strengths = self._safe_get_list(data, 'strengths')
                result.gaps = self._safe_get_list(data, 'gaps')
                result.fatal_flaws = self._safe_get_list(data, 'fatal_flaws')
                result.highlight_opportunities = self._safe_get_list(data, 'highlight_opportunities')
                result.rewrite_strategy = self._safe_get_dict(data, 'rewrite_strategy')
                result.content_to_emphasize = self._safe_get_list(data, 'content_to_emphasize')
                result.content_to_weaken = self._safe_get_list(data, 'content_to_weaken')
                result.recruiter_tips = self._safe_get_list(data, 'recruiter_tips')
                result.differentiation_strategy = self._safe_get_dict(data, 'differentiation_strategy')
                result.success = True
            else:
                result.success = False
                result.error = "无法从响应中提取JSON"
        except Exception as e:
            logger.error(f"匹配分析失败: {e}")
            result.success = False
            result.error = str(e)

        logger.info(f"阶段2完成: match_score={result.match_score}")
        return result

    # ==================== Writer-Reviewer 闭环方法 ====================

    def _init_reviewer_providers(self):
        """根据配置初始化审阅模型 provider 实例"""
        model_list = [m.strip() for m in config.WRITER_REVIEWER_REVIEWER_MODELS.split(',') if m.strip()]

        # 已知的 AntiGravity 模型
        antigravity_models = {
            'gpt-4o', 'gpt-4-turbo', 'claude-sonnet-4-5', 'claude-3-5-sonnet',
            'gemini-2.5-pro', 'gemini-2.0-flash-exp', 'gemini-1.5-pro', 'gemini-1.5-flash'
        }

        for model_id in model_list:
            provider = None
            if model_id in antigravity_models:
                from .providers.antigravity_provider import AntiGravityProvider
                p = AntiGravityProvider()
                if p.is_available():
                    provider = p
                else:
                    logger.warning(f"AntiGravity 代理不可用，跳过审阅模型: {model_id}")
            elif model_id.startswith('qwen') or model_id.startswith('kimi'):
                from .providers.alibaba_provider import AlibabaProvider
                p = AlibabaProvider()
                if p.is_available():
                    provider = p
                else:
                    logger.warning(f"阿里云不可用，跳过审阅模型: {model_id}")
            else:
                # 未知模型，尝试 AntiGravity
                from .providers.antigravity_provider import AntiGravityProvider
                p = AntiGravityProvider()
                if p.is_available():
                    provider = p
                else:
                    logger.warning(f"无法为审阅模型 {model_id} 找到可用 provider")

            if provider:
                self._reviewer_providers[model_id] = provider

    def _review_tailored_resume(self, tailored_resume_json: str,
                                original_resume: str,
                                jd_requirements_json: str,
                                provider, model_id: str) -> Optional[Dict]:
        """调用单个审阅模型评估定制简历"""
        prompt = self.prompts['review_content'].format(
            tailored_resume=tailored_resume_json,
            original_resume=original_resume,
            jd_requirements=jd_requirements_json
        )

        response = provider.call(
            prompt=prompt,
            model_id=model_id,
            max_tokens=4096,
            temperature=0.3
        )

        if not response.success:
            logger.warning(f"审阅模型 {model_id} 调用失败: {response.error_message}")
            return None

        json_str = self._extract_json(response.content)
        if json_str:
            try:
                review = json.loads(json_str)
                logger.info(f"审阅模型 {model_id} 完成: score={review.get('overall_score', '?')}, "
                            f"converged={review.get('converged', False)}")
                return review
            except json.JSONDecodeError:
                logger.warning(f"审阅模型 {model_id} 返回的 JSON 解析失败")
        return None

    def _aggregate_reviews(self, reviews: List[Dict]) -> Dict:
        """合并多个审阅者的评审结果"""
        if not reviews:
            return {"converged": False, "overall_score": 0, "summary": "无审阅结果"}

        dimension_names = ['jd_alignment', 'authenticity', 'keyword_coverage',
                           'logical_flow', 'quantification', 'professional_tone']
        aggregated_dimensions = {}

        for dim in dimension_names:
            scores = [r.get('dimensions', {}).get(dim, {}).get('score')
                      for r in reviews
                      if isinstance(r.get('dimensions', {}).get(dim), dict)]
            if scores:
                avg_score = round(sum(scores) / len(scores), 1)
                issues = []
                suggestions = []
                for r in reviews:
                    dim_data = r.get('dimensions', {}).get(dim, {})
                    if isinstance(dim_data, dict):
                        issues.extend(dim_data.get('issues', []))
                        suggestions.extend(dim_data.get('suggestions', []))
                aggregated_dimensions[dim] = {
                    "score": avg_score,
                    "issues": list(set(issues)),
                    "suggestions": list(set(suggestions))
                }

        dim_scores = [d['score'] for d in aggregated_dimensions.values()]
        overall_score = round(sum(dim_scores) / len(dim_scores)) if dim_scores else 0

        # 去重 specific_revisions
        seen = set()
        all_revisions = []
        for r in reviews:
            for rev in r.get('specific_revisions', []):
                key = (rev.get('section', ''), rev.get('item_index', -1), rev.get('reason', ''))
                if key not in seen:
                    seen.add(key)
                    all_revisions.append(rev)

        all_converged = all(r.get('converged', False) for r in reviews)
        summaries = [r.get('summary', '') for r in reviews if r.get('summary')]

        return {
            "overall_score": overall_score,
            "dimensions": aggregated_dimensions,
            "specific_revisions": all_revisions,
            "converged": all_converged,
            "reviewer_count": len(reviews),
            "summary": " | ".join(summaries) if summaries else ""
        }

    def _calculate_version_diff(self, version_a: Dict, version_b: Dict) -> float:
        """计算两版简历的差异比例 (0.0 ~ 1.0)"""
        text_a = json.dumps(version_a, ensure_ascii=False, sort_keys=True)
        text_b = json.dumps(version_b, ensure_ascii=False, sort_keys=True)
        if not text_a or not text_b:
            return 1.0 if text_a != text_b else 0.0
        return 1.0 - SequenceMatcher(None, text_a, text_b).ratio()

    def _rewrite_with_review_loop(self, original_resume: str,
                                   parsed_resume: ParseResumeResult,
                                   match_result: MatchAnalysisResult,
                                   jd_analysis: DecodeJdResult,
                                   progress_callback=None,
                                   jd_content: str = '') -> RewriteContentResult:
        """执行 Writer-Reviewer 闭环改写"""
        max_iterations = config.WRITER_REVIEWER_MAX_ITERATIONS
        score_threshold = config.WRITER_REVIEWER_SCORE_THRESHOLD
        min_diff_threshold = config.WRITER_REVIEWER_MIN_DIFF_THRESHOLD

        # === 第 0 轮：初次改写 ===
        if progress_callback:
            progress_callback(3, "正在精心打磨你的简历...", 58)

        result = self._rewrite_single_pass(original_resume, parsed_resume, match_result, jd_analysis, jd_content)
        if not result.success:
            return result

        current_tailored = result.tailored_resume
        review_iterations = 0
        review_scores = []

        # 构造 JD 需求 JSON（供审阅模型使用）
        jd_requirements_json = json.dumps({
            'job_title': jd_analysis.job_title,
            'must_have': jd_analysis.must_have,
            'keyword_weights': jd_analysis.keyword_weights,
            'nice_to_have': jd_analysis.nice_to_have,
        }, ensure_ascii=False, indent=2)

        # 计算每轮迭代占的进度区间
        review_progress_start = 64
        review_progress_end = 82
        progress_per_iteration = (review_progress_end - review_progress_start) / max_iterations

        for iteration in range(1, max_iterations + 1):
            review_iterations = iteration
            iter_start_pct = int(review_progress_start + progress_per_iteration * (iteration - 1))
            iter_end_pct = int(review_progress_start + progress_per_iteration * iteration)

            if progress_callback:
                progress_callback(3, f"审阅优化第 {iteration}/{max_iterations} 轮...", iter_start_pct)

            logger.info(f"=== Writer-Reviewer 循环 第 {iteration}/{max_iterations} 轮 ===")

            # === 并行审阅 ===
            tailored_json_str = json.dumps(current_tailored, ensure_ascii=False, indent=2)
            logger.info(f"审阅请求: 发送给 {len(self._reviewer_providers)} 个审阅模型, "
                        f"简历JSON长度: {len(tailored_json_str)} 字符")

            reviews = []
            with ThreadPoolExecutor(max_workers=len(self._reviewer_providers)) as executor:
                futures = {}
                for model_id, provider in self._reviewer_providers.items():
                    future = executor.submit(
                        self._review_tailored_resume,
                        tailored_json_str, original_resume, jd_requirements_json,
                        provider, model_id
                    )
                    futures[future] = model_id

                for future in futures:
                    model_id = futures[future]
                    try:
                        review = future.result(timeout=120)
                        if review:
                            reviews.append(review)
                    except Exception as e:
                        logger.warning(f"审阅模型 {model_id} 异常: {e}")

            if not reviews:
                logger.warning("所有审阅模型调用失败，停止循环")
                break

            logger.info(f"审阅完成: 成功 {len(reviews)}/{len(self._reviewer_providers)} 个")

            # === 聚合反馈 ===
            aggregated = self._aggregate_reviews(reviews)

            # 输出各维度分数
            dim_scores = aggregated.get('dimensions', {})
            dim_log = ', '.join(f"{k}={v['score']}" for k, v in dim_scores.items())
            logger.info(f"各维度分数: {dim_log}")

            review_scores.append({
                "iteration": iteration,
                "overall_score": aggregated['overall_score'],
                "reviewer_count": aggregated['reviewer_count'],
                "converged": aggregated['converged'],
                "revision_count": len(aggregated['specific_revisions']),
                "summary": aggregated.get('summary', '')[:300],
                "dimension_scores": {k: v['score'] for k, v in dim_scores.items()}
            })
            logger.info(f"聚合审阅: score={aggregated['overall_score']}, "
                        f"converged={aggregated['converged']}, "
                        f"revisions={len(aggregated['specific_revisions'])}")

            # === 收敛检查 ===
            logger.info(f"收敛检查: converged={aggregated['converged']}, "
                        f"score={aggregated['overall_score']}/{score_threshold}, "
                        f"revisions={len(aggregated['specific_revisions'])}")

            if aggregated['converged']:
                logger.info("所有审阅者认为已收敛，停止循环")
                break

            if aggregated['overall_score'] >= score_threshold:
                logger.info(f"分数 {aggregated['overall_score']} >= 阈值 {score_threshold}，停止循环")
                break

            if not aggregated['specific_revisions']:
                logger.info("无实质性修改建议，停止循环")
                break

            # === 作者修订 ===
            feedback_json = json.dumps(aggregated, ensure_ascii=False, indent=2)
            logger.info(f"准备修订: 反馈JSON长度={len(feedback_json)} 字符, "
                        f"修改建议数={len(aggregated['specific_revisions'])}")
            logger.info(f"修改建议摘要: {aggregated.get('summary', '无')[:200]}")

            if progress_callback:
                progress_callback(3, f"根据审阅意见修订中...", iter_start_pct + progress_per_iteration // 2)

            feedback_json = json.dumps(aggregated, ensure_ascii=False, indent=2)

            revise_prompt = self.prompts['revise_content'].format(
                original_resume=original_resume,
                current_tailored_resume=json.dumps(current_tailored, ensure_ascii=False, indent=2),
                aggregated_feedback=feedback_json,
                match_analysis=json.dumps({
                    'match_score': match_result.match_score,
                    'rewrite_intensity': match_result.rewrite_intensity,
                    'strengths': match_result.strengths,
                    'gaps': match_result.gaps,
                    'rewrite_strategy': match_result.rewrite_strategy,
                }, ensure_ascii=False, indent=2),
                jd_requirements=jd_requirements_json
            )

            try:
                logger.info(f"调用作者模型修订 (prompt长度={len(revise_prompt)} 字符)...")
                response, model_id, tokens = self._call_model(
                    revise_prompt, 'rewrite_content', max_tokens=6144, temperature=0.4
                )
                logger.info(f"修订完成: model={model_id}, tokens={tokens}")

                json_str = self._extract_json(response)
                if json_str:
                    data = json.loads(json_str)
                    new_tailored = self._safe_get_dict(data, 'tailored_resume')
                    # 时间字段保护：修订版也可能错误修改日期
                    self._protect_time_fields(new_tailored, parsed_resume)
                    new_tailored = self._convert_tailored_format(new_tailored)

                    # 检查版本差异
                    diff = self._calculate_version_diff(current_tailored, new_tailored)
                    logger.info(f"版本差异: {diff:.2%}")

                    if diff < min_diff_threshold:
                        logger.info(f"版本差异 {diff:.2%} < {min_diff_threshold:.2%}，停止循环")
                        current_tailored = new_tailored
                        break

                    current_tailored = new_tailored
                    result.change_log.extend(data.get('change_log', []))
                else:
                    logger.warning("修订版 JSON 解析失败，保留当前版本")
                    break
            except Exception as e:
                logger.error(f"修订调用失败: {e}")
                break

        # === 构建最终结果 ===
        result.tailored_resume = current_tailored
        result.review_iterations = review_iterations
        result.review_scores = review_scores
        result.review_feedback_summary = review_scores[-1].get('summary', '') if review_scores else ""
        result.review_stop_reason = stop_reason

        # 重新验证 JD 关键词覆盖率
        jd_core_requirements = self._build_jd_core_requirements(jd_analysis, match_result)
        coverage_result = self._validate_jd_keyword_coverage(
            current_tailored, jd_core_requirements['top_keywords']
        )
        result.jd_keyword_coverage = coverage_result

        if progress_callback:
            progress_callback(3, "简历内容定制完成", review_progress_end)

        final_score = review_scores[-1]['overall_score'] if review_scores else 'N/A'
        stop_reason = '初次改写无审阅' if review_iterations == 0 else '正常完成'
        if review_scores and not review_scores[-1].get('converged') and review_iterations >= max_iterations:
            stop_reason = f'达到最大迭代次数 {max_iterations}'
        elif review_scores and review_scores[-1].get('converged'):
            stop_reason = '审阅者认为已收敛'
        elif review_scores and review_scores[-1]['overall_score'] >= score_threshold:
            stop_reason = f'分数达标 ({review_scores[-1]["overall_score"]}>= {score_threshold})'
        elif review_scores and not review_scores[-1].get('specific_revisions'):
            stop_reason = '无修改建议'
        elif review_scores:
            stop_reason = f'版本差异过小 (<{min_diff_threshold})'

        logger.info(f" Writer-Reviewer 闭环总结:")
        logger.info(f"   迭代轮数: {review_iterations}")
        logger.info(f"   最终分数: {final_score}")
        logger.info(f"   停止原因: {stop_reason}")
        logger.info(f"   JD关键词覆盖率: {coverage_result['coverage_rate']:.0%}")
        logger.info(f"   各轮分数变化: {[s['overall_score'] for s in review_scores]}")

        logger.info(f"Writer-Reviewer 循环完成: iterations={review_iterations}, final_score={final_score}")

        # 结构化审阅日志（便于从日志文件中 grep 解析）
        review_log = json.dumps({
            'iterations': review_iterations,
            'stop_reason': stop_reason,
            'final_score': final_score,
            'score_progression': [s['overall_score'] for s in review_scores],
            'config': {'max_iterations': max_iterations, 'score_threshold': score_threshold}
        }, ensure_ascii=False)
        logger.info(f"WRITER_REVIEWER_SUMMARY: {review_log}")
        return result

    # ==================== 阶段3: 内容改写 ====================

    def rewrite_content(self, original_resume: str,
                        parsed_resume: ParseResumeResult,
                        match_result: MatchAnalysisResult,
                        jd_analysis: DecodeJdResult,
                        progress_callback=None,
                        jd_content: str = '') -> RewriteContentResult:
        """阶段3: 内容深度改写（支持 Writer-Reviewer 闭环）"""
        logger.info("开始阶段3: 内容深度改写")

        if self._reviewer_providers:
            return self._rewrite_with_review_loop(
                original_resume, parsed_resume, match_result, jd_analysis,
                progress_callback=progress_callback,
                jd_content=jd_content
            )

        return self._rewrite_single_pass(original_resume, parsed_resume, match_result, jd_analysis, jd_content)

    def _rewrite_single_pass(self, original_resume: str,
                             parsed_resume: ParseResumeResult,
                             match_result: MatchAnalysisResult,
                             jd_analysis: DecodeJdResult,
                             jd_content: str = '') -> RewriteContentResult:
        """阶段3: 内容深度改写"""
        logger.info("开始阶段3: 内容深度改写")

        # 数据验证日志
        if not parsed_resume.work_experience and not parsed_resume.projects:
            logger.warning("⚠️ 解析结果为空，将使用原始简历作为主要参考")
        logger.info(f"原始简历长度: {len(original_resume)} 字符")

        # 提取 JD 核心要求（用于强化约束）
        jd_core_requirements = self._build_jd_core_requirements(jd_analysis, match_result)
        logger.info(f"📋 JD核心要求: job_title={jd_core_requirements.get('job_title')}, "
                    f"必备技能={jd_core_requirements.get('must_have_skills')}, "
                    f"关键词数={len(jd_core_requirements.get('top_keywords', []))}, "
                    f"改写强度={jd_core_requirements.get('rewrite_intensity')}")
        logger.info(f"📋 原始JD文本长度: {len(jd_content)} 字符")

        rewrite_intensity = jd_core_requirements.get('rewrite_intensity', 'L2')

        prompt = self.prompts['rewrite_content'].format(
            rewrite_intensity=rewrite_intensity,
            jd_content=jd_content or '（未提供原始JD）',
            original_resume=original_resume,
            parsed_resume=json.dumps({
                'basic_info': parsed_resume.basic_info,
                'education': parsed_resume.education,
                'work_experience': parsed_resume.work_experience,
                'projects': parsed_resume.projects,
                'skills': parsed_resume.skills,
                'awards': parsed_resume.awards,                       # 新增
                'certificates': parsed_resume.certificates,           # 新增
                'self_evaluation': parsed_resume.self_evaluation,     # 新增
                'raw_materials': parsed_resume.raw_materials
            }, ensure_ascii=False, indent=2),
            match_analysis=json.dumps({
                'match_score': match_result.match_score,
                'rewrite_intensity': match_result.rewrite_intensity,
                'strengths': match_result.strengths,
                'gaps': match_result.gaps,
                'rewrite_strategy': match_result.rewrite_strategy,
                'content_to_emphasize': match_result.content_to_emphasize,
                'content_to_weaken': match_result.content_to_weaken,
                'differentiation_strategy': match_result.differentiation_strategy
            }, ensure_ascii=False, indent=2),
            jd_requirements=json.dumps({
                'job_title': jd_analysis.job_title,
                'company_overview': jd_analysis.company_overview,
                'salary_range': jd_analysis.salary_range,             # 新增
                'must_have': jd_analysis.must_have,
                'nice_to_have': jd_analysis.nice_to_have,
                'keyword_weights': jd_analysis.keyword_weights,
                'implicit_requirements': jd_analysis.implicit_requirements,
                'success_indicators': jd_analysis.success_indicators,
                'red_flags': jd_analysis.red_flags,
                'pain_points': jd_analysis.pain_points,
                'competitor_profile': jd_analysis.competitor_profile  # 新增
            }, ensure_ascii=False, indent=2),
            jd_core_requirements=json.dumps(jd_core_requirements, ensure_ascii=False, indent=2)
        )

        logger.info(f"📝 rewrite prompt 长度: {len(prompt)} 字符 (含原始JD {len(jd_content)} 字符)")

        try:
            response, model_id, tokens = self._call_model(
                prompt, 'rewrite_content', max_tokens=6144, temperature=0.5
            )
        except RuntimeError as e:
            logger.error(f"阶段3模型调用失败，使用降级方案: {e}")
            result = RewriteContentResult()
            result.success = False
            result.error = f"模型调用失败: {e}"
            result.tailored_resume = self._create_enhanced_fallback_tailored_resume(
                parsed_resume, jd_analysis, match_result
            )
            result.tailored_resume = self._convert_tailored_format(result.tailored_resume)
            coverage_result = self._validate_jd_keyword_coverage(
                result.tailored_resume,
                jd_core_requirements['top_keywords']
            )
            result.jd_keyword_coverage = coverage_result
            return result

        result = RewriteContentResult()
        result.raw_response = response
        result.model_used = model_id
        result.tokens_used = tokens

        try:
            json_str = self._extract_json(response)
            logger.info(f"📝 阶段3 JSON提取: {'成功' if json_str else '失败'}")
            if json_str:
                data = json.loads(json_str)
                logger.info(f"📝 阶段3 data keys: {list(data.keys())}")
                result.tailored_resume = self._safe_get_dict(data, 'tailored_resume')
                logger.info(f"📝 阶段3 tailored_resume keys: {list(result.tailored_resume.keys()) if result.tailored_resume else '空'}")
                # 时间字段保护：AI 可能错误修改日期，强制还原
                self._protect_time_fields(result.tailored_resume, parsed_resume)
                # 格式转换：将 AI 返回的嵌套格式转为扁平格式
                result.tailored_resume = self._convert_tailored_format(result.tailored_resume)
                result.change_log = self._safe_get_list(data, 'change_log')
                result.keyword_coverage = self._safe_get_dict(data, 'keyword_coverage')

                # 验证 JD 关键词覆盖率
                coverage_result = self._validate_jd_keyword_coverage(
                    result.tailored_resume,
                    jd_core_requirements['top_keywords']
                )
                result.jd_keyword_coverage = coverage_result
                logger.info(f"📊 阶段3 JD关键词覆盖率: {coverage_result['coverage_rate']:.0%}")

                result.success = True
            else:
                result.success = False
                result.error = "无法从响应中提取JSON"
                logger.warning(f"📝 阶段3 原始响应前500字符: {response[:500] if response else '空'}")

                # 增强降级：使用 JD 定向的轻量定制
                result.tailored_resume = self._create_enhanced_fallback_tailored_resume(
                    parsed_resume, jd_analysis, match_result
                )
                result.tailored_resume = self._convert_tailored_format(result.tailored_resume)

                # 验证覆盖率
                coverage_result = self._validate_jd_keyword_coverage(
                    result.tailored_resume,
                    jd_core_requirements['top_keywords']
                )
                result.jd_keyword_coverage = coverage_result

                result.change_log = [{
                    "section": "enhanced_fallback",
                    "original": "AI改写失败",
                    "tailored": "JD定向轻量定制",
                    "reason": "JSON提取失败，启用增强降级方案",
                    "rewrite_type": "enhanced_fallback",
                    "jd_keyword_coverage": coverage_result['coverage_rate']
                }]
                logger.info(f"📝 阶段3 启用增强降级方案，JD关键词覆盖率: {coverage_result['coverage_rate']:.0%}")
        except Exception as e:
            logger.error(f"内容改写失败: {e}")
            result.success = False
            result.error = str(e)

            # 增强降级：使用 JD 定向的轻量定制
            result.tailored_resume = self._create_enhanced_fallback_tailored_resume(
                parsed_resume, jd_analysis, match_result
            )
            result.tailored_resume = self._convert_tailored_format(result.tailored_resume)

            # 验证覆盖率
            coverage_result = self._validate_jd_keyword_coverage(
                result.tailored_resume,
                jd_core_requirements['top_keywords']
            )
            result.jd_keyword_coverage = coverage_result

            result.change_log = [{
                "section": "enhanced_fallback",
                "original": "AI改写异常",
                "tailored": "JD定向轻量定制",
                "reason": f"异常: {str(e)}",
                "rewrite_type": "enhanced_fallback",
                "jd_keyword_coverage": coverage_result['coverage_rate']
            }]
            logger.info(f"📝 阶段3 启用增强降级方案（异常），JD关键词覆盖率: {coverage_result['coverage_rate']:.0%}")

        logger.info(f"阶段3完成: success={result.success}")
        return result

    def quality_check(self, original_resume: str,
                      tailored_resume: Dict[str, Any],
                      jd_requirements: Dict[str, Any],
                      change_log: List[Dict[str, Any]]) -> QualityCheckResult:
        """阶段4: 质量验证"""
        logger.info("开始阶段4: 质量验证")

        prompt = self.prompts['quality_check'].format(
            original_resume=original_resume,  # 移除截断，传递完整简历
            tailored_resume=json.dumps(tailored_resume, ensure_ascii=False, indent=2),
            jd_requirements=json.dumps(jd_requirements, ensure_ascii=False, indent=2),
            change_log=json.dumps(change_log, ensure_ascii=False, indent=2)
        )

        response, model_id, tokens = self._call_model(
            prompt, 'quality_check', max_tokens=4096, temperature=0.2
        )

        result = QualityCheckResult()
        result.raw_response = response
        result.model_used = model_id
        result.tokens_used = tokens

        try:
            json_str = self._extract_json(response)
            if json_str:
                data = json.loads(json_str)
                result.overall_score = data.get('overall_score', 0)
                result.score_breakdown = self._safe_get_dict(data, 'score_breakdown')
                result.keyword_coverage = self._safe_get_dict(data, 'keyword_coverage')
                result.authenticity_check = self._safe_get_dict(data, 'authenticity_check')
                result.improvement_analysis = self._safe_get_dict(data, 'improvement_analysis')
                result.recruiter_feedback = self._safe_get_dict(data, 'recruiter_feedback')
                result.evidence_validation = self._safe_get_list(data, 'evidence_validation')
                result.final_verdict = self._safe_get_dict(data, 'final_verdict')
                result.success = True
            else:
                result.success = False
                result.error = "无法从响应中提取JSON"
        except Exception as e:
            logger.error(f"质量验证失败: {e}")
            result.success = False
            result.error = str(e)

        logger.info(f"阶段4完成: overall_score={result.overall_score}")
        return result

    # ==================== 完整流程 ====================

    def tailor(self, resume_content: str, jd_content: str,
               progress_callback: Optional[Callable[[int, str, int], None]] = None) -> TailorResultV2:
        """
        完整五阶段定制流程

        Args:
            resume_content: 原版简历
            jd_content: 职位JD
            progress_callback: 进度回调函数 (stage, message, progress)

        Returns:
            TailorResultV2: 完整定制结果
        """

        def report_progress(stage: int, message: str, progress: int):
            """内部进度报告函数"""
            if progress_callback:
                try:
                    progress_callback(stage, message, progress)
                except Exception as e:
                    logger.warning(f"进度回调失败: {e}")

        def simulate_progress(stage: int, messages: list, start_pct: int, end_pct: int, stop_event: threading.Event):
            """后台线程模拟进度更新"""
            for i, msg in enumerate(messages):
                if stop_event.is_set():
                    return
                pct = int(start_pct + (end_pct - start_pct) * (i + 1) / (len(messages) + 1))
                report_progress(stage, msg, pct)
                stop_event.wait(1.5)  # 每1.5秒更新一次

        logger.info("开始五阶段定制流程（并行优化版）")

        result = TailorResultV2()

        # 用于线程间共享的统计数据（线程安全）
        stats_lock = threading.Lock()

        try:
            # ===== 阶段0和阶段1并行执行 =====
            # 这两个阶段完全独立，可以并行执行
            parallel_stop_event = threading.Event()

            # 并行进度消息（交替显示两个阶段的消息）
            parallel_messages = [
                "正在理解你的经历亮点...",
                "正在分析职位核心要求...",
                "正在提取关键技能...",
                "正在解码JD关键词...",
                "正在匹配专业能力...",
                "正在评估岗位需求..."
            ]
            parallel_progress_thread = threading.Thread(
                target=simulate_progress,
                args=(0, parallel_messages, 0, 38, parallel_stop_event),
                daemon=True
            )
            parallel_progress_thread.start()

            # 使用 ThreadPoolExecutor 并行执行（2秒错峰避免并发500错误）
            with ThreadPoolExecutor(max_workers=2) as executor:
                future_parse = executor.submit(self.parse_resume, resume_content)
                time.sleep(2)  # 错峰：智谱AI同一API key并发请求会返回500
                future_decode = executor.submit(self.decode_jd, jd_content)

                # 等待两个任务完成
                result.parse_result = future_parse.result()
                result.decode_result = future_decode.result()

            parallel_stop_event.set()
            parallel_progress_thread.join(timeout=0.1)

            # decode_jd 结果验证
            jd_ok = result.decode_result.success
            jd_title = result.decode_result.job_title or ''
            jd_kw_count = len(result.decode_result.keyword_weights or {})
            logger.info(f"📋 decode_jd 结果: success={jd_ok}, job_title='{jd_title}', keyword_count={jd_kw_count}")
            if not jd_ok:
                logger.warning(f"⚠️ decode_jd 失败: {result.decode_result.error}，将使用原始JD文本作为兜底")
            if not jd_title:
                logger.warning(f"⚠️ decode_jd 未提取到职位名称，JD解析可能不完整")
            if jd_kw_count == 0:
                logger.warning(f"⚠️ decode_jd 未提取到关键词权重，JD解析可能不完整")

            # 低置信度警告
            if result.parse_result.parsing_confidence < 0.7:
                logger.warning(f"⚠️ 简历解析置信度较低 ({result.parse_result.parsing_confidence:.2f})，定制质量可能受影响")
            report_progress(1, "简历和职位分析完成", 40)

            # 阶段2: 匹配分析
            stop_event = threading.Event()
            thread = threading.Thread(
                target=simulate_progress,
                args=(2, [
                    "正在寻找你与职位的契合点...",
                    "正在挖掘你的独特优势...",
                    "正在分析如何扬长避短...",
                    "正在制定个性化策略..."
                ], 40, 58, stop_event),
                daemon=True
            )
            thread.start()

            result.match_result = self.match_analysis(
                result.parse_result, result.decode_result
            )

            stop_event.set()
            thread.join(timeout=0.1)
            report_progress(2, "匹配度分析完成", 60)

            # 阶段3: 内容改写
            has_reviewers = bool(self._reviewer_providers)
            if has_reviewers:
                # Writer-Reviewer 闭环：进度由闭环内部管理 (58-82)
                result.rewrite_result = self.rewrite_content(
                    resume_content,
                    result.parse_result, result.match_result, result.decode_result,
                    progress_callback=lambda stage, msg, pct: report_progress(stage, msg, pct),
                    jd_content=jd_content
                )
            else:
                stop_event = threading.Event()
                thread = threading.Thread(
                    target=simulate_progress,
                    args=(3, [
                        "正在精心打磨你的简历...",
                        "正在优化表达方式...",
                        "正在突出核心亮点...",
                        "正在植入职位关键词..."
                    ], 60, 78, stop_event),
                    daemon=True
                )
                thread.start()

                result.rewrite_result = self.rewrite_content(
                    resume_content,
                    result.parse_result, result.match_result, result.decode_result,
                    jd_content=jd_content
                )

                stop_event.set()
                thread.join(timeout=0.1)
                report_progress(3, "简历内容定制完成", 80 if not has_reviewers else 82)

            # 阶段4: 质量验证
            s3_end = 82 if has_reviewers else 80
            stop_event = threading.Event()
            thread = threading.Thread(
                target=simulate_progress,
                args=(4, [
                    "正在进行最后的质量检查...",
                    "正在验证内容准确性...",
                    "正在生成专业建议...",
                    "即将完成..."
                ], s3_end, 93, stop_event),
                daemon=True
            )
            thread.start()

            result.quality_result = self.quality_check(
                resume_content,
                result.rewrite_result.tailored_resume,
                {
                    'job_title': result.decode_result.job_title,
                    'company_overview': result.decode_result.company_overview,
                    'salary_range': result.decode_result.salary_range,
                    'must_have': result.decode_result.must_have,
                    'nice_to_have': result.decode_result.nice_to_have,
                    'keyword_weights': result.decode_result.keyword_weights,
                    'implicit_requirements': result.decode_result.implicit_requirements,
                    'success_indicators': result.decode_result.success_indicators,
                    'red_flags': result.decode_result.red_flags,
                    'pain_points': result.decode_result.pain_points,
                    'competitor_profile': result.decode_result.competitor_profile
                },
                result.rewrite_result.change_log
            )

            stop_event.set()
            thread.join(timeout=0.1)
            report_progress(4, "质量验证完成", 95)

            # 汇总信息
            result.total_tokens = self.stats['total_tokens']
            result.total_latency_ms = self.stats['total_latency_ms']
            result.models_used = list(set([
                result.parse_result.model_used,
                result.decode_result.model_used,
                result.match_result.model_used,
                result.rewrite_result.model_used,
                result.quality_result.model_used
            ]))

            # 最终输出（兼容旧版接口）
            result.tailored_resume = result.rewrite_result.tailored_resume

            # 构建依据报告
            result.evidence_report = self._build_evidence_report(
                result.rewrite_result.change_log,
                result.quality_result.evidence_validation
            )

            # 构建优化摘要
            result.optimization_summary = {
                'jd_match_improvement': result.quality_result.improvement_analysis.get('improvement', 'N/A'),
                'key_improvements': result.quality_result.improvement_analysis.get('key_improvements', []),
                'quality_score': result.quality_result.overall_score,
                'keyword_coverage': result.quality_result.keyword_coverage.get('coverage_rate', 0),
                'recruiter_feedback': result.quality_result.recruiter_feedback
            }

            # 合并 Writer-Reviewer 闭环数据
            if result.rewrite_result and result.rewrite_result.review_iterations > 0:
                result.optimization_summary['review_loop'] = {
                    'iterations': result.rewrite_result.review_iterations,
                    'stop_reason': result.rewrite_result.review_stop_reason,
                    'final_score': result.rewrite_result.review_scores[-1]['overall_score'] if result.rewrite_result.review_scores else 'N/A',
                    'score_progression': [s['overall_score'] for s in result.rewrite_result.review_scores],
                    'iteration_details': result.rewrite_result.review_scores,
                    'feedback_summary': result.rewrite_result.review_feedback_summary,
                }
            else:
                result.optimization_summary['review_loop'] = None

            # 分析信息
            result.analysis = {
                'match_score': result.match_result.match_score,
                'match_level': result.match_result.match_level,
                'rewrite_intensity': result.match_result.rewrite_intensity,
                'strengths': result.match_result.strengths,
                'gaps': result.match_result.gaps,
                'recruiter_tips': result.match_result.recruiter_tips,
                'differentiation_strategy': result.match_result.differentiation_strategy,
                # 新增：分数计算明细
                'score_breakdown': result.match_result.score_breakdown,
                'requirements_analysis': result.match_result.requirements_analysis
            }

            logger.info(f"五阶段定制完成: tokens={result.total_tokens}, quality_score={result.quality_result.overall_score}")

        except Exception as e:
            import traceback as _tb
            full_traceback = _tb.format_exc()
            logger.error(f"五阶段定制失败: {e}\n{full_traceback}")
            # 写入文件确保不丢失
            try:
                with open('storage/pipeline_error.log', 'a', encoding='utf-8') as f:
                    f.write(f"\n{'='*60}\n")
                    f.write(f"时间: {__import__('datetime').datetime.now()}\n")
                    f.write(f"异常类型: {type(e).__name__}\n")
                    f.write(f"异常消息: {str(e)}\n")
                    f.write(f"Traceback:\n{full_traceback}\n")
            except Exception:
                pass
            result.tailored_resume = {'error': str(e), 'error_type': type(e).__name__, 'traceback': full_traceback}
            result.evidence_report = {'error': str(e)}
            result.optimization_summary = {'error': str(e)}

        return result

    def _build_evidence_report(self, change_log: List[Dict[str, Any]],
                                evidence_validation: List[Dict[str, Any]]) -> Dict[str, Any]:
        """构建依据报告"""
        total_items = len(change_log)
        validated = sum(1 for e in evidence_validation if e.get('has_evidence', False))
        needs_review = total_items - validated

        return {
            'total_items': total_items,
            'validated': validated,
            'needs_review': needs_review,
            'coverage': validated / total_items if total_items > 0 else 0,
            'change_log': change_log,
            'validation_details': evidence_validation
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取调用统计"""
        stats = self.stats.copy()
        model_stats = self.model_manager.get_stats()
        stats.update(model_stats)
        return stats
