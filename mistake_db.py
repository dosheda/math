"""
K12 数学错题讲解助手 —— SQLite 数据库模块
========================================

这个文件只负责“数据怎么存、怎么查”，暂时不做网页、不接 AI。

数据库文件：
  mistakes.db
  和本文件放在同一个项目目录下。

两张核心表：
  1. knowledge_points：知识点库
  2. mistakes：错题表

说明：
  - 代码里的列名用英文，方便 Python 和 SQL 编写。
  - 每个字段旁边都有中文注释，对应你设计的中文业务字段。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


# 数据库文件固定放在项目目录下。
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "mistakes.db"


# 掌握状态：后面 UI 可以做成下拉框。
VALID_MASTERY_STATUSES = {"未掌握", "复习中", "已掌握"}


def now_text() -> str:
    """返回当前时间字符串，统一用于录入时间、最后复习时间。"""
    return datetime.now().isoformat(timespec="seconds")


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """把 SQLite 查询结果转换成普通 dict，方便打印和后续给前端使用。"""
    return dict(row)


def get_connection() -> sqlite3.Connection:
    """
    获取数据库连接。

    关键点：
      - row_factory 让查询结果可以用字段名读取。
      - PRAGMA foreign_keys = ON 开启外键约束。

    SQLite 默认不开外键，所以每次连接都要打开一次。
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_tables() -> bool:
    """
    建表。

    如果表已经存在，CREATE TABLE IF NOT EXISTS 不会重复创建，也不会清空数据。
    返回 True 表示成功，False 表示失败。
    """
    try:
        with get_connection() as conn:
            # 表一：知识点库 knowledge_points
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,      -- 知识点ID：主键
                    name TEXT NOT NULL,                        -- 名称：如“一元二次方程的解法”
                    subject TEXT NOT NULL DEFAULT '数学',       -- 学科：当前固定为“数学”
                    grade TEXT NOT NULL,                       -- 年级：如“初二”
                    chapter TEXT NOT NULL,                     -- 所属章节：如“二次方程”
                    parent_id INTEGER,                         -- 上级知识点ID：指向本表自己，可为空
                    description TEXT NOT NULL,                 -- 知识点描述：这个知识点讲什么
                    common_mistakes TEXT NOT NULL,             -- 常见易错点：学生容易错在哪里
                    created_at TEXT NOT NULL,                  -- 创建时间
                    UNIQUE(name, subject, grade, chapter),
                    FOREIGN KEY(parent_id)
                        REFERENCES knowledge_points(id)
                        ON UPDATE CASCADE
                        ON DELETE SET NULL
                )
                """
            )

            # 表二：错题 mistakes
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mistakes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,      -- 错题ID：主键
                    question_text TEXT NOT NULL,               -- 题目内容：文字
                    image_path TEXT,                           -- 题目图片路径：可选，以后拍照搜题用
                    subject TEXT NOT NULL DEFAULT '数学',       -- 学科：当前固定为“数学”
                    grade TEXT NOT NULL,                       -- 年级：如“初二”
                    question_type TEXT NOT NULL,               -- 题型：选择/填空/解答
                    difficulty TEXT NOT NULL,                  -- 难度：简单/中等/困难等
                    knowledge_point_id INTEGER NOT NULL,       -- 知识点ID：外键，关联知识点库
                    correct_answer TEXT NOT NULL,              -- 正确答案
                    detailed_solution TEXT NOT NULL,           -- 详细解析
                    student_answer TEXT NOT NULL,              -- 学生的错误答案
                    error_reason TEXT,                         -- 学生的错误原因：可选
                    ai_explanation TEXT,                       -- AI生成的讲解：可缓存，可为空
                    reasoning_tags TEXT,                       -- AI提取的解题思路/能力标签(JSON数组)，供跨知识点相似题检索
                    mastery_status TEXT NOT NULL DEFAULT '未掌握', -- 掌握状态
                    review_count INTEGER NOT NULL DEFAULT 0,   -- 复习次数
                    last_reviewed_at TEXT,                     -- 最后复习时间：可为空
                    created_at TEXT NOT NULL,                  -- 录入时间
                    FOREIGN KEY(knowledge_point_id)
                        REFERENCES knowledge_points(id)
                        ON UPDATE CASCADE
                        ON DELETE RESTRICT,
                    CHECK(mastery_status IN ('未掌握', '复习中', '已掌握')),
                    CHECK(review_count >= 0)
                )
                """
            )

            # 常用查询索引：让“按知识点查错题”和“按掌握状态查错题”更快。
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_mistakes_knowledge_point_id
                ON mistakes(knowledge_point_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_mistakes_mastery_status
                ON mistakes(mastery_status)
                """
            )

            # 轻量迁移：老库（已存在的 mistakes 表）补齐后加的列。
            existing_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(mistakes)").fetchall()
            }
            if "reasoning_tags" not in existing_columns:
                conn.execute("ALTER TABLE mistakes ADD COLUMN reasoning_tags TEXT")

        return True
    except sqlite3.Error as exc:
        print(f"[数据库错误] 建表失败：{exc}")
        return False


def add_knowledge_point(
    name: str,
    grade: str,
    chapter: str,
    description: str,
    common_mistakes: str,
    subject: str = "数学",
    parent_id: int | None = None,
) -> int | None:
    """
    往知识点库里新增一个知识点。

    如果同名、同学科、同年级、同章节的知识点已经存在，就返回已有 ID。
    这样反复运行预置脚本也不会插入重复知识点。
    """
    try:
        with get_connection() as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO knowledge_points (
                        name, subject, grade, chapter, parent_id,
                        description, common_mistakes, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        subject,
                        grade,
                        chapter,
                        parent_id,
                        description,
                        common_mistakes,
                        now_text(),
                    ),
                )
                return int(cursor.lastrowid)
            except sqlite3.IntegrityError:
                row = conn.execute(
                    """
                    SELECT id FROM knowledge_points
                    WHERE name = ? AND subject = ? AND grade = ? AND chapter = ?
                    """,
                    (name, subject, grade, chapter),
                ).fetchone()
                return int(row["id"]) if row else None
    except sqlite3.Error as exc:
        print(f"[数据库错误] 新增知识点失败：{exc}")
        return None


def get_knowledge_point_id(name: str, grade: str | None = None) -> int | None:
    """按知识点名称查 ID。grade 可选，用来避免同名知识点跨年级混淆。"""
    try:
        with get_connection() as conn:
            if grade:
                row = conn.execute(
                    "SELECT id FROM knowledge_points WHERE name = ? AND grade = ?",
                    (name, grade),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT id FROM knowledge_points WHERE name = ?",
                    (name,),
                ).fetchone()
            return int(row["id"]) if row else None
    except sqlite3.Error as exc:
        print(f"[数据库错误] 查询知识点ID失败：{exc}")
        return None


def list_knowledge_points() -> list[dict[str, Any]]:
    """
    列出知识点库里的所有知识点。

    这个函数主要给“AI 自动归类”使用：
      - AI 需要看到每个知识点的 ID、名称、描述，才能判断题目应该归到哪里。
      - 同时带上 parent_name，方便 AI 理解层级关系。
    """
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    kp.id,
                    kp.name,
                    kp.subject,
                    kp.grade,
                    kp.chapter,
                    kp.parent_id,
                    parent.name AS parent_name,
                    kp.description,
                    kp.common_mistakes
                FROM knowledge_points kp
                LEFT JOIN knowledge_points parent ON parent.id = kp.parent_id
                ORDER BY kp.id
                """
            ).fetchall()
            return [row_to_dict(row) for row in rows]
    except sqlite3.Error as exc:
        print(f"[数据库错误] 查询知识点清单失败：{exc}")
        return []


