# tailorCV 测试方案文档

> **这份文档解决什么问题**：为什么要分层测试？为什么选 pytest？怎么组织目录？新增测试时按什么套路来？
>
> **一句话定位**：测试的**设计思路和规则**，不涉及具体用例。
>
> **谁该看**：设计测试架构的人、需要新增测试类型的开发者。
>
> **配合关系**：本文档定规则 → [测试计划文档](test-plan.md)按规则列出具体用例和执行步骤。

---

## 1. 测试目标

| 目标 | 说明 |
|------|------|
| 防止回归 | 代码变更后自动检测命名冲突、引用错误、接口异常 |
| 质量度量 | 通过基准测试量化简历定制的忠实度、关键词覆盖率、JD 对齐度 |
| 快速反馈 | pytest 一键运行，秒级出结果 |
| 易于扩展 | 新增模块时有清晰的测试模板和目录规范 |

---

## 2. 测试分层架构

采用**六层金字塔**，从底层到上层逐步增加集成范围：

```
            ┌──────────────┐
            │  安全测试      │  20 用例 — SQL注入/XSS/认证/上传
            │(test_security)│
           ┌┴──────────────┴┐
           │  AI 质量回归   │  12 用例 — 关键词/忠实度/JD对齐
           │ (regression/)  │
          ┌┴────────────────┴┐
          │  基准测试          │  14 用例 — 量化定制质量
          │ (benchmark/)      │
         ┌┴──────────────────┴┐
         │  API 集成测试         │  51 用例 — 端到端请求/响应
         │ (test_api_*)         │
        ┌┴──────────────────────┴┐
        │  前端静态分析             │  75 用例 — HTML/JS 结构检查
        │ (test_static_*)         │
       ┌┴─────────────────────────┴┐
       │  单元测试                   │  206 用例 — 独立模块逻辑
       │ (test_*.py, 非 api/static) │
       └───────────────────────────┘
```

### 2.1 静态分析层（75 用例）

**职责**：在不运行代码的情况下，扫描 HTML/JS 源码检测结构性错误。

**检测类型**（`tests/test_static_checks.py`）：

| 类型 | 检测内容 | 为什么重要 |
|------|----------|-----------|
| HTML id 唯一性 | 同 id 多个元素 | `getElementById` 只返回第一个 |
| JS function 唯一性 | 同名函数声明 | 后者静默覆盖前者 |
| getElementById 引用 | 引用不存在的 id | 返回 null，后续操作报错 |
| querySelector 引用 | `#xxx` 不存在 | 同上 |
| inline 事件处理器 | onclick 调用未定义函数 | 点击时 ReferenceError |
| addEventListener | 绑定不存在的元素 | 报错 |
| classList/style 操作 | 操作不存在的元素 | 报错 |

**技术特点**：
- 使用正则表达式扫描，不依赖浏览器环境
- `@pytest.mark.parametrize` 自动遍历所有 HTML 文件
- `JS_BUILTINS` 白名单过滤内置对象/方法（100+ 条目），消除误报
- `_is_dynamic_ref()` 识别动态拼接引用，跳过合法的模板化 id

**扩展**：新增检测类型只需添加一个新的 `Test*` 类 + 对应的正则模式。

### 2.2 单元测试层（206 用例）

**职责**：测试独立模块的内部逻辑，不依赖网络或数据库。

**现有覆盖**：
- `tests/test_writer_reviewer.py` — Writer-Reviewer 闭环（prompt 加载、收敛逻辑、provider 配置）
- `tests/test_expert_team.py` — ExpertTeamV2 五阶段 A/B/C 三层测试（26 用例）
- `tests/test_resume_parser.py` — 简历解析器（信息提取、置信度、格式支持）（28 用例）
- `tests/test_resume_generator.py` — 简历生成器（文档结构、tailored 优先、多格式字段）（20 用例）
- `tests/test_resume_builder.py` — 简历构建器（表单→简历转换）（13 用例）
- `tests/test_match_scorer.py` — 匹配评分（教育/经验/技能匹配）（22 用例）
- `tests/test_cache_manager.py` — 缓存管理（CRUD、过期、统计）（17 用例）
- `tests/test_template_processor.py` — 模板处理器（上下文构建、兼容性、ID 生成）（30 用例）
- `tests/test_structure_detector.py` — 结构检测（姓名/联系/章节/条目检测）（16 用例）
- `tests/test_evidence_tracker.py` — 依据追踪（模糊匹配、可疑关键词、AI 验证）（17 用例）
- `tests/test_config.py` — 配置管理（默认值、模型映射、验证）（19 用例）
- `tests/test_database.py` — 数据库操作（用户/任务/订单/历史 CRUD）（21 用例）
- `tests/test_model_manager.py` — 模型管理（调用/降级/统计）（11 用例）
- `tests/test_qwen_connectivity.py` — 阿里云连通性诊断

