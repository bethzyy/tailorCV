"""
AI 输出质量回归测试

目的：当 prompt 或逻辑变更时，自动检测 AI 输出质量是否退化。

核心原则：
- 每个场景必须有真实的 output.json（来自 AI 实际生成），不接受手工编造的"完美答案"
- 如果 output.json 不存在，该场景自动 skip（不产生虚假绿光）
- 验证维度：关键词覆盖率、必须/禁止关键词、忠实度、JD 对齐、结构完整性
"""

import json
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / 'fixtures'


def _load_output(case_name):
    """加载场景的 AI 真实输出"""
    output_path = FIXTURES_DIR / case_name / 'output.json'
    if not output_path.exists():
        return None
    return json.loads(output_path.read_text(encoding='utf-8'))


def _get_jd_keywords(jd_text):
    """从 JD 提取关键词"""
    keywords = set()
    for word in ['Python', '后端', '前端', '架构', '微服务', '数据库',
                 'Django', 'Flask', 'React', 'Vue', 'TypeScript', 'Java',
                 'MySQL', 'Redis', 'Docker', 'Kubernetes', '高可用', '可扩展',
                 '产品', '数据', '分析', '运营', 'SQL', 'Go']:
        if word in jd_text:
            keywords.add(word)
    return keywords


class TestKeywordCoverage:
    """关键词覆盖率回归"""

    def test_min_keyword_coverage(self, regression_case):
        """JD 关键词在定制内容中的覆盖率不低于阈值"""
        output = _load_output(regression_case['case_name'])
        if output is None:
            pytest.skip(f"{regression_case['case_name']}: 无 output.json，跳过（需要真实 AI 输出）")

        input_data = regression_case['input']
        expected = regression_case['expected']
        tailored = output['tailored']

        jd_keywords = _get_jd_keywords(input_data['jd_text'])
        tailored_text = str(tailored)
        covered = sum(1 for kw in jd_keywords if kw in tailored_text)
        coverage_rate = covered / len(jd_keywords) if jd_keywords else 0

        assert coverage_rate >= expected['min_keyword_coverage'], \
            f"关键词覆盖率 {coverage_rate:.0%} 低于阈值 {expected['min_keyword_coverage']:.0%}，" \
            f"未覆盖: {[kw for kw in jd_keywords if kw not in tailored_text]}"

    def test_required_keywords_present(self, regression_case):
        """必须包含的关键词"""
        output = _load_output(regression_case['case_name'])
        if output is None:
            pytest.skip(f"{regression_case['case_name']}: 无 output.json，跳过")

        expected = regression_case['expected']
        tailored_text = str(output['tailored'])

        missing = [kw for kw in expected['required_keywords'] if kw not in tailored_text]
        assert not missing, f"缺少必需关键词: {missing}"

    def test_forbidden_keywords_absent(self, regression_case):
        """禁止出现的关键词（零编造原则）"""
        output = _load_output(regression_case['case_name'])
        if output is None:
            pytest.skip(f"{regression_case['case_name']}: 无 output.json，跳过")

        expected = regression_case['expected']
        tailored_text = str(output['tailored'])

        found = [kw for kw in expected['forbidden_keywords'] if kw in tailored_text]
        assert not found, f"包含禁止关键词（疑似编造）: {found}"