def seed_core_knowledge_points() -> dict[str, int]:
    """
    预置一批初中数学核心知识点。

    返回值：
      {知识点名称: 知识点ID}

    设计思路：
      - 先插入“章节/大类”节点。
      - 再插入具体知识点，并用 parent_id 指向上级节点。
      - parent_id 就是你要的“层级关系”。
    """
    if not create_tables():
        return {}

    result: dict[str, int] = {}

    def add(
        name: str,
        grade: str,
        chapter: str,
        description: str,
        common_mistakes: str,
        parent_name: str | None = None,
    ) -> int | None:
        parent_id = result.get(parent_name or "")
        new_id = add_knowledge_point(
            name=name,
            grade=grade,
            chapter=chapter,
            parent_id=parent_id,
            description=description,
            common_mistakes=common_mistakes,
        )
        if new_id is not None:
            result[name] = new_id
        return new_id

    # 章节/大类节点
    add(
        "数与式",
        "初一",
        "代数基础",
        "研究数、代数式、整式、分式等基本代数对象。",
        "符号看错、运算顺序混乱、去括号和合并同类项出错。",
    )
    add(
        "方程与不等式",
        "初一",
        "方程与不等式",
        "用等式或不等式表示数量关系，并通过变形求解。",
        "移项变号、去分母、检验解、解集表示容易出错。",
    )
    add(
        "函数",
        "初二",
        "函数基础",
        "研究变量之间的对应关系，用图像、表格、解析式表达变化规律。",
        "看不懂自变量和因变量，图像与解析式互相转化困难。",
    )
    add(
        "几何图形",
        "初一",
        "几何基础",
        "研究点、线、角、三角形、四边形、圆等图形的性质。",
        "图形条件漏看，辅助线不会作，证明步骤跳步。",
    )
    add(
        "统计与概率",
        "初一",
        "统计与概率",
        "用数据描述现实问题，并用概率刻画随机事件可能性。",
        "平均数和中位数混淆，概率分母选错，忽略等可能条件。",
    )

    # 数与式
    add(
        "有理数运算",
        "初一",
        "有理数",
        "掌握正负数、绝对值、有理数加减乘除和乘方。",
        "负号处理错误，乘方和负数括号混淆，运算顺序出错。",
        "数与式",
    )
    add(
        "整式的加减",
        "初一",
        "整式",
        "理解单项式、多项式、同类项，并会合并同类项和去括号。",
        "同类项判断错，去括号漏乘负号，合并系数时符号出错。",
        "数与式",
    )
    add(
        "因式分解",
        "初二",
        "整式乘法与因式分解",
        "把多项式分解成几个整式乘积，常用提公因式和公式法。",
        "公因式提不全，平方差公式和完全平方公式混用，分解不彻底。",
        "数与式",
    )
    add(
        "分式运算",
        "初二",
        "分式",
        "掌握分式的约分、通分、加减乘除以及分式方程基础。",
        "忽略分母不为0，通分漏乘，约分把加减项直接约掉。",
        "数与式",
    )
    add(
        "二次根式",
        "初二",
        "二次根式",
        "理解二次根式的意义、性质、化简和简单运算。",
        "忽略被开方数非负，根号化简不彻底，合并非同类根式。",
        "数与式",
    )

    # 方程与不等式
    add(
        "一元一次方程",
        "初一",
        "一元一次方程",
        "用方程表示简单数量关系，并通过移项、合并、系数化1求解。",
        "移项忘记变号，去括号漏乘，最后没有检查是否符合题意。",
        "方程与不等式",
    )
    add(
        "二元一次方程组",
        "初一",
        "二元一次方程组",
        "掌握代入消元和加减消元，解决两个未知数的问题。",
        "消元方向选错，等式两边没有同时变形，应用题设未知数不清。",
        "方程与不等式",
    )
    add(
        "一元一次不等式",
        "初一",
        "不等式与不等式组",
        "掌握不等式基本性质、解集表示和数轴表示。",
        "两边乘除负数时忘记改变不等号方向，区间端点开闭混淆。",
        "方程与不等式",
    )
    add(
        "一元二次方程的解法",
        "初三",
        "一元二次方程",
        "掌握直接开平方法、配方法、公式法、因式分解法解一元二次方程。",
        "漏掉一个根，判别式算错，公式中的负号和根号位置写错。",
        "方程与不等式",
    )

    # 函数
    add(
        "一次函数图像与性质",
        "初二",
        "一次函数",
        "理解一次函数 y=kx+b 的图像、斜率、截距和增减性。",
        "k 和 b 的作用混淆，图像经过象限判断错，读图时横纵坐标看反。",
        "函数",
    )
    add(
        "反比例函数",
        "初二",
        "反比例函数",
        "理解 y=k/x 的图像、比例系数 k 与象限、增减性的关系。",
        "忽略 x 不能为0，k 的正负与象限关系记反，把双曲线画成直线。",
        "函数",
    )
    add(
        "二次函数图像与性质",
        "初三",
        "二次函数",
        "理解抛物线开口、顶点、对称轴、最值以及解析式变换。",
        "顶点公式记错，对称轴符号写反，平移方向和正负号混淆。",
        "函数",
    )

    # 几何
    add(
        "相交线与平行线",
        "初一",
        "相交线与平行线",
        "掌握对顶角、同位角、内错角、同旁内角和平行线判定性质。",
        "角的对应关系找错，把判定和性质混用，图中隐藏平行条件漏看。",
        "几何图形",
    )
    add(
        "三角形全等",
        "初二",
        "三角形",
        "掌握 SSS、SAS、ASA、AAS、HL 等全等判定方法。",
        "SSA 误当成判定条件，对应边角写错，证明顺序不完整。",
        "几何图形",
    )
    add(
        "勾股定理",
        "初二",
        "直角三角形",
        "在直角三角形中使用 a²+b²=c² 求边长或判断直角。",
        "斜边找错，平方和开方漏步骤，非直角三角形直接套公式。",
        "几何图形",
    )
    add(
        "平行四边形性质与判定",
        "初二",
        "四边形",
        "掌握平行四边形的边、角、对角线性质以及常见判定方法。",
        "性质和判定混淆，只证明一组对边平行就下结论，条件不充分。",
        "几何图形",
    )
    add(
        "圆的基本性质",
        "初三",
        "圆",
        "掌握半径、弦、弧、圆周角、切线等基本性质。",
        "圆周角和圆心角关系用错，切线垂直半径条件漏写，辅助线不会连半径。",
        "几何图形",
    )

    # 统计与概率
    add(
        "数据的平均数中位数众数",
        "初一",
        "数据的收集与整理",
        "理解平均数、中位数、众数的意义，并能根据数据选择合适指标。",
        "中位数排序后才找，平均数受极端值影响，众数可能不唯一。",
        "统计与概率",
    )
    add(
        "简单概率",
        "初二",
        "概率初步",
        "理解等可能事件概率，能计算简单随机事件的概率。",
        "样本空间列不全，分子分母选错，把非等可能事件当成等可能。",
        "统计与概率",
    )

    return result


