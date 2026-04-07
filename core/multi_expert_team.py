"""
多模型 AI 专家团队模块

实现多模型并行调用架构，支持结果对比。
用于多模型工具。
"""

import json
import logging
import re
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

from .multi_model_manager import MultiModelManager, MultiModelResult
from .providers.base_provider import ModelResponse
from .config import config
from . import response_parser

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """分析阶段结果"""
    resume_analysis: Dict[str, Any] = field(default_factory=dict)
    jd_requirements: Dict[str, Any] = field(default_factory=dict)
    matching_strategy: Dict[str, Any] = field(default_factory=dict)
    raw_response: str = ""
    model_used: str = ""
    provider_id: str = ""
    tokens_used: int = 0


@dataclass
class GenerationResult:
    """生成阶段结果"""
    tailored_resume: Dict[str, Any] = field(default_factory=dict)
    evidence_report: Dict[str, Any] = field(default_factory=dict)
    optimization_summary: Dict[str, Any] = field(default_factory=dict)
    raw_response: str = ""
    model_used: str = ""
    provider_id: str = ""
    tokens_used: int = 0


@dataclass
class MultiModelAnalysisResult:
    """多模型分析结果"""
    success: bool
    results: Dict[str, AnalysisResult]  # provider_id -> result
    best_result: Optional[AnalysisResult]
    error_message: str = ""

    def get_successful_results(self) -> List[Tuple[str, AnalysisResult]]:
        """获取所有成功的结果"""
        return [(pid, r) for pid, r in self.results.items() if r.matching_strategy]


@dataclass
class MultiModelGenerationResult:
    """多模型生成结果"""
    success: bool
    results: Dict[str, GenerationResult]  # provider_id -> result
    best_result: Optional[GenerationResult]
    error_message: str = ""


