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
            json_str = self._extract_json_from_response(response)
            
            if json_str:
                try:
                    data = json.loads(json_str)
                    logger.info(f"JSON解析成功")

                    # 安全获取各字段，带完整默认值
                    result.resume_analysis = self._safe_get_dict(data, 'resume_analysis')
                    result.jd_requirements = self._safe_get_dict(data, 'jd_requirements')
                    result.matching_strategy = self._safe_get_dict(data, 'matching_strategy')

                    # 验证关键字段
                    self._validate_analysis_result(result)

                except json.JSONDecodeError as e:
                    logger.error(f"JSON解析失败: {e}, 尝试修复...")
                    result = self._try_repair_analysis_json(json_str, response)
            else:
                logger.warning("未找到JSON响应，尝试从文本提取关键信息")
                result = self._extract_from_text(response)

        except Exception as e:
            # 捕获所有异常，确保不会传播到调用方
            logger.error(f"解析响应时发生异常: {e}")
            logger.debug(f"原始响应前200字符: {response[:200] if response else 'empty'}")
            result = self._create_fallback_analysis_result(response)

        return result

    def _extract_json_from_response(self, response: str) -> Optional[str]:
        """从响应中提取JSON字符串"""
        # Level 1: 尝试匹配 