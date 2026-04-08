# tailorCV 测试计划文档

> **这份文档解决什么问题**：现在测了什么、没测什么？每个模块有哪些用例？下一步该写什么？怎么跑？
>
> **一句话定位**：测试的**现状清单和行动清单**，不解释为什么要这样设计。
>
> **谁该看**：执行测试的人、补写用例的开发者、检查覆盖率的负责人。
>
> **配合关系**：[测试方案文档](test-strategy.md)定规则 → 本文档按规则列出具体用例和执行步骤。

---

## 1. 测试范围总览

### 1.1 模块 × 测试类型矩阵

| 模块 | 静态分析 | 单元测试 | API 集成 | 基准测试 | 回归测试 | 安全测试 | 状态 |
|------|:--------:|:--------:|:--------:|:--------:|:--------:|:--------:|------|
| 认证 (`core/auth.py`) | - | - | 12 | - | - | - | 已覆盖 |
| 健康检查 | - | - | 3 | - | - | - | 已覆盖 |
| 支付 (`core/payment/`) | - | - | 9 | - | - | - | 已覆盖 |
| 配额 (`core/quota.py`) | - | - | 5 | - | - | - | 已覆盖 |
| 简历定制 API | - | - | 7 | - | - | - | 已覆盖 |
| 模板管理 (`core/template_manager.py`) | - | - | 8 | - | - | - | 已覆盖 |
| 用户中心 | - | - | 3 | - | - | - | 已覆盖 |
| 用户参数 | - | - | 4 | - | - | - | 已覆盖 |
| Writer-Reviewer (`core/expert_team.py`) | - | 26 | - | - | - | - | 已覆盖 |
| 前端 HTML/JS | 64 | - | - | - | - | - | 已覆盖 |
| 前端结构 | 11 | - | - | - | - | - | 已覆盖 |
| 阿里云连通 | - | 5 | - | - | - | - | 已覆盖 |
| 定制质量 | - | - | - | 14 | - | - | 已覆盖 |
| 简历解析 (`core/resume_parser.py`) | - | 28 | - | - | - | - | 已覆盖 |
| 简历构建 (`core/resume_builder.py`) | - | 13 | - | - | - | - | 已覆盖 |
| 简历生成 (`core/resume_generator.py`) | - | 20 | - | - | - | - | 已覆盖 |
| 依据追踪 (`core/evidence_tracker.py`) | - | 17 | - | - | - | - | 已覆盖 |
| 匹配评分 (`core/match_scorer.py`) | - | 22 | - | - | - | - | 已覆盖 |
| 缓存管理 (`core/cache_manager.py`) | - | 17 | - | - | - | - | 已覆盖 |
| 模板处理 (`core/template_processor.py`) | - | 30 | - | - | - | - | 已覆盖 |
| 结构检测 (`core/structure_detector.py`) | - | 16 | - | - | - | - | 已覆盖 |
| Jinja2 插入 (`core/jinja_inserter.py`) | - | - | - | 2 | - | - | 部分覆盖 |
| 数据库 (`core/database.py`) | - | 21 | - | - | - | - | 已覆盖 |
| 配置 (`core/config.py`) | - | 19 | - | - | - | - | 已覆盖 |
| 模型管理 (`core/model_manager.py`) | - | 11 | - | - | - | - | 已覆盖 |
| AI 质量回归 | - | - | - | - | 12 | - | **新增** |
| 安全测试 | - | - | - | - | - | 20 | **新增** |

### 1.2 统计摘要

| 指标 | 数值 |
|------|------|
| 测试文件总数 | 22（含 3 个 conftest） |
| 测试用例总数 | 379（+2 skipped） |
| 已覆盖模块 | 24 |
| 未覆盖模块 | 1（jinja_inserter 部分覆盖） |
| API 端点覆盖率 | ~95%（主要端点已覆盖） |
| 安全测试覆盖 | 20 用例（SQL 注入、XSS、认证绕过、文件上传、输入验证、限流） |
| AI 质量回归 | 12 用例（关键词覆盖、忠实度、JD 对齐、结构完整性） |

### 1.3 未覆盖模块复杂度地图

> 评估维度：行数（代码规模）、外部依赖（是否需要 mock）、可测试性（编写测试的难度）

| 模块 | 行数 | 外部依赖 | 可测试性 | 核心公共接口 | Mock 策略 |
|------|------|----------|----------|-------------|-----------|
| `resume_builder.py` | 298 | 无 | Easy | `build_from_form()`, `build_structured()` | 无需 mock |
| `match_scorer.py` | 444 | 无 | Easy | `calculate_score()`, `calculate_match_score()` | 无需 mock |
| `cache_manager.py` | 220 | 文件系统 | Easy | `get()`, `set()`, `clear_expired()` | tmpdir |
| `config.py` | 247 | 环境变量 | Easy | `validate()`, `get_model_for_task()` | os.environ |
| `model_manager.py` | 147 | AI provider | Medium | `call()`, `is_available()` | mock provider.call() |
| `evidence_tracker.py` | 391 | AI 验证 | Medium | `validate_content()`, `validate_resume()` | mock _ai_validate() |
| `structure_detector.py` | 390 | docx 文件 | Medium | `detect_structure()` | fixture .docx 文件 |
| `database.py` | 970 | 无（已有 fixture） | Medium | `create_user()`, `save_history()` 等 | 已有临时 DB |
| `resume_parser.py` | 736 | PDF/Word 库 | Medium | `parse()`, `_parse_pdf()`, `_parse_word()` | fixture 文件 |
| `resume_generator.py` | 459 | python-docx | Medium | `generate_word()`, `generate_pdf()` | 检查输出文件 |
| `template_processor.py` | 683 | Jinja2 + docx | Medium | `preprocess()`, `render()` | fixture 模板 |
| `jinja_inserter.py` | 517 | docx XML 操作 | Hard | `insert_tags()`, `_replace_paragraph_text()` | fixture .docx |
| `expert_team.py` | 2229 | AI 模型 + 管道 | Hard | `tailor()` 五阶段 + Writer-Reviewer | mock model_manager |

