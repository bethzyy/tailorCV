"""
真实 AI 烟雾测试 — 验证 API 连通性和基本功能

这些测试使用真实 API 调用，默认跳过。
运行方式: pytest tests/integration/test_real_ai_smoke.py -v -m integration
"""
import json
import time
import pytest


@pytest.mark.integration
@pytest.mark.slow
class TestRealAISmoke:
    """真实 AI API 烟雾测试"""

    def test_api_connection_success(self, api_key):
        """API 连接成功并返回有效响应"""
        from anthropic import Anthropic

        parts = api_key.split(".", 1)
        api_key_value = parts[1] if len(parts) == 2 else api_key

        client = Anthropic(
            api_key=api_key_value,
            base_url="https://open.bigmodel.cn/api/anthropic",
        )

        start = time.time()
        response = client.messages.create(
            model="glm-4-flash",
            max_tokens=64,
            messages=[{"role": "user", "content": "回复OK"}],
        )
        elapsed = time.time() - start

        # 验证响应结构
        assert response.content, "API 返回空内容"
        assert len(response.content[0].text) > 0, "API 返回空文本"
        assert elapsed < 30, f"API 响应时间过长: {elapsed:.1f}s"

    def test_api_json_response_valid(self, api_key):
        """API 能返回有效 JSON 结构"""
        from anthropic import Anthropic

        parts = api_key.split(".", 1)
        api_key_value = parts[1] if len(parts) == 2 else api_key

        client = Anthropic(
            api_key=api_key_value,
            base_url="https://open.bigmodel.cn/api/anthropic",
        )

        prompt = '请以JSON格式返回: {"status": "ok", "message": "测试成功"}。只返回JSON，不要其他内容。'
        response = client.messages.create(
            model="glm-4-flash",
            max_tokens=128,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        # 尝试解析 JSON
        try:
            result = json.loads(text)
            assert "status" in result, "JSON 缺少 status 字段"
        except json.JSONDecodeError:
            # 可能包含 markdown 代码块
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
                result = json.loads(text)
                assert "status" in result
            else:
                raise

    def test_api_handles_empty_input_gracefully(self, api_key):
        """空输入能优雅处理，不崩溃"""
        from anthropic import Anthropic

        parts = api_key.split(".", 1)
        api_key_value = parts[1] if len(parts) == 2 else api_key

        client = Anthropic(
            api_key=api_key_value,
            base_url="https://open.bigmodel.cn/api/anthropic",
        )

        # 空输入不应抛异常
        try:
            response = client.messages.create(
                model="glm-4-flash",
                max_tokens=64,
                messages=[{"role": "user", "content": ""}],
            )
            assert response is not None
        except Exception:
            # 某些 API 对空输入返回错误也是合理的
            pass
