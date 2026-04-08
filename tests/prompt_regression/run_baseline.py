#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Prompt 回归基线生成工具

用法:
    python tests/prompt_regression/run_baseline.py [--case case_name] [--all]

功能:
    对指定的回归场景，调用真实 AI 生成输出，保存为基线快照。
    同时运行 benchmark 评估，保存质量指标。

输出:
    tests/prompt_regression/baselines/{case_name}_{timestamp}.json
    包含 AI 输出 + 评估指标
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# 将项目根目录加入 path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

BASELINES_DIR = Path(__file__).parent / "baselines"

# 可用的回归场景
AVAILABLE_CASES = [
    "case_01_tech_writer",
    "case_02_frontend_dev",
    "case_03_fresh_grad",
    "case_04_product_manager",
    "case_05_career_change",
]


def get_api_key():
    """获取 API Key"""
    key = os.environ.get("ZHIPU_API_KEY", "")
    if not key:
        key = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
    return key


def load_case_input(case_name):
    """加载场景输入数据"""
    input_path = PROJECT_ROOT / "tests" / "regression" / "fixtures" / case_name / "input.json"
    if not input_path.exists():
        print(f"[ERROR] 场景文件不存在: {input_path}")
        return None
    return json.loads(input_path.read_text(encoding="utf-8"))


def evaluate_keywords(jd_text, tailored_text):
    """评估关键词覆盖率"""
    import re

    # 简单分词提取 JD 关键词
    stopwords = {"的", "和", "与", "或", "等", "及", "在", "有", "对", "为",
                 "能", "会", "可", "要", "是", "了", "着", "过", "不", "也",
                 "1", "2", "3", "4", "5", "以上", "经验", "熟悉", "掌握"}

    # 提取 JD 中的关键词（2-4字词组）
    keywords = set()
    for word in re.findall(r'[\u4e00-\u9fff]{2,6}', jd_text):
        if word not in stopwords and len(word) >= 2:
            keywords.add(word)

    # 也提取英文关键词
    for word in re.findall(r'[A-Za-z][A-Za-z0-9+#.]+', jd_text):
        if len(word) >= 2:
            keywords.add(word)

    if not keywords:
        return {"coverage": 0, "total": 0, "covered": 0, "missing": []}

    covered = sum(1 for kw in keywords if kw in tailored_text)
    missing = [kw for kw in keywords if kw not in tailored_text]
    coverage = covered / len(keywords)

    return {
        "coverage": round(coverage, 3),
        "total": len(keywords),
        "covered": covered,
        "missing": missing[:20],  # 最多显示 20 个缺失关键词
    }


def evaluate_structure(tailored):
    """评估结构完整性"""
    required_sections = ["basic_info", "work_experience", "education", "skills"]
    missing = [s for s in required_sections if s not in tailored or not tailored[s]]
    return {
        "complete": len(missing) == 0,
        "missing_sections": missing,
        "section_count": sum(1 for s in required_sections if s in tailored),
    }


def generate_baseline(case_name, api_key):
    """为指定场景生成基线"""
    print(f"\n{'='*60}")
    print(f"生成基线: {case_name}")
    print(f"{'='*60}")

    # 加载输入
    case_data = load_case_input(case_name)
    if not case_data:
        return None

    resume_text = case_data["resume_text"]
    jd_text = case_data["jd_text"]

    # 尝试调用真实 AI（如果可用）
    ai_output = None
    if api_key:
        try:
            from anthropic import Anthropic

            parts = api_key.split(".", 1)
            api_key_value = parts[1] if len(parts) == 2 else api_key

            client = Anthropic(
                api_key=api_key_value,
                base_url="https://open.bigmodel.cn/api/anthropic",
            )

            prompt = f"""请根据以下简历和目标职位JD，生成定制化的简历内容。
要求：保留原始简历中的所有真实信息，不编造经历和成果。

原始简历：
{resume_text}

目标JD：
{jd_text}

请以JSON格式返回定制化后的简历内容，结构如下：
{{
    "tailored": {{
        "basic_info": {{"name": "", "phone": "", "email": ""}},
        "summary": "定制化摘要",
        "education": [],
        "work_experience": [],
        "projects": [],
        "skills": [],
        "self_evaluation": ""
    }}
}}"""

            print("  调用 AI 生成中...")
            start = time.time()
            response = client.messages.create(
                model="glm-4-flash",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            elapsed = time.time() - start
            print(f"  AI 生成完成，耗时 {elapsed:.1f}s")

            # 解析响应
            text = response.content[0].text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            ai_output = json.loads(text)
            ai_output["_meta"] = {
                "model": "glm-4-flash",
                "generation_time": round(elapsed, 2),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            print(f"  [WARNING] AI 调用失败: {e}")
            print("  将保存输入数据作为基线（无 AI 输出）")
    else:
        print("  [INFO] 无 API Key，仅保存输入数据")

    # 评估指标
    metrics = {}
    if ai_output and "tailored" in ai_output:
        tailored_text = json.dumps(ai_output["tailored"], ensure_ascii=False)
        metrics["keyword_coverage"] = evaluate_keywords(jd_text, tailored_text)
        metrics["structure"] = evaluate_structure(ai_output["tailored"])
        print(f"  关键词覆盖率: {metrics['keyword_coverage']['coverage']:.1%}")
        print(f"  结构完整性: {'完整' if metrics['structure']['complete'] else '缺失: ' + str(metrics['structure']['missing_sections'])}")

    # 保存基线
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = BASELINES_DIR / f"{case_name}_{timestamp}.json"

    baseline = {
        "case_name": case_name,
        "timestamp": timestamp,
        "input": case_data,
        "ai_output": ai_output,
        "metrics": metrics,
    }

    output_file.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  基线已保存: {output_file}")
    return output_file


def main():
    parser = argparse.ArgumentParser(description="Prompt 回归基线生成工具")
    parser.add_argument("--case", type=str, help="指定场景名称")
    parser.add_argument("--all", action="store_true", help="生成所有场景基线")
    parser.add_argument("--list", action="store_true", help="列出可用场景")
    args = parser.parse_args()

    if args.list:
        print("可用场景:")
        for case in AVAILABLE_CASES:
            print(f"  - {case}")
        return

    if not args.case and not args.all:
        parser.print_help()
        print("\n提示: 使用 --case <名称> 或 --all")
        return

    api_key = get_api_key()
    if not api_key:
        print("[WARNING] 未设置 ZHIPU_API_KEY，将仅保存输入数据")

    cases = AVAILABLE_CASES if args.all else [args.case]
    results = []

    for case in cases:
        if case not in AVAILABLE_CASES:
            print(f"[WARNING] 未知场景: {case}，跳过")
            continue
        result = generate_baseline(case, api_key)
        if result:
            results.append(str(result))

    print(f"\n{'='*60}")
    print(f"完成! 生成了 {len(results)} 个基线文件")
    for r in results:
        print(f"  - {r}")


if __name__ == "__main__":
    main()