---

## 2. 现有测试用例清单

### 2.1 静态分析测试（64 用例）

**文件**：`tests/test_static_checks.py`
**机制**：自动扫描 `web/templates/` 下所有 HTML 文件（当前 8 个文件 × 8 类检测）

| 用例 ID | 类 | 方法 | 检测内容 |
|---------|-----|------|----------|
| SC-01 | TestHTMLIDDuplicates | test_no_duplicate_ids | HTML id 唯一性 |
| SC-02 | TestJSDuplicates | test_no_duplicate_function_declarations | JS function 声明唯一性 |
| SC-03 | TestElementReferences | test_getElementById_targets_exist | getElementById 引用的 id 存在 |
| SC-04 | TestElementReferences | test_querySelector_id_targets_exist | querySelector('#xxx') 引用的 id 存在 |
| SC-05 | TestInlineEventHandlerReferences | test_inline_handlers_reference_existing_functions | inline 事件调用的函数已定义 |
| SC-06 | TestEventListenerTargets | test_addEventListener_on_existing_ids | addEventListener 绑定的元素存在 |
| SC-07 | TestClassListOperations | test_classList_on_existing_ids | classList 操作的元素存在 |
| SC-08 | TestStyleOperations | test_style_on_existing_ids | style 操作的元素存在 |

> 每类检测对每个 HTML 文件生成 1 个用例，共 8 类 × 8 文件 = 64 用例。

### 2.2 前端结构测试（11 用例）

**文件**：`tests/test_frontend.py`

| 用例 ID | 类 | 方法 | 验证内容 |
|---------|-----|------|----------|
| FE-01 | TestJSFunctionReferences | test_all_onclick_functions_exist | onclick 引用的函数都已定义 |
| FE-02 | TestElementIdReferences | test_all_referenced_ids_exist | JS 引用的 HTML id 都存在 |
| FE-03 | TestAPIEndpointsMatch | test_all_frontend_endpoints_exist | 前端调用的 API 端点都在后端定义 |
| FE-04 | TestModalDisplayConsistency | test_no_classlist_show_on_inline_hidden_modals | 隐藏的弹窗没有 classList.show 调用 |
| FE-05 | TestHTMLStructure | test_html_has_login_modal | 登录弹窗存在 |
| FE-06 | TestHTMLStructure | test_html_has_payment_modal | 支付弹窗存在 |
| FE-07 | TestHTMLStructure | test_html_has_user_center_modal | 用户中心弹窗存在 |
| FE-08 | TestHTMLStructure | test_html_has_template_preview_modal | 模板预览弹窗存在 |
| FE-09 | TestHTMLStructure | test_html_has_login_guide | 登录引导页存在 |
| FE-10 | TestHTMLStructure | test_html_has_quota_badge | 配额徽标存在 |
| FE-11 | TestHTMLStructure | test_html_has_bfcache_prevention | bfcache 防止机制存在 |

### 2.3 API 集成测试（47 用例）

#### 认证（12 用例）

**文件**：`tests/test_api_auth.py`

| 用例 ID | 类 | 方法 | 场景 | 预期 |
|---------|-----|------|------|------|
| AUTH-01 | TestAuthSendCode | test_send_code_empty_email | 空邮箱 | 400 |
| AUTH-02 | TestAuthSendCode | test_send_code_no_body | 无请求体 | 400 |
| AUTH-03 | TestAuthSendCode | test_send_code_invalid_email | 非法邮箱格式 | 400 |
| AUTH-04 | TestAuthSendCode | test_send_code_valid_email | 正常发送 | 200 |
| AUTH-05 | TestAuthSendCode | test_send_code_rate_limit | 限流触发 | 429 |
| AUTH-06 | TestAuthLogin | test_login_empty_fields | 空字段 | 400 |
| AUTH-07 | TestAuthLogin | test_login_wrong_code | 错误验证码 | 401 |
| AUTH-08 | TestAuthLogin | test_login_success | 正常登录 | 200 + session |
| AUTH-09 | TestAuthLogin | test_login_existing_user | 老用户登录 | 200（非首次） |
| AUTH-10 | TestAuthLogout | test_logout | 正常登出 | 200 + session 清除 |
| AUTH-11 | TestAuthLogout | test_get_current_user_none_when_not_logged_in | 未登录查状态 | null |
| AUTH-12 | TestAuthMe | test_me_unauthorized | 未登录访问 | 401 |

#### 健康检查（3 用例）

**文件**：`tests/test_api_health.py`

