# AGENTS.md — 项目协作规则

> 给 AI 的说明：本文件是项目的长期规则。每次任务开始前请先读。
> 本文件以当前代码为准；如果事实不确定，先问用户，不要擅自猜。

---

## 项目概述
- 这个项目是一个独立的 K12 数学错题讲解助手，和之前的古诗词项目分开。
- 目标：围绕“录入错题 -> 自动归类 -> 对症讲解 -> 错题本复习 -> 学情分析 -> 相似题推荐”形成一个本地可运行的学习闭环。
- 当前形态：Streamlit 网页界面 + Python 后端模块 + SQLite 本地数据库 + DeepSeek API + Chroma 本地向量库 + 命令行测试脚本。

## 当前核心模块
- `mistake_db.py`：SQLite 数据库模块，负责建表、预置初中数学知识点、录入错题、查询错题、更新掌握状态、统计学情。
- `mistake_ai.py`：DeepSeek AI 模块，负责自动归类、生成对症讲解、生成学情报告。
- `mistake_recommender.py`：相似题推荐模块，负责把错题同步到 Chroma，并生成“同知识点 + 思路相近”两层推荐。
- `seed_similar_mistake_samples.py`：批量准备约 48 道测试错题，录入时走现有 DeepSeek 自动归类流程。
- `app.py`：Streamlit 网页入口，串联录入错题、讲解、错题本、学情分析和相似题推荐。
- `test_*.py`：脚本式测试，覆盖数据库、自动归类、AI 讲解、错题本/学情分析、相似题推荐。

## 技术栈
- 语言/界面：Python + Streamlit。
- 数据库：SQLite，本地文件默认是 `mistakes.db`。
- AI：DeepSeek API，通过 OpenAI SDK 兼容接口调用，模型当前为 `deepseek-v4-pro`。
- API key：只允许从系统环境变量 `DEEPSEEK_API_KEY` 读取。
- 向量库：ChromaDB 本地 `PersistentClient`，默认路径 `mistake_chroma_db/`。
- Embedding：`BAAI/bge-small-zh-v1.5`，通过 Chroma 内置 `SentenceTransformerEmbeddingFunction` 加载。
- 依赖版本：`openai==2.41.0`、`chromadb==1.5.9`、`sentence-transformers==2.7.0`、`streamlit==1.58.0`。

## 重要约定
- 不要把这个项目和古诗词 RAG 项目混在一起；当前项目目录是 `D:\k12_math_mistake_helper`。
- 未经用户确认，不要更换 DeepSeek 模型、Embedding 模型、向量库方案或数据库方案。
- Chroma 当前只允许本地 `PersistentClient` 方式；不得改成 HTTP server，不得开放 Chroma 网络端口。
- 运行时数据不进 git：`mistakes.db`、`mistake_chroma_db/`、`__pycache__/`、`.env`、密钥文件都必须忽略。
- 新增真实题库数据时，优先用脚本生成或导入，不要直接提交本地 SQLite 数据库文件。
- 批量脚本会调用 DeepSeek，涉及 API 成本；大批量运行前要提醒用户。
- 每段核心逻辑保持中文注释，方便 vibe coder 继续跟进。

## 安全红线
- 严禁把 API key、密码、token 等密钥硬编码进代码、文档、测试数据或可提交脚本。
- 严禁提交 `.env`、密钥文件、真实数据库、向量库、缓存目录。
- 所有 SQL 必须使用参数化查询，不要拼接用户输入。
- SQLite 连接必须开启外键约束，错题表的 `knowledge_point_id` 必须指向真实知识点。
- 用户输入的题目、答案、错因、图片路径等后续接入 UI 时必须做长度、类型、路径边界校验。
- 错误信息不要向最终用户暴露系统路径、堆栈、API 响应原文或密钥。
- 当前数据主要是本地测试数据；如果接入真实学生数据，必须补隐私说明、数据清理策略和第三方 API 数据流说明。
- 相似题向量库只保存本地错题文本和 metadata；如果未来使用真实学生数据，先做脱敏和授权设计。

## 质量与测试
- 改数据库 schema、AI prompt、归类逻辑、统计口径、推荐逻辑后，必须补或更新对应测试脚本。
- 关键验证命令：
  - `python -m compileall mistake_db.py mistake_ai.py mistake_recommender.py seed_similar_mistake_samples.py test_*.py`
  - `python test_mistake_db.py`
  - `python test_auto_classify.py`（需要 `DEEPSEEK_API_KEY`）
  - `python test_generate_explanation.py`（需要 `DEEPSEEK_API_KEY`）
  - `python test_mistake_book_analysis.py`（需要 `DEEPSEEK_API_KEY` 才生成 AI 报告）
  - `python test_similar_recommendations.py`（需要已安装 Chroma/embedding 依赖；有 key 时会走样例录入检查）
  - `python -m streamlit run app.py`（启动网页界面）
- Chroma 首次加载 embedding 模型可能较慢，这是正常现象。

## 文档维护
- 新增模块、改变运行方式、改变依赖版本后，同步更新 `PROGRESS.md`。
- 后续如果要对外展示项目，应补 `README.md`：项目简介、安装依赖、设置 `DEEPSEEK_API_KEY`、建库/预置知识点、运行测试、同步向量库。
- 发布版本前必须确认 `.gitignore` 生效，运行时文件没有进入暂存区。

## 工作流程
- 开始较大任务前，先简短说明计划；用户已经明确要求执行时，可以小步推进。
- 遇到不确定事实，先读当前代码和文件；仍不确定再问用户。
- 不要顺手重构无关代码。
- 完成后说明改了哪些文件、验证了什么、还有哪些风险或下一步。
