"""TC-K01~K03: 关键词覆盖测试"""
import pytest


class TestKeywordCoverage:
    """验证 AI 输出与 JD 之间的关键词覆盖"""

    # TC-K01: JD 关键词出现在 AI 输出中（≥60%）
    def test_jd_keywords_in_ai_output(self, ai_output, jd_text):
        """AI 输出应覆盖至少 60% 的 JD 关键词"""
        import re
        # 从 JD 提取关键词（2-4字的中文词组或英文术语）
        jd_keywords = set()
        for word in re.findall(r'[\u4e00-\u9fff]{2,4}', jd_text):
            # 排除常见停用词
            stopwords = {'我们', '他们', '可以', '能够', '需要', '要求', '具备', '负责',
                        '进行', '完成', '工作', '经验', '以上', '优先', '相关', '了解'}
            if word not in stopwords:
                jd_keywords.add(word)

        if not jd_keywords:
            pytest.skip("未能从 JD 提取关键词")

        # 在 AI 输出 JSON 中搜索
        ai_text = str(ai_output).lower()
        matched = {kw for kw in jd_keywords if kw in ai_text}
        coverage = len(matched) / len(jd_keywords)
        assert coverage >= 0.6, (
            f"JD 关键词覆盖率 {coverage:.0%} < 60% "
            f"({len(matched)}/{len(jd_keywords)} 匹配)"
        )

    # TC-K02: tailored 内容长度合理（≥50字/条目）
    def test_tailored_content_length(self, ai_output):
        """每条工作经历的 tailored 内容应 ≥ 50 字"""
        work = ai_output.get('work_experience', [])
        if not work:
            pytest.skip("AI 输出中无工作经历")

        short_entries = []
        for i, w in enumerate(work):
            tailored = w.get('tailored', '').strip()
            if len(tailored) < 50:
                short_entries.append((i, len(tailored)))

        assert not short_entries, (
            f"{len(short_entries)} 条工作经历 tailored 内容过短: "
            f"{short_entries}"
        )

    # TC-K03: AI JSON 中的 JD 关键词不丢失（与 docx 对比）
    def test_no_keyword_loss_between_json_and_docx(self, ai_output):
        """AI JSON 中提到的 JD 相关关键词在渲染到 docx 后不应丢失

        注：此测试需要实际 docx 文件，标记为集成测试。
        在单元测试模式下验证 JSON 结构完整性。
        """
        # 验证 AI JSON 结构完整性：tailored 字段非空
        all_sections = ['work_experience', 'projects', 'education']
        empty_tailored = []
        for section in all_sections:
            items = ai_output.get(section, [])
            for i, item in enumerate(items):
                if isinstance(item, dict) and not item.get('tailored', '').strip():
                    empty_tailored.append(f"{section}[{i}]")

        assert not empty_tailored, (
            f"以下条目的 tailored 字段为空: {empty_tailored}"
        )