**设计原则**：
- Mock 外部依赖（API 调用、数据库）
- 每个测试只验证一个行为
- 测试数据在测试内构造，不依赖外部文件

### 2.3 API 集成测试层（47 用例）

**职责**：通过 Flask test client 发送 HTTP 请求，验证端到端的请求/响应行为。

**覆盖模块**（7 个文件）：

| 文件 | 用例数 | 覆盖端点 |
|------|--------|----------|
| `test_api_auth.py` | 12 | `/api/auth/*` |
| `test_api_health.py` | 3 | `/`、`/api/health` |
| `test_api_payment.py` | 9 | `/api/payment/*` |
| `test_api_quota.py` | 5 | `/api/quota` |
| `test_api_tailor.py` | 7 | `/api/tailor/*` |
| `test_api_templates.py` | 8 | `/api/templates/*` |
| `test_api_user.py` | 3 | `/api/user/*` |
| `test_api_user_params.py` | 4 | `/api/user_params` |

**技术特点**：
- 通过 `conftest.py` 共享 fixture，所有测试使用同一个临时 SQLite 数据库
- session 级 fixture（`db_path`、`app`）避免重复初始化
- 自动修补所有模块的 `db` 引用，确保测试隔离
- 限流自动禁用（`RATE_LIMIT_ANON=10000 per minute`）

### 2.4 基准测试层（14 用例）

**职责**：使用真实 AI 输出数据，量化简历定制的质量指标。

**质量维度**（5 个文件）：

| 维度 | 用例数 | 指标 |
|------|--------|------|
| 渲染完整性 | 3 | 基本信息、工作经历、项目经历的 tailored 覆盖率 ≥80% |
| 关键词覆盖率 | 3 | JD 关键词在定制内容中覆盖率 ≥60% |
| JD 对齐度 | 3 | 摘要包含职位名称、工作经历含 JD 关键词、自我评价对齐 |
| 忠实度 | 3 | 非定制字段不变、工作经历条数一致、教育背景完整 |
| 端到端 | 2 | JinjaInserter 变量生成、后处理换行分割 |

**数据来源**：`tests/benchmark/fixtures/case_01_tech_writer/` 目录下的真实测试数据。

### 2.5 AI 质量回归层（12 用例）

**职责**：当 prompt 或逻辑变更时，自动检测 AI 输出质量是否退化。

**质量维度**（`tests/regression/test_quality_regression.py`）：

| 维度 | 用例数 | 指标 |
|------|--------|------|
| 关键词覆盖率 | 3 | JD 关键词覆盖率 ≥40%、必需关键词存在、禁止关键词不存在 |
| 忠实度 | 4 | 姓名/电话不变、教育/工作经历条数一致 |
| JD 对齐度 | 3 | 摘要包含职位关键词、工作经历含 JD 关键词、自我评价相关 |
| 结构完整性 | 2 | 所有必需章节存在、工作经历有实质内容 |

**技术特点**：
- 不依赖真实 AI 调用，使用预设的 golden set（AI 输出快照）
- golden set 以 JSON 文件存储在 `tests/regression/fixtures/` 下
- 当真实 AI 输出快照可用时，替换 fixture 数据即可

### 2.6 安全测试层（20 用例）

**职责**：验证应用的安全性，防止常见攻击向量。

**覆盖维度**（`tests/test_security.py`）：

