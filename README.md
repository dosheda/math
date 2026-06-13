# K12 数学错题讲解助手

一个本地运行的 K12 数学错题助手：把错题录入后，自动判断知识点，生成针对学生具体错误的讲解，并提供错题本、学情分析和相似题推荐。

## 项目特点

- **完整错题闭环**：录入错题 -> 自动归类 -> 对症讲解 -> 错题本复习 -> 学情分析 -> 相似题推荐。
- **初中数学知识点库**：内置 24 个核心知识点，覆盖数与式、方程与不等式、函数、几何、统计概率等方向。
- **AI 自动归类**：调用 DeepSeek 判断题目所属知识点；小学题、高中题、非数学题或库外题会提示超范围。
- **针对错因讲解**：不是只给标准答案，而是围绕学生的错误答案和错误原因生成讲解。
- **两层相似题推荐**：同知识点题目直接推荐；跨知识点题目用 Chroma 向量检索按“解题思路相近”推荐。
- **本地优先**：SQLite 和 Chroma 都保存在本地目录，不启动数据库服务，不开放 Chroma 网络端口。

## 技术栈

| 模块 | 技术 | 说明 |
| --- | --- | --- |
| 语言 | Python | 当前项目以脚本和模块形式实现 |
| 数据库 | SQLite | 本地保存知识点和错题 |
| AI | DeepSeek API + OpenAI SDK | 自动归类、错题讲解、学情报告 |
| 向量库 | ChromaDB `PersistentClient` | 本地保存错题向量 |
| Embedding | `BAAI/bge-small-zh-v1.5` | 中文语义向量化 |
| 测试 | Python 脚本 | 当前是脚本式端到端测试 |

## 当前功能

### 1. 知识点库与错题库

`mistake_db.py` 负责数据库逻辑：

- 创建 `knowledge_points` 知识点表。
- 创建 `mistakes` 错题表。
- 用外键把错题关联到知识点。
- 预置初中数学核心知识点。
- 支持按知识点、掌握状态、年级、待复习状态查询错题。
- 支持统计每个知识点的错题数量和掌握情况。

### 2. DeepSeek 自动归类

`mistake_ai.py` 负责 AI 能力：

- 输入一道题，把题目和知识点清单发给 DeepSeek。
- 返回结构化结果：匹配的知识点 ID，或“超出支持范围 + 原因”。
- 录入错题时自动关联知识点。

### 3. 针对学生错因生成讲解

讲解会按固定结构输出：

- 【你错在哪里】
- 【一起想一想】
- 【正确解法】
- 【举一反三】

生成结果会缓存到错题表的 `ai_explanation` 字段，同一道题不用每次重新生成。

### 4. 错题本与学情分析

支持：

- 按知识点查看错题。
- 按掌握状态查看错题：`未掌握`、`复习中`、`已掌握`。
- 按年级查看错题。
- 查看待复习错题：`未掌握` + `复习中`。
- 统计薄弱知识点、整体掌握率、上级知识点方向。
- 调用 DeepSeek 生成给家长/老师看的学情报告。

统计口径：只统计数据库里真实录入的错题，每道错题算一次；同题同错答同知识点的重复测试记录默认只保留最新一条。

### 5. 相似题推荐

`mistake_recommender.py` 提供两层推荐：

- **同知识点推荐**：从 SQLite 查询同一知识点下的其他错题。
- **思路相近推荐**：把题目、知识点、错因、解析向量化后存入 Chroma，从其他知识点里找语义相近的题。

例如，一道一元二次方程因式分解题，可能推荐到：

- 同知识点下的其他一元二次方程题。
- 分式运算里需要因式分解的题。
- 二次函数里需要判别式或求零点的题。

## 项目结构

```text
.
├── mistake_db.py                    # SQLite 数据库与统计逻辑
├── mistake_ai.py                    # DeepSeek 自动归类、讲解、学情报告
├── mistake_recommender.py           # Chroma 向量库同步与相似题推荐
├── seed_similar_mistake_samples.py  # 批量生成相似题推荐测试错题
├── test_mistake_db.py               # 数据库链路测试
├── test_auto_classify.py            # 自动归类测试
├── test_generate_explanation.py     # AI 讲解测试
├── test_mistake_book_analysis.py    # 错题本与学情分析测试
├── test_similar_recommendations.py  # 相似题推荐测试
├── requirements.txt                 # 依赖版本
├── AGENTS.md                        # AI 协作规则
└── PROGRESS.md                      # 当前进展记录
```

运行后本地会生成：

```text
mistakes.db          # SQLite 数据库，本地运行时文件，不提交 git
mistake_chroma_db/   # Chroma 向量库，本地运行时目录，不提交 git
```

