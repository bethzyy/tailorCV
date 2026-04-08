"""
内容连贯性测试

设计原则：
- 规则检测部分（不需要 API）：从 fixture 加载真实 AI 输出后检测
- LLM Judge 部分（需要 API）：从同一份 fixture 加载后评判
- 没有 fixture → skip，不产生虚假信号

fixture 数据来源：
  python tests/prompt_regression/run_baseline.py --case case_01_tech_writer
  # 然后将 baselines/ 中的输出复制到 tests/semantic/fixtures/case_01_tech_writer.json
"""
import json
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / 'fixtures'


def _load_semantic_fixture(case_name):
    """加载语义测试的真实 AI 输出 fixture"""
    path = FIXTURES_DIR / f"{case_name}.json"
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return None


def _extract_work_times(work_experience):
    """从工作经历中提取时间段列表 [(start, end), ...]"""
    times = []
    for exp in work_experience:
        time_str = exp.get("time", "")
        if "-" in time_str:
            parts = time_str.split("-")
            try:
                times.append((int(parts[0].strip()), int(parts[1].strip())))
            except (ValueError, IndexError):
                continue
    return times


def _extract_project_times(projects):
    """从项目经历中提取时间段列表"""
    times = []
    for proj in projects:
        time_str = proj.get("time", "")
        if "-" in time_str:
            parts = time_str.split("-")
            try:
                times.append((int(parts[0].strip()), int(parts[1].strip())))
            except (ValueError, IndexError):
                continue
    return times


def _extract_education_end(education):
    """从教育经历中提取毕业年份"""
    if not education:
        return None
    edu = education[0]
    time_str = edu.get("time", "")
    if "-" in time_str:
        return int(time_str.split("-")[1].strip())
    return None


class TestRuleBasedCoherence:
    """规则检测 — 从真实 AI 输出 fixture 中加载数据后检测"""

    @pytest.fixture(params=["case_01_tech_writer"])
    def ai_output(self, request):
        """加载真实 AI 输出"""
        data = _load_semantic_fixture(request.param)
        if data is None:
            pytest.skip(f"无 fixture: {request.param}（运行 run_baseline.py 并复制到 semantic/fixtures/）")
        return data

    def test_work_timeline_no_overlap(self, ai_output):
        """不同公司的工作时间不应重叠"""
        tailored = ai_output.get("tailored", {})
        work_exp = tailored.get("work_experience", [])
        if len(work_exp) < 2:
            pytest.skip("只有一段工作经历，无需检测重叠")

        times = _extract_work_times(work_exp)
        for i in range(len(times) - 1):
            assert times[i][1] <= times[i + 1][0], \
                f"工作时间重叠: {times[i]} 和 {times[i+1]}"

    def test_education_before_work(self, ai_output):
        """教育结束时间应 <= 第一份工作开始时间"""
        tailored = ai_output.get("tailored", {})
        education = tailored.get("education", [])
        work_exp = tailored.get("work_experience", [])

        edu_end = _extract_education_end(education)
        work_times = _extract_work_times(work_exp)

        if not edu_end or not work_times:
            pytest.skip("缺少教育或工作时间信息")

        assert edu_end <= work_times[0][0], \
            f"教育结束({edu_end})晚于工作开始({work_times[0][0]})"

    def test_project_time_within_work(self, ai_output):
        """项目时间应在某段工作经历的时间范围内"""
        tailored = ai_output.get("tailored", {})
        work_exp = tailored.get("work_experience", [])
        projects = tailored.get("projects", [])

        if not projects or not work_exp:
            pytest.skip("缺少项目或工作经历")

        work_times = _extract_work_times(work_exp)
        project_times = _extract_project_times(projects)

        for p_start, p_end in project_times:
            within_any = any(
                w_start <= p_start and p_end <= w_end
                for w_start, w_end in work_times
            )
            assert within_any, \
                f"项目时间({p_start}-{p_end})不在任何工作经历范围内"


@pytest.mark.semantic
@pytest.mark.slow
class TestLLMJudgeCoherence:
    """LLM Judge 连贯性测试 — 需要真实 AI 输出 + API Key"""

    @pytest.fixture(params=["case_01_tech_writer"])
    def semantic_case(self, request):
        """加载真实 AI 输出"""
        data = _load_semantic_fixture(request.param)
        if data is None:
            pytest.skip(f"无 fixture: {request.param}")
        return data

    def test_content_coherent_with_original(self, semantic_case, judge_coherence):
        """生成内容与原始简历连贯一致"""
        original = semantic_case.get("original_resume", "")
        jd = semantic_case.get("target_jd", "")
        generated = semantic_case.get("generated_content", "")

        if not all([original, jd, generated]):
            pytest.skip("fixture 数据不完整")

        result = judge_coherence(original, jd, generated)
        if result:
            assert result["score"] >= 3.5, f"内容不够连贯: {result['reason']}"
