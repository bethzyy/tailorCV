#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Prompt 回归对比工具

用法:
    python tests/prompt_regression/compare_output.py --before <name_before> --after <name_after>

功能:
    读取两个版本的基线输出，对比:
    1. 关键词覆盖率变化（±%）
    2. 结构完整性变化
    3. 内容差异 diff
    4. 输出文本摘要对比

输出:
    控制台报告 + 可选的 JSON 报告
"""
import argparse
import json
import sys
from pathlib import Path

# 将项目根目录加入 path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

BASELINES_DIR = Path(__file__).parent / "baselines"


def load_baseline(name_pattern):
    """加载匹配名称模式的最新基线文件"""
    matches = sorted(BASELINES_DIR.glob(f"{name_pattern}*.json"))
    if not matches:
        return None
    # 取最新的
    latest = matches[-1]
    return json.loads(latest.read_text(encoding="utf-8")), latest.name


def compare_metrics(before_metrics, after_metrics):
    """对比两组指标"""
    report = []

    # 关键词覆盖率对比
    before_cov = before_metrics.get("keyword_coverage", {})
    after_cov = after_metrics.get("keyword_coverage", {})

    if before_cov and after_cov:
        b_rate = before_cov.get("coverage", 0)
        a_rate = after_cov.get("coverage", 0)
        delta = a_rate - b_rate
        direction = "+" if delta > 0 else ""

        report.append(f"关键词覆盖率: {b_rate:.1%} → {a_rate:.1%} ({direction}{delta:.1%})")

        # 新增缺失的关键词
        new_missing = set(after_cov.get("missing", [])) - set(before_cov.get("missing", []))
        if new_missing:
            report.append(f"  新增缺失关键词: {list(new_missing)[:10]}")

        # 恢复的关键词
        recovered = set(before_cov.get("missing", [])) - set(after_cov.get("missing", []))
        if recovered:
            report.append(f"  恢复的关键词: {list(recovered)[:10]}")

    # 结构完整性对比
    before_struct = before_metrics.get("structure", {})
    after_struct = after_metrics.get("structure", {})

    if before_struct and after_struct:
        b_sections = before_struct.get("section_count", 0)
        a_sections = after_struct.get("section_count", 0)
        if b_sections != a_sections:
            report.append(f"结构章节: {b_sections} → {a_sections}")

        if not after_struct.get("complete") and before_struct.get("complete"):
            report.append(f"[REGRESSION] 结构完整性退化! 缺失: {after_struct.get('missing_sections', [])}")

    return report


def compare_content(before_output, after_output):
    """对比 AI 输出内容差异"""
    report = []

    if not before_output or not after_output:
        report.append("[INFO] 无法对比内容（缺少 AI 输出）")
        return report

    before_tailored = before_output.get("tailored", {})
    after_tailored = after_output.get("tailored", {})

    # 摘要对比
    before_summary = before_tailored.get("summary", "")
    after_summary = after_tailored.get("summary", "")

    if before_summary and after_summary:
        if before_summary == after_summary:
            report.append("摘要: 未变化")
        else:
            report.append(f"摘要: 已变化")
            report.append(f"  旧: {before_summary[:80]}...")
            report.append(f"  新: {after_summary[:80]}...")

    # 工作经历数量对比
    before_work = before_tailored.get("work_experience", [])
    after_work = after_tailored.get("work_experience", [])

    if len(before_work) != len(after_work):
        report.append(f"[WARNING] 工作经历数量变化: {len(before_work)} → {len(after_work)}")

    # 技能对比
    before_skills = set(before_tailored.get("skills", []))
    after_skills = set(after_tailored.get("skills", []))

    added_skills = after_skills - before_skills
    removed_skills = before_skills - after_skills

    if added_skills:
        report.append(f"新增技能: {list(added_skills)}")
    if removed_skills:
        report.append(f"[WARNING] 移除技能: {list(removed_skills)}")

    return report


def generate_report(before_name, after_name):
    """生成完整对比报告"""
    print(f"\n{'='*60}")
    print("Prompt 回归对比报告")
    print(f"{'='*60}")

    # 加载基线
    before_data, before_file = load_baseline(before_name)
    after_data, after_file = load_baseline(after_name)

    if not before_data:
        print(f"[ERROR] 找不到 before 基线: {before_name}")
        return
    if not after_data:
        print(f"[ERROR] 找不到 after 基线: {after_name}")
        return

    print(f"Before: {before_file}")
    print(f"After:  {after_file}")
    print(f"{'='*60}")

    # 场景信息
    case_name = after_data.get("case_name", "unknown")
    print(f"场景: {case_name}")
    print()

    # 指标对比
    print("--- 指标对比 ---")
    before_metrics = before_data.get("metrics", {})
    after_metrics = after_data.get("metrics", {})
    metric_report = compare_metrics(before_metrics, after_metrics)
    for line in metric_report:
        print(line)

    # 内容对比
    print()
    print("--- 内容对比 ---")
    before_output = before_data.get("ai_output")
    after_output = after_data.get("ai_output")
    content_report = compare_content(before_output, after_output)
    for line in content_report:
        print(line)

    # 总结
    print()
    print("--- 总结 ---")
    regression_found = any("[REGRESSION]" in line for line in metric_report + content_report)
    warning_found = any("[WARNING]" in line for line in metric_report + content_report)

    if regression_found:
        print("[REGRESSION] 检测到退化! 请仔细检查上述变化。")
    elif warning_found:
        print("[WARNING] 存在需要关注的差异。")
    else:
        print("[OK] 未检测到明显退化。")

    # 保存 JSON 报告
    report_data = {
        "case_name": case_name,
        "before_file": before_file,
        "after_file": after_file,
        "metrics_comparison": metric_report,
        "content_comparison": content_report,
        "regression_found": regression_found,
        "warning_found": warning_found,
    }

    report_file = BASELINES_DIR / f"report_{case_name}.json"
    report_file.write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告已保存: {report_file}")


def main():
    parser = argparse.ArgumentParser(description="Prompt 回归对比工具")
    parser.add_argument("--before", type=str, required=True, help="before 版本名称模式")
    parser.add_argument("--after", type=str, required=True, help="after 版本名称模式")
    parser.add_argument("--list", action="store_true", help="列出已有基线")
    args = parser.parse_args()

    if args.list:
        baselines = sorted(BASELINES_DIR.glob("*.json"))
        if not baselines:
            print("暂无基线文件")
        else:
            print("已有基线:")
            for b in baselines:
                print(f"  - {b.name}")
        return

    generate_report(args.before, args.after)


if __name__ == "__main__":
    main()
