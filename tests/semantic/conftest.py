"""语义质量测试基础设施 — LLM-as-Judge 模式

核心设计：
- 用 glm-4-flash 做评判（便宜快速）
- 评判 prompt 模板化，可复用
- 返回结构化评分（1-5分 + 理由）
- 阈值可配置，默认 >= 3.5
"""
import json
import os
import pytest
from pathlib import Path

# 评判使用的模型（便宜快速）
JUDGE_MODEL = "glm-4-flash"

# 默认通过阈值
DEFAULT_PASS_THRESHOLD = 3.5

# 评判 prompt 模板
JUDGE_PROMPT_TEMPLATE = """你是一个专业简历评审专家。请评估以下 AI 生成的简历内容，从「{dimension}」角度打分（1-5分）。

评分标准：
5分 - 完全符合要求，无可挑剔
4分 - 基本符合，有小瑕疵
3分 - 部分符合，有明显问题
2分 - 大部分不符合要求
1分 - 完全不符合要求

原始简历内容：
{original_resume}

目标职位JD：
{target_jd}

AI生成的定制简历内容：
{generated_content}

请以 JSON 格式返回评分结果：
{{"score": <1-5的数字>, "reason": "<一句话理由>"}}"""

# 各维度评判 prompt
DIMENSION_PROMPTS = {
    "coherence": {
        "dimension": "内容连贯性",
        "description": "工作经历描述是否逻辑自洽，时间线是否合理，技能与经历是否一致",
    },
    "professionalism": {
        "dimension": "专业度",
        "description": "用词是否专业规范，不口语化不夸张，量化成果是否合理",
    },
    "no_hallucination": {
        "dimension": "信息真实性（反幻觉）",
        "description": "内容是否忠实于原始简历，没有编造经历、夸大职责、虚构成果",
    },
}


def get_api_key():
    """获取 ZhipuAI API Key"""
    key = os.environ.get("ZHIPU_API_KEY", "")
    if not key:
        key = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
    return key


def has_api_key():
    """检查是否有可用的 API Key"""
    return bool(get_api_key())


def call_judge(original_resume, target_jd, generated_content, dimension):
    """
    调用 LLM Judge 进行评分。

    Returns:
        dict: {"score": float, "reason": str} 或 None（API 不可用时）
    """
    api_key = get_api_key()
    if not api_key:
        return None

    dim_config = DIMENSION_PROMPTS.get(dimension, {"dimension": dimension})
    prompt = JUDGE_PROMPT_TEMPLATE.format(
        dimension=dim_config["dimension"],
        original_resume=original_resume[:2000],  # 截断避免超长
        target_jd=target_jd[:1000],
        generated_content=generated_content[:2000],
    )

    try:
        from anthropic import Anthropic

        # 解析 API key（支持 id.secret 格式）
        parts = api_key.split(".", 1)
        if len(parts) == 2:
            api_key_value = parts[1]
        else:
            api_key_value = api_key

        client = Anthropic(
            api_key=api_key_value,
            base_url="https://open.bigmodel.cn/api/anthropic",
        )
        response = client.messages.create(
            model=JUDGE_MODEL,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )

        # 解析 JSON 响应
        text = response.content[0].text.strip()
        # 尝试提取 JSON
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        result = json.loads(text)
        score = float(result.get("score", 0))
        reason = result.get("reason", "")

        return {"score": score, "reason": reason}

    except Exception as e:
        pytest.skip(f"LLM Judge API 调用失败: {e}")
        return None


def assert_judge_pass(score, reason, threshold=DEFAULT_PASS_THRESHOLD):
    """断言评判分数通过阈值"""
    assert score >= threshold, \
        f"LLM Judge 评分 {score} 低于阈值 {threshold}。理由: {reason}"


# 每个维度的 fixture
@pytest.fixture
def judge_coherence():
    """连贯性评判函数"""
    return lambda orig, jd, gen: call_judge(orig, jd, gen, "coherence")


@pytest.fixture
def judge_professionalism():
    """专业度评判函数"""
    return lambda orig, jd, gen: call_judge(orig, jd, gen, "professionalism")


@pytest.fixture
def judge_no_hallucination():
    """反幻觉评判函数"""
    return lambda orig, jd, gen: call_judge(orig, jd, gen, "no_hallucination")


# 跳过条件
def pytest_runtest_setup(item):
    """如果环境没有 API Key，跳过语义测试"""
    if "tests/semantic" in str(item.fspath):
        if not has_api_key():
            pytest.skip("ZHIPU_API_KEY 未设置，跳过语义测试")
