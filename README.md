<div align="center">

# ∑ &nbsp;K12 数学错题讲解助手

**把一个孩子的错题，沉淀成 · 可追踪 · 可统计 · 可检索 · 的纵向学习资产**

![version](https://img.shields.io/badge/version-v0.6.0-0f766e?style=flat-square)
![python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)
![storage](https://img.shields.io/badge/SQLite%20·%20Chroma-local--first-64748b?style=flat-square)
![ai](https://img.shields.io/badge/DeepSeek-AI-b7791f?style=flat-square)

一个 **本地运行** 的初中数学错题助手：录入错题后自动判断知识点，围绕学生<br>**具体错误** 生成讲解，并提供错题本、间隔复习、学情分析和相似题推荐。

<sub>[设计理念](#-设计理念价值到底在哪) · [功能](#-功能一览) · [快速开始](#-快速开始) · [路线图](#-路线图) · [安全](#-数据与安全)</sub>

</div>

```mermaid
flowchart LR
    A([📝 录入错题]) --> B([🎯 自动归类]) --> C([💡 对症讲解])
    C --> D([📚 错题本 · 间隔复习]) --> E([📊 学情分析]) --> F([🔁 相似题推荐])
    F -.回到复习闭环.-> A
    classDef s fill:#0f766e,stroke:#0b5f58,color:#fff,rx:6,ry:6;
    class A,B,C,D,E,F s;
```

---

## 🧭 设计理念：价值到底在哪

回答一个尖锐的问题——**数学是确定性的，DeepSeek 本来就会解题，那这个项目有什么用？**

<table>
<tr>
<td width="50%" valign="top">

### ❌ 大模型已免费给你的

不值得投入，聊天窗随时可替代：

- **数学知识本身** —— 知识点、解法、易错点，模型全会。
- **单道题的讲解** —— 粘三行进聊天窗一样能生成。

> `x = 3 或 4` 不管哪本教材都一样，**「生成答案 / 讲解」这层没有护城河**。

</td>
<td width="50%" valign="top">

### ✅ 只能靠本地沉淀的价值

大模型是**无状态**的，它不记得你的孩子：

- **纵向记忆** —— 3 个月错了哪些、哪里反复错、掌握到什么程度。
- **确定性统计** —— 掌握率、薄弱点，用 SQL 算又快又准。
- **对自有数据检索** —— 在你积累的错题里找下一题。

> 越靠近数据沉淀越有价值，越靠近讲题越可被替代。

</td>
</tr>
</table>

> **防御性价值 =「结构化的纵向错题状态 + 确定性学情统计 + 对自有数据的检索」。大模型只是零件，不是产品本身。**

**私有知识库才是护城河**：通用数学知识无壁垒；真正值得私有导入的是模型训练数据里没有 / 被平均掉的东西——**方法边界**（本版本进度只教到哪、允许用哪些方法）、**书写与评分规范**、**私有题库 / 本校月考卷 / 名师讲法**、**地区考纲**。知识点库的正确定位不是「存数学知识」，而是「**存私有约束 + 私有内容锚点**」。

---

## ✨ 功能一览

| 模块 | 能力 |
| :-- | :-- |
| 🏠 **概览首页** | 关键指标（有效错题 / 掌握率 / 今日复习 / 待复习）+ 快捷操作 + 薄弱知识点 Top5 + 最近录入 |
| 📝 **录入错题** | DeepSeek 自动归类或手动选知识点；**录入前查重**；库外题（小学/高中/非数学）提示超范围 |
| 💡 **对症讲解** | 围绕学生**具体错答和错因**生成四段式讲解（你错在哪里 / 一起想一想 / 正确解法 / 举一反三），结果缓存 |
| 📚 **错题本** | **今日复习**（遗忘曲线）/ 待复习 / 全部 / 按知识点·状态·年级；**搜索 + 分页**；状态更新、**编辑、删除** |
| ⏳ **间隔复习** | 按复习次数 + 掌握状态排「今日到期」清单（1→3→7→15→30 天），复习后自动进入下一间隔，纯本地不烧 API |
| 📊 **学情分析** | 本地统计薄弱点、掌握率、方向聚合；DeepSeek 生成家长/老师可读报告（只发聚合摘要，不发原题） |
| 🔁 **相似题推荐** | ① 同知识点直接巩固；② 跨知识点「思路相近」——用 **AI 提取的解题思路标签**做向量检索 |

---

## 🧱 技术栈

| 层 | 选型 | 说明 |
| :-- | :-- | :-- |
| 界面 | Python + Streamlit | 本地网页工作台，侧栏导航 + 仪表盘 |
| 数据库 | SQLite（`mistakes.db`） | 外键约束 + 参数化查询 |
| AI | DeepSeek（OpenAI SDK 兼容） | 归类、讲解、学情报告、解题思路标签 |
| 向量库 | ChromaDB `PersistentClient` | 本地落盘，不开网络端口 |
| Embedding | `BAAI/bge-small-zh-v1.5` | 中文语义向量化 |

---

## 🚀 快速开始

```powershell
# 1. 克隆 & 进入
git clone https://github.com/dosheda/math.git
cd math

# 2. 虚拟环境 + 依赖
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 3. 配置 DeepSeek API Key（只从系统环境变量读取）
$env:DEEPSEEK_API_KEY = "你的 DeepSeek API Key"

# 4. 启动网页 → 浏览器打开 http://localhost:8501
python -m streamlit run app.py
```

> 📖 网页端逐页操作说明见 **`使用手册.html`**。首次使用相似题推荐会加载 `BAAI/bge-small-zh-v1.5`，需要一点时间。
> 没有配置 `DEEPSEEK_API_KEY` 时，网页仍可浏览错题本和间隔复习，但 AI 相关功能不可用。

<details>
<summary>🧪 <b>命令行测试脚本（可选）</b></summary>

<br>

| 脚本 | 作用 | 需要 Key |
| :-- | :-- | :--: |
| `python test_mistake_db.py` | 建表、预置知识点、录入/查询链路 | — |
| `python test_auto_classify.py` | 自动归类（含超范围判断） | ✅ |
| `python test_generate_explanation.py` | 对症讲解生成 | ✅ |
| `python test_mistake_book_analysis.py` | 错题本 + 学情报告 | ✅ |
| `python seed_similar_mistake_samples.py` | 录入约 48 道相似题测试数据 | ✅ |
| `python test_similar_recommendations.py` | 同步向量库 + 两层推荐 | embedding |

批量脚本会调用 DeepSeek，涉及 API 成本，大批量运行前请留意。

</details>

---

## 📂 项目结构

```text
.
├── app.py                           # Streamlit 网页工作台（导航 + 仪表盘 + 各页面）
├── mistake_db.py                    # SQLite 数据库、统计、编辑/删除/查重、间隔复习调度
├── mistake_ai.py                    # DeepSeek 归类、讲解、学情报告、解题思路标签
├── mistake_recommender.py           # Chroma 向量同步与两层相似题推荐
├── seed_similar_mistake_samples.py  # 批量测试错题
├── test_*.py                        # 脚本式端到端测试
├── 使用手册.html                     # 网页端逐页使用手册
└── requirements.txt · AGENTS.md · PROGRESS.md
```

运行时本地生成（均不提交 git）：`mistakes.db`、`mistake_chroma_db/`。

---

## 🗺 路线图

按「模型替代不了 + 价值/成本」排序。价值随 **错题数量 × 时间跨度 × 学生人数** 增长。

| 方向 | 价值 | 成本 | 状态 |
| :-- | :--: | :--: | :-- |
| **AI 解题思路标签** 替代硬编码关键词 | 中高 | 低 | ✅ 已完成 |
| **遗忘曲线 / 间隔复习**（今日到期清单，纯本地不烧 API） | 高 | 低-中 | ✅ 已完成 |
| **掌握率趋势**（按时间留快照，看变化而非当前快照） | 中 | 中 | 🔜 计划中 |
| **多学生 / 班级维度**（从「一个孩子」到「一个老师带一批」） | 高 | 高 | 🔜 计划中 |
| **私有知识库导入**（教材版本 / 方法边界 / 私有题库 / 考纲） | 护城河 | 高 | 🌱 愿景 |

---

## 🔒 数据与安全

- `mistakes.db`、`mistake_chroma_db/`、`.env`、API key 一律不提交 git。
- API key 只从系统环境变量 `DEEPSEEK_API_KEY` 读取，不写进代码或文档。
- 所有 SQL 参数化；SQLite 开启外键约束。
- Chroma 仅本地 `PersistentClient`，不开放网络端口。
- 学情报告只发送**统计聚合摘要**，不发送每道题原文。
- 接入真实学生数据前，需补隐私说明、数据清空/备份策略和第三方 API 数据流说明。

## ⚠️ 当前限制

- Streamlit UI 已可用，但还不是完整产品化系统。
- 测试仍是脚本式，尚未迁移到 `pytest` / CI。
- 相似题推荐依赖 embedding 语义相似度 + AI 思路标签，后续可用人工标注评测集继续调优。
- DeepSeek 相关功能需要网络和 `DEEPSEEK_API_KEY`。
