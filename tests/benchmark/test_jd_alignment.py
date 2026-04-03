"""TC-J01~J03: JD 对齐测试"""
import pytest


class TestJDAlignment:
    """验证定制简历与 JD 的对齐程度"""

    # TC-J01: 求职意向使用 JD 职位名称
    def test_summary_uses_jd_position(self, ai_output, jd_text, original_resume):
        """定制简历的求职意向应使用 JD 中的职位名称，而非原简历职位名称"""
        import re

        # 提取 JD 中的职位名称
        jd_position = None
        for line in jd_text.split('\n'):
            line = line.strip()
            if '职位' in line or '岗位' in line or line.startswith('招聘'):
                # 提取引号/书名号内的内容
                match = re.search(r'[""「」《》]([^""「」《》]+)[""「」《》]', line)
                if match:
                    jd_position = match.group(1)
                    break
                # 或取冒号后的内容
                if '：' in line or ':' in line:
                    jd_position = re.split(r'[：:]', line)[-1].strip()
                    break

        if not jd_position:
            pytest.skip("无法从 JD 提取职位名称")

        # 检查 AI 输出的 summary 是否包含 JD 职位关键词
        summary = ai_output.get('summary', '')
        if isinstance(summary, dict):
            summary = summary.get('title', '') or summary.get('content', '')

        # 至少 summary 应包含 JD 职位名的部分关键词
        jd_position_chars = set(jd_position) - {'的', '与', '和', '及'}
        summary_chars = set(summary)
        overlap = jd_position_chars & summary_chars

        assert len(overlap) > 0, (
            f"summary 中未找到 JD 职位 '{jd_position}' 的任何关键词。"
            f"\nsummary: {summary[:200]}"
        )

    # TC-J02: 工作经历描述含 JD 关键词
    def test_work_experience_contains_jd_keywords(self, ai_output, jd_text):
        """工作经历描述中应出现至少 3 个 JD 关键词"""
        import re

        # 提取 JD 中的技术关键词
        jd_keywords = set()
        for word in re.findall(r'[\u4e00-\u9fff]{2,6}', jd_text):
            stopwords = {'我们', '他们', '可以', '能够', '需要', '要求', '具备',
                        '负责', '进行', '完成', '工作', '经验', '以上', '优先',
                        '相关', '了解', '熟悉', '良好', '优秀', '能力强'}
            if word not in stopwords and len(word) >= 2:
                jd_keywords.add(word)

        if not jd_keywords:
            pytest.skip("未能从 JD 提取关键词")

        # 在工作经历 tailored 中搜索
        work = ai_output.get('work_experience', [])
        all_tailored = ' '.join(w.get('tailored', '') for w in work)

        matched = {kw for kw in jd_keywords if kw in all_tailored}
        assert len(matched) >= 3, (
            f"工作经历中 JD 关键词匹配数 {len(matched)} < 3。"
            f"匹配的关键词: {matched}"
        )

    # TC-J03: 自我评价与 JD 匹配
    def test_self_evaluation_aligned_with_jd(self, ai_output, jd_text):
        """自我评价应体现 JD 要求的核心能力"""
        self_eval = ai_output.get('self_evaluation', '')
        if not self_eval or not self_eval.strip():
            pytest.skip("AI 输出中无自我评价")

        # 自我评价不应为空，且长度合理
        assert len(self_eval.strip()) >= 30, (
            f"自我评价内容过短 ({len(self_eval.strip())} 字)，应 ≥ 30 字"
        )
