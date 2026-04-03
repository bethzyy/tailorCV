# tailorCV 简历定制工具 - 产品需求文档 (PRD)

## 文档信息

| 项目 | 内容 |
|------|------|
| 产品名称 | tailorCV - 智能简历定制工具 |
| 版本 | v1.3.1 |
| 创建日期 | 2026-03-11 |
| 更新日期 | 2026-04-04 |
| 文档状态 | ✅ 已实现 |
| 技术栈 | Flask + ZhipuAI GLM-5 + 多模型审阅闭环 |

---

## 1. 产品概述

### 1.1 产品定位

tailorCV 是一款基于 AI 的智能简历定制工具，帮助求职者根据目标职位 JD 快速生成定制化简历。

**核心差异化**：
- **零编造**：所有生成内容必须有据可依（90%+依据覆盖）
- **依据追踪**：透明的修改来源展示，三重验证机制
- **双模式输入**：文件上传 + 引导输入
- **Writer-Reviewer 闭环**：多模型审阅迭代，简历质量多轮打磨

### 1.2 目标用户

**适用人群**：所有受过高等教育的人

| 类别 | 说明 |
|------|------|
| 教育背景 | 大专/本科/硕士/博士（受过系统的高等教育） |
| 工作经验 | 不限（应届生、职场人士、高管均可） |
| 年龄范围 | 不限 |
| 职业阶段 | 不限 |

**设计原则**：
- 产品核心功能适用于所有教育背景良好的用户
- 无工作经验者：重点展示教育背景、项目经历、技能和潜力
- 有工作经验者：全面展示工作经历、项目成果和专业能力

### 1.3 核心价值主张

| 价值点 | 说明 |
|--------|------|
| 零编造 | 每条内容可追溯到原简历，置信度低于0.7自动标记 |
| 高匹配 | AI深度分析JD，针对性优化 |
| 双模式 | 文件上传或引导输入，灵活选择 |
| 高效率 | 两阶段调用，~11,000 tokens完成定制 |

---

## 2. 功能需求

### 2.1 原版简历输入（两种模式）

#### 模式A：文件上传
- **支持格式**：PDF、Word (.docx)、TXT、Markdown
- **交互方式**：拖拽上传或点击选择
- **解析策略**：多级fallback
  - Level 1: pdfplumber（推荐）
  - Level 2: PyPDF2（备选）
- **最大文件**：16MB

#### 模式B：引导输入
- **交互方式**：分步表单填写
- **必填信息**：
  - 基本信息：姓名、手机、邮箱
  - 教育背景：学校、学历、专业、时间段
  - 职位JD：目标职位描述
- **选填信息**：
  - 性别、年龄、现居地、政治面貌
  - 工作经历：公司、职位、时间、工作内容（应届生可不填）
  - 项目经历
  - 专业技能
  - 奖项荣誉
  - 证书资质
  - 自我评价
- **实时预览**：填写过程中可预览生成的原版简历

### 2.2 职位JD输入

- **方式1**：文本框直接粘贴
- **方式2**：上传文件（PDF、Word、TXT）
- **智能识别**：自动提取JD中的关键要求

### 2.3 AI五阶段定制

#### 调用架构

```
┌─────────────────────────────────────────────────────────────┐
│  阶段0+1: 并行（简历解析 + JD解码）                          │
│  模型: GLM-5 | Token: ~5000 | Temperature: 0.3              │
├─────────────────────────────────────────────────────────────┤
│  阶段2: 匹配度分析                                           │
│  模型: GLM-5 | Token: ~4000 | Temperature: 0.3              │
├─────────────────────────────────────────────────────────────┤
│  阶段3: 内容深度改写（支持 Writer-Reviewer 闭环）             │
│  ├─ 作者模型: GLM-5（写/修订简历）                           │
│  ├─ 审阅模型: Qwen/GPT-4o/Claude 等（并行审阅）             │
│  ├─ 闭环: 作者写 → 审阅 → 聚合反馈 → 修订 → 再审阅 → 收敛   │
│  └─ 收敛条件: 分数达标/无建议/版本稳定/最大3轮               │
├─────────────────────────────────────────────────────────────┤
│  阶段4: 质量验证                                             │
│  模型: GLM-5 | Token: ~4000 | Temperature: 0.2              │
└─────────────────────────────────────────────────────────────┘
```

#### 依据追踪机制

- **目标**：90%+依据覆盖
- **置信度阈值**：0.7为通过线
- **无法验证内容**：标记为 `[需人工确认]`

### 2.4 Writer-Reviewer 闭环（v1.3 新增）

#### 核心机制

在 Stage 3（内容改写）中引入多模型审阅闭环，让简历质量经过多轮打磨：

