"""真实 AI 集成测试 fixtures

注意：
- 集成测试默认跳过，需要通过 pytest -m integration 手动触发
- 需要 ZHIPU_API_KEY 环境变量
- 使用最简输入，最小化 token 消耗
"""
import os
import pytest

# 最简测试输入 — 最小化 token 消耗
MINIMAL_RESUME = """张测试\n13800000000\ntest@example.com\n
教育背景\n2018-2022 北京大学 计算机科学 本科\n
工作经历\n2022-至今 测试公司 后端工程师\n- 负责API开发"""

MINIMAL_JD = """后端开发工程师\n3年以上开发经验\n熟悉Python"""

# API 配置
API_TIMEOUT = 30  # 秒


def get_api_key():
    """获取 ZhipuAI API Key"""
    key = os.environ.get("ZHIPU_API_KEY", "")
    if not key:
        key = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
    return key


def has_api_key():
    """检查 API Key 是否可用"""
    return bool(get_api_key())


def pytest_runtest_setup(item):
    """集成测试需要 API Key"""
    if "tests/integration" in str(item.fspath):
        if not has_api_key():
            pytest.skip("ZHIPU_API_KEY 未设置，跳过集成测试")


@pytest.fixture
def api_key():
    """API Key fixture"""
    key = get_api_key()
    if not key:
        pytest.skip("ZHIPU_API_KEY 未设置")
    return key


@pytest.fixture
def minimal_input():
    """最简测试输入"""
    return {
        "resume_text": MINIMAL_RESUME,
        "jd_text": MINIMAL_JD,
    }


@pytest.fixture
def api_timeout():
    """API 超时时间"""
    return API_TIMEOUT
