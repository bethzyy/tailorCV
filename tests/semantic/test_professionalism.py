"""
专业度测试

设计原则：同 test_coherence.py
- 规则检测部分直接运行，检测的是 fixture 中的真实 AI 输出
- LLM Judge 部分仅在有真实 fixture 时激活
- 没有 fixture 时全部 skip，不产生虚假信号
"""
import json
import re
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / 'fixtures'


def _load_semantic_fixture(case_name):
    path = FIXTURES_DIR / f"{case_name}.json"
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return None


class TestRuleBasedProfessionalism:
    """规则检测 — 需要真实 AI 输出 fixture，没有则 skip"""

    @pytest.fixture(params=["case_01_tech_writer"])
    def ai_output(self, request):
        """加载真实 AI 输出用于规则检测"""
        data = _load_semantic_fixture(request.param)
        if data is None:
            pytest.skip(f"无语义测试 fixture: {request.param}（需要先运行 run_baseline.py 生成并复制到 semantic/fixtures/）")
        return data

    def test_no_emoji_in_generated_content(self, ai_output):
        """生成的简历内容中不应出现 emoji"""
        generated = ai_output.get("generated_content", "") or str(ai_output.get("tailored", ""))
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE,
        )
        found = emoji_pattern.findall(generated)
        assert not found, f"生成内容中不应出现 emoji: {found}"

    def test_self_evaluation_reasonable_length(self, ai_output):
        """自我评价长度应在 10-200 字之间"""
        tailored = ai_output.get("tailored", {})
        evaluation = tailored.get("self_evaluation", "")
        if not evaluation:
            pytest.skip("无 self_evaluation 字段")
        assert 10 <= len(evaluation) <= 200, \
            f"自我评价长度异常: {len(evaluation)}字（合理范围: 10-200）"

    def test_basic_info_no_url(self, ai_output):
        """基本信息中不应包含 URL"""
        tailored = ai_output.get("tailored", {})
        basic_info = tailored.get("basic_info", {})
        info_text = str(basic_info)
        assert "http" not in info_text.lower(), "基本信息中不应包含 URL"


@pytest.mark.semantic
@pytest.mark.slow
class TestLLMJudgeProfessionalism:
    """LLM Judge 专业度测试 — 需要真实 AI 输出 + API Key"""

    @pytest.fixture(params=["case_01_tech_writer"])
    def semantic_case(self, request):
        data = _load_semantic_fixture(request.param)
        if data is None:
            pytest.skip(f"无语义测试 fixture: {request.param}")
        return data

    def test_professional_tone(self, semantic_case, judge_professionalism):
        """用词专业规范"""
        original = semantic_case.get("original_resume", "")
        jd = semantic_case.get("target_jd", "")
        generated = semantic_case.get("generated_content", "")

        if not all([original, jd, generated]):
            pytest.skip("fixture 数据不完整")

        result = judge_professionalism(original, jd, generated)
        if result:
            assert result["score"] >= 3.5, f"用词不够专业: {result['reason']}"