```
GLM 作者（初写/修订）──→ 多个审阅模型并行审阅 ──→ 聚合反馈 ──→ GLM 修订 ──→ 再次审阅 ──→ ... ──→ 收敛
```

#### 角色分工

| 角色 | 模型 | 职责 |
|------|------|------|
| 作者 (Writer) | GLM-5 | 根据匹配分析和 JD 撰写/修订简历 |
| 审阅者 (Reviewer) | Qwen3.5-plus, GPT-4o, Claude 等 | 从 6 个维度打分并提出修改建议 |

#### 审阅维度

| 维度 | 说明 |
|------|------|
| JD 对齐度 | 简历内容是否紧密围绕 JD 要求 |
| 内容真实性 | 是否有编造内容，是否基于原始简历 |
| 关键词覆盖 | JD 核心关键词是否自然融入 |
| 逻辑连贯 | 叙述是否清晰连贯 |
| 量化表达 | 成果是否有数据支撑 |
| 专业语气 | 用语是否专业精炼 |

#### 收敛机制（5 重保险）

| # | 条件 | 阈值 | 说明 |
|---|------|------|------|
| 1 | 所有审阅者标记 converged | 全部 true | 审阅者明确认可 |
| 2 | 平均分 >= 阈值 | 85 分（可配置） | 质量达标 |
| 3 | 无实质性修改建议 | specific_revisions 为空 | 没有可改的了 |
| 4 | 版本差异 < 阈值 | < 5%（可配置） | 改不动了（震荡/停滞） |
| 5 | 最大迭代次数 | 3 轮（可配置） | 硬性上限防死循环 |

#### 降级策略

| 场景 | 行为 |
|------|------|
| `WRITER_REVIEWER_ENABLED=false` | 完全不初始化，零开销 |
| 审阅模型不可用 | 自动降级为单次改写（原有流程） |
| 单个审阅模型失败 | 用其他审阅者结果继续 |
| GLM 修订调用失败 | 保留上一版本，停止循环 |

#### 配置参数

```bash
# .env
WRITER_REVIEWER_ENABLED=true                                    # 启用闭环
WRITER_REVIEWER_MAX_ITERATIONS=3                                # 最大迭代轮数
WRITER_REVIEWER_SCORE_THRESHOLD=85.0                            # 收敛分数阈值
WRITER_REVIEWER_MIN_DIFF_THRESHOLD=0.05                         # 版本差异阈值
WRITER_REVIEWER_REVIEWER_MODELS=qwen3.5-plus,gpt-4o             # 审阅模型列表
ANTIGRAVITY_BASE_URL=http://127.0.0.1:8045/v1                  # AntiGravity 代理地址
```

#### Token 成本估算

| 场景 | Token 消耗 |
|------|-----------|
| 单次改写（闭环关闭） | ~14K |
| 1 个审阅者 + 1 轮迭代 | ~32K |
| 2 个审阅者 + 3 轮迭代（最差） | ~68K |

#### 涉及文件

| 文件 | 说明 |
|------|------|
| `core/expert_team.py` | 闭环核心逻辑 |
| `core/providers/antigravity_provider.py` | AntiGravity 模型提供者 |
| `core/config.py` | 闭环配置项 |
| `prompts/review_content_prompt.txt` | 审阅者 Prompt |
| `prompts/revise_content_prompt.txt` | 修订者 Prompt |

### 2.5 简历输出

#### v1.0（当前版本）
- **格式**：Word (.docx)
- **模板**：原版风格（MVP阶段唯一模板）
- **输出方式**：浏览器下载

#### v2.0（规划中）
- **多模板支持**：提供多种经典简历风格
  - 专业版：传统商务风格，适合大多数岗位
  - 简约版：简洁现代，突出核心内容
  - 技术版：适合技术岗位，突出技能和项目
  - 创意版：适合设计、营销等创意类岗位
- **模板管理**：独立的模板管理和切换系统
- **自定义模板**：支持用户上传自定义模板（进阶功能）

### 2.6 进度反馈

```
[==========----------] 50% 正在分析JD核心要求...
当前阶段：阶段1/2 - 分析JD需求
```

---

## 3. 技术架构

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      双入口设计                              │
│  文件上传 (/)  │  引导输入 (/guided)                        │
├─────────────────────────────────────────────────────────────┤
│                    Flask 后端服务                            │
│  app.py - 路由 + API端点                                    │
├─────────────────────────────────────────────────────────────┤
│                      核心模块层                              │
│  resume_parser   │ resume_builder  │ expert_team           │
│  resume_generator│ evidence_tracker│ cache_manager         │
│  model_manager   │ config          │                       │
├─────────────────────────────────────────────────────────────┤
│                      数据存储层                              │
│  cache/ (MD5缓存)  │ output/ (生成文件)                     │
├─────────────────────────────────────────────────────────────┤
│                    AI 服务层                                 │
│        ZhipuAI GLM-4.6 (主) / GLM-4-flash (备)              │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 目录结构

