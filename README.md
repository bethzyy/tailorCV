# tailorCV - 智能简历定制工具

基于 AI 的智能简历定制工具，帮助求职者根据目标职位 JD 快速生成定制化简历。

## 核心特性

- **零编造**：所有生成内容必须有据可依（90%+依据覆盖）
- **依据追踪**：透明的修改来源展示
- **双模式输入**：文件上传 + 引导输入
- **智能优化**：AI 深度分析 JD，针对性优化简历
- **Writer-Reviewer 闭环**：多模型审阅迭代，简历质量多轮打磨

## 技术栈

- **后端**：Flask 2.x
- **AI 模型**：ZhipuAI GLM-5 / GLM-4-flash, 阿里云 Qwen
- **文档处理**：pdfplumber, PyPDF2, python-docx
- **数据存储**：SQLite

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API 密钥

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env 文件，填入你的 ZhipuAI API 密钥
ZHIPU_API_KEY=your_api_key_here
```

### 3. 启动服务

```bash
python app.py
```

访问 http://localhost:5000 开始使用。

## 使用方式

### 方式一：文件上传

1. 上传原版简历（支持 PDF、Word、TXT、Markdown）
2. 粘贴或上传目标职位 JD
3. 点击"开始定制"
4. 下载定制后的简历

### 方式二：引导输入

1. 填写基本信息、教育背景、工作经历等
2. 粘贴目标职位 JD
3. 点击"生成定制简历"
4. 下载定制后的简历

## 项目结构

```
tailorCV/
├── apps/
│   ├── simple_app.py      # 简版工具 Flask 应用
│   └── multi_app.py       # 多模型工具 Flask 应用
├── core/
│   ├── config.py          # 配置管理
│   ├── expert_team.py     # AI 专家团队（含 Writer-Reviewer 闭环）
│   ├── template_processor.py  # 模板渲染处理器
│   ├── jinja_inserter.py  # Jinja2 标签插入器
│   ├── structure_detector.py  # 简历结构检测器
│   ├── auth.py            # 用户认证
│   ├── quota.py           # 配额管理
│   └── providers/         # AI 提供商适配器
├── web/templates/simple/  # 简版工具前端
├── prompts/               # AI 提示词
├── templates/             # 简历模板
├── tests/benchmark/       # Benchmark 测试套件
└── docs/                  # 文档
```

## API 文档

### POST /api/tailor/file

文件上传模式定制简历。

**请求**：
- `resume`: 简历文件（PDF/Word/TXT/MD）
- `jd`: JD 文件或文本

**响应**：
```json
{
  "session_id": "uuid-xxx",
  "status": "completed",
  "tailored_word": "base64...",
  "tailored_pdf": "base64...",
  "evidence_report": {...}
}
```

### POST /api/tailor/form

引导输入模式定制简历。

### GET /api/status/<task_id>

查询处理进度。

### GET /api/history

获取历史记录。

## 许可证

MIT License