def add_mistake(
    question_text: str,
    grade: str,
    question_type: str,
    difficulty: str,
    knowledge_point_id: int,
    correct_answer: str,
    detailed_solution: str,
    student_answer: str,
    image_path: str | None = None,
    subject: str = "数学",
    error_reason: str | None = None,
    ai_explanation: str | None = None,
    mastery_status: str = "未掌握",
) -> int | None:
    """
    录入一道错题。

    核心字段是 knowledge_point_id：
      它是外键，必须指向 knowledge_points 表中真实存在的知识点。
      如果传了不存在的 ID，SQLite 会拒绝插入，保证数据一致。
    """
    if mastery_status not in VALID_MASTERY_STATUSES:
        print(f"[输入错误] 掌握状态不合法：{mastery_status}")
        return None

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO mistakes (
                    question_text, image_path, subject, grade,
                    question_type, difficulty, knowledge_point_id,
                    correct_answer, detailed_solution, student_answer,
                    error_reason, ai_explanation, mastery_status,
                    review_count, last_reviewed_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?)
                """,
                (
                    question_text,
                    image_path,
                    subject,
                    grade,
                    question_type,
                    difficulty,
                    knowledge_point_id,
                    correct_answer,
                    detailed_solution,
                    student_answer,
                    error_reason,
                    ai_explanation,
                    mastery_status,
                    now_text(),
                ),
            )
            return int(cursor.lastrowid)
    except sqlite3.IntegrityError as exc:
        print(f"[数据库错误] 录入错题失败，可能是知识点ID不存在或字段不合法：{exc}")
        return None
    except sqlite3.Error as exc:
        print(f"[数据库错误] 录入错题失败：{exc}")
        return None


def get_mistakes_by_knowledge_point(knowledge_point_id: int) -> list[dict[str, Any]]:
    """按知识点ID查询错题。"""
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    m.*,
                    kp.name AS knowledge_point_name,
                    kp.chapter AS knowledge_point_chapter
                FROM mistakes m
                JOIN knowledge_points kp ON kp.id = m.knowledge_point_id
                WHERE m.knowledge_point_id = ?
                ORDER BY m.created_at DESC, m.id DESC
                """,
                (knowledge_point_id,),
            ).fetchall()
            return [row_to_dict(row) for row in rows]
    except sqlite3.Error as exc:
        print(f"[数据库错误] 按知识点查询错题失败：{exc}")
        return []