| 用例 ID | 方法 | 场景 | 预期 |
|---------|------|------|------|
| HL-01 | test_index_returns_html | 访问首页 | 200 + HTML |
| HL-02 | test_index_no_cache_headers | 缓存头检查 | no-cache |
| HL-03 | test_health_check | 健康端点 | 200 + status ok |

#### 支付（9 用例）

**文件**：`tests/test_api_payment.py`

| 用例 ID | 类 | 方法 | 场景 | 预期 |
|---------|-----|------|------|------|
| PAY-01 | TestPaymentPlans | test_get_plans | 获取套餐列表 | 200 + 列表 |
| PAY-02 | TestPaymentPlans | test_plan_prices | 套餐价格正确 | 价格 > 0 |
| PAY-03 | TestPaymentCreate | test_create_unauthorized | 未登录创建订单 | 401 |
| PAY-04 | TestPaymentLogic | test_create_pack5_direct | 创建套餐5订单 | 订单号 + 支付信息 |
| PAY-05 | TestPaymentLogic | test_create_invalid_plan_direct | 无效套餐 | 400 |
| PAY-06 | TestPaymentLogic | test_create_free_plan_direct | 免费套餐 | 正常处理 |
| PAY-07 | TestPaymentLogic | test_simulate_full_flow | 模拟完整支付流程 | 订单状态 paid |
| PAY-08 | TestPaymentLogic | test_query_order | 查询订单 | 订单详情 |
| PAY-09 | TestPaymentLogic | test_simulate_nonexistent | 查询不存在订单 | 404 |

#### 配额（5 用例）

**文件**：`tests/test_api_quota.py`

| 用例 ID | 类 | 方法 | 场景 | 预期 |
|---------|-----|------|------|------|
| QT-01 | TestQuotaAPI | test_quota_unauthorized | 未登录查配额 | 401 |
| QT-02 | TestQuotaLogic | test_check_quota_free_user_can_use | 免费用户首次使用 | 可用 |
| QT-03 | TestQuotaLogic | test_check_quota_exhausted | 配额用尽 | 403 |
| QT-04 | TestQuotaLogic | test_activate_pack5 | 激活套餐5 | 配额增加 |
| QT-05 | TestQuotaLogic | test_get_quota_display | 配额展示信息 | 正确的剩余/总数 |

#### 简历定制（7 用例）

**文件**：`tests/test_api_tailor.py`

| 用例 ID | 类 | 方法 | 场景 | 预期 |
|---------|-----|------|------|------|
| TL-01 | TestTailorFileQuota | test_tailor_file_no_file | 未上传文件 | 400 |
| TL-02 | TestTailorFileQuota | test_tailor_file_anonymous_first_time_passes | 匿名首次 | 通过 |
| TL-03 | TestTailorFileQuota | test_tailor_file_logged_in_no_quota | 登录无配额 | 403 |
| TL-04 | TestTailorTextQuota | test_tailor_text_no_body | 无请求体 | 400 |
| TL-05 | TestTailorTextQuota | test_tailor_text_anonymous_blocked | 匿名文本模式 | 403 |
| TL-06 | TestTailorFormQuota | test_tailor_form_no_body | 无请求体 | 400 |
| TL-07 | TestTailorFormQuota | test_tailor_form_anonymous_blocked | 匿名表单模式 | 403 |

#### 模板管理（8 用例）

**文件**：`tests/test_api_templates.py`

| 用例 ID | 类 | 方法 | 场景 | 预期 |
|---------|-----|------|------|------|
| TP-01 | TestTemplateList | test_get_templates | 获取模板列表 | 200 + 列表 |
| TP-02 | TestTemplateList | test_builtin_templates_exist | 内置模板存在 | 列表非空 |
| TP-03 | TestTemplateDetail | test_get_template_detail | 获取模板详情 | 200 + 详情 |
| TP-04 | TestTemplateDetail | test_get_nonexistent_template | 不存在的模板 | 404 |
| TP-05 | TestTemplateDelete | test_delete_builtin_forbidden | 删除内置模板 | 403 |
| TP-06 | TestTemplatePreview | test_html_preview | HTML 预览 | 200 + HTML |
| TP-07 | TestTemplateRecommend | test_recommend | 模板推荐 | 200 + 推荐 |
| TP-08 | TestTemplateCompatibility | test_compatibility | 兼容性检查 | 200 |

#### 用户中心（3 用例）

**文件**：`tests/test_api_user.py`

| 用例 ID | 类 | 方法 | 场景 | 预期 |
|---------|-----|------|------|------|
| US-01 | TestUserHistory | test_history_unauthorized | 未登录查历史 | 401 |
| US-02 | TestUserLogic | test_record_usage | 记录使用 | 正常记录 |
| US-03 | TestUserLogic | test_get_user_orders | 获取订单 | 订单列表 |

### 2.4 单元测试（30 用例）

#### Writer-Reviewer（30 用例）

**文件**：`tests/test_writer_reviewer.py`