```
tailorCV/
├── app.py                      # Flask主入口
├── requirements.txt            # 依赖清单
├── .env                        # API密钥配置
├── .gitignore
├── README.md
│
├── core/                       # 核心业务逻辑
│   ├── __init__.py
│   ├── config.py               # 配置管理
│   ├── resume_parser.py        # 简历解析器（多级fallback）
│   ├── resume_builder.py       # 简历构建器（引导输入）
│   ├── expert_team.py          # AI专家团队（两阶段）
│   ├── model_manager.py        # 模型管理（主备切换）
│   ├── evidence_tracker.py     # 依据追踪（混合验证）
│   ├── resume_generator.py     # 简历生成器
│   └── cache_manager.py        # 缓存管理
│
├── web/                        # Web界面
│   └── templates/
│       ├── index.html          # 主页面（文件上传）
│       ├── guided_input.html   # 引导输入页
│       └── history.html        # 历史记录页
│
├── prompts/                    # AI提示词
│   ├── analyze_prompt.txt      # 分析阶段Prompt
│   ├── generate_prompt.txt     # 生成阶段Prompt
│   └── constraints.txt         # 约束规则
│
├── templates/                  # 简历模板
│   └── original/               # 原版风格
│
├── storage/                    # 数据存储
├── output/                     # 输出文件
├── cache/                      # 缓存文件
└── docs/                       # 文档
```

### 3.3 技术栈

| 层级 | 技术选型 | 版本 | 说明 |
|------|----------|------|------|
| 后端框架 | Flask | 2.3+ | 轻量、易扩展 |
| 前端 | HTML + CSS + JavaScript | - | MVP简洁方案 |
| PDF解析 | pdfplumber | 0.10+ | 主解析器 |
| PDF备选 | PyPDF2 | 3.0+ | fallback |
| Word处理 | python-docx | 1.1+ | 读写Word |
| AI调用 | zhipuai | 2.0+ | GLM-4.6主模型 |
| 文本相似度 | Levenshtein | 0.21+ | 模糊匹配 |
| 环境配置 | python-dotenv | 1.0+ | .env支持 |

### 3.4 模型配置

```python
# 实际配置 (core/config.py)
TASK_MODEL_MAPPING = {
    'analyze': 'glm-4.6',      # 分析任务 - 高精度
    'generate': 'glm-4.6',     # 生成任务 - 高质量
    'validate': 'glm-4-flash'  # 验证任务 - 低成本
}

# 主备切换
PRIMARY_MODEL = 'glm-4.6'
FALLBACK_MODEL = 'glm-4-flash'
```

---

## 4. 核心模块详解

### 4.1 简历解析器 (ResumeParser)

**文件**: `core/resume_parser.py`

**功能**:
- 多格式支持：PDF、Word、TXT、Markdown
- 多级fallback解析
- 结构化信息提取

**数据结构**:
```python
@dataclass
class ParsedResume:
    raw_text: str                    # 原始文本
    basic_info: Dict[str, Any]       # 基本信息
    education: List[Dict]            # 教育背景
    work_experience: List[Dict]      # 工作经历
    projects: List[Dict]             # 项目经历
    skills: List[str]                # 技能
    awards: List[str]                # 奖项
    certificates: List[str]          # 证书
    self_evaluation: str             # 自我评价
    source_format: str               # 来源格式
    parse_confidence: float          # 解析置信度
```

**解析策略**:
```
PDF文件 → pdfplumber (推荐)
       → PyPDF2 (fallback)
       → 抛出异常

Word文件 → python-docx
        → 提取段落 + 表格内容

文本文件 → UTF-8解码
```

### 4.2 AI专家团队 (ExpertTeam)

**文件**: `core/expert_team.py`

**两阶段调用**:

```python
# 阶段1: 分析+策略
def analyze(resume_content, jd_content) -> AnalysisResult:
    """
    模型: glm-4.6
    Temperature: 0.3
    Max Tokens: 4096
    """
    pass

# 阶段2: 生成+自验证
def generate(analysis_result, original_resume, jd_content) -> GenerationResult:
    """
    模型: glm-4.6
    Temperature: 0.5
    Max Tokens: 6144
    """
    pass

# 完整流程
def tailor(resume_content, jd_content) -> Tuple[AnalysisResult, GenerationResult]:
    analysis = self.analyze(...)
    generation = self.generate(...)
    return analysis, generation
```