def get_mistakes_by_mastery_status(mastery_status: str) -> list[dict[str, Any]]:
    """按掌握状态查询错题，如：未掌握/复习中/已掌握。"""
    if mastery_status not in VALID_MASTERY_STATUSES:
        print(f"[输入错误] 掌握状态不合法：{mastery_status}")
        return []

    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    m.*,
                    kp.name AS knowledge_point_name,
                    kp.chapter AS knowledge_point_chapter
                FROM mistakes m
                JOIN knowledge_points kp ON kp.id = m.knowledge_point_id
                WHERE m.mastery_status = ?
                ORDER BY m.created_at DESC, m.id DESC
                """,
                (mastery_status,),
            ).fetchall()
            return [row_to_dict(row) for row in rows]
    except sqlite3.Error as exc:
        print(f"[数据库错误] 按掌握状态查询错题失败：{exc}")
        return []


def get_mistakes_by_grade(grade: str) -> list[dict[str, Any]]:
    """
    按年级查询错题。

    这是“错题本”的一个常用视图：
      比如只看初二错题，方便按当前学段复习。
    """
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    m.*,
                    kp.name AS knowledge_point_name,
                    kp.chapter AS knowledge_point_chapter
                FROM mistakes m
                JOIN knowledge_points kp ON kp.id = m.knowledge_point_id
                WHERE m.grade = ?
                ORDER BY m.created_at DESC, m.id DESC
                """,
                (grade,),
            ).fetchall()
            return [row_to_dict(row) for row in rows]
    except sqlite3.Error as exc:
        print(f"[数据库错误] 按年级查询错题失败：{exc}")
        return []


