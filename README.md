# tailorCV - 智能简历定制工具

基于 AI 的智能简历定制工具，帮助求职者根据目标职位 JD 快速生成定制化简历。

## 核心特性

- **零编造**：所有生成内容必须有据可依（90%+依据覆盖）
- **依据追踪**：透明的修改来源展示
- **双模式输入**：文件上传 + 引导输入
- **智能优化**：AI 深度分析 JD，针对性优化简历

## 技术栈

- **后端**：Flask 2.x
- **AI 模型**：ZhipuAI GLM-4.6 / GLM-4-flash
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
├── app.py                 # Flask 主入口
├── core/                  # 核心业务逻辑
│   ├── config.py          # 配置管理
│   ├── resume_parser.py   # 简历解析器
│   ├── expert_team.py     # AI 专家团队
│   ├── evidence_tracker.py# 依据追踪器
│   └── resume_generator.py# 简历生成器
├── api/                   # REST API
├── web/                   # Web 界面
├── prompts/               # AI 提示词
├── templates/             # 简历模板
└── storage/               # 数据存储
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