**数据结构**:
```python
@dataclass
class AnalysisResult:
    resume_analysis: Dict      # 简历解析结果
    jd_requirements: Dict      # JD需求分析
    matching_strategy: Dict    # 匹配策略
    model_used: str
    tokens_used: int

@dataclass
class GenerationResult:
    tailored_resume: Dict      # 定制简历
    evidence_report: Dict      # 依据报告
    optimization_summary: Dict # 优化总结
    model_used: str
    tokens_used: int
```

### 4.3 依据追踪器 (EvidenceTracker)

**文件**: `core/evidence_tracker.py`

**三重验证机制**:

```
┌─────────────────────────────────────────────────────────────┐
│  第一重：本地文本相似度                                       │
│  ├─ SequenceMatcher 计算基础相似度                           │
│  ├─ 关键词重叠率计算                                        │
│  ├─ 综合相似度 = 基础×0.6 + 关键词×0.4                       │
│  └─ 阈值: 0.6 (低于则 reject)                               │
├─────────────────────────────────────────────────────────────┤
│  第二重：可疑关键词检查                                       │
│  ├─ 模式: 精通、专家、权威、顶级、国家级、世界级、首创、独家   │
│  └─ 发现可疑关键词 → 进入第三重                              │
├─────────────────────────────────────────────────────────────┤
│  第三重：AI验证（仅对可疑内容）                               │
│  ├─ 触发条件: 可疑关键词 + confidence < 0.7                  │
│  ├─ 模型: glm-4-flash (低成本)                              │
│  └─ 返回: {valid, confidence, reason}                       │
└─────────────────────────────────────────────────────────────┘
```

**置信度计算**:
```python
final_confidence = (
    base_confidence * 0.4 +      # AI自评置信度
    similarity * 0.4 +           # 相似度
    max(0, 0.2 - suspicious_penalty)  # 可疑词扣分
)
```

**验证结果**:
```python
@dataclass
class ValidationResult:
    item_id: str
    valid: bool
    confidence: float
    action: str  # 'pass' / 'needs_review' / 'reject'
    reason: str
    details: Dict
```

### 4.4 模型管理器 (ModelManager)

**文件**: `core/model_manager.py`

**主备切换机制**:
```python
def call(prompt, task_type, max_tokens, temperature, max_retries=3):
    models_to_try = [preferred_model] + fallback_models

    for model in models_to_try:
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(...)
                return ModelResponse(success=True, ...)
            except Exception as e:
                if is_quota_error(e):
                    break  # 切换模型
                time.sleep((attempt + 1) * 2)  # 指数退避
```

**配额错误检测**:
```python
def _is_quota_error(error):
    keywords = ['quota', 'limit', 'exhausted', 'rate', '1310']
    return any(kw in str(error).lower() for kw in keywords)
```

### 4.5 缓存管理器 (CacheManager)

**文件**: `core/cache_manager.py`

**MD5缓存机制**:
```python
def get_cache_key(resume_content, jd_content):
    combined = resume_content + jd_content
    return hashlib.md5(combined.encode('utf-8')).hexdigest()

# 缓存结构
{
    "cache_key": "abc123...",
    "timestamp": "2026-03-11T12:00:00",
    "result": {...}  # 完整结果
}

# 过期策略: 30天自动清理
```

### 4.6 匹配度分数计算器 (MatchScorer)

**文件**: `core/match_scorer.py`

**设计目标**:
- 分数透明可解释，用户清楚知道分数来源
- 基于明确的权重规则，而非 AI 主观判断
- 结果稳定一致，相同输入得到相同分数

#### 分数计算公式

```
最终分数 = 基础分(60) + 加分项 - 扣分项

分数范围: 0 - 100
```

#### 要求类型与分数影响

| 要求类型 | 完全匹配 | 部分匹配 | 不匹配 | 超出要求 | 未知 |
|----------|----------|----------|--------|----------|------|
| **硬性要求** (must_have) | +10 | +3 | -20 | +12 | -5 |
| **加分项** (nice_to_have) | +6 | +2 | 0 | +8 | 0 |
| **优先项** (preferred) | +5 | +2 | 0 | +6 | 0 |

#### 要求类型说明

| 类型 | 说明 | 示例 |
|------|------|------|
| must_have | JD 明确要求的硬性条件 | "本科及以上学历"、"3年以上开发经验" |
| nice_to_have | JD 中的加分项/优先项 | "有创业经验优先"、"熟悉机器学习优先" |
| preferred | 可选的优先条件 | "985/211院校优先"、"有开源项目经验" |

#### 匹配状态说明

| 状态 | 说明 |
|------|------|
| fully_matched | 完全符合要求 |
| partially_matched | 部分符合（如要求5年经验，实际3年） |
| not_matched | 明确不满足要求 |
| exceeds | 超出要求（如要求本科，实际硕士） |
| unknown | 无法判断（需人工确认） |

#### 分数等级划分