## 如何运行

### 1. 克隆项目

```powershell
git clone https://github.com/dosheda/math.git
cd math
```

### 2. 创建虚拟环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. 安装依赖

```powershell
pip install -r requirements.txt
```

首次使用 `BAAI/bge-small-zh-v1.5` 时会下载或加载本地模型缓存，可能需要一些时间。

### 4. 配置 DeepSeek API Key

PowerShell 临时设置：

```powershell
$env:DEEPSEEK_API_KEY = "你的 DeepSeek API Key"
```

也可以在 Windows 系统环境变量里长期设置 `DEEPSEEK_API_KEY`。

注意：不要把真实 API key 写入代码、README、`.env` 或任何会提交到 git 的文件。

### 5. 初始化数据库并跑基础测试

```powershell
python test_mistake_db.py
```

这个脚本会：

- 创建 SQLite 表。
- 预置初中数学知识点。
- 录入测试错题。
- 查询并打印结果。

### 6. 测试自动归类

```powershell
python test_auto_classify.py
```

这个脚本会测试：

- 初中数学题：应自动归类。
- 小学题：应提示超出支持范围。
- 非数学题：应提示超出支持范围。

### 7. 测试对症讲解

```powershell
python test_generate_explanation.py
```

这个脚本会读取测试错题，调用 DeepSeek 生成针对学生具体错因的讲解，并写回数据库缓存。

### 8. 测试错题本和学情报告

```powershell
python test_mistake_book_analysis.py
```

这个脚本会打印：

- 按知识点查询结果。
- 按掌握状态查询结果。
- 按年级查询结果。
- 待复习错题。
- 统计概览。
- AI 学情报告。

### 9. 准备相似题测试数据

```powershell
python seed_similar_mistake_samples.py
```

这个脚本内置 48 道初中数学测试错题，集中在“方程与不等式”和“函数”方向。

注意：它会调用 DeepSeek 自动归类，首次运行会产生 API 调用成本。重复运行时，已存在的题会自动跳过。

### 10. 测试相似题推荐

```powershell
python test_similar_recommendations.py
```

这个脚本会：

- 检查并准备测试错题。
- 把 SQLite 里的错题同步到 Chroma 本地向量库。
- 选一道一元二次方程错题。
- 打印同知识点推荐和跨知识点思路相近推荐。

## 常用代码示例

### 自动归类并录入错题

```python
import mistake_ai

result = mistake_ai.add_mistake_with_auto_classification(
    question_text="解方程：x^2 - 7x + 12 = 0。",
    grade="初三",
    question_type="解答",
    difficulty="基础",
    correct_answer="x = 3 或 x = 4",
    detailed_solution="因式分解得 (x - 3)(x - 4) = 0，所以 x = 3 或 x = 4。",
    student_answer="x = 3",
    error_reason="因式分解后只写了一个根，漏掉另一个因式对应的解。",
)

print(result)
```

### 生成并缓存错题讲解

```python
import mistake_ai

result = mistake_ai.generate_and_cache_mistake_explanation(mistake_id=1)
print(result["explanation"])
```

### 生成学情报告

```python
import mistake_ai

result = mistake_ai.generate_learning_report()
print(result["report"])
```

### 同步向量库并推荐相似题

```python
import mistake_recommender

mistake_recommender.sync_mistakes_to_vector_store()
result = mistake_recommender.recommend_similar_mistakes(mistake_id=1)

for item in result["recommendations"]:
    print(item["recommendation_type"], item["knowledge_point_name"], item["question_text"])
```

## 数据与安全说明

- `mistakes.db` 是本地 SQLite 数据库，不提交 git。
- `mistake_chroma_db/` 是本地 Chroma 向量库，不提交 git。
- `.env`、API key、密钥文件都不提交 git。
- 当前 Chroma 只使用本地 `PersistentClient`，不以 HTTP server 方式运行，也不开放网络端口。
- 如果后续接入真实学生数据，需要补充隐私说明、数据清空策略和第三方 API 数据流说明。

## 当前限制

- 目前没有 Web UI，主要通过 Python 脚本运行。
- 测试还是脚本式测试，尚未迁移到 `pytest`。
- DeepSeek 相关功能需要网络和 `DEEPSEEK_API_KEY`。
- 相似题推荐依赖 embedding 语义相似度和轻量“解题思路标签”，后续可以用人工标注评测集继续调优。

## 后续规划

- 增加 Streamlit 或 CLI 操作界面。
- 补正式测试框架和 CI。
- 增加错题导入、导出、备份和清空功能。
- 增加真实学生数据场景下的隐私与权限设计。
- 继续优化相似题推荐质量，让推荐更像老师布置的分层复习路径。
