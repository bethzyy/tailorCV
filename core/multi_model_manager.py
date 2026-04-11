"""
多模型管理器模块

负责管理多个模型提供者，支持并行调用和结果对比。
用于多模型工具。
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

from .providers.base_provider import BaseModelProvider, ModelResponse
from .providers.zhipu_provider import ZhipuProvider
from .providers.alibaba_provider import AlibabaProvider
from .config import config

logger = logging.getLogger(__name__)


@dataclass
class MultiModelResult:
    """多模型调用结果"""
    success: bool
    results: Dict[str, ModelResponse]  # provider_id -> response
    best_result: Optional[ModelResponse]
    error_message: str = ""

    def get_successful_results(self) -> List[Tuple[str, ModelResponse]]:
        """获取所有成功的结果"""
        return [(pid, resp) for pid, resp in self.results.items() if resp.success]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'success': self.success,
            'results': {
                pid: resp.to_dict()
                for pid, resp in self.results.items()
            },
            'best_result': self.best_result.to_dict() if self.best_result else None,
            'error_message': self.error_message
        }


class MultiModelManager:
    """多模型管理器 - 支持多个提供者并行调用"""

    def __init__(self, providers: Dict[str, BaseModelProvider] = None):
        """
        初始化多模型管理器

        Args:
            providers: 提供者字典 {provider_id: provider}（可选，默认自动检测）
        """
        if providers is None:
            providers = self._auto_detect_providers()

        self.providers = providers
        self.primary_provider = self._get_primary_provider()

        # 调用统计
        self.stats = {
            'total_calls': 0,
            'success_calls': 0,
            'failed_calls': 0,
            'parallel_calls': 0,
            'total_tokens': 0,
            'total_latency_ms': 0
        }

    def _auto_detect_providers(self) -> Dict[str, BaseModelProvider]:
        """自动检测可用的提供者"""
        providers = {}

        # 检测智谱
        zhipu = ZhipuProvider()
        if zhipu.is_available():
            providers['zhipu'] = zhipu
            logger.info("检测到智谱AI提供者")

        # 检测阿里云
        alibaba = AlibabaProvider()
        if alibaba.is_available():
            providers['alibaba'] = alibaba
            logger.info("检测到阿里云提供者")

        if not providers:
            logger.warning("未检测到任何可用的模型提供者")

        return providers

    def _get_primary_provider(self) -> Optional[BaseModelProvider]:
        """获取首选提供者"""
        # 优先智谱
        if 'zhipu' in self.providers:
            return self.providers['zhipu']
        # 否则返回第一个
        if self.providers:
            return list(self.providers.values())[0]
        return None

    @property
    def available_providers(self) -> Dict[str, str]:
        """获取可用提供者列表"""
        return {
            pid: provider.provider_name
            for pid, provider in self.providers.items()
        }

    @property
    def available_models(self) -> Dict[str, Dict[str, str]]:
        """获取所有提供者的可用模型"""
        return {
            pid: provider.available_models
            for pid, provider in self.providers.items()
        }

    def call_single(self, prompt: str, provider_id: str = None,
                    model_id: str = None, max_tokens: int = 4096,
                    temperature: float = 0.7, max_retries: int = 3) -> ModelResponse:
        """
        调用单个模型

        Args:
            prompt: 输入提示词
            provider_id: 提供者ID（可选，使用首选）
            model_id: 模型ID（可选，使用默认）
            max_tokens: 最大输出token数
            temperature: 温度参数
            max_retries: 最大重试次数

        Returns:
            ModelResponse: 模型响应
        """
        self.stats['total_calls'] += 1

        # 选择提供者
        if provider_id and provider_id in self.providers:
            provider = self.providers[provider_id]
        else:
            provider = self.primary_provider

        if provider is None:
            self.stats['failed_calls'] += 1
            return ModelResponse(
                success=False,
                content="",
                model_id="",
                model_name="",
                error_message="无可用的模型提供者"
            )

        # 调用模型
        response = provider.call(
            prompt=prompt,
            model_id=model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            max_retries=max_retries
        )

        # 更新统计
        if response.success:
            self.stats['success_calls'] += 1
            self.stats['total_tokens'] += response.tokens_used
            self.stats['total_latency_ms'] += response.latency_ms
        else:
            self.stats['failed_calls'] += 1

        return response

    def call_parallel(self, prompt: str, provider_ids: List[str] = None,
                      model_ids: Dict[str, str] = None,
                      max_tokens: int = 4096, temperature: float = 0.7,
                      max_retries: int = 3) -> MultiModelResult:
        """
        并行调用多个模型

        Args:
            prompt: 输入提示词
            provider_ids: 要调用的提供者ID列表（可选，默认全部）
            model_ids: 每个提供者使用的模型 {provider_id: model_id}
            max_tokens: 最大输出token数
            temperature: 温度参数
            max_retries: 最大重试次数

        Returns:
            MultiModelResult: 多模型结果
        """
        self.stats['total_calls'] += 1
        self.stats['parallel_calls'] += 1

        model_ids = model_ids or {}

        # 确定要调用的提供者
        target_providers = self._get_target_providers(provider_ids)
        
        if not target_providers:
            return MultiModelResult(
                success=False,
                results={},
                best_result=None,
                error_message="无可用的模型提供者"
            )

        # 并行调用
        results = self._execute_parallel_calls(
            target_providers, prompt, model_ids, max_tokens, temperature, max_retries
        )

        # 找出最佳结果并更新统计
        return self._process_parallel_results(results)

    def _get_target_providers(self, provider_ids: Optional[List[str]]) -> Dict[str, BaseModelProvider]:
        """获取目标提供者字典"""
        if provider_ids:
            return {
                pid: self.providers[pid]
                for pid in provider_ids
                if pid in self.providers
            }
        return self.providers

    def _execute_parallel_calls(
        self,
        target_providers: Dict[str, BaseModelProvider],
        prompt: str,
        model_ids: Dict[str, str],
        max_tokens: int,
        temperature: float,
        max_retries: int
    ) -> Dict[str, ModelResponse]:
        """执行并行调用"""
        results = {}
        with ThreadPoolExecutor(max_workers=len(target_providers)) as executor:
            futures = {}
            for pid, provider in target_providers.items():
                future = executor.submit(
                    provider.call,
                    prompt=prompt,
                    model_id=model_ids.get(pid),
                    max_tokens=max_tokens,
                    temperature=temperature,
                    max_retries=max_retries
                )
                futures[future] = pid

            for future in futures:
                pid = futures[future]
                try:
                    response = future.result()
                    results[pid] = response
                except Exception as e:
                    logger.error(f"提供者 {pid} 调用异常: {e}")
                    results[pid] = ModelResponse(
                        success=False,
                        content="",
                        model_id="",
                        model_name="",
                        error_message=str(e)
                    )
        return results

    def _process_parallel_results(self, results: Dict[str, ModelResponse]) -> MultiModelResult:
        """处理并行调用结果，更新统计并返回MultiModelResult"""
        successful_results = [
            (pid, resp) for pid, resp in results.items() if resp.success
        ]

        best_result = None
        if successful_results:
            # 选择响应时间最短的作为最佳结果
            best_result = min(successful_results, key=lambda x: x[1].latency_ms)[1]
            self.stats['success_calls'] += 1
            self.stats['total_tokens'] += sum(r.tokens_used for _, r in successful_results)
            self.stats['total_latency_ms'] += max(r.latency_ms for _, r in successful_results)
        else:
            self.stats['failed_calls'] += 1

        return MultiModelResult(
            success=len(successful_results) > 0,
            results=results,
            best_result=best_result,
            error_message="" if successful_results else "所有模型调用失败"
        )

    def call_with_fallback(self, prompt: str, provider_order: List[str] = None,
                           max_tokens: int = 4096, temperature: float = 0.7,
                           max_retries: int = 3) -> ModelResponse:
        """
        带降级策略的调用（依次尝试各提供者）

        Args:
            prompt: 输入提示词
            provider_order: 提供者优先级顺序（可选）
            max_tokens: 最大输出token数
            temperature: 温度参数
            max_retries: 最大重试次数

        Returns:
            ModelResponse: 第一个成功的响应
        """
        self.stats['total_calls'] += 1

        # 确定顺序
        if provider_order is None:
            # 使用切片创建副本，避免修改原始字典键视图
            provider_order = list(self.providers.keys())

        last_error = None
        for pid in provider_order:
            if pid not in self.providers:
                continue

            provider = self.providers[pid]
            response = provider.call(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                max_retries=max_retries
            )

            if response.success:
                self.stats['success_calls'] += 1
                self.stats['total_tokens'] += response.tokens_used
                self.stats['total_latency_ms'] += response.latency_ms
                return response

            last_error = response.error_message

        # 全部失败
        self.stats['failed_calls'] += 1
        return ModelResponse(
            success=False,
            content="",
            model_id="",
            model_name="",
            error_message=str(last_error)
        )

    def get_stats(self) -> Dict[str, Any]:
        """获取调用统计"""
        stats = self.stats.copy()
        if stats['success_calls'] > 0:
            stats['avg_latency_ms'] = stats['total_latency_ms'] // stats['success_calls']
            stats['avg_tokens'] = stats['total_tokens'] // stats['success_calls']

        # 各提供者统计
        stats['providers'] = {
            pid: provider.get_stats()
            for pid, provider in self.providers.items()
        }

        return stats

    def is_available(self) -> bool:
        """检查是否有可用的提供者"""
        return len(self.providers) > 0

    def get_provider(self, provider_id: str) -> Optional[BaseModelProvider]:
        """获取指定提供者"""
        return self.providers.get(provider_id)