| 维度 | 用例数 | 测试内容 |
|------|--------|---------|
| SQL 注入 | 3 | 特殊字符不注入、非数字 ID 不崩溃 |
| XSS 防护 | 3 | 简历/JD 文本含 script 标签时安全处理 |
| 认证绕过 | 5 | 无 token、无效 token、空 token、错误 scheme |
| 文件上传 | 3 | .exe 拒绝、路径遍历防护、无文件 400 |
| 输入验证 | 4 | 空 JSON、畸形 JSON、超长输入、null 字节 |
| 限流 | 2 | 健康检查不受限、公开端点可访问 |

---

## 3. 技术选型

| 选择 | 理由 |
|------|------|
| **pytest** | Python 生态最主流的测试框架，parametrize 原生支持，fixture 体系成熟 |
| **Flask test client** | 零网络开销的 HTTP 测试，与 Flask 应用无缝集成 |
| **正则表达式** | 静态分析无需 AST 解析器，正则足够检测 HTML/JS 结构问题 |
| **SQLite 临时文件** | 每个 session 独立 DB，测试间零干扰 |
| **pytest.mark.parametrize** | 自动扫描所有 HTML 文件，新增页面无需修改测试代码 |

---

## 4. 共享设施（Fixture 体系）

### 4.1 主 conftest.py（`tests/conftest.py`）

```
session scope          function scope
┌──────────┐          ┌──────────┐
│ db_path  │─────────→│  client  │
│  (临时DB) │          │(HTTP客户端)│
└────┬─────┘          └──────────┘
     │
     ▼
┌──────────┐          ┌──────────┐
│   app    │─────────→│ test_user│
│(Flask应用)│          │(测试用户) │
└──────────┘          └──────────┘
```

| Fixture | Scope | 职责 |
|---------|-------|------|
| `db_path` | session | 创建临时 SQLite 文件，session 结束自动删除 |
| `app` | session | 初始化 Flask 应用，修补所有模块的 db 引用，禁用限流 |
| `client` | function | 创建 Flask test client |
| `test_user` | function | 在临时 DB 中创建测试用户，返回 `(client, user_id)` |

**关键设计**：`_next_email()` 全局计数器确保每个测试用例使用唯一邮箱，避免唯一约束冲突。

### 4.2 基准 conftest.py（`tests/benchmark/conftest.py`）

| Fixture | 职责 |
|---------|------|
| `ai_output` | 加载 AI 输出 JSON |
| `jd_text` | 加载 JD 文本 |
| `original_resume` | 加载原始简历 JSON |
| `jd_keywords` | 从 JD 中自动提取关键词 |

数据文件不存在时自动 `pytest.skip`，不会因缺失数据导致测试套件失败。

---

## 5. 目录规范

```
tests/
├── conftest.py              # 全局 fixture（DB、app、client、user）
├── run_all.py               # 便捷运行脚本
├── test_api_*.py            # API 集成测试（按端点模块分文件）
├── test_frontend.py         # 前端结构一致性检查
├── test_static_checks.py    # HTML/JS 静态分析
├── test_writer_reviewer.py  # 单元测试
├── test_qwen_connectivity.py # 外部连通性测试
└── benchmark/               # 基准测试
    ├── conftest.py          # 基准测试 fixture（测试数据加载）
    ├── fixtures/            # 测试数据目录
    │   └── case_01_*/       # 按场景分目录
    └── test_*.py            # 基准测试用例
```

### 命名约定

| 类型 | 命名规则 | 示例 |
|------|----------|------|
| 测试文件 | `test_<模块>_<功能>.py` | `test_api_auth.py` |
| 测试类 | `Test<功能描述>` | `TestHTMLIDDuplicates` |
| 测试方法 | `test_<具体行为>` | `test_no_duplicate_ids` |
| fixture 数据目录 | `case_<编号>_<场景描述>` | `case_01_tech_writer` |
| fixture 数据文件 | `<数据类型>.json/txt` | `ai_output.json` |

---

## 6. 扩展指南

### 6.1 新增 API 端点测试

1. 在 `tests/` 下创建 `test_api_<模块名>.py`
2. 使用 `client` fixture 发送请求
3. 按正常/异常/边界分组织测试用例