def get_pending_review_mistakes(deduplicate: bool = True) -> list[dict[str, Any]]:
    """
    待复习视图。

    规则：
      - “未掌握”和“复习中”的错题，都是现在最该复习的。
      - “已掌握”的题暂时不放进待复习列表。
      - 默认按同题同错答同知识点去重，避免测试重复录入影响复习清单。
    """
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    m.*,
                    kp.name AS knowledge_point_name,
                    kp.chapter AS knowledge_point_chapter
                FROM mistakes m
                JOIN knowledge_points kp ON kp.id = m.knowledge_point_id
                WHERE m.mastery_status IN ('未掌握', '复习中')
                ORDER BY
                    CASE m.mastery_status
                        WHEN '未掌握' THEN 0
                        WHEN '复习中' THEN 1
                        ELSE 2
                    END,
                    m.last_reviewed_at ASC,
                    m.created_at DESC,
                    m.id DESC
                """
            ).fetchall()
            mistakes = [row_to_dict(row) for row in rows]
            if deduplicate:
                mistakes, _duplicate_count = deduplicate_mistakes(mistakes)
            return mistakes
    except sqlite3.Error as exc:
        print(f"[数据库错误] 查询待复习错题失败：{exc}")
        return []


def get_all_mistakes_with_knowledge() -> list[dict[str, Any]]:
    """
    查询所有错题，并带上知识点信息。

    这个函数主要给“统计概览”和“学情分析”使用。
    """
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    m.*,
                    kp.name AS knowledge_point_name,
                    kp.description AS knowledge_point_description,
                    kp.common_mistakes AS knowledge_point_common_mistakes,
                    kp.chapter AS knowledge_point_chapter,
                    kp.parent_id AS knowledge_point_parent_id,
                    parent.name AS parent_knowledge_point_name
                FROM mistakes m
                JOIN knowledge_points kp ON kp.id = m.knowledge_point_id
                LEFT JOIN knowledge_points parent ON parent.id = kp.parent_id
                ORDER BY m.id DESC
                """
            ).fetchall()
            return [row_to_dict(row) for row in rows]
    except sqlite3.Error as exc:
        print(f"[数据库错误] 查询全部错题失败：{exc}")
        return []


def update_mistake_mastery(
    mistake_id: int,
    mastery_status: str,
    increase_review_count: bool = True,
) -> bool:
    """
    更新错题掌握状态和复习次数。

    参数：
      mistake_id：错题ID。
      mastery_status：新的掌握状态。
      increase_review_count：是否复习次数 +1。

    典型用法：
      学生复习一次后，把状态从“未掌握”改成“复习中”，复习次数自动 +1。
    """
    if mastery_status not in VALID_MASTERY_STATUSES:
        print(f"[输入错误] 掌握状态不合法：{mastery_status}")
        return False

    try:
        with get_connection() as conn:
            if increase_review_count:
                cursor = conn.execute(
                    """
                    UPDATE mistakes
                    SET mastery_status = ?,
                        review_count = review_count + 1,
                        last_reviewed_at = ?
                    WHERE id = ?
                    """,
                    (mastery_status, now_text(), mistake_id),
                )
            else:
                cursor = conn.execute(
                    """
                    UPDATE mistakes
                    SET mastery_status = ?
                    WHERE id = ?
                    """,
                    (mastery_status, mistake_id),
                )
            if cursor.rowcount == 0:
                print(f"[提示] 没找到错题ID：{mistake_id}")
                return False
            return True
    except sqlite3.Error as exc:
        print(f"[数据库错误] 更新错题掌握状态失败：{exc}")
        return False


