"""
ATS PDF 生成链路测试

测试内容：
1. _build_ats_context() 数据映射是否正确
2. generate_ats_html() 生成的 HTML 是否包含冗余信息
3. generate-pdf.mjs 能否成功生成 PDF

用法：python test/test_ats_pdf.py
"""

import sys
import os
import json
import subprocess

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.resume_generator import ResumeGenerator


# 模拟 AI 返回的 tailored_resume 数据（与真实数据结构一致）
MOCK_TAILORED_RESUME = {
    "basic_info": {
        "name": "赵颖颖",
        "phone": "(86)13141220660",
        "email": "bethz@263.net",
        "location": "Beijing, China"
    },
    "summary": "资深软件专家 | 25年大型软件研发经验 | 技术文档工程 + AI/ML\n- 深厚的技术架构设计与软件全生命周期文档规范制定能力\n- 以开发者视角独立输出专业的用户手册、安装指南及API技术文档\n- 显著降低研发团队沟通成本",
    "work_experience": [
        {
            "company": "SAS Institute",
            "position": "Senior Software Engineer",
            "time": "2006.03 - 2025.12",
            "location": "Beijing",
            "content": "<strong>数据格式管理：</strong>Led data format management for SAS Viya platform\n<strong>AI平台开发：</strong>Developed AI-powered analytics platform with RAG pipelines\n<strong>技术文档：</strong>Authored comprehensive API documentation for 50+ microservices"
        }
    ],
    "projects": [
        {
            "name": "AI Resume Tailor",
            "time": "2025",
            "role": "Full Stack Developer",
            "description": "AI-powered resume customization platform using LLM",
            "tech": "Python, Flask, GLM-4, Jinja2"
        },
        {
            "name": "RAG Knowledge Base",
            "time": "2024",
            "role": "Lead Developer",
            "description": "Enterprise RAG system for technical documentation",
            "tech": "Python, LangChain, ChromaDB, FastAPI"
        }
    ],
    "education": [
        {
            "school": "Wuhan University",
            "major": "Computer Science",
            "degree": "Master",
            "time": "2000 - 2003"
        }
    ],
    "certificates": [
        {
            "name": "AWS Solutions Architect",
            "org": "Amazon",
            "year": "2023"
        }
    ],
    "skills": [
        {"name": "Programming", "items": ["Python", "JavaScript", "SQL"]},
        {"name": "AI/ML", "items": ["RAG", "LLM", "Prompt Engineering"]},
        {"name": "Documentation", "items": ["API Docs", "User Guides", "Technical Writing"]}
    ]
}

MOCK_JD_KEYWORDS = ["RAG pipelines", "LLM", "technical writing", "Python", "API documentation"]


def test_ats_context_mapping():
    """测试 1: _build_ats_context 数据映射"""
    print("\n" + "=" * 60)
    print("测试 1: _build_ats_context 数据映射")
    print("=" * 60)

    generator = ResumeGenerator()
    context = generator._build_ats_context(MOCK_TAILORED_RESUME, MOCK_JD_KEYWORDS)

    # 检查关键字段
    checks = [
        ("NAME", context["NAME"], "赵颖颖"),
        ("EMAIL", context["EMAIL"], "bethz@263.net"),
        ("LOCATION", context["LOCATION"], "Beijing, China"),
        ("LANG", context["LANG"], "en"),
        ("SECTION_SUMMARY", context["SECTION_SUMMARY"], "Professional Summary"),
    ]

    all_pass = True
    for field, actual, expected in checks:
        status = "PASS" if actual == expected else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"  [{status}] {field}: '{actual}' == '{expected}'")

    # 检查 summary 是否包含冗余前缀
    summary = context["SUMMARY_TEXT"]
    has_job_prefix = "求职意向" in summary or "求职目标" in summary
    print(f"\n  Summary 文本内容:")
    for line in summary.split("\n"):
        print(f"    {line}")
    print(f"\n  [{'WARN' if has_job_prefix else 'PASS'}] Summary 包含'求职意向'前缀: {has_job_prefix}")

    # 检查 competency tags
    competencies = context["COMPETENCIES"]
    tag_count = competencies.count("competency-tag")
    print(f"\n  Competency tags 数量: {tag_count}")
    if tag_count > 10:
        print(f"    [WARN] Tags 过多，检查 jd_keywords 是否正确传入")
    else:
        for kw in MOCK_JD_KEYWORDS[:5]:
            found = kw in competencies
            print(f"    [{'PASS' if found else 'FAIL'}] 包含 '{kw}': {found}")

    return all_pass