| 用例 ID | 类 | 方法 | 验证内容 |
|---------|-----|------|----------|
| WR-01 | TestAntiGravityProvider | test_provider_id | provider ID 正确 |
| WR-02 | TestAntiGravityProvider | test_provider_name | provider 名称正确 |
| WR-03 | TestAntiGravityProvider | test_available_models | 可用模型列表非空 |
| WR-04 | TestAntiGravityProvider | test_custom_base_url | 自定义 base URL |
| WR-05 | TestReviewPromptExists | test_review_prompt_exists | review prompt 文件存在 |
| WR-06 | TestReviewPromptExists | test_revise_prompt_exists | revise prompt 文件存在 |
| WR-07 | TestReviewPromptExists | test_review_prompt_has_placeholders | review prompt 包含占位符 |
| WR-08 | TestReviewPromptExists | test_revise_prompt_has_placeholders | revise prompt 包含占位符 |
| WR-09 | TestConfigDefaults | test_default_disabled | 默认关闭 review |
| WR-10 | TestConfigDefaults | test_max_iterations_default | 最大迭代次数默认值 |
| WR-11 | TestConfigDefaults | test_score_threshold_default | 分数阈值默认值 |
| WR-12 | TestConfigDefaults | test_min_diff_threshold_default | 最小差异阈值默认值 |
| WR-13 | TestExpertTeamV2ReviewLoop | test_reviewer_providers_empty_when_disabled | 关闭时 reviewer 为空 |
| WR-14 | TestExpertTeamV2ReviewLoop | test_rewrite_content_result_has_review_fields | 结果包含 review 字段 |
| WR-15 | TestExpertTeamV2ReviewLoop | test_aggregate_reviews_single_reviewer | 单 reviewer 聚合 |
| WR-16 | TestExpertTeamV2ReviewLoop | test_aggregate_reviews_converged_when_all_agree | 全部同意→收敛 |
| WR-17 | TestExpertTeamV2ReviewLoop | test_aggregate_reviews_not_converged_when_one_disagrees | 一人不同意→不收敛 |
| WR-18 | TestExpertTeamV2ReviewLoop | test_aggregate_reviews_empty_input | 空输入处理 |
| WR-19 | TestExpertTeamV2ReviewLoop | test_aggregate_reviews_dedup_revisions | 修订去重 |
| WR-20 | TestExpertTeamV2ReviewLoop | test_aggregate_reviews_average_scores | 平均分计算 |
| WR-21 | TestExpertTeamV2ReviewLoop | test_calculate_version_diff_identical | 相同版本→diff=0 |
| WR-22 | TestExpertTeamV2ReviewLoop | test_calculate_version_diff_completely_different | 完全不同→diff=1 |
| WR-23 | TestExpertTeamV2ReviewLoop | test_calculate_version_diff_minor_change | 小改动→0<diff<1 |
| WR-24 | TestExpertTeamV2ReviewLoop | test_calculate_version_diff_empty | 空版本处理 |
| WR-25 | TestReviewLoopConvergence | test_convergence_on_high_score | 高分→收敛 |
| WR-26 | TestReviewLoopConvergence | test_convergence_on_no_revisions | 无修订→收敛 |
| WR-27 | TestReviewLoopConvergence | test_convergence_on_all_converged | 全部收敛→停止 |
| WR-28 | TestReviewLoopConvergence | test_max_iterations_cap | 达到最大迭代→停止 |
| WR-29 | TestTemplatesRegression | test_builtin_templates_loadable | 内置模板可加载 |
| WR-30 | TestTemplatesRegression | test_builtin_template_ids | 内置模板 ID 正确 |

#### 阿里云连通性（5 用例）

**文件**：`tests/test_qwen_connectivity.py`

| 用例 ID | 方法 | 验证内容 |
|---------|------|----------|
| QW-01 | test_api_key | API key 可加载 |
| QW-02 | test_dns | DNS 解析正常 |
| QW-03 | test_tcp | TCP 连接正常 |
| QW-04 | test_https | HTTPS 握手正常 |
| QW-05 | test_model_call | 模型调用正常 |

### 2.5 基准测试（14 用例）

**数据目录**：`tests/benchmark/fixtures/case_01_tech_writer/`

#### 渲染完整性（3 用例）

**文件**：`tests/benchmark/test_render_integrity.py`

| 用例 ID | 方法 | 指标 | 阈值 |
|---------|------|------|------|
| BM-R01 | test_basic_info_fields_in_context | 基本信息（姓名、电话、邮箱等）完整 | 全部存在 |
| BM-R02 | test_work_tailored_coverage | 工作经历 tailored 字段覆盖率 | ≥80% |
| BM-R03 | test_project_tailored_coverage | 项目经历 tailored 字段覆盖率 | ≥80% |

#### 关键词覆盖率（3 用例）

**文件**：`tests/benchmark/test_keyword_coverage.py`

| 用例 ID | 方法 | 指标 | 阈值 |
|---------|------|------|------|
| BM-K01 | test_jd_keywords_in_ai_output | JD 关键词在 AI 输出中出现 | ≥60% |
| BM-K02 | test_tailored_content_length | 定制内容长度 | ≥50 词 |
| BM-K03 | test_no_keyword_loss_between_json_and_docx | JSON→DOCX 无关键词丢失 | 0 丢失 |

#### JD 对齐度（3 用例）

**文件**：`tests/benchmark/test_jd_alignment.py`

| 用例 ID | 方法 | 指标 |
|---------|------|------|
| BM-J01 | test_summary_uses_jd_position | 摘要包含 JD 中的职位名称 |
| BM-J02 | test_work_experience_contains_jd_keywords | 工作经历包含 JD 关键词 |
| BM-J03 | test_self_evaluation_aligned_with_jd | 自我评价与 JD 对齐 |

#### 忠实度（3 用例）

**文件**：`tests/benchmark/test_fidelity.py`