def count_mistakes_by_knowledge_point() -> list[dict[str, Any]]:
    """统计每个知识点下面有多少道错题。"""
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    kp.id AS knowledge_point_id,
                    kp.name AS knowledge_point_name,
                    kp.grade,
                    kp.chapter,
                    COUNT(m.id) AS mistake_count
                FROM knowledge_points kp
                LEFT JOIN mistakes m ON m.knowledge_point_id = kp.id
                GROUP BY kp.id
                ORDER BY mistake_count DESC, kp.grade, kp.chapter, kp.id
                """
            ).fetchall()
            return [row_to_dict(row) for row in rows]
    except sqlite3.Error as exc:
        print(f"[数据库错误] 统计知识点错题数失败：{exc}")
        return []


def get_mistake_detail(mistake_id: int) -> dict[str, Any] | None:
    """
    查询一道错题的完整信息。

    为什么要单独写这个函数：
      生成 AI 讲解时，不只需要错题表里的题目、错误答案、解析；
      还需要知识点库里的“名称、描述、常见易错点”。

    返回结果里会额外带上：
      - knowledge_point_name：知识点名称
      - knowledge_point_description：知识点描述
      - knowledge_point_common_mistakes：知识点常见易错点
    """
    try:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    m.*,
                    kp.name AS knowledge_point_name,
                    kp.description AS knowledge_point_description,
                    kp.common_mistakes AS knowledge_point_common_mistakes,
                    kp.chapter AS knowledge_point_chapter
                FROM mistakes m
                JOIN knowledge_points kp ON kp.id = m.knowledge_point_id
                WHERE m.id = ?
                """,
                (mistake_id,),
            ).fetchone()
            return row_to_dict(row) if row else None
    except sqlite3.Error as exc:
        print(f"[数据库错误] 查询错题详情失败：{exc}")
        return None