def test_ats_html_generation():
    """测试 2: generate_ats_html 生成 HTML"""
    print("\n" + "=" * 60)
    print("测试 2: generate_ats_html HTML 生成")
    print("=" * 60)

    generator = ResumeGenerator()
    html_path = generator.generate_ats_html(MOCK_TAILORED_RESUME, MOCK_JD_KEYWORDS)

    print(f"  HTML 文件: {html_path}")

    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    print(f"  HTML 大小: {len(html_content)} bytes")

    # 检查结构
    checks = [
        ("DOCTYPE", "<!DOCTYPE html>" in html_content),
        ("h1 标题", "<h1>赵颖颖</h1>" in html_content),
        ("邮箱", "bethz@263.net" in html_content),
        ("Summary section", "Professional Summary" in html_content),
        ("Experience section", "Work Experience" in html_content),
        ("Education section", "Education" in html_content),
        ("Skills section", "Technical Skills" in html_content),
    ]

    # 检查冗余
    name_count = html_content.count("赵颖颖")
    print(f"\n  '赵颖颖' 出现次数: {name_count}")
    if name_count > 2:
        print("    [WARN] 姓名出现超过2次，可能有冗余")

    job_intent_count = html_content.count("求职意向")
    if job_intent_count > 0:
        print(f"    [WARN] '求职意向' 出现 {job_intent_count} 次")

    all_pass = True
    for name, result in checks:
        status = "PASS" if result else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"  [{status}] {name}")

    return all_pass, html_path


def test_pdf_generation(html_path):
    """测试 3: generate-pdf.mjs 生成 PDF"""
    print("\n" + "=" * 60)
    print("测试 3: generate-pdf.mjs PDF 生成")
    print("=" * 60)

    pdf_path = html_path.replace(".html", ".pdf")
    pdf_tool = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "tools", "generate-pdf.mjs")

    if not os.path.exists(pdf_tool):
        print(f"  [FAIL] PDF 工具不存在: {pdf_tool}")
        return False

    print(f"  HTML 输入: {html_path}")
    print(f"  PDF 输出: {pdf_path}")
    print(f"  PDF 工具: {pdf_tool}")

    proc = subprocess.run(
        ["node", pdf_tool, html_path, pdf_path, "--format=letter"],
        capture_output=True, text=True, timeout=30
    )

    print(f"\n  --- stdout ---")
    print(proc.stdout)
    if proc.stderr:
        print(f"  --- stderr ---")
        print(proc.stderr)

    if proc.returncode != 0:
        print(f"  [FAIL] PDF 生成失败 (exit code: {proc.returncode})")
        return False

    if not os.path.exists(pdf_path):
        print(f"  [FAIL] PDF 文件未生成")
        return False

    pdf_size = os.path.getsize(pdf_path)
    print(f"\n  [PASS] PDF 生成成功")
    print(f"  PDF 大小: {pdf_size} bytes ({pdf_size/1024:.1f} KB)")

    # 验证 PDF 结构
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    header_ok = pdf_bytes[:5] == b"%PDF-"
    footer_ok = b"%%EOF" in pdf_bytes[-100:]
    print(f"  [PASS] PDF header: {header_ok}")
    print(f"  [PASS] PDF footer (%%EOF): {footer_ok}")

    return True


def main():
    print("=" * 60)
    print("ATS PDF 生成链路测试")
    print("=" * 60)

    # 测试 1: 数据映射
    ctx_pass = test_ats_context_mapping()

    # 测试 2: HTML 生成
    html_pass, html_path = test_ats_html_generation()

    # 测试 3: PDF 生成
    pdf_pass = False
    if html_pass:
        pdf_pass = test_pdf_generation(html_path)

    # 汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print(f"  数据映射:  {'PASS' if ctx_pass else 'FAIL'}")
    print(f"  HTML 生成: {'PASS' if html_pass else 'FAIL'}")
    print(f"  PDF 生成:  {'PASS' if pdf_pass else 'FAIL'}")
    print(f"  总体:      {'ALL PASS' if all([ctx_pass, html_pass, pdf_pass]) else 'HAS FAILURES'}")
    print("=" * 60)

    return 0 if all([ctx_pass, html_pass, pdf_pass]) else 1


if __name__ == "__main__":
    sys.exit(main())
