"""
智谱AI 模型提供者

实现智谱AI（GLM系列）模型的调用接口。
"""

import os
import time
import logging
from typing import Dict, Any, Optional

from .base_provider import BaseModelProvider, ModelResponse

logger = logging.getLogger(__name__)


class ZhipuProvider(BaseModelProvider):
    """智谱AI 模型提供者"""

    # 支持的模型列表
    MODELS = {
        'glm-4.6': 'GLM-4.6',
        'glm-4-flash': 'GLM-4-Flash',
        'glm-4': 'GLM-4',
        'glm-4-air': 'GLM-4-Air',
    }

    def __init__(self, api_key: str = None):
        """
        初始化智谱AI提供者

        Args:
            api_key: API密钥（可选，默认从环境变量读取）
        """
        self._api_key = api_key or os.getenv('ZHIPU_API_KEY', '')
        self._client = None

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
            try:
                from zhipuai import ZhipuAI
                self._client = ZhipuAI(api_key=self._api_key)
            except ImportError:
                logger.error("zhipuai 未安装，请运行: pip install zhipuai")
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

    def call(self, prompt: str, model_id: str = None,
             max_tokens: int = 4096, temperature: float = 0.7,
             max_retries: int = 3, **kwargs) -> ModelResponse:
        """
        调用智谱AI模型

        Args:
            prompt: 输入提示词
            model_id: 模型ID（默认 glm-4.6）
            max_tokens: 最大输出token数
            temperature: 温度参数
            max_retries: 最大重试次数

        Returns:
            ModelResponse: 模型响应
        """
        self._ensure_client()

        model_id = model_id or 'glm-4.6'
        model_name = self.get_model_name(model_id)

        self.stats['total_calls'] += 1

        last_error = None
        for attempt in range(max_retries):
            try:
                start_time = time.time()

                response = self._client.chat.completions.create(
                    model=model_id,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }],
                    max_tokens=max_tokens,
                    temperature=temperature
                )

                latency_ms = int((time.time() - start_time) * 1000)
                content = response.choices[0].message.content

                # 更新统计
                self.stats['success_calls'] += 1
                self.stats['total_tokens'] += response.usage.total_tokens
                self.stats['total_latency_ms'] += latency_ms

                logger.info(f"智谱AI调用成功: model={model_id}, tokens={response.usage.total_tokens}, latency={latency_ms}ms")

                return ModelResponse(
                    success=True,
                    content=content,
                    model_id=model_id,
                    model_name=model_name,
                    tokens_used=response.usage.total_tokens,
                    latency_ms=latency_ms
                )

            except Exception as e:
                last_error = e
                logger.warning(f"智谱AI调用失败 (model={model_id}, attempt={attempt+1}): {e}")

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

    def _is_quota_error(self, error: Exception) -> bool:
        """判断是否为配额错误"""
        error_str = str(error).lower()
        quota_keywords = ['quota', 'limit', 'exhausted', 'rate', '1310']
        return any(kw in error_str for kw in quota_keywords)

    def get_stats(self) -> Dict[str, Any]:
        """获取调用统计"""
        stats = self.stats.copy()
        if stats['success_calls'] > 0:
            stats['avg_latency_ms'] = stats['total_latency_ms'] // stats['success_calls']
            stats['avg_tokens'] = stats['total_tokens'] // stats['success_calls']
        return stats