def update_mistake_ai_explanation(mistake_id: int, ai_explanation: str) -> bool:
    """
    把 AI 生成的讲解写回错题表。

    这样同一道题下次再看时，可以直接读 ai_explanation 缓存，
    不需要每次都重新调用 DeepSeek。
    """
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE mistakes
                SET ai_explanation = ?
                WHERE id = ?
                """,
                (ai_explanation, mistake_id),
            )
            if cursor.rowcount == 0:
                print(f"[提示] 没找到错题ID：{mistake_id}")
                return False
            return True
    except sqlite3.Error as exc:
        print(f"[数据库错误] 保存 AI 讲解失败：{exc}")
        return False


def _normalize_for_stats(value: str | None) -> str:
    """统计去重用：去掉多余空白，避免同一道题因为换行/空格不同被重复计数。"""
    return " ".join(str(value or "").split())


def _mistake_dedup_key(mistake: dict[str, Any]) -> tuple:
    """
    生成错题去重 key。

    当前口径：
      同一个知识点下，题目内容相同、学生错误答案相同，就认为是同一道错题的重复测试记录。
    """
    return (
        int(mistake.get("knowledge_point_id") or 0),
        _normalize_for_stats(mistake.get("question_text")),
        _normalize_for_stats(mistake.get("student_answer")),
    )


def deduplicate_mistakes(mistakes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """
    对错题列表去重。

    数据库里可能因为测试脚本多次运行，出现同一道题重复录入。
    为了让学情分析不被测试数据放大，默认保留 ID 最新的一条。
    """
    seen = set()
    unique: list[dict[str, Any]] = []
    duplicate_count = 0

    # get_all_mistakes_with_knowledge() 默认按 id desc 排序，所以先遇到的是最新记录。
    for mistake in mistakes:
        key = _mistake_dedup_key(mistake)
        if key in seen:
            duplicate_count += 1
            continue
        seen.add(key)
        unique.append(mistake)

    return unique, duplicate_count


def build_learning_overview(
    deduplicate: bool = True,
    weakest_limit: int = 5,
) -> dict[str, Any]:
    """
    生成深度学情统计概览。

    统计口径：
      - 只统计数据库里真实录入的错题。
      - 每道错题算一次。
      - 如果 deduplicate=True，同题同错答同知识点的重复测试记录只算最新一条。

    返回内容：
      - 总错题数 / 去重后错题数 / 重复记录数
      - 掌握状态分布
      - 整体掌握率
      - 每个知识点的错题数和掌握情况
      - 最薄弱知识点
      - 按上级知识点聚合的大方向薄弱情况
    """
    try:
        create_tables()
        all_mistakes = get_all_mistakes_with_knowledge()
        total_records = len(all_mistakes)

        if deduplicate:
            mistakes, duplicate_records_ignored = deduplicate_mistakes(all_mistakes)
        else:
            mistakes = all_mistakes
            duplicate_records_ignored = 0

        total_mistakes = len(mistakes)
        status_counts = {status: 0 for status in VALID_MASTERY_STATUSES}
        for mistake in mistakes:
            status = mistake.get("mastery_status") or "未掌握"
            if status not in status_counts:
                status_counts[status] = 0
            status_counts[status] += 1

        mastered_count = status_counts.get("已掌握", 0)
        mastery_rate = round(mastered_count / total_mistakes * 100, 1) if total_mistakes else 0.0

        # 先把全部知识点放进统计表，保证 0 错题的知识点也能显示。
        knowledge_points = list_knowledge_points()
        kp_stats: dict[int, dict[str, Any]] = {}
        for kp in knowledge_points:
            kp_id = int(kp["id"])
            kp_stats[kp_id] = {
                "knowledge_point_id": kp_id,
                "knowledge_point_name": kp["name"],
                "grade": kp["grade"],
                "chapter": kp["chapter"],
                "parent_id": kp["parent_id"],
                "parent_name": kp.get("parent_name") or "无",
                "description": kp["description"],
                "common_mistakes": kp["common_mistakes"],
                "mistake_count": 0,
                "status_counts": {status: 0 for status in VALID_MASTERY_STATUSES},
                "unmastered_count": 0,
                "mastery_rate": 0.0,
            }

        # 每道去重后的错题计入所属知识点。
        for mistake in mistakes:
            kp_id = int(mistake["knowledge_point_id"])
            if kp_id not in kp_stats:
                continue
            status = mistake.get("mastery_status") or "未掌握"
            kp_stats[kp_id]["mistake_count"] += 1
            kp_stats[kp_id]["status_counts"][status] = (
                kp_stats[kp_id]["status_counts"].get(status, 0) + 1
            )

        for item in kp_stats.values():
            count = item["mistake_count"]
            mastered = item["status_counts"].get("已掌握", 0)
            unmastered = item["status_counts"].get("未掌握", 0) + item["status_counts"].get("复习中", 0)
            item["unmastered_count"] = unmastered
            item["mastery_rate"] = round(mastered / count * 100, 1) if count else 0.0

        by_knowledge_point = sorted(
            kp_stats.values(),
            key=lambda item: (
                -item["mistake_count"],
                -item["unmastered_count"],
                item["grade"],
                item["knowledge_point_id"],
            ),
        )

        active_points = [item for item in by_knowledge_point if item["mistake_count"] > 0]
        weakest_points = sorted(
            active_points,
            key=lambda item: (
                -item["unmastered_count"],
                -item["mistake_count"],
                item["mastery_rate"],
                item["knowledge_point_id"],
            ),
        )[:weakest_limit]

        parent_stats: dict[str, dict[str, Any]] = {}
        for item in active_points:
            area_name = item["parent_name"] if item["parent_name"] != "无" else item["knowledge_point_name"]
            if area_name not in parent_stats:
                parent_stats[area_name] = {
                    "area_name": area_name,
                    "mistake_count": 0,
                    "unmastered_count": 0,
                    "mastered_count": 0,
                    "knowledge_points": [],
                }
            parent_stats[area_name]["mistake_count"] += item["mistake_count"]
            parent_stats[area_name]["unmastered_count"] += item["unmastered_count"]
            parent_stats[area_name]["mastered_count"] += item["status_counts"].get("已掌握", 0)
            parent_stats[area_name]["knowledge_points"].append(item["knowledge_point_name"])

        by_parent_area = []
        for item in parent_stats.values():
            count = item["mistake_count"]
            item["mastery_rate"] = round(item["mastered_count"] / count * 100, 1) if count else 0.0
            by_parent_area.append(item)
        by_parent_area.sort(key=lambda item: (-item["unmastered_count"], -item["mistake_count"], item["area_name"]))

        return {
            "deduplicated": deduplicate,
            "total_records": total_records,
            "total_mistakes": total_mistakes,
            "duplicate_records_ignored": duplicate_records_ignored,
            "status_counts": status_counts,
            "overall_mastery_rate": mastery_rate,
            "pending_review_count": status_counts.get("未掌握", 0) + status_counts.get("复习中", 0),
            "by_knowledge_point": by_knowledge_point,
            "weakest_points": weakest_points,
            "by_parent_area": by_parent_area,
        }
    except Exception as exc:
        print(f"[统计错误] 生成学情统计失败：{exc}")
        return {
            "deduplicated": deduplicate,
            "total_records": 0,
            "total_mistakes": 0,
            "duplicate_records_ignored": 0,
            "status_counts": {status: 0 for status in VALID_MASTERY_STATUSES},
            "overall_mastery_rate": 0.0,
            "pending_review_count": 0,
            "by_knowledge_point": [],
            "weakest_points": [],
            "by_parent_area": [],
        }


# 允许在错题本里直接编辑的字段白名单。
# 只允许这些列被 UPDATE，避免外部传入任意列名造成 SQL 拼接风险。
EDITABLE_MISTAKE_FIELDS = {
    "question_text",
    "student_answer",
    "error_reason",
    "correct_answer",
    "detailed_solution",
    "grade",
    "question_type",
    "difficulty",
}


def find_existing_mistake(
    knowledge_point_id: int,
    question_text: str,
    student_answer: str,
) -> dict[str, Any] | None:
    """
    录入前查重：判断这道题是否已经录入过。

    去重口径和学情统计保持一致：
      同一个知识点下，题目内容相同、学生错误答案相同，就认为是重复录入。
    命中返回已存在的错题详情，否则返回 None。
    """
    try:
        kp_id = int(knowledge_point_id)
    except (TypeError, ValueError):
        return None

    target_key = (
        kp_id,
        _normalize_for_stats(question_text),
        _normalize_for_stats(student_answer),
    )
    for existing in get_mistakes_by_knowledge_point(kp_id):
        if _mistake_dedup_key(existing) == target_key:
            return existing
    return None


def update_mistake_fields(mistake_id: int, fields: dict[str, Any]) -> bool:
    """
    编辑一道错题的内容字段。

    只更新 EDITABLE_MISTAKE_FIELDS 白名单里的列；列名来自白名单，值用参数化传入，
    不会把用户输入拼进 SQL。掌握状态和复习次数不走这里，仍由 update_mistake_mastery 管理。
    """
    updates = {key: fields[key] for key in fields if key in EDITABLE_MISTAKE_FIELDS}
    if not updates:
        print("[提示] 没有可更新的错题字段。")
        return False

    set_clause = ", ".join(f"{column} = ?" for column in updates)
    params = list(updates.values()) + [mistake_id]

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE mistakes SET {set_clause} WHERE id = ?",
                params,
            )
            if cursor.rowcount == 0:
                print(f"[提示] 没找到错题ID：{mistake_id}")
                return False
            return True
    except sqlite3.Error as exc:
        print(f"[数据库错误] 编辑错题失败：{exc}")
        return False


def update_mistake_reasoning_tags(mistake_id: int, reasoning_tags: str | None) -> bool:
    """
    把 AI 提取的解题思路标签写回错题表（存 JSON 字符串）。

    和 ai_explanation 一样是缓存字段：同一道题只在缺标签或强制刷新时才重新调用 AI。
    """
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "UPDATE mistakes SET reasoning_tags = ? WHERE id = ?",
                (reasoning_tags, mistake_id),
            )
            if cursor.rowcount == 0:
                print(f"[提示] 没找到错题ID：{mistake_id}")
                return False
            return True
    except sqlite3.Error as exc:
        print(f"[数据库错误] 保存解题思路标签失败：{exc}")
        return False


def clear_mistake_ai_explanation(mistake_id: int) -> bool:
    """
    清空一道错题的 AI 讲解缓存。

    编辑题目或答案后调用：旧讲解是针对旧内容生成的，直接作废，
    下次在讲解页会重新生成，避免展示与新题目不符的过期讲解。
    """
    try:
        with get_connection() as conn:
            conn.execute(
                "UPDATE mistakes SET ai_explanation = NULL WHERE id = ?",
                (mistake_id,),
            )
            return True
    except sqlite3.Error as exc:
        print(f"[数据库错误] 清空 AI 讲解缓存失败：{exc}")
        return False


def delete_mistake(mistake_id: int) -> bool:
    """
    删除一道错题。

    只删 mistakes 表里的记录，不影响知识点库。
    向量库里的对应向量由上层调用 mistake_recommender.delete_mistake_from_vector_store 清理。
    """
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM mistakes WHERE id = ?",
                (mistake_id,),
            )
            if cursor.rowcount == 0:
                print(f"[提示] 没找到错题ID：{mistake_id}")
                return False
            return True
    except sqlite3.Error as exc:
        print(f"[数据库错误] 删除错题失败：{exc}")
        return False