| 分数区间 | 等级 | 说明 |
|----------|------|------|
| 80-100 | 优秀匹配 | 简历与职位高度匹配，建议突出差异化优势 |
| 60-79 | 良好匹配 | 简历与职位基本匹配，建议优化待提升项 |
| 40-59 | 待提升 | 简历与职位有一定差距，建议重点提升核心要求 |
| 0-39 | 高风险/低匹配 | 简历与职位匹配度较低，建议重点补充核心技能 |

#### 计算示例

**场景**: 5年Python开发经验岗位

| JD要求 | 类型 | 简历情况 | 匹配状态 | 分数影响 |
|--------|------|----------|----------|----------|
| 本科及以上学历 | must_have | 硕士 | exceeds | +12 |
| 5年Python开发经验 | must_have | 3年 | partially_matched | +3 |
| 熟悉Django/Flask | must_have | 熟悉Django | partially_matched | +3 |
| 有微服务经验优先 | nice_to_have | 无 | not_matched | 0 |
| 熟悉Docker/K8s | nice_to_have | 熟悉Docker | partially_matched | +2 |

```
最终分数 = 60(基础) + 12 + 3 + 3 + 0 + 2 = 80分
等级: 优秀匹配
```

#### 数据结构

```python
@dataclass
class MatchScoreResult:
    score: int                           # 最终分数 (0-100)
    level: str                           # 等级
    breakdown: Dict[str, int]            # 分数明细
    requirements_analysis: List[Dict]    # 各项分析
    summary: str                         # 总结说明

# 返回示例
{
    'score': 80,
    'level': '优秀匹配',
    'breakdown': {
        '基础分': 60,
        '硬性要求匹配': 18,
        '加分项匹配': 2,
        '优先项匹配': 0,
        '扣分项': 0
    },
    'summary': '匹配度优秀！5/5项要求匹配',
    'requirements': [...]
}
```

#### 与 AI 分析的协作

```
┌─────────────────────────────────────────────────────────────┐
│  AI 负责语义理解                                            │
│  ├─ 识别 JD 中的各项要求                                     │
│  ├─ 判断每项要求的类型（硬性/加分/优先）                      │
│  ├─ 在简历中查找匹配证据                                     │
│  └─ 返回 jd_requirements_checklist                          │
├─────────────────────────────────────────────────────────────┤
│  代码负责数学计算                                            │
│  ├─ 根据权重表计算分数                                       │
│  ├─ 生成分数明细                                            │
│  └─ 确定匹配等级                                            │
└─────────────────────────────────────────────────────────────┘
```

#### 前端展示

分数明细在匹配分析卡片下方显示：

```
📊 分数计算明细
[基础分 60] [硬性要求匹配 +18] [加分项匹配 +2]
```

---

## 5. API设计

### 5.1 核心端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/` | GET | 主页（文件上传模式） |
| `/guided` | GET | 引导输入页面 |
| `/history` | GET | 历史记录页面 |
| `/api/tailor/file` | POST | 文件上传模式定制 |
| `/api/tailor/form` | POST | 引导输入模式定制 |
| `/api/preview` | POST | 实时预览 |
| `/api/status/<task_id>` | GET | 查询进度 |
| `/api/health` | GET | 健康检查 |
| `/api/stats` | GET | 系统统计 |

### 5.2 文件上传模式 API

**请求**: `POST /api/tailor/file`

```
Content-Type: multipart/form-data

resume: <文件> (PDF/Word/TXT/MD)
jd_text: <文本> 或 jd: <文件>
style: "original" (可选)
```

**响应**:
```json
{
    "session_id": "uuid-xxx",
    "status": "completed",
    "tailored_word": "base64...",
    "evidence_report": {
        "total_items": 10,
        "validated": 9,
        "needs_review": 1,
        "rejected": 0,
        "coverage": 0.9
    },
    "validation_result": "pass",
    "analysis": {
        "match_score": 75,
        "match_level": "良好",
        "strengths": ["Python开发经验", "数据分析能力"],
        "gaps": ["团队管理经验"]
    }
}
```

### 5.3 引导输入模式 API

**请求**: `POST /api/tailor/form`

```json
{
    "name": "张三",
    "phone": "13800138000",
    "email": "zhangsan@example.com",
    "gender": "男",
    "age": 28,
    "location": "北京",
    "edu_school_0": "北京大学",
    "edu_major_0": "计算机科学",
    "edu_degree_0": "本科",
    "edu_time_0": "2016.09-2020.06",
    "work_company_0": "字节跳动",
    "work_position_0": "Python开发工程师",
    "work_time_0": "2020.07-至今",
    "work_content_0": "负责后端API开发...",
    "jd": "职位描述内容..."
}
```

**响应**: 同文件上传模式