```python
# tests/test_api_newfeature.py
import pytest

class TestNewFeatureList:
    def test_success(self, client):
        resp = client.get('/api/newfeature')
        assert resp.status_code == 200

    def test_unauthorized(self, client):
        resp = client.get('/api/newfeature')
        # 验证未授权逻辑
```

### 6.2 新增静态分析检测类型

1. 在 `tests/test_static_checks.py` 中添加新的 `Test*` 类
2. 使用 `@pytest.mark.parametrize` 遍历所有 HTML 文件
3. 在 `JS_BUILTINS` 中添加必要的白名单条目

```python
class TestNewCheckType:
    @pytest.mark.parametrize('html_file', HTML_FILES)
    def test_something(self, html_file):
        html = html_file.read_text(encoding='utf-8')
        # 正则检测 + 断言
```

### 6.3 新增基准测试场景

1. 在 `tests/benchmark/fixtures/` 下创建 `case_02_<场景>/` 目录
2. 放入 `ai_output.json`、`jd_text.txt`、`original_resume.json`
3. 在 `tests/benchmark/conftest.py` 中扩展 fixture 以支持新场景
4. 创建对应的 `test_*.py` 文件

### 6.4 新增单元测试

1. 在 `tests/` 下创建 `test_<模块名>.py`
2. Mock 外部依赖（`@patch` 或 `pytest-mock`）
3. 每个测试只验证一个行为

---

## 7. 质量门禁建议