class MultiExpertTeam:
    """多模型 AI 专家团队 - 并行调用"""

    def __init__(self, multi_manager: MultiModelManager = None):
        """
        初始化多模型专家团队

        Args:
            multi_manager: 多模型管理器（可选，默认自动创建）
        """
        if multi_manager is None:
            multi_manager = MultiModelManager()

        self.multi_manager = multi_manager

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

    def analyze_parallel(self, resume_content: str, jd_content: str,
                         provider_ids: List[str] = None) -> MultiModelAnalysisResult:
        """
        并行分析（所有模型同时调用）

        Args:
            resume_content: 原版简历内容
            jd_content: 职位JD内容
            provider_ids: 要使用的提供者列表（可选，默认全部）

        Returns:
            MultiModelAnalysisResult: 多模型分析结果
        """
        self.stats['analyze_calls'] += 1
        logger.info(f"开始并行分析: providers={provider_ids or 'all'}")

        # 构建 Prompt
        prompt = self.analyze_prompt.format(
            resume_content=resume_content,
            jd_content=jd_content
        )

        # 并行调用
        multi_result = self.multi_manager.call_parallel(
            prompt=prompt,
            provider_ids=provider_ids,
            max_tokens=4096,
            temperature=0.3
        )

        # 解析各模型结果
        results = {}
        for provider_id, response in multi_result.results.items():
            if response.success:
                result = self._parse_analysis_response(response.content)
                result.model_used = response.model_id
                result.provider_id = provider_id
                result.tokens_used = response.tokens_used
                results[provider_id] = result

                self.stats['total_tokens'] += response.tokens_used
                self.stats['total_latency_ms'] += response.latency_ms

        # 选择最佳结果
        best_result = None
        if results:
            # 选择第一个成功的结果作为最佳（后续可根据质量评分选择）
            best_result = list(results.values())[0]

        return MultiModelAnalysisResult(
            success=len(results) > 0,
            results=results,
            best_result=best_result,
            error_message="" if results else "所有模型分析失败"
        )

    def generate_parallel(self, analysis_results: Dict[str, AnalysisResult],
                         original_resume: str, jd_content: str,
                         provider_ids: List[str] = None) -> MultiModelGenerationResult:
        """
        并行生成（所有模型同时调用）

        Args:
            analysis_results: 各提供者的分析结果 {provider_id: AnalysisResult}
            original_resume: 原版简历
            jd_content: 职位JD
            provider_ids: 要使用的提供者列表（可选）

        Returns:
            MultiModelGenerationResult: 多模型生成结果
        """
        self.stats['generate_calls'] += 1
        logger.info("开始并行生成")

        results = {}

        # 为每个提供者构建不同的 prompt（使用其自己的分析结果）
        def generate_for_provider(provider_id: str) -> Tuple[str, Optional[GenerationResult]]:
            if provider_id not in self.multi_manager.providers:
                return provider_id, None

            analysis = analysis_results.get(provider_id)
            if not analysis:
                # 使用最佳分析结果
                analysis = list(analysis_results.values())[0] if analysis_results else None

            if not analysis:
                return provider_id, None

            # 构建 Prompt
            analysis_json = json.dumps({
                'resume_analysis': analysis.resume_analysis,
                'jd_requirements': analysis.jd_requirements,
                'matching_strategy': analysis.matching_strategy
            }, ensure_ascii=False, indent=2)

            prompt = self.generate_prompt.format(
                analysis_result=analysis_json,
                original_resume=original_resume,
                jd_content=jd_content
            )

            # 调用模型
            response = self.multi_manager.call_single(
                prompt=prompt,
                provider_id=provider_id,
                max_tokens=6144,
                temperature=0.5
            )

            if response.success:
                result = self._parse_generation_response(response.content)
                result.model_used = response.model_id
                result.provider_id = provider_id
                result.tokens_used = response.tokens_used
                return provider_id, result

            return provider_id, None

        # 并行执行
        target_providers = provider_ids or list(self.multi_manager.providers.keys())

        with ThreadPoolExecutor(max_workers=len(target_providers)) as executor:
            futures = [executor.submit(generate_for_provider, pid) for pid in target_providers]

            for future in futures:
                try:
                    provider_id, result = future.result()
                    if result:
                        results[provider_id] = result
                        self.stats['total_tokens'] += result.tokens_used
                except Exception as e:
                    logger.error(f"生成异常: {e}")

        # 选择最佳结果
        best_result = None
        if results:
            best_result = list(results.values())[0]

        return MultiModelGenerationResult(
            success=len(results) > 0,
            results=results,
            best_result=best_result,
            error_message="" if results else "所有模型生成失败"
        )

    def tailor_parallel(self, resume_content: str, jd_content: str,
                       provider_ids: List[str] = None) -> Tuple[MultiModelAnalysisResult, MultiModelGenerationResult]:
        """
        完整并行定制流程

        Args:
            resume_content: 原版简历
            jd_content: 职位JD
            provider_ids: 要使用的提供者列表

        Returns:
            Tuple: 多模型分析结果和生成结果
        """
        logger.info("开始完整并行定制流程")

        # 阶段1: 并行分析
        analysis = self.analyze_parallel(resume_content, jd_content, provider_ids)

        if not analysis.success:
            # 返回空生成结果
            return analysis, MultiModelGenerationResult(
                success=False,
                results={},
                best_result=None,
                error_message="分析阶段失败"
            )

        # 阶段2: 并行生成（每个模型使用自己的分析结果）
        generation = self.generate_parallel(
            analysis.results,
            resume_content,
            jd_content,
            provider_ids
        )

        logger.info(f"并行定制流程完成: 成功模型数={len(generation.results)}")
        return analysis, generation

    def tailor_single(self, resume_content: str, jd_content: str,
                     provider_id: str = None) -> Tuple[AnalysisResult, GenerationResult]:
        """
        单模型定制流程（指定一个提供者）

        Args:
            resume_content: 原版简历
            jd_content: 职位JD
            provider_id: 提供者ID

        Returns:
            Tuple: 分析结果和生成结果
        """
        logger.info(f"开始单模型定制流程: provider={provider_id}")

        # 阶段1: 分析
        prompt = self.analyze_prompt.format(
            resume_content=resume_content,
            jd_content=jd_content
        )

        analysis_response = self.multi_manager.call_single(
            prompt=prompt,
            provider_id=provider_id,
            max_tokens=4096,
            temperature=0.3
        )

        if not analysis_response.success:
            raise RuntimeError(f"分析阶段失败: {analysis_response.error_message}")

        analysis_result = self._parse_analysis_response(analysis_response.content)
        analysis_result.model_used = analysis_response.model_id
        analysis_result.provider_id = analysis_response.provider_id if hasattr(analysis_response, 'provider_id') else provider_id
        analysis_result.tokens_used = analysis_response.tokens_used

        # 阶段2: 生成
        analysis_json = json.dumps({
            'resume_analysis': analysis_result.resume_analysis,
            'jd_requirements': analysis_result.jd_requirements,
            'matching_strategy': analysis_result.matching_strategy
        }, ensure_ascii=False, indent=2)

        prompt = self.generate_prompt.format(
            analysis_result=analysis_json,
            original_resume=resume_content,
            jd_content=jd_content
        )

        generation_response = self.multi_manager.call_single(
            prompt=prompt,
            provider_id=provider_id,
            max_tokens=6144,
            temperature=0.5
        )

        if not generation_response.success:
            raise RuntimeError(f"生成阶段失败: {generation_response.error_message}")

        generation_result = self._parse_generation_response(generation_response.content)
        generation_result.model_used = generation_response.model_id
        generation_result.provider_id = generation_response.provider_id if hasattr(generation_response, 'provider_id') else provider_id
        generation_result.tokens_used = generation_response.tokens_used

        logger.info(f"单模型定制完成: model={generation_result.model_used}")
        return analysis_result, generation_result

    # ==================== JSON 解析方法（复用自 ExpertTeam）====================

    def _parse_analysis_response(self, response: str) -> AnalysisResult:
        """解析分析阶段响应"""
        result = AnalysisResult()

        try:
            json_str = None
            extraction_method = None

            # Level 1: ```json ... ```
            json_pattern = r'```json\s*([\s\S]*?)\s*```'
            match = re.search(json_pattern, response)
            if match:
                json_str = match.group(1)
                extraction_method = 'code_block'

            # Level 2: 平衡JSON
            if not json_str:
                json_str = self._extract_balanced_json(response)
                if json_str:
                    extraction_method = 'balanced'

            # Level 3: 正则
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

                    result.resume_analysis = self._safe_get_dict(data, 'resume_analysis')
                    result.jd_requirements = self._safe_get_dict(data, 'jd_requirements')
                    result.matching_strategy = self._safe_get_dict(data, 'matching_strategy')

                    self._validate_analysis_result(result)

                except json.JSONDecodeError as e:
                    logger.error(f"JSON解析失败: {e}")
                    result = self._create_fallback_analysis_result(response)
            else:
                result = self._extract_from_text(response)

        except Exception as e:
            logger.error(f"解析响应异常: {e}")
            result = self._create_fallback_analysis_result(response)

        result.raw_response = response
        return result

    def _parse_generation_response(self, response: str) -> GenerationResult:
        """解析生成阶段响应"""
        result = GenerationResult()

        try:
            json_str = None

            json_pattern = r'```json\s*([\s\S]*?)\s*```'
            match = re.search(json_pattern, response)
            if match:
                json_str = match.group(1)

            if not json_str:
                json_str = self._extract_balanced_json(response)

            if not json_str:
                json_pattern = r'\{[\s\S]*\}'
                match = re.search(json_pattern, response)
                if match:
                    json_str = match.group(0)

            if json_str:
                try:
                    data = json.loads(json_str)
                    result.tailored_resume = self._safe_get_dict(data, 'tailored_resume')
                    result.evidence_report = self._safe_get_dict(data, 'evidence_report')
                    result.optimization_summary = self._safe_get_dict(data, 'optimization_summary')
                    self._validate_generation_result(result)
                except json.JSONDecodeError:
                    result = self._create_fallback_generation_result(response)
            else:
                result = self._create_fallback_generation_result(response)

        except Exception as e:
            logger.error(f"解析生成响应异常: {e}")
            result = self._create_fallback_generation_result(response)

        result.raw_response = response
        return result

    def _extract_balanced_json(self, text: str) -> Optional[str]:
        """使用栈匹配提取平衡的JSON"""
        return response_parser.extract_balanced_json(text)

    def _safe_get_dict(self, data: dict, key: str) -> dict:
        """安全获取字典字段"""
        return response_parser.safe_get_dict(data, key, default={})

    def _validate_analysis_result(self, result: AnalysisResult) -> None:
        """验证分析结果"""
        result.matching_strategy = response_parser.validate_analysis_fields(
            result.matching_strategy
        )

    def _validate_generation_result(self, result: GenerationResult) -> None:
        """验证生成结果"""
        result.tailored_resume = response_parser.validate_generation_fields(
            result.tailored_resume
        )

    def _create_fallback_analysis_result(self, response: str) -> AnalysisResult:
        """创建兜底分析结果"""
        result = AnalysisResult()
        result.matching_strategy = {
            'match_score': 50,
            'match_level': '未知',
            'strengths': ['无法解析AI响应'],
            'gaps': ['请检查原始输入'],
            'error': 'JSON解析失败'
        }
        return result

    def _create_fallback_generation_result(self, response: str) -> GenerationResult:
        """创建兜底生成结果"""
        result = GenerationResult()
        result.tailored_resume = {
            'basic_info': {},
            'education': [],
            'work_experience': [],
            'projects': [],
            'skills': [],
            'error': 'JSON解析失败'
        }
        result.evidence_report = {'total_items': 0, 'validated': 0, 'coverage': 0.0}
        result.optimization_summary = {'key_changes': ['无法解析AI响应']}
        return result

    def _extract_from_text(self, response: str) -> AnalysisResult:
        """从文本提取"""
        result = AnalysisResult()
        result.matching_strategy = {'match_score': 50, 'match_level': '未知', 'strengths': [], 'gaps': []}
        return result

    def get_stats(self) -> Dict[str, Any]:
        """获取调用统计"""
        stats = self.stats.copy()
        stats['providers'] = self.multi_manager.get_stats()
        return stats