### 5.4 健康检查 API

**请求**: `GET /api/health`

**响应**:
```json
{
    "status": "healthy",
    "version": "1.0.0",
    "timestamp": "2026-03-11T12:00:00"
}
```

### 5.5 系统统计 API

**请求**: `GET /api/stats`

**响应**:
```json
{
    "model_stats": {
        "total_calls": 10,
        "success_calls": 10,
        "failed_calls": 0,
        "total_tokens": 50000
    },
    "cache_stats": {
        "hits": 5,
        "misses": 5,
        "hit_rate": 0.5,
        "cache_count": 5
    },
    "parser_stats": {
        "pdfplumber": 3,
        "pypdf2": 1,
        "docx": 2,
        "text": 4
    }
}
```

---

## 6. 配置参数

### 6.1 环境变量 (.env)

```bash
# ZhipuAI API Key (必填)
ZHIPU_API_KEY=your_api_key_here

# 模型配置
PRIMARY_MODEL=glm-4.6
FALLBACK_MODEL=glm-4-flash

# 处理配置
MAX_PROCESSING_TIME=60
EVIDENCE_THRESHOLD=0.7

# 存储配置
DATABASE_PATH=storage/tailorcv.db
HISTORY_RETENTION_DAYS=30
```

### 6.2 核心参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| SIMILARITY_THRESHOLD | 0.6 | 文本相似度阈值，低于则拒绝 |
| CONFIDENCE_THRESHOLD | 0.7 | 置信度阈值，低于则需人工确认 |
| EVIDENCE_COVERAGE_TARGET | 0.90 | 依据覆盖目标 |
| MAX_CONTENT_LENGTH | 16MB | 最大上传文件大小 |
| HISTORY_RETENTION_DAYS | 30 | 历史记录保留天数 |

---

## 7. 非功能需求

### 7.1 性能指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 单次处理时间 | < 45秒 | 两阶段AI调用 + 本地验证 |
| 文件解析成功率 | > 90% | 多级fallback保障 |
| AI调用成功率 | > 98% | 主备切换 + 重试机制 |
| 依据覆盖率 | > 90% | 三重验证保障 |
| 缓存命中率 | > 50% | 相同简历-JD组合 |

### 7.2 安全要求

- ✅ API密钥通过环境变量配置
- ✅ 本地存储，不上传外部服务器
- ✅ .env 文件在 .gitignore 中
- ✅ 最大文件大小限制 (16MB)

### 7.3 可用性要求

- ✅ 中文界面
- ✅ 友好的错误提示
- ✅ 分步引导流程
- ✅ 进度实时反馈

---

## 8. 使用指南

### 8.1 安装部署

```bash
# 1. 进入项目目录
cd tailorCV

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置API密钥
cp .env.example .env
# 编辑 .env 填入 ZHIPU_API_KEY

# 4. 启动服务
python app.py
```

### 8.2 访问地址

- 本地: http://127.0.0.1:5000
- 局域网: http://<本机IP>:5000

### 8.3 使用流程

**文件上传模式**:
1. 访问主页 http://127.0.0.1:5000
2. 拖拽或点击上传简历文件
3. 粘贴或上传职位JD
4. 点击"开始定制简历"
5. 查看匹配分析和依据报告
6. 下载定制后的Word文档

**引导输入模式**:
1. 访问 http://127.0.0.1:5000/guided
2. 填写基本信息、教育背景、工作经历等
3. 粘贴职位JD
4. 点击"生成定制简历"
5. 下载定制后的Word文档

---

## 9. v2.0 模板系统技术规划

### 9.1 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    模板系统架构                              │
├─────────────────────────────────────────────────────────────┤
│  模板管理层 (TemplateManager)                               │
│  ├─ 模板注册表：管理所有可用模板                             │
│  ├─ 模板加载器：动态加载模板文件                             │
│  └─ 模板切换器：根据用户选择切换模板                         │
├─────────────────────────────────────────────────────────────┤
│  模板接口层 (TemplateInterface)                             │
│  ├─ 统一接口：render(resume_data) -> Word文档               │
│  ├─ 配置接口：get_config(), set_config()                    │
│  └─ 预览接口：get_preview() -> 图片/HTML                     │
├─────────────────────────────────────────────────────────────┤
│  模板存储层                                                 │
│  templates/                                                 │
│  ├─ original/        # 原版风格（v1.0）                     │
│  ├─ professional/    # 专业版                               │
│  ├─ minimal/         # 简约版                               │
│  ├─ technical/       # 技术版                               │
│  └─ creative/        # 创意版                               │
└─────────────────────────────────────────────────────────────┘
```

### 9.2 目录结构

```
tailorCV/
├── templates/                    # 简历模板目录
│   ├── base_template.py          # 模板基类
│   ├── template_manager.py       # 模板管理器
│   │
│   ├── original/                 # 原版风格（v1.0默认）
│   │   ├── template.py           # 模板实现
│   │   ├── config.json           # 模板配置
│   │   └── preview.png           # 预览图
│   │
│   ├── professional/             # 专业版
│   │   ├── template.py
│   │   ├── config.json
│   │   └── preview.png
│   │
│   ├── minimal/                  # 简约版
│   │   ├── template.py
│   │   ├── config.json
│   │   └── preview.png
│   │
│   ├── technical/                # 技术版
│   │   ├── template.py
│   │   ├── config.json
│   │   └── preview.png
│   │
│   └── creative/                 # 创意版
│       ├── template.py
│       ├── config.json
│       └── preview.png
```

### 9.3 模板接口规范

```python
from abc import ABC, abstractmethod
from typing import Dict, Any
from docx import Document