| 用例 ID | 方法 | 指标 |
|---------|------|------|
| BM-F01 | test_non_customized_fields_preserved | 非定制字段保持不变 |
| BM-F02 | test_work_experience_count_preserved | 工作经历条数一致 |
| BM-F03 | test_education_preserved | 教育背景完整保留 |

#### 端到端（2 用例）

**文件**：`tests/benchmark/test_e2e.py`

| 用例 ID | 方法 | 指标 |
|---------|------|------|
| BM-E01 | test_jinja_inserter_creates_tailored_variables | Jinja2 变量正确生成 |
| BM-E02 | test_post_process_splits_newlines | 换行符正确分割为段落 |

---

## 3. 覆盖缺口

> 缺口按实施难度分三批推进，详见[第 4 节 新增测试计划](#4-新增测试计划)。
> 以下只列出"缺什么"，不重复"怎么补"。

### 3.1 未覆盖的 API 端点

| 端点 | 方法 | 归属批次 | 说明 |
|------|------|----------|------|
| `/api/user_params` | GET/POST | 第二批 | 用户参数持久化（新增功能） |
| `/api/preview` | POST | 第二批 | 简历预览 |
| `/api/preview/tailored` | POST | 第二批 | 定制简历预览 |
| `/api/shutdown` | POST | 暂不测试 | 服务器关闭（低优先级） |
| `/api/status/<task_id>` | GET | 暂不测试 | 任务状态查询（低优先级） |

### 3.2 未覆盖的核心模块

| 模块 | 归属批次 | 说明 |
|------|----------|------|
| `core/resume_builder.py` | 第一批 | 表单→简历，纯数据转换 |
| `core/match_scorer.py` | 第一批 | 简历-JD 评分，纯规则计算 |
| `core/cache_manager.py` | 第一批 | 缓存读写过期 |
| `core/evidence_tracker.py` | 第二批 | 依据追踪，需 mock AI |
| `core/structure_detector.py` | 第二批 | 结构检测，需 fixture .docx |
| `core/config.py` | 第二批 | 配置管理 |
| `core/database.py` | 第二批 | 数据库 CRUD |
| `core/model_manager.py` | 第二批 | 模型管理，需 mock provider |
| `core/resume_parser.py` | 第三批 | 简历解析，多格式多降级 |
| `core/resume_generator.py` | 第三批 | 文档生成 |
| `core/template_processor.py` | 第三批 | 模板渲染 + fallback |
| `core/expert_team.py` | 第三批 | 五阶段管道，最复杂 |
| `core/jinja_inserter.py` | 第三批 | docx XML 操作，最难测 |
| `core/multi_model_manager.py` | 暂不测试 | 多模型管理（多模型工具专用） |
| `core/multi_expert_team.py` | 暂不测试 | 多模型专家团队（多模型工具专用） |

---

## 4. 新增测试计划

> 分三批实施，按依赖复杂度从低到高递进。详细策略见[测试方案文档 - 第 8 节](test-strategy.md#8-分批实施路线图)。

### 第一批：零依赖纯逻辑（3 个模块，~35 用例）

> 这些模块不依赖 AI、不依赖文件系统，纯数据转换/计算，写测试最快。

#### 4.1.1 简历构建测试

**目标文件**：`tests/test_resume_builder.py`
**被测模块**：`core/resume_builder.py`（298 行，无外部依赖）

| 用例 ID | 场景 | 输入 | 预期 |
|---------|------|------|------|
| RB-01 | 完整表单构建 | 含所有字段的表单数据 | 正常生成简历文本 |
| RB-02 | 缺少必填字段（姓名） | 无姓名的表单 | 提示缺少姓名 |
| RB-03 | 缺少必填字段（联系方式） | 无联系方式的表单 | 提示缺少联系方式 |
| RB-04 | 工作经历为空 | 无工作经历的表单 | 正常处理（跳过该节） |
| RB-05 | 教育经历为空 | 无教育经历的表单 | 正常处理 |
| RB-06 | 多段工作经历 | 3 段工作经历 | 按顺序输出 |
| RB-07 | build_structured 调用 | 完整表单 | 返回结构化 JSON |
| RB-08 | 特殊字符处理 | 包含特殊字符的输入 | 不崩溃，正确转义 |

#### 4.1.2 匹配评分测试

**目标文件**：`tests/test_match_scorer.py`
**被测模块**：`core/match_scorer.py`（444 行，无外部依赖）

| 用例 ID | 场景 | 预期 |
|---------|------|------|
| MS-01 | 完全匹配 | JD 要求与简历完全对应 | 高分 |
| MS-02 | 完全不匹配 | 简历与 JD 无关 | 低分 |
| MS-03 | 部分匹配 | 部分技能匹配 | 中等分数 |
| MS-04 | 学历要求检查 | JD 要求本科，简历为硕士 | 通过 |
| MS-05 | 学历要求不满足 | JD 要求硕士，简历为本科 | 扣分 |
| MS-06 | 工作年限检查 | JD 要求 3 年，简历 5 年 | 通过 |
| MS-07 | 工作年限不足 | JD 要求 5 年，简历 2 年 | 扣分 |
| MS-08 | 技能关键词匹配 | JD 列出的技能在简历中出现 | 计入匹配 |
| MS-09 | 空简历输入 | 空数据 | 返回 0 分，不崩溃 |
| MS-10 | calculate_match_score 便捷调用 | 简历 + JD | 返回带 level 和 summary 的结果 |

#### 4.1.3 缓存管理测试

**目标文件**：`tests/test_cache_manager.py`
**被测模块**：`core/cache_manager.py`（220 行，仅文件系统）

| 用例 ID | 场景 | 预期 |
|---------|------|------|
| CM-01 | 写入和读取 | set 后 get | 返回相同值 |
| CM-02 | 缓存未命中 | get 不存在的 key | 返回 None |
| CM-03 | 缓存过期 | set 后等待过期 | get 返回 None |
| CM-04 | 删除缓存 | set 后 delete | get 返回 None |
| CM-05 | 清空过期缓存 | 混合过期/未过期 | 只删除过期的 |
| CM-06 | 清空全部 | 多条缓存后 clear_all | get 全部返回 None |
| CM-07 | 缓存统计 | 多次操作后 | stats 正确反映命中/未命中 |
| CM-08 | 相同 key 覆盖 | set 同一 key 两次 | 后者覆盖前者 |

---

### 第二批：Mock 外部依赖（5 个模块，~50 用例）

> 这些模块需要 mock 文件库或 AI 调用，但逻辑本身是确定的。

#### 4.2.1 依据追踪测试

**目标文件**：`tests/test_evidence_tracker.py`
**被测模块**：`core/evidence_tracker.py`（391 行，mock `_ai_validate()`）

| 用例 ID | 场景 | 预期 |
|---------|------|------|
| ET-01 | 验证通过的内容 | 有明确来源的内容 | 通过 |
| ET-02 | 无来源的内容 | 缺少依据的内容 | 标记为可疑 |
| ET-03 | 可疑关键词检测 | 含"精通"、"精通各种"等词 | 触发警告 |
| ET-04 | 模糊匹配 | 原文与依据略有差异 | 仍能匹配（阈值内） |
| ET-05 | 整体验证 | 完整简历 + 完整依据 | 覆盖率 ≥90% |
| ET-06 | AI 验证失败 | mock AI 返回错误 | 降级到规则验证 |

#### 4.2.2 结构检测测试

**目标文件**：`tests/test_structure_detector.py`
**被测模块**：`core/structure_detector.py`（390 行，使用 fixture .docx）

| 用例 ID | 场景 | 输入 | 预期 |
|---------|------|------|------|
| SD-01 | 标准简历结构 | 标准格式 fixture .docx | 正确识别各节 |
| SD-02 | 姓名检测 | 含明确姓名行的文档 | 正确提取姓名 |
| SD-03 | 联系方式检测 | 含电话/邮箱的文档 | 正确提取联系方式 |
| SD-04 | 教育背景检测 | 含学历/学校信息 | 正确识别教育节 |
| SD-05 | 工作经历检测 | 含公司/职位信息 | 正确识别工作节 |
| SD-06 | 非标准结构 | 无明确标题的简历 | 合理猜测 |
| SD-07 | 置信度计算 | 标准简历 | confidence ≥0.7 |
| SD-08 | 空文档 | 空内容 | 返回空结构，不崩溃 |

#### 4.2.3 配置管理测试

**目标文件**：`tests/test_config.py`
**被测模块**：`core/config.py`（247 行，mock 环境变量）

| 用例 ID | 场景 | 预期 |
|---------|------|------|
| CF-01 | 默认配置加载 | 无环境变量 | 使用默认值 |
| CF-02 | 环境变量覆盖 | 设置 ZHIPU_API_KEY | 读取到设置的值 |
| CF-03 | 配置验证通过 | 合法配置 | validate() 返回 True |
| CF-04 | 配置验证失败 | 缺少必需配置 | validate() 返回错误 |
| CF-05 | get_model_for_task | 请求特定任务的模型 | 返回正确的模型名 |
| CF-06 | get_confidence_weights | 请求权重配置 | 返回权重字典 |
| CF-07 | 端口配置 | 检查端口常量 | SIMPLE_APP_PORT=5001 等 |

#### 4.2.4 数据库操作测试

**目标文件**：`tests/test_database.py`
**被测模块**：`core/database.py`（970 行，使用已有临时 DB fixture）

| 用例 ID | 场景 | 预期 |
|---------|------|------|
| DB-01 | 创建用户 | 合法邮箱/手机 | 返回 user_id |
| DB-02 | 创建用户重复邮箱 | 相同邮箱 | 抛出唯一约束错误 |
| DB-03 | 查询用户 | 按 email 查询 | 返回正确用户 |
| DB-04 | 查询不存在用户 | 不存在的 email | 返回 None |
| DB-05 | 创建任务 | 合法参数 | 返回 task_id |
| DB-06 | 更新任务状态 | task_id + 新状态 | 状态正确更新 |
| DB-07 | 保存历史 | user_id + 结果 | 正确保存 |
| DB-08 | 获取历史列表 | user_id | 返回列表，按时间倒序 |
| DB-09 | 创建订单 | user_id + 套餐 | 返回订单号 |
| DB-10 | 更新订单支付状态 | 订单号 + paid | 状态变为已支付 |
| DB-11 | 缓存分析结果 | key + JSON | 正确保存和读取 |
| DB-12 | 并发写入 | 同时创建多个用户 | 不冲突 |

#### 4.2.5 模型管理测试

**目标文件**：`tests/test_model_manager.py`
**被测模块**：`core/model_manager.py`（147 行，mock provider）

| 用例 ID | 场景 | 预期 |
|---------|------|------|
| MM-01 | 正常调用 | 有效消息 | 返回模型响应 |
| MM-02 | provider 不可用 | mock 抛出异常 | 正确处理错误 |
| MM-03 | 降级模型 | 主模型失败 | 切换到 fallback 模型 |
| MM-04 | is_available | 检查状态 | 返回布尔值 |
| MM-05 | get_stats | 多次调用后 | 返回正确的统计信息 |

---

### 第三批：重依赖复杂管道（4 个模块，~40 用例）

> 这些模块依赖深、管道长，需要精心构造测试数据。

#### 4.3.1 简历解析测试

**目标文件**：`tests/test_resume_parser.py`
**被测模块**：`core/resume_parser.py`（736 行，使用 fixture 文件）

| 用例 ID | 场景 | 输入 | 预期 |
|---------|------|------|------|
| RP-01 | 解析 TXT 简历 | 纯文本 fixture | 正确提取各字段 |
| RP-02 | 解析 PDF 简历 | PDF fixture | 正确提取文本 |
| RP-03 | 解析 Word 简历 | .docx fixture | 正确提取文本 |
| RP-04 | PDF 多级降级 | pdfplumber 失败 | 降级到 PyPDF2 |
| RP-05 | 空文件处理 | 空文件 | 友好错误提示 |
| RP-06 | 不支持的格式 | .exe 文件 | 返回错误 |
| RP-07 | 编码异常 | 非 UTF-8 文件 | 降级处理 |
| RP-08 | 置信度计算 | 标准简历 | confidence ≥0.7 |
| RP-09 | 基本信息提取 | 含姓名/电话/邮箱 | 正确提取 |
| RP-10 | 工作经历提取 | 多段工作经历 | 正确分段 |
| RP-11 | 教育背景提取 | 多段教育经历 | 正确分段 |

#### 4.3.2 简历生成测试

**目标文件**：`tests/test_resume_generator.py`
**被测模块**：`core/resume_generator.py`（459 行，检查输出文件）

| 用例 ID | 场景 | 预期 |
|---------|------|------|
| RG-01 | 生成 DOCX | 完整 AI 输出 JSON | 输出有效 .docx |
| RG-02 | 生成 PDF | 完整 AI 输出 JSON | 输出有效 PDF |
| RG-03 | 生成字节流 | 调用 generate_bytes | 返回非空字节 |
| RG-04 | AI 输出为空 | 空数据 | 友好错误 |
| RG-05 | 模板不存在 | 无效模板 ID | 回退到默认模板 |
| RG-06 | 基本信息写入 | 含姓名/电话/邮箱 | DOCX 中包含该信息 |
| RG-07 | 工作经历写入 | 多段工作经历 | DOCX 中按顺序包含 |
| RG-08 | 教育背景写入 | 多段教育 | DOCX 中包含 |

#### 4.3.3 模板处理测试

**目标文件**：`tests/test_template_processor.py`
**被测模块**：`core/template_processor.py`（683 行，使用 fixture 模板）

| 用例 ID | 场景 | 预期 |
|---------|------|------|
| TMP-01 | 预处理 Jinja2 标签 | 原始 .docx 模板 | 正确检测和转义已有 Jinja2 语法 |
| TMP-02 | 渲染模板 | fixture 模板 + context | 变量正确填充 |
| TMP-03 | 后处理换行 | 含 \n 的 tailored 内容 | 分割为独立段落 |
| TMP-04 | 空变量处理 | context 中缺少变量 | 优雅降级（保留占位符或清空） |
| TMP-05 | render_with_fallback | 渲染失败 | 回退到备选方案 |
| TMP-06 | render_by_id | 内置模板 ID | 正确找到并渲染 |
| TMP-07 | render_by_id 不存在 | 无效 ID | 返回错误 |
| TMP-08 | _build_context | AI 输出 JSON | 生成正确的 context 字典 |

#### 4.3.4 AI 专家团队测试（分层策略）

**目标文件**：`tests/test_expert_team.py`
**被测模块**：`core/expert_team.py`（2229 行，mock `model_manager.call()`）

> `expert_team.py` 是最大最复杂的模块，采用**分层测试**策略：
> - **A 层：单阶段测试** — mock AI 调用，逐阶段验证输入→输出
> - **B 层：管道集成** — 串联所有阶段，验证数据流转
> - **C 层：降级测试** — 模拟异常/超时，验证 fallback

**A 层：单阶段测试**

| 用例 ID | 阶段 | 场景 | 预期 |
|---------|------|------|------|
| ET-01 | parse_resume | 正常简历文本 | 返回结构化 JSON |
| ET-02 | parse_resume | 异常输入 | 友好错误 |
| ET-03 | decode_jd | 正常 JD 文本 | 返回职位/要求/关键词 |
| ET-04 | match_analysis | 简历 + JD | 返回匹配分析结果 |
| ET-05 | rewrite_content | 匹配分析 + 原始简历 | 返回定制内容 |
| ET-06 | quality_check | 定制内容 | 返回质量评分 |
| ET-07 | quality_check | 质量不达标内容 | 返回修订建议 |

**B 层：管道集成**

| 用例 ID | 场景 | 预期 |
|---------|------|------|
| ET-08 | 完整 tailor 流程 | 五阶段全部通过 | 返回完整定制结果 |
| ET-09 | 阶段间数据传递 | 验证各阶段输出→输入一致 | 数据无丢失 |
| ET-10 | Writer-Reviewer 闭环 | 开启 review 模式 | 至少 1 轮 review |

**C 层：降级测试**

| 用例 ID | 场景 | 预期 |
|---------|------|------|
| ET-11 | AI 超时 | mock 抛出 TimeoutError | 降级处理，返回部分结果 |
| ET-12 | AI 返回无效 JSON | mock 返回非 JSON | 解析错误处理 |
| ET-13 | AI 返回空内容 | mock 返回空字符串 | 友好错误 |
| ET-14 | 阶段失败继续 | 某阶段失败 | 后续阶段使用默认值继续 |

---

### 补充：新增 API 端点测试

**目标文件**：`tests/test_api_user_params.py`

| 用例 ID | 场景 | 预期 |
|---------|------|------|
| UP-01 | 未登录保存参数 | 401 |
| UP-02 | 保存参数成功 | 200 |
| UP-03 | 读取已保存参数 | 返回保存的数据 |
| UP-04 | 未保存时读取 | 返回默认值 |
| UP-05 | 更新已保存参数 | 覆盖旧值 |

---

## 5. 测试数据管理

### 5.1 Fixture 数据

| 位置 | 内容 | 用途 |
|------|------|------|
| `tests/conftest.py` | 临时 DB、Flask app | 所有 API 测试 |
| `tests/benchmark/conftest.py` | AI 输出、JD、原始简历 | 基准测试 |
| `tests/benchmark/fixtures/case_01_tech_writer/` | 真实测试数据 | 基准测试场景 |

### 5.2 数据目录规范

```
tests/benchmark/fixtures/
└── case_01_tech_writer/          # 场景目录
    ├── ai_output.json            # AI 生成的定制简历 JSON
    ├── jd_text.txt               # 职位描述文本
    └── original_resume.json      # 原始简历 JSON
```

新增场景时：
1. 创建 `case_02_<场景名>/` 目录
2. 放入对应的数据文件
3. 基准测试 fixture 会自动 `pytest.skip` 缺失数据

### 5.3 Mock 策略

| 依赖 | 策略 | 原因 |
|------|------|------|
| 数据库 | 临时 SQLite 文件 | 真实行为，无额外依赖 |
| AI API | mock / skip | 依赖外部服务，不稳定 |
| 邮件发送 | mock | 避免发送真实邮件 |
| 支付回调 | 模拟接口 | 支付宝/微信需要真实凭证 |
| 限流 | 测试环境禁用 | 避免测试被限流阻断 |

---

## 6. 执行指南

### 6.1 运行全部测试

```bash
# 方式一：便捷脚本
python tests/run_all.py

# 方式二：直接 pytest
pytest tests/ -v --tb=short
```

### 6.2 按层级运行

```bash
# 静态分析（秒级完成）
pytest tests/test_static_checks.py -v

# 前端结构检查
pytest tests/test_frontend.py -v

# API 集成测试
pytest tests/test_api_auth.py tests/test_api_health.py tests/test_api_payment.py \
       tests/test_api_quota.py tests/test_api_tailor.py tests/test_api_templates.py \
       tests/test_api_user.py -v

# 单元测试
pytest tests/test_writer_reviewer.py -v

# 基准测试（需要 fixture 数据）
pytest tests/benchmark/ -v
```

### 6.3 按关键词过滤

```bash
# 只跑认证相关
pytest tests/ -k "auth" -v

# 只跑模板相关
pytest tests/ -k "template" -v

# 只跑支付相关
pytest tests/ -k "payment" -v

# 排除基准测试
pytest tests/ -v --ignore=tests/benchmark/
```

### 6.4 运行单个文件

```bash
pytest tests/test_api_auth.py -v
pytest tests/test_static_checks.py -v
```

### 6.5 查看覆盖率

```bash
pip install pytest-cov
pytest tests/ --cov=core --cov=apps --cov-report=term-missing
```

### 6.6 预期结果

| 测试类型 | 预期时间 | 前提条件 |
|----------|---------|----------|
| 静态分析 | < 1 秒 | 无 |
| 前端结构 | < 1 秒 | 无 |
| API 集成 | < 5 秒 | 无（使用临时 DB） |
| 单元测试 | < 2 秒 | 无 |
| 基准测试 | < 2 秒 | fixture 数据文件存在 |
| 阿里云连通 | 5-10 秒 | 网络可达、API key 有效 |
| **全量** | **< 15 秒** | 同上 |

---

## 7. 版本记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-04-04 | v1.2 | 实施完成：新增 145 个测试用例（3 批次），总计 316 用例。新增文件：test_resume_builder(13), test_match_scorer(22), test_cache_manager(17), test_evidence_tracker(16), test_structure_detector(16), test_config(15), test_database(17), test_model_manager(11), test_resume_parser(4), test_resume_generator(5), test_template_processor(1), test_expert_team(11), test_api_user_params(4), test_resume_generator(3) |
| 2026-04-04 | v1.1 | 补充模块复杂度地图、分三批实施路线、~125 个新增用例规划 |
| 2026-04-04 | v1.0 | 初始版本，覆盖 171 个现有用例，识别 15 个覆盖缺口 |

---

*最后更新：2026-04-04*
