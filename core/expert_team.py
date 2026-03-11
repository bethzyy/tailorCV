"""
AI 专家团队模块

实现两阶段调用架构：
- 阶段1: 分析+策略（合并3专家为1次调用）
- 阶段2: 生成+自验证（合并2层为1次调用）
"""

import json
import logging
import re
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field

from .model_manager import ModelManager, ModelResponse
from .config import config

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """分析阶段结果"""
    resume_analysis: Dict[str, Any] = field(default_factory=dict)
    jd_requirements: Dict[str, Any] = field(default_factory=dict)
    matching_strategy: Dict[str, Any] = field(default_factory=dict)
    raw_response: str = ""
    model_used: str = ""
    tokens_used: int = 0


@dataclass
class GenerationResult:
    """生成阶段结果"""
    tailored_resume: Dict[str, Any] = field(default_factory=dict)
    evidence_report: Dict[str, Any] = field(default_factory=dict)
    optimization_summary: Dict[str, Any] = field(default_factory=dict)
    raw_response: str = ""
    model_used: str = ""
    tokens_used: int = 0


class ExpertTeam:
    """AI 专家团队 - 两阶段调用"""

    def __init__(self):
        self.model_manager = ModelManager()

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
        result.model_used = response.model_used
        result.tokens_used = response.tokens_used

        logger.info(f"阶段1完成: model={response.model_used}, tokens={response.tokens_used}")
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
        result.model_used = response.model_used
        result.tokens_used = response.tokens_used

        logger.info(f"阶段2完成: model={response.model_used}, tokens={response.tokens_used}")
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
        """解析分析阶段响应 - 增强版fallback机制"""
        result = AnalysisResult()

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
        """尝试补全不完整的JSON（缺少外层{}）"""
        # 检测是否以 JSON 键开头（如 "resume_analysis":）
        trimmed = text.strip()

        # 如果以 " 开头但不是 { 开头，可能是缺少外层 {}
        if trimmed.startswith('"') and not trimmed.startswith('{'):
            # 尝试在开头加 {，结尾加 }
            completed = '{' + trimmed + '}'
            try:
                json.loads(completed)
                logger.info("成功补全不完整的JSON（添加外层{}）")
                return completed
            except json.JSONDecodeError:
                pass

        # 如果以 } 结尾但缺少开头 {
        if trimmed.endswith('}') and not trimmed.startswith('{'):
            completed = '{' + trimmed
            try:
                json.loads(completed)
                logger.info("成功补全不完整的JSON（添加开头{）")
                return completed
            except json.JSONDecodeError:
                pass

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
        """解析生成阶段响应 - 增强版fallback机制"""
        result = GenerationResult()

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