class BaseTemplate(ABC):
    """模板基类"""

    @property
    @abstractmethod
    def template_id(self) -> str:
        """模板唯一标识"""
        pass

    @property
    @abstractmethod
    def template_name(self) -> str:
        """模板显示名称"""
        pass

    @property
    @abstractmethod
    def template_description(self) -> str:
        """模板描述"""
        pass

    @property
    @abstractmethod
    def suitable_for(self) -> list:
        """适用场景列表"""
        pass

    @abstractmethod
    def render(self, resume_data: Dict[str, Any]) -> Document:
        """
        渲染简历

        Args:
            resume_data: 结构化简历数据

        Returns:
            Document: python-docx Document对象
        """
        pass

    def get_preview(self) -> bytes:
        """获取模板预览图（PNG格式）"""
        pass

    def get_config(self) -> Dict[str, Any]:
        """获取模板配置"""
        pass
```

### 9.4 模板配置规范 (config.json)

```json
{
    "template_id": "professional",
    "template_name": "专业版",
    "version": "1.0.0",
    "description": "传统商务风格，适合大多数岗位",
    "suitable_for": [
        "企业管理",
        "金融财务",
        "市场销售",
        "人力资源"
    ],
    "features": {
        "photo_support": true,
        "color_scheme": ["#1a365d", "#2d3748", "#4a5568"],
        "font_family": "Microsoft YaHei",
        "page_size": "A4",
        "margins": {
            "top": "1.5cm",
            "bottom": "1.5cm",
            "left": "2cm",
            "right": "2cm"
        }
    },
    "sections": {
        "basic_info": {"order": 1, "required": true},
        "summary": {"order": 2, "required": false, "max_length": 200},
        "work_experience": {"order": 3, "required": true},
        "education": {"order": 4, "required": true},
        "skills": {"order": 5, "required": true},
        "projects": {"order": 6, "required": false},
        "awards": {"order": 7, "required": false},
        "self_evaluation": {"order": 8, "required": false}
    }
}
```

### 9.5 模板加载和切换机制

```python
class TemplateManager:
    """模板管理器"""

    def __init__(self):
        self._templates = {}
        self._current_template = None
        self._load_all_templates()

    def _load_all_templates(self):
        """加载所有可用模板"""
        templates_dir = Path('templates')
        for template_dir in templates_dir.iterdir():
            if template_dir.is_dir():
                self._register_template(template_dir)

    def _register_template(self, template_dir: Path):
        """注册模板"""
        template_module = importlib.import_module(
            f'templates.{template_dir.name}.template'
        )
        template_class = getattr(template_module, 'Template')
        self._templates[template_dir.name] = template_class()

    def get_template(self, template_id: str) -> BaseTemplate:
        """获取指定模板"""
        return self._templates.get(template_id)

    def list_templates(self) -> List[Dict]:
        """列出所有模板"""
        return [
            {
                'id': t.template_id,
                'name': t.template_name,
                'description': t.template_description,
                'suitable_for': t.suitable_for
            }
            for t in self._templates.values()
        ]

    def render(self, template_id: str, resume_data: dict) -> Document:
        """使用指定模板渲染简历"""
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"模板不存在: {template_id}")
        return template.render(resume_data)
```

### 9.6 预期模板列表

| 模板ID | 名称 | 风格描述 | 适用场景 |
|--------|------|----------|----------|
| original | 原版风格 | 简洁清晰，MVP默认 | 通用 |
| professional | 专业版 | 传统商务风格 | 企业管理、金融、销售 |
| minimal | 简约版 | 现代极简设计 | 互联网、设计、创意 |
| technical | 技术版 | 突出技术栈和项目 | 程序员、工程师、技术岗 |
| creative | 创意版 | 个性化设计 | 设计、营销、新媒体 |

### 9.7 API 扩展

```python
# 新增API端点

