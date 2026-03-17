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
from typing import Dict, Any, Optional, Tuple, List, Callable, TYPE_CHECKING
from pathlib import Path
from dataclasses import dataclass, field

from .config import config

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


@dataclass
class RewriteContentResult(StageResult):
    """阶段3: 内容深度改写结果"""
    tailored_resume: Dict[str, Any] = field(default_factory=dict)
    change_log: List[Dict[str, Any]] = field(default_factory=list)
    keyword_coverage: Dict[str, Any] = field(default_factory=dict)


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
                        return text[start_idx:i+1]

        # 如果没有找到完整的JSON，尝试补全
        return self._try_complete_json(text)

    def _try_complete_json(self, text: str) -> Optional[str]:
        """尝试补全不完整的JSON（缺少外层{}）

        处理多种前导字符情况：
        - 空格、换行符、制表符开头
        - 以 "key": 开头但缺少外层 {}
        - 以 } 结尾但缺少开头 {
        """
        # 先去除前导空白，保留原始内容
        trimmed = text.strip()

        if not trimmed:
            return None

        # 情况1：以 " 开头但不是 { 开头 → 缺少外层 {}
        if trimmed.startswith('"') and not trimmed.startswith('{'):
            completed = '{' + trimmed + '}'
            try:
                json.loads(completed)
                logger.info("成功补全JSON（添加外层{}）")
                return completed
            except json.JSONDecodeError as e:
                logger.debug(f"补全尝试1失败: {e}")
                # 继续尝试其他方案

        # 情况2：以 } 结尾但缺少开头 {
        if trimmed.endswith('}') and not trimmed.startswith('{'):
            completed = '{' + trimmed
            try:
                json.loads(completed)
                logger.info("成功补全JSON（添加开头{）")
                return completed
            except json.JSONDecodeError as e:
                logger.debug(f"补全尝试2失败: {e}")

        # 情况3：尝试查找第一个 " 和最后一个 } 之间的内容
        first_quote = trimmed.find('"')
        last_brace = trimmed.rfind('}')
        if first_quote != -1 and last_brace != -1 and first_quote < last_brace:
            inner = trimmed[first_quote:last_brace+1]
            completed = '{' + inner + '}'
            try:
                json.loads(completed)
                logger.info("成功补全JSON（提取内部内容）")
                return completed
            except json.JSONDecodeError as e:
                logger.debug(f"补全尝试3失败: {e}")

        return None

    def _repair_json(self, json_str: str) -> Optional[str]:
        """尝试修复常见的JSON错误"""
        repaired = json_str

        # 1. 修复末尾多余的逗号
        repaired = re.sub(r',\s*}', '}', repaired)
        repaired = re.sub(r',\s*]', ']', repaired)

        # 2. 修复缺失的引号（只对未加引号的键）
        # 使用负向前瞻确保键名前面没有引号
        repaired = re.sub(r'(?<!")(\b\w+\b)(?=\s*:)', r'"\1"', repaired)

        # 3. 修复单引号（仅当整个字符串用单引号时）
        # 避免破坏已经是双引号的内容

        return repaired if repaired != json_str else None

    def _safe_get_dict(self, data: dict, key: str) -> dict:
        """安全获取字典字段"""
        value = data.get(key, {})
        if isinstance(value, dict):
            return value
        elif isinstance(value, list):
            return {key: value}
        else:
            return {}

    def _safe_get_list(self, data: dict, key: str) -> list:
        """安全获取列表字段"""
        value = data.get(key, [])
        if isinstance(value, list):
            return value
        else:
            return []

    def _validate_analysis_result(self, result: AnalysisResult) -> None:
        """验证分析结果的关键字段"""
        # 确保matching_strategy有基本字段
        if not result.matching_strategy:
            result.matching_strategy = {}
        if 'match_score' not in result.matching_strategy:
            result.matching_strategy['match_score'] = 50
        if 'match_level' not in result.matching_strategy:
            result.matching_strategy['match_level'] = '未知'
        if 'strengths' not in result.matching_strategy:
            result.matching_strategy['strengths'] = []
        if 'gaps' not in result.matching_strategy:
            result.matching_strategy['gaps'] = []

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
        # 确保tailored_resume有基本结构
        if not result.tailored_resume:
            result.tailored_resume = {}

        required_fields = ['basic_info', 'education', 'work_experience', 'skills']
        for field in required_fields:
            if field not in result.tailored_resume:
                result.tailored_resume[field] = [] if field != 'basic_info' else {}

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
        # 尝试匹配 ```json ... ``` 格式
        json_pattern = r'```json\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, text)
        if match:
            return match.group(1)

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
                        return text[start_idx:i+1]

        return None

    def _safe_get_dict(self, data: dict, key: str, default=None) -> dict:
        """安全获取字典字段"""
        if default is None:
            default = {}
        value = data.get(key, default)
        return value if isinstance(value, dict) else default

    def _safe_get_list(self, data: dict, key: str, default=None) -> list:
        """安全获取列表字段"""
        if default is None:
            default = []
        value = data.get(key, default)
        return value if isinstance(value, list) else default

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
                result.match_score = data.get('match_score', 50)
                result.match_level = data.get('match_level', '未知')
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

    def rewrite_content(self, original_resume: str,
                        parsed_resume: ParseResumeResult,
                        match_result: MatchAnalysisResult,
                        jd_analysis: DecodeJdResult) -> RewriteContentResult:
        """阶段3: 内容深度改写"""
        logger.info("开始阶段3: 内容深度改写")

        # 数据验证日志
        if not parsed_resume.work_experience and not parsed_resume.projects:
            logger.warning("⚠️ 解析结果为空，将使用原始简历作为主要参考")
        logger.info(f"原始简历长度: {len(original_resume)} 字符")

        prompt = self.prompts['rewrite_content'].format(
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
            }, ensure_ascii=False, indent=2)
        )

        response, model_id, tokens = self._call_model(
            prompt, 'rewrite_content', max_tokens=6144, temperature=0.5
        )

        result = RewriteContentResult()
        result.raw_response = response
        result.model_used = model_id
        result.tokens_used = tokens

        try:
            json_str = self._extract_json(response)
            if json_str:
                data = json.loads(json_str)
                result.tailored_resume = self._safe_get_dict(data, 'tailored_resume')
                result.change_log = self._safe_get_list(data, 'change_log')
                result.keyword_coverage = self._safe_get_dict(data, 'keyword_coverage')
                result.success = True
            else:
                result.success = False
                result.error = "无法从响应中提取JSON"
        except Exception as e:
            logger.error(f"内容改写失败: {e}")
            result.success = False
            result.error = str(e)

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

        logger.info("开始五阶段定制流程")

        result = TailorResultV2()

        try:
            # 阶段0: 解析简历结构
            stop_event = threading.Event()
            thread = threading.Thread(
                target=simulate_progress,
                args=(0, [
                    "正在识别简历格式...",
                    "正在提取基本信息...",
                    "正在解析工作经历...",
                    "正在分析技能关键词..."
                ], 0, 18, stop_event),
                daemon=True
            )
            thread.start()

            result.parse_result = self.parse_resume(resume_content)

            stop_event.set()  # 停止进度模拟
            thread.join(timeout=0.1)
            # 低置信度警告
            if result.parse_result.parsing_confidence < 0.7:
                logger.warning(f"⚠️ 简历解析置信度较低 ({result.parse_result.parsing_confidence:.2f})，定制质量可能受影响")
            report_progress(0, "简历结构解析完成", 20)

            # 阶段1: 解码JD
            stop_event = threading.Event()
            thread = threading.Thread(
                target=simulate_progress,
                args=(1, [
                    "正在识别职位核心要求...",
                    "正在提取关键词权重...",
                    "正在分析隐性需求...",
                    "正在评估竞争态势..."
                ], 20, 38, stop_event),
                daemon=True
            )
            thread.start()

            result.decode_result = self.decode_jd(jd_content)

            stop_event.set()
            thread.join(timeout=0.1)
            report_progress(1, "职位需求分析完成", 40)

            # 阶段2: 匹配分析
            stop_event = threading.Event()
            thread = threading.Thread(
                target=simulate_progress,
                args=(2, [
                    "正在计算匹配度得分...",
                    "正在识别优势亮点...",
                    "正在分析差距项...",
                    "正在制定改写策略..."
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
            stop_event = threading.Event()
            thread = threading.Thread(
                target=simulate_progress,
                args=(3, [
                    "正在优化个人总结...",
                    "正在调整工作经历...",
                    "正在强化项目描述...",
                    "正在植入关键词..."
                ], 60, 78, stop_event),
                daemon=True
            )
            thread.start()

            result.rewrite_result = self.rewrite_content(
                resume_content,  # 传递原始简历作为主要参考
                result.parse_result, result.match_result, result.decode_result
            )

            stop_event.set()
            thread.join(timeout=0.1)
            report_progress(3, "简历内容定制完成", 80)

            # 阶段4: 质量验证
            stop_event = threading.Event()
            thread = threading.Thread(
                target=simulate_progress,
                args=(4, [
                    "正在检查内容一致性...",
                    "正在验证关键词覆盖...",
                    "正在评估真实性...",
                    "正在生成优化建议..."
                ], 80, 93, stop_event),
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

            # 分析信息
            result.analysis = {
                'match_score': result.match_result.match_score,
                'match_level': result.match_result.match_level,
                'rewrite_intensity': result.match_result.rewrite_intensity,
                'strengths': result.match_result.strengths,
                'gaps': result.match_result.gaps,
                'recruiter_tips': result.match_result.recruiter_tips,
                'differentiation_strategy': result.match_result.differentiation_strategy
            }

            logger.info(f"五阶段定制完成: tokens={result.total_tokens}, quality_score={result.quality_result.overall_score}")

        except Exception as e:
            logger.error(f"五阶段定制失败: {e}")
            result.tailored_resume = {'error': str(e)}
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