> 运行命令见[测试计划文档 - 第 6 节 执行指南](test-plan.md#6-执行指南)。

### 7.1 覆盖率目标

| 层级 | 当前状态 | 目标 |
|------|---------|------|
| 单元测试 | 206 用例，覆盖 13 个核心模块 | 新增模块必须有对应测试 |
| API 集成测试 | 51 用例，覆盖主要端点 | 新增端点必须有对应测试 |
| 静态分析 | 75 用例，7 类检测 | 新增 HTML 文件自动纳入扫描 |
| 安全测试 | 20 用例，6 个维度 | 定期审计并补充新攻击向量 |
| AI 质量回归 | 12 用例，4 个维度 | 新增模板类型时补充场景 |
| 基准测试 | 14 用例，5 个维度 | 新增模板类型时补充场景 |

### 7.2 CI 分层策略

```yaml
# PR 触发 — 快速反馈（<2 分钟）
pytest tests/test_static_checks.py tests/test_api_*.py tests/test_resume_builder.py \
       tests/test_match_scorer.py tests/test_cache_manager.py tests/test_config.py \
       tests/test_model_manager.py tests/test_security.py -v --tb=short

# 合并后 — 完整回归（<5 分钟）
pytest tests/ -v --ignore=tests/benchmark --ignore=tests/regression \
       --ignore=tests/test_qwen_connectivity.py --ignore=tests/test_writer_reviewer.py

# 手动/定时 — 全量（含 AI 回归）
pytest tests/ -v
```

```yaml
# GitHub Actions 示例
- name: Run tests
  run: |
    pip install -r requirements.txt
    pytest tests/ -v --tb=short
```

建议在 CI 中至少运行：静态分析 + API 集成测试 + 单元测试。基准测试依赖外部数据文件，可在手动触发时运行。

---

## 8. 分批实施路线图

> 基于模块复杂度和依赖关系，分三批从简到难递进实施。
> 详细用例清单见[测试计划文档 - 第 4 节](test-plan.md#4-新增测试计划)。

### 8.1 第一批：零依赖纯逻辑（3 个模块，~35 用例）

**原则**：先攻最容易的，快速提升覆盖率。

| 模块 | 行数 | 为什么第一批 | 目标文件 |
|------|------|-------------|----------|
| `resume_builder.py` | 298 | 纯数据转换，零外部依赖 | `tests/test_resume_builder.py` |
| `match_scorer.py` | 444 | 纯规则计算，零外部依赖 | `tests/test_match_scorer.py` |
| `cache_manager.py` | 220 | 仅文件系统，用 tmpdir 即可 | `tests/test_cache_manager.py` |

**测试策略**：
- 测试数据在测试函数内直接构造（dict、str），无需外部 fixture 文件
- 不需要 mock，直接调用模块函数
- 重点覆盖：正常路径 + 空输入 + 边界值

### 8.2 第二批：Mock 外部依赖（5 个模块，~50 用例）

**原则**：有了第一批的经验，第二批处理需要 mock 的模块。

| 模块 | 行数 | 需要的 mock | 目标文件 |
|------|------|------------|----------|
| `evidence_tracker.py` | 391 | `_ai_validate()` | `tests/test_evidence_tracker.py` |
| `structure_detector.py` | 390 | fixture .docx 文件 | `tests/test_structure_detector.py` |
| `config.py` | 247 | `os.environ` 赋值 | `tests/test_config.py` |
| `database.py` | 970 | 无需 mock（已有临时 DB） | `tests/test_database.py` |
| `model_manager.py` | 147 | mock `provider.call()` | `tests/test_model_manager.py` |

**测试策略**：
- AI 依赖：用 `@patch` mock 掉 AI 调用，返回预设的 JSON 响应
- 文件依赖：准备固定的 fixture 文件（.docx、.pdf），放入 `tests/fixtures/`
- 数据库：复用 `conftest.py` 的临时 DB fixture

### 8.3 第三批：重依赖复杂管道（4 个模块，~40 用例）

**原则**：最难的部分放最后，需要精心构造测试数据和 mock 策略。

| 模块 | 行数 | 难点 | 目标文件 |
|------|------|------|----------|
| `resume_parser.py` | 736 | 多级降级、PDF/Word 库 | `tests/test_resume_parser.py` |
| `resume_generator.py` | 459 | docx/pdf 生成验证 | `tests/test_resume_generator.py` |
| `template_processor.py` | 683 | Jinja2 + docx + fallback | `tests/test_template_processor.py` |
| `expert_team.py` | 2229 | 五阶段管道 + Writer-Reviewer | `tests/test_expert_team.py` |

**测试策略**：
- 文件处理：准备多格式 fixture（TXT/PDF/DOCX），验证解析输出
- 生成验证：不检查视觉格式，只验证输出文件非空且包含关键段落
- 模板处理：fixture 模板 + 固定 context，检查渲染后变量是否正确填充
- **expert_team.py 采用分层测试**：
  - **A 层（单阶段）**：mock `model_manager.call()` 返回预设 JSON，逐阶段验证
  - **B 层（管道集成）**：串联所有阶段，验证数据在各阶段间正确流转
  - **C 层（降级）**：模拟 AI 超时/返回无效 JSON/空内容，验证 fallback 路径

### 8.4 实施总览

```
第一批 (~35 用例)     第二批 (~50 用例)        第三批 (~40 用例)
┌──────────────┐    ┌──────────────────┐    ┌──────────────────────┐
│ resume_builder│    │ evidence_tracker  │    │ resume_parser         │
│ match_scorer  │───→│ structure_detector│───→│ resume_generator      │
│ cache_manager │    │ config            │    │ template_processor    │
│               │    │ database          │    │ expert_team           │
│               │    │ model_manager     │    │ (A/B/C 三层)         │
└──────────────┘    └──────────────────┘    └──────────────────────┘
  零依赖，纯逻辑       Mock 外部依赖            重依赖，复杂管道
```

**目标**：三批完成后，测试用例从 171 → 379，模块覆盖率从 11/23 → 24/25（已完成）。

---

## 9. 设计决策记录

| 决策 | 选择 | 原因 |
|------|------|------|
| 静态分析用正则而非 AST | 正则 | HTML/JS 混合代码，AST 解析器需要额外依赖且配置复杂 |
| 不测 `const/let` 重复 | 跳过 | JS 块级作用域允许同名变量，正确检测需要完整作用域分析 |
| API 测试用真实 DB 而非 mock | SQLite | 更接近真实行为，临时 DB 开销可忽略 |
| 基准测试用 `pytest.skip` | 跳过 | 数据文件可选，不应阻塞其他测试 |
| 限流在测试中禁用 | 禁用 | 测试不应受限流影响，避免 flaky tests |

---

*最后更新：2026-04-04*
*变更记录：v1.2 — 基于专家评估改进：修复失败测试、重写低质量测试、新增安全测试和 AI 回归测试；v1.1 — 新增第 8 节分批实施路线图；v1.0 — 初始版本*