# 获取模板列表
GET /api/templates
Response: {
    "templates": [
        {"id": "original", "name": "原版风格", ...},
        {"id": "professional", "name": "专业版", ...},
        ...
    ]
}

# 获取模板预览
GET /api/templates/{template_id}/preview
Response: image/png

# 定制简历（指定模板）
POST /api/tailor/file
Request: {
    ...
    "template": "professional"  // 新增参数
}
```

### 9.8 开发路线

| 阶段 | 内容 | 预计工期 |
|------|------|----------|
| Phase 1 | 模板系统架构搭建 | 2天 |
| Phase 2 | professional模板开发 | 1天 |
| Phase 3 | minimal模板开发 | 1天 |
| Phase 4 | technical模板开发 | 1天 |
| Phase 5 | creative模板开发 | 1天 |
| Phase 6 | 前端模板选择UI | 2天 |
| Phase 7 | 测试和优化 | 2天 |

---

## 10. 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.3.1 | 2026-04-04 | 模板渲染修复：tailored 内容正确渲染到 docx；登录引导页重设计（紧凑居中卡片）；用户参数服务端持久化；GLM API 并发错峰；免费体验 3 次；Benchmark 测试套件 |
| v1.3.0 | 2026-04-03 | Writer-Reviewer 闭环：多模型审阅迭代改写，5 重收敛机制，AntiGravity 代理支持 |
| v1.2.0 | 2026-03-24 | 多模型支持: 添加GLM-5模型，三层服务架构（工具选择器/简版/多模型），模板管理功能（6个内置模板） |
| v1.1.0 | 2026-03-11 | PRD调整：目标用户扩大为"所有受过高等教育的人"；工作经历改为选填；新增v2.0模板系统规划 |
| v1.0.0 | 2026-03-11 | 初始版本，实现MVP全部功能 |

### 实现状态追踪

| 功能 | 状态 | 说明 |
|------|------|------|
| 文件上传模式 | ✅ 已实现 | PDF/DOCX/TXT/MD |
| 引导输入模式 | ✅ 已实现 | 分步表单 |
| AI五阶段定制 | ✅ 已实现 | GLM-5 五阶段流程 |
| Writer-Reviewer 闭环 | ✅ 已实现 | 多模型审阅迭代，5 重收敛机制 |
| 依据追踪 | ✅ 已实现 | 三重验证 |
| 匹配度分数 | ✅ 已实现 | 基于权重规则 |
| 多模型支持 | ✅ 已实现 | GLM-5 + 阿里云Qwen + AntiGravity 代理 |
| 模板管理 | ✅ 已实现 | 6个内置模板，选择器UI |
| 用户认证 + 支付 | ✅ 已实现 | 邮箱验证码登录，支付宝当面付 |
| 模板渲染修复 | ✅ 已实现 | tailored 内容 Jinja2 变量化 + 换行拆段 + 求职意向识别 |
| 用户参数持久化 | ✅ 已实现 | localStorage + 服务端双写，清缓存不丢失 |
| Benchmark 测试 | ✅ 已实现 | 14 个测试用例（渲染完整性/关键词覆盖/JD对齐/忠实度/E2E） |
| 表格转图像 | 📋 规划中 | v2.0功能 |

---

## 10. 附录

### A. 关键文件清单

| 文件 | 用途 | 代码行数 |
|------|------|----------|
| `app.py` | Flask主入口 | ~300 |
| `core/config.py` | 配置管理（含置信度权重配置） | ~120 |
| `core/database.py` | SQLite数据库存储（历史记录/任务状态） | ~350 |
| `core/resume_parser.py` | 简历解析 | ~420 |
| `core/resume_builder.py` | 简历构建 | ~200 |
| `core/expert_team.py` | AI两阶段调用（增强JSON fallback） | ~450 |
| `core/model_manager.py` | 模型管理 | ~150 |
| `core/evidence_tracker.py` | 依据追踪（优化AI验证） | ~400 |
| `core/resume_generator.py` | 简历生成 | ~300 |
| `core/cache_manager.py` | 缓存管理 | ~180 |
| `core/match_scorer.py` | 匹配度分数计算器 | ~350 |
| `prompts/analyze_prompt.txt` | 分析Prompt（支持应届生） | ~130 |
| `prompts/generate_prompt.txt` | 生成Prompt（支持应届生） | ~160 |

### B. 依赖清单

```
Flask>=2.3.0
Flask-CORS>=4.0.0
pdfplumber>=0.10.0
PyPDF2>=3.0.0
python-docx>=1.1.0
docx2pdf>=0.1.8
zhipuai>=2.0.0
python-Levenshtein>=0.21.0
fuzzywuzzy>=0.18.0
python-dotenv>=1.0.0
requests>=2.31.0
```

---

**文档结束**
