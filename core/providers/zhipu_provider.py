"""
智谱AI 模型提供者

使用 Anthropic 兼容端点调用智谱AI（GLM系列）模型。
端点: https://open.bigmodel.cn/api/anthropic
"""

import os
import time
import logging
import traceback
from typing import Dict, Any, Optional, Callable

# 将 ZhipuProvider 的引用移动到文件顶部，避免循环导入
from .base_provider import BaseModelProvider, ModelResponse

logger = logging.getLogger(__name__)

# 将 Anthropic 客户端导入移动到 _ensure_client 方法中，避免循环导入
class ZhipuProvider(BaseModelProvider):
    """智谱AI 模型提供者 - Anthropic 兼容端点"""

    # Anthropic 兼容端点
    BASE_URL = "https://open.bigmodel.cn/api/anthropic"

    # 支持的模型列表
    MODELS = {
        'glm-5': 'GLM-5',
        'glm-4.7': 'GLM-4.7',
        'glm-4.6': 'GLM-4.6',
        'glm-4-flash': 'GLM-4-Flash',
        'glm-4': 'GLM-4',
        'glm-4-air': 'GLM-4-Air',
    }

    def __init__(self, api_key: str = None, client=None,
                 client_factory: Callable = None):
        """
        初始化智谱AI提供者

        Args:
            api_key: API密钥（可选，默认从环境变量读取）
            client: 外部注入的Anthropic客户端（可选，用于依赖注入避免循环导入）
            client_factory: 客户端工厂函数（可选，用于延迟创建客户端避免循环导入）
        """
        self._api_key = api_key or os.getenv('ZHIPU_API_KEY', '')
        self._client = client
        self._client_factory = client_factory

        # 调用统计
        self.stats = {
            'total_calls': 0,
            'success_calls': 0,
            'failed_calls': 0,
            'total_tokens': 0,
            'total_latency_ms': 0
        }

    def _ensure_client(self):
        """确保客户端已初始化"""
        if self._client is None and self._api_key:
            # 优先使用注入的工厂函数，避免循环导入
            if self._client_factory is not None:
                self._client = self._client_factory(self._api_key)
                logger.info(f"智谱AI客户端初始化成功 (通过工厂函数, Anthropic兼容端点: {self.BASE_URL})")
            else:
                try:
                    from anthropic import Anthropic
                    self._client = Anthropic(
                        api_key=self._api_key,
                        base_url=self.BASE_URL
                    )
                    logger.info(f"智谱AI客户端初始化成功 (Anthropic兼容端点: {self.BASE_URL})")
                except ImportError:
                    logger.error("anthropic 未安装，请运行: pip install anthropic")
                    raise

    @property
    def provider_id(self) -> str:
        return 'zhipu'

    @property
    def provider_name(self) -> str:
        return '智谱AI'

    @property
    def available_models(self) -> Dict[str, str]:
        return self.MODELS.copy()

    def is_available(self) -> bool:
        """检查智谱AI是否可用"""
        return bool(self._api_key)

    def _execute_api_call(self, model_id: str, prompt: str,
                          max_tokens: int) -> tuple:
        """
        执行单次API调用

        Args:
            model_id: 模型ID
            prompt: 输入提示词
            max_tokens: 最大输出token数

        Returns:
            tuple: (response, latency_ms)
        """
        start_time = time.time()

        # Anthropic 风格的 API 调用
        response = self._client.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        latency_ms = int((time.time() - start_time) * 1000)
        return response, latency_ms

    def _build_success_response(self, response, latency_ms: int,
                                model_id: str, model_name: str) -> ModelResponse:
        """
        构建成功响应并更新统计

        Args:
            response: API响应对象
            latency_ms: 延迟毫秒数
            model_id: 模型ID
            model_name: 模型名称

        Returns:
            ModelResponse: 模型响应
        """
        content = response.content[0].text

        # 更新统计
        total_tokens = response.usage.input_tokens + response.usage.output_tokens
        self.stats['success_calls'] += 1
        self.stats['total_tokens'] += total_tokens
        self.stats['total_latency_ms'] += latency_ms

        logger.info(f"智谱AI调用成功: model={model_id}, tokens={total_tokens}, latency={latency_ms}ms")

        return ModelResponse(
            success=True,
            content=content,
            model_id=model_id,
            model_name=model_name,
            tokens_used=total_tokens,
            latency_ms=latency_ms
        )

    def _call_with_retry(self, model_id: str, prompt: str,
                         max_tokens: int, max_retries: int,
                         model_name: str) -> ModelResponse:
        """
        带重试逻辑的模型调用

        Args:
            model_id: 模型ID
            prompt: 输入提示词
            max_tokens: 最大输出token数
            max_retries: 最大重试次数
            model_name: 模型名称

        Returns:
            ModelResponse: 模型响应
        """
        last_error = None
        for attempt in range(max_retries):
            try:
                response, latency_ms = self._execute_api_call(
                    model_id, prompt, max_tokens
                )
                return self._build_success_response(
                    response, latency_ms, model_id, model_name
                )

            except Exception as e:
                last_error = e
                logger.warning(f"智谱AI调用失败 (model={model_id}, attempt={attempt+1}): {e}\n{traceback.format_exc()}")

                # 配额错误不重试
                if self._is_quota_error(e):
                    break

                # 等待后重试
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    time.sleep(wait_time)

        # 失败
        self.stats['failed_calls'] += 1
        logger.error(f"智谱AI调用最终失败: {last_error}")

        return ModelResponse(
            success=False,
            content="",
            model_id=model_id,
            model_name=model_name,
            error_message=str(last_error)
        )

    def call(self, prompt: str, model_id: str = None,
             max_tokens: int = 4096, temperature: float = 0.7,
             max_retries: int = 3, **kwargs) -> ModelResponse:
        """
        调用智谱AI模型

        Args:
            prompt: 输入提示词
            model_id: 模型ID（默认 glm-5）
            max_tokens: 最大输出token数
            temperature: 温度参数
            max_retries: 最大重试次数

        Returns:
            ModelResponse: 模型响应
        """
        self._ensure_client()

        model_id = model_id or 'glm-5'
        model_name = self.get_model_name(model_id)

        self.stats['total_calls'] += 1

        return self._call_with_retry(
            model_id, prompt, max_tokens, max_retries, model_name
        )

    def _is_quota_error(self, error: Exception) -> bool:
        """判断是否为配额错误"""
        error_str = str(error).lower()
        quota_keywords = ['quota', 'limit', 'exhausted', 'rate', '1302', '1310']
        return any(kw in error_str for kw in quota_keywords)

    def get_stats(self) -> Dict[str, Any]:
        """获取调用统计"""
        stats = self.stats.copy()
        if stats['success_calls'] > 0:
            stats['avg_latency_ms'] = stats['total_latency_ms'] // stats['success_calls']
            stats['avg_tokens'] = stats['total_tokens'] // stats['success_calls']
        return stats