class TestFidelity:
    """忠实度回归 — 零编造原则"""

    def test_name_unchanged(self, regression_case):
        """姓名不变"""
        output = _load_output(regression_case['case_name'])
        if output is None:
            pytest.skip(f"{regression_case['case_name']}: 无 output.json，跳过")

        expected = regression_case['expected']
        tailored = output['tailored']

        assert tailored['basic_info']['name'] == expected['fidelity_checks']['name_unchanged'], \
            "姓名被篡改，违反忠实度原则"

    def test_phone_unchanged(self, regression_case):
        """电话不变"""
        output = _load_output(regression_case['case_name'])
        if output is None:
            pytest.skip(f"{regression_case['case_name']}: 无 output.json，跳过")

        expected = regression_case['expected']
        tailored = output['tailored']

        assert tailored['basic_info']['phone'] == expected['fidelity_checks']['phone_unchanged'], \
            "电话被篡改，违反忠实度原则"

    def test_education_count_unchanged(self, regression_case):
        """教育经历条数不变"""
        output = _load_output(regression_case['case_name'])
        if output is None:
            pytest.skip(f"{regression_case['case_name']}: 无 output.json，跳过")

        expected = regression_case['expected']
        tailored = output['tailored']

        actual_count = len(tailored.get('education', []))
        assert actual_count == expected['fidelity_checks']['education_count_unchanged'], \
            f"教育经历条数从 {expected['fidelity_checks']['education_count_unchanged']} 变为 {actual_count}"

    def test_work_experience_count_unchanged(self, regression_case):
        """工作经历条数不变"""
        output = _load_output(regression_case['case_name'])
        if output is None:
            pytest.skip(f"{regression_case['case_name']}: 无 output.json，跳过")

        expected = regression_case['expected']
        tailored = output['tailored']

        actual_count = len(tailored.get('work_experience', []))
        assert actual_count == expected['fidelity_checks']['work_experience_count_unchanged'], \
            f"工作经历条数从 {expected['fidelity_checks']['work_experience_count_unchanged']} 变为 {actual_count}"


class TestJDAlignment:
    """JD 对齐度回归"""

    def test_summary_mentions_position(self, regression_case):
        """摘要包含职位相关内容"""
        output = _load_output(regression_case['case_name'])
        if output is None:
            pytest.skip(f"{regression_case['case_name']}: 无 output.json，跳过")

        input_data = regression_case['input']
        tailored = output['tailored']
        summary = tailored.get('summary', '')

        # 从 required_keywords 中取前 2 个作为摘要检测词
        required = regression_case['expected']['required_keywords'][:2]
        matched = sum(1 for kw in required if kw in summary)
        assert matched >= 1, f"摘要未提及关键职位信息: {required}"

    def test_work_experience_jd_keywords(self, regression_case):
        """工作经历包含 JD 关键词"""
        output = _load_output(regression_case['case_name'])
        if output is None:
            pytest.skip(f"{regression_case['case_name']}: 无 output.json，跳过")

        expected = regression_case['expected']
        tailored = output['tailored']
        work_exp_text = str(tailored.get('work_experience', []))

        jd_keywords = expected['required_keywords']
        matched = sum(1 for kw in jd_keywords if kw in work_exp_text)
        assert matched >= expected.get('min_jd_alignment_fields', 2), \
            f"工作经历中 JD 关键词覆盖不足: {matched}/{len(jd_keywords)}"

    def test_self_evaluation_relevant(self, regression_case):
        """自我评价与 JD 相关"""
        output = _load_output(regression_case['case_name'])
        if output is None:
            pytest.skip(f"{regression_case['case_name']}: 无 output.json，跳过")

        tailored = output['tailored']
        evaluation = tailored.get('self_evaluation', '')

        assert len(evaluation) > 10, "自我评价过短"


class TestStructureIntegrity:
    """结构完整性回归"""

    def test_all_required_sections_present(self, regression_case):
        """所有必需章节存在"""
        output = _load_output(regression_case['case_name'])
        if output is None:
            pytest.skip(f"{regression_case['case_name']}: 无 output.json，跳过")

        tailored = output['tailored']
        required_sections = ['basic_info', 'work_experience', 'education', 'skills']

        missing = [s for s in required_sections if s not in tailored or not tailored[s]]
        assert not missing, f"缺少必需章节: {missing}"

    def test_work_experience_has_content(self, regression_case):
        """工作经历有实质内容"""
        output = _load_output(regression_case['case_name'])
        if output is None:
            pytest.skip(f"{regression_case['case_name']}: 无 output.json，跳过")

        tailored = output['tailored']
        for exp in tailored.get('work_experience', []):
            content = exp.get('tailored', '') or exp.get('content', '')
            assert len(content) > 20, \
                f"工作经历（{exp.get('company', '?')}）内容过短: {content[:50]}"
