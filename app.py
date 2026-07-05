"""
K12 数学错题讲解助手 —— Streamlit 网页界面
==========================================

这个文件只负责页面交互：
  - 录入真实错题
  - 生成针对性讲解
  - 查看错题本
  - 生成学情分析
  - 推荐相似题

底层数据库、AI、向量检索逻辑仍然复用 mistake_db.py、mistake_ai.py、mistake_recommender.py。
"""

from __future__ import annotations

import os
from html import escape
from typing import Any

import streamlit as st

import mistake_ai
import mistake_db
import mistake_recommender


GRADE_OPTIONS = ["初一", "初二", "初三"]
QUESTION_TYPE_OPTIONS = ["选择", "填空", "解答"]
DIFFICULTY_OPTIONS = ["基础", "中等", "提高"]
MASTERY_OPTIONS = ["未掌握", "复习中", "已掌握"]


def configure_page() -> None:
    """设置页面基础信息和整体视觉风格。"""
    st.set_page_config(
        page_title="K12 数学错题助手",
        page_icon="∑",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(
        """
        <style>
        :root {
            --ink: #17202a;
            --muted: #667085;
            --line: #d8dee8;
            --panel: #ffffff;
            --soft: #f3f7f8;
            --teal: #0f766e;
            --coral: #d65f4a;
            --gold: #b7791f;
            --blue: #2563eb;
        }

        .stApp {
            background:
                linear-gradient(180deg, #f7faf9 0%, #edf3f4 42%, #f8fafc 100%);
            color: var(--ink);
        }

        .block-container {
            max-width: 1280px;
            padding-top: 1.35rem;
            padding-bottom: 3rem;
        }

        .hero {
            border: 1px solid rgba(23, 32, 42, 0.10);
            border-radius: 8px;
            padding: 22px 24px;
            background:
                linear-gradient(135deg, rgba(15,118,110,0.96), rgba(23,32,42,0.94) 52%, rgba(183,121,31,0.88));
            color: #ffffff;
            box-shadow: 0 18px 45px rgba(20, 35, 45, 0.12);
        }

        .hero h1 {
            font-size: 34px;
            line-height: 1.18;
            margin: 0 0 8px 0;
            letter-spacing: 0;
        }

        .hero p {
            margin: 0;
            color: rgba(255,255,255,0.82);
            font-size: 15px;
            line-height: 1.7;
        }

        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            border-radius: 999px;
            padding: 5px 10px;
            font-size: 12px;
            font-weight: 700;
            margin-right: 6px;
            border: 1px solid rgba(255,255,255,0.28);
            background: rgba(255,255,255,0.12);
            color: #fff;
        }

        .section-title {
            margin: 18px 0 8px 0;
            font-size: 18px;
            font-weight: 800;
            color: var(--ink);
        }

        .quiet {
            color: var(--muted);
            font-size: 13px;
            line-height: 1.65;
        }

        .mini-label {
            color: var(--muted);
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }

        .metric-card {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 14px 16px;
            min-height: 98px;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
        }

        .metric-card .value {
            font-size: 28px;
            font-weight: 850;
            color: var(--ink);
            margin-top: 6px;
        }

        .metric-card .caption {
            color: var(--muted);
            font-size: 12px;
            margin-top: 2px;
        }

        .mistake-card {
            background: var(--panel);
            border: 1px solid var(--line);
            border-left: 5px solid var(--teal);
            border-radius: 8px;
            padding: 14px 16px;
            margin: 10px 0;
            box-shadow: 0 12px 28px rgba(15, 23, 42, 0.055);
        }

        .mistake-card.same {
            border-left-color: var(--teal);
        }

        .mistake-card.cross {
            border-left-color: var(--coral);
        }

        .mistake-card.target {
            border-left-color: var(--blue);
        }

        .mistake-head {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
        }

        .badge {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 3px 9px;
            font-size: 12px;
            font-weight: 750;
            background: #eef7f5;
            color: #0f766e;
            border: 1px solid #cfe6e2;
        }

        .badge.warn {
            background: #fff5ed;
            color: #b45309;
            border-color: #fed7aa;
        }

        .badge.danger {
            background: #fff1f0;
            color: #be3a2f;
            border-color: #fecaca;
        }

        .badge.neutral {
            background: #eef2f7;
            color: #475467;
            border-color: #d8dee8;
        }

        .question {
            font-weight: 760;
            color: var(--ink);
            line-height: 1.7;
            margin-bottom: 8px;
        }

        .detail-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 10px;
            margin-top: 10px;
        }

        .detail-box {
            background: #f8fafb;
            border: 1px solid #e5ebf0;
            border-radius: 8px;
            padding: 10px 12px;
            min-height: 74px;
        }

        .detail-box b {
            display: block;
            color: #344054;
            font-size: 12px;
            margin-bottom: 4px;
        }

        .detail-box span {
            color: #1f2937;
            font-size: 13px;
            line-height: 1.65;
        }

        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 12px 14px;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.045);
        }

        div[data-testid="stTabs"] [data-baseweb="tab-list"] {
            gap: 8px;
        }

        div[data-testid="stTabs"] button[role="tab"] {
            border: 1px solid #d8dee8;
            border-radius: 8px;
            background: #ffffff;
            padding: 8px 12px;
        }

        div[data-testid="stTabs"] button[aria-selected="true"] {
            border-color: #0f766e;
            background: #eef7f5;
        }

        .stButton > button {
            border-radius: 8px;
            border: 1px solid #0f766e;
            background: #0f766e;
            color: white;
            font-weight: 760;
        }

        .stButton > button:hover {
            border-color: #115e59;
            background: #115e59;
            color: white;
        }

        @media (max-width: 760px) {
            .hero h1 {
                font-size: 26px;
            }
            .detail-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource(show_spinner=False)
def bootstrap_data() -> bool:
    """
    启动时确保数据库和知识点库存在。

    用 cache_resource 保证建表和预置知识点在整个进程里只跑一次，
    而不是每次 Streamlit rerun 都重复建表、逐条尝试插入 24 个知识点。
    """
    mistake_db.create_tables()
    mistake_db.seed_core_knowledge_points()
    return True


def has_deepseek_key() -> bool:
    """检查 DeepSeek API key 是否存在，但不读取、不展示具体值。"""
    return bool(os.environ.get(mistake_ai.DEEPSEEK_API_KEY_ENV))


@st.cache_data(show_spinner=False)
def all_mistakes() -> list[dict[str, Any]]:
    """读取全部错题，默认按 ID 倒序。结果缓存，写操作后由 refresh_data_cache 清理。"""
    return mistake_db.get_all_mistakes_with_knowledge()


@st.cache_data(show_spinner=False)
def all_knowledge_points() -> list[dict[str, Any]]:
    """读取知识点清单，给手动归类和筛选使用。结果缓存。"""
    return mistake_db.list_knowledge_points()


@st.cache_data(show_spinner=False)
def learning_overview() -> dict[str, Any]:
    """读取去重后的学情概览。侧栏和学情分析共用同一份缓存，避免一次渲染算两遍。"""
    return mistake_db.build_learning_overview(deduplicate=True)


def refresh_data_cache() -> None:
    """任何写操作（录入/编辑/删除/更新状态/同步演示题）后调用，让缓存重新取数。"""
    all_mistakes.clear()
    all_knowledge_points.clear()
    learning_overview.clear()


def truncate_text(value: Any, limit: int = 56) -> str:
    """把长文本压短，适合放进下拉框和卡片标题。"""
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "..."


def status_badge_class(status: str | None) -> str:
    """掌握状态对应不同颜色。"""
    if status == "未掌握":
        return "danger"
    if status == "复习中":
        return "warn"
    return "neutral"


def mistake_label(item: dict[str, Any]) -> str:
    """生成错题下拉框选项文字。"""
    return (
        f"#{item['id']} | {item.get('grade') or '-'} | "
        f"{item.get('knowledge_point_name') or '未归类'} | "
        f"{truncate_text(item.get('question_text'), 46)}"
    )


def metric_card(label: str, value: Any, caption: str = "") -> None:
    """自定义指标卡，让概览区更稳、更清楚。"""
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="mini-label">{escape(str(label))}</div>
            <div class="value">{escape(str(value))}</div>
            <div class="caption">{escape(str(caption))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_header(api_ready: bool, total_mistakes: int) -> None:
    """页面顶部工作台标题。"""
    api_text = "DeepSeek 已连接" if api_ready else "DeepSeek 未配置"
    st.markdown(
        f"""
        <div class="hero">
            <div style="margin-bottom: 12px;">
                <span class="status-pill">{escape(api_text)}</span>
                <span class="status-pill">本地错题 {total_mistakes} 道</span>
                <span class="status-pill">SQLite + Chroma 本地运行</span>
            </div>
            <h1>K12 数学错题讲解助手</h1>
            <p>把真实错题沉淀成可复习、可讲解、可分析、可推荐的学习资产。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(api_ready: bool, mistakes: list[dict[str, Any]]) -> None:
    """左侧状态栏和轻量工具。"""
    with st.sidebar:
        st.markdown("### 工作台")
        st.caption("本地数据不会自动上传。")

        st.markdown("#### 环境")
        st.write("DeepSeek API：", "已配置" if api_ready else "未配置")
        st.write("SQLite：", str(mistake_db.DB_PATH.name))
        st.write("Chroma：", str(mistake_recommender.CHROMA_DB_PATH.name))

        st.markdown("#### 数据")
        overview = learning_overview()
        st.metric("原始记录", overview.get("total_records", 0))
        st.metric("有效错题", overview.get("total_mistakes", 0))
        st.metric("待复习", overview.get("pending_review_count", 0))

        st.markdown("#### 向量库")
        if st.button("同步错题向量", width="stretch"):
            with st.spinner("正在同步到本地 Chroma..."):
                result = mistake_recommender.sync_mistakes_to_vector_store()
            st.success(result.get("message", "同步完成。"))
            st.caption(f"同步：{result.get('synced_count', 0)} 条")

        with st.expander("演示数据"):
            st.caption("当前已有批量样例时会自动跳过，不会重复录入。首次运行会调用 DeepSeek。")
            if st.button("检查 48 道演示题", width="stretch", disabled=not api_ready):
                import seed_similar_mistake_samples

                with st.spinner("正在检查演示题..."):
                    stats = seed_similar_mistake_samples.seed_samples()
                refresh_data_cache()
                st.json(stats)

        st.markdown("---")
        st.caption(f"当前列表：{len(mistakes)} 道错题")


def render_mistake_card(
    item: dict[str, Any],
    card_type: str = "same",
    show_details: bool = True,
) -> None:
    """渲染一张错题卡片。"""
    status = item.get("mastery_status") or "未掌握"
    status_class = status_badge_class(status)
    distance = item.get("distance")
    distance_html = ""
    if distance is not None:
        distance_html = f'<span class="badge neutral">distance {escape(str(distance))}</span>'

    recommendation_type = item.get("recommendation_type")
    type_html = ""
    if recommendation_type:
        type_html = f'<span class="badge">{escape(str(recommendation_type))}</span>'

    detail_html = ""
    if show_details:
        detail_html = (
            '<div class="detail-grid">'
            f'<div class="detail-box"><b>学生答案</b><span>{escape(str(item.get("student_answer") or "未填写"))}</span></div>'
            f'<div class="detail-box"><b>错因</b><span>{escape(str(item.get("error_reason") or "未填写"))}</span></div>'
            f'<div class="detail-box"><b>正确答案</b><span>{escape(str(item.get("correct_answer") or "未填写"))}</span></div>'
            f'<div class="detail-box"><b>年级 / 难度</b><span>{escape(str(item.get("grade") or "-"))} / {escape(str(item.get("difficulty") or "-"))}</span></div>'
            "</div>"
        )

    card_html = (
        f'<div class="mistake-card {escape(card_type)}">'
        '<div class="mistake-head">'
        f'<span class="badge neutral">#{escape(str(item.get("id") or item.get("mistake_id")))}</span>'
        f'<span class="badge">{escape(str(item.get("knowledge_point_name") or "未归类"))}</span>'
        f'<span class="badge {status_class}">{escape(status)}</span>'
        f"{type_html}{distance_html}"
        "</div>"
        f'<div class="question">{escape(str(item.get("question_text") or ""))}</div>'
        f"{detail_html}"
        "</div>"
    )

    # Streamlit 对分段 HTML 容错有限，所以整张卡片一次性输出，避免闭合标签露出。
    st.markdown(card_html, unsafe_allow_html=True)


def choose_mistake(
    label: str,
    mistakes: list[dict[str, Any]],
    key: str,
    default_id: int | None = None,
) -> dict[str, Any] | None:
    """通用错题选择器，返回完整错题详情。"""
    if not mistakes:
        st.info("还没有错题。")
        return None

    labels = [mistake_label(item) for item in mistakes]
    ids = [int(item["id"]) for item in mistakes]
    default_index = 0
    if default_id in ids:
        default_index = ids.index(int(default_id))

    selected = st.selectbox(label, labels, index=default_index, key=key)
    selected_id = ids[labels.index(selected)]
    return mistake_db.get_mistake_detail(selected_id)


def render_entry_tab(api_ready: bool) -> None:
    """录入真实错题。"""
    st.markdown('<div class="section-title">录入错题</div>', unsafe_allow_html=True)

    classify_mode = st.radio(
        "归类方式",
        ["DeepSeek 自动归类", "手动选择知识点"],
        horizontal=True,
        disabled=False,
    )

    knowledge_points = all_knowledge_points()
    kp_labels = [
        f"#{item['id']} | {item['grade']} | {item['name']} | {item.get('parent_name') or '无'}"
        for item in knowledge_points
    ]

    with st.form("add_mistake_form", clear_on_submit=False):
        left, right = st.columns([1.2, 1])
        with left:
            question_text = st.text_area("题目内容", height=132, max_chars=1200)
            student_answer = st.text_area("学生错误答案", height=86, max_chars=600)
            error_reason = st.text_area("学生错误原因", height=86, max_chars=800)

        with right:
            grade = st.selectbox("年级", GRADE_OPTIONS, index=1)
            question_type = st.selectbox("题型", QUESTION_TYPE_OPTIONS, index=2)
            difficulty = st.selectbox("难度", DIFFICULTY_OPTIONS, index=1)
            mastery_status = st.selectbox("掌握状态", MASTERY_OPTIONS, index=0)
            manual_kp_id = None
            if classify_mode == "手动选择知识点":
                kp_choice = st.selectbox("知识点", kp_labels)
                manual_kp_id = int(kp_choice.split("|", 1)[0].replace("#", "").strip())

        correct_answer = st.text_area("正确答案", height=86, max_chars=800)
        detailed_solution = st.text_area("详细解析", height=132, max_chars=1600)
        generate_after_save = st.checkbox(
            "保存后生成讲解",
            value=False,
            disabled=not api_ready,
        )

        submitted = st.form_submit_button(
            "保存错题",
            width="stretch",
            disabled=(classify_mode == "DeepSeek 自动归类" and not api_ready),
        )

    if not submitted:
        if classify_mode == "DeepSeek 自动归类" and not api_ready:
            st.warning("未检测到 DEEPSEEK_API_KEY，自动归类暂不可用。")
        return

    required = {
        "题目内容": question_text,
        "学生错误答案": student_answer,
        "正确答案": correct_answer,
        "详细解析": detailed_solution,
    }
    missing = [name for name, value in required.items() if not str(value or "").strip()]
    if missing:
        st.error("这些内容还没填：" + "、".join(missing))
        return

    with st.spinner("正在保存错题..."):
        if classify_mode == "DeepSeek 自动归类":
            result = mistake_ai.add_mistake_with_auto_classification(
                question_text=question_text,
                grade=grade,
                question_type=question_type,
                difficulty=difficulty,
                correct_answer=correct_answer,
                detailed_solution=detailed_solution,
                student_answer=student_answer,
                error_reason=error_reason,
                mastery_status=mastery_status,
            )
            mistake_id = result.get("mistake_id")
        else:
            existing = mistake_db.find_existing_mistake(
                int(manual_kp_id), question_text, student_answer
            )
            if existing is not None:
                result = {
                    "saved": False,
                    "duplicate": True,
                    "mistake_id": int(existing["id"]),
                    "message": f"这道题已存在（#{existing['id']}），未重复录入。",
                    "classification": {"reason": "手动选择知识点"},
                }
                mistake_id = None
            else:
                mistake_id = mistake_db.add_mistake(
                    question_text=question_text,
                    grade=grade,
                    question_type=question_type,
                    difficulty=difficulty,
                    knowledge_point_id=int(manual_kp_id),
                    correct_answer=correct_answer,
                    detailed_solution=detailed_solution,
                    student_answer=student_answer,
                    error_reason=error_reason,
                    mastery_status=mastery_status,
                )
                result = {
                    "saved": mistake_id is not None,
                    "duplicate": False,
                    "mistake_id": mistake_id,
                    "message": "错题已录入。",
                    "classification": {"reason": "手动选择知识点"},
                }

    if not result.get("saved"):
        if result.get("duplicate"):
            st.warning(result.get("message", "这道题已存在，未重复录入。"))
        else:
            st.error(result.get("message", "保存失败。"))
        return

    # 录入成功后清理缓存，保证其他 Tab（错题本/学情/推荐）立刻看到新错题。
    refresh_data_cache()
    st.success(f"已保存错题 #{mistake_id}")
    st.session_state["last_mistake_id"] = int(mistake_id)

    classification = result.get("classification") or {}
    if classification:
        st.caption(f"归类结果：{classification.get('knowledge_point_name') or '手动选择'} · {classification.get('reason')}")

    if generate_after_save:
        with st.spinner("正在生成讲解..."):
            explanation_result = mistake_ai.generate_and_cache_mistake_explanation(int(mistake_id))
        if explanation_result.get("saved"):
            st.markdown(explanation_result.get("explanation") or "")
        else:
            st.warning(explanation_result.get("message", "讲解生成失败。"))


def render_explanation_tab(api_ready: bool, mistakes: list[dict[str, Any]]) -> None:
    """生成或查看 AI 讲解。"""
    st.markdown('<div class="section-title">错题讲解</div>', unsafe_allow_html=True)
    selected = choose_mistake(
        "选择错题",
        mistakes,
        key="explanation_mistake",
        default_id=st.session_state.get("last_mistake_id"),
    )
    if not selected:
        return

    render_mistake_card(selected, card_type="target")
    cached = str(selected.get("ai_explanation") or "").strip()

    col_a, col_b = st.columns([1, 1])
    with col_a:
        force_refresh = st.checkbox("重新生成", value=False, disabled=not api_ready)
    with col_b:
        generate = st.button(
            "生成 / 查看讲解",
            width="stretch",
            disabled=not api_ready,
        )

    if not api_ready:
        st.warning("未检测到 DEEPSEEK_API_KEY，暂时不能生成讲解。")

    if cached and not generate:
        st.markdown("#### 已缓存讲解")
        st.markdown(cached)

    if generate:
        with st.spinner("正在整理这道题的讲解..."):
            result = mistake_ai.generate_and_cache_mistake_explanation(
                int(selected["id"]),
                force_refresh=force_refresh,
            )
        if result.get("saved"):
            st.success(result.get("message", "讲解已生成。"))
            st.markdown(result.get("explanation") or "")
        else:
            st.error(result.get("message", "讲解生成失败。"))


def filtered_mistakes(view: str, mistakes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """根据错题本视图筛选数据。"""
    if view == "待复习":
        return mistake_db.get_pending_review_mistakes()
    if view == "全部":
        return mistakes
    if view == "按状态":
        status = st.selectbox("掌握状态", MASTERY_OPTIONS, index=0, key="book_status")
        return mistake_db.get_mistakes_by_mastery_status(status)
    if view == "按年级":
        grade = st.selectbox("年级", GRADE_OPTIONS, index=1, key="book_grade")
        return mistake_db.get_mistakes_by_grade(grade)

    knowledge_points = [item for item in all_knowledge_points() if item.get("parent_id")]
    labels = [f"#{item['id']} | {item['grade']} | {item['name']}" for item in knowledge_points]
    if not labels:
        return []
    choice = st.selectbox("知识点", labels, key="book_kp")
    kp_id = int(choice.split("|", 1)[0].replace("#", "").strip())
    return mistake_db.get_mistakes_by_knowledge_point(kp_id)


def search_mistakes(items: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """按关键词过滤错题：命中题目、知识点或学生答案即可。"""
    query = query.strip()
    if not query:
        return items
    return [
        item
        for item in items
        if query in str(item.get("question_text") or "")
        or query in str(item.get("knowledge_point_name") or "")
        or query in str(item.get("student_answer") or "")
    ]


def render_mistake_admin(item: dict[str, Any]) -> None:
    """错题本里单道错题的管理面板：更新状态、编辑内容、删除。"""
    mid = int(item["id"])

    st.markdown("**更新掌握状态**")
    current_status = item.get("mastery_status") or "未掌握"
    col_a, col_b, col_c = st.columns([1, 1, 1])
    with col_a:
        new_status = st.selectbox(
            "掌握状态",
            MASTERY_OPTIONS,
            index=MASTERY_OPTIONS.index(current_status) if current_status in MASTERY_OPTIONS else 0,
            key=f"status_{mid}",
        )
    with col_b:
        increase = st.checkbox("计入复习次数", value=True, key=f"review_{mid}")
    with col_c:
        st.write("")
        st.write("")
        if st.button("保存状态", key=f"save_status_{mid}", width="stretch"):
            if mistake_db.update_mistake_mastery(mid, new_status, increase_review_count=increase):
                refresh_data_cache()
                st.success("已更新。")
                st.rerun()
            else:
                st.error("更新失败。")

    st.markdown("---")
    with st.form(f"edit_form_{mid}"):
        st.markdown("**编辑内容**")
        e_question = st.text_area(
            "题目", value=item.get("question_text") or "", key=f"e_q_{mid}", height=100, max_chars=1200
        )
        col_l, col_r = st.columns(2)
        with col_l:
            e_student = st.text_area(
                "学生答案", value=item.get("student_answer") or "", key=f"e_s_{mid}", height=80, max_chars=600
            )
            e_correct = st.text_area(
                "正确答案", value=item.get("correct_answer") or "", key=f"e_c_{mid}", height=80, max_chars=800
            )
        with col_r:
            e_reason = st.text_area(
                "错误原因", value=item.get("error_reason") or "", key=f"e_r_{mid}", height=80, max_chars=800
            )
            grade_value = item.get("grade")
            e_grade = st.selectbox(
                "年级",
                GRADE_OPTIONS,
                index=GRADE_OPTIONS.index(grade_value) if grade_value in GRADE_OPTIONS else 1,
                key=f"e_g_{mid}",
            )
            difficulty_value = item.get("difficulty")
            e_difficulty = st.selectbox(
                "难度",
                DIFFICULTY_OPTIONS,
                index=DIFFICULTY_OPTIONS.index(difficulty_value) if difficulty_value in DIFFICULTY_OPTIONS else 1,
                key=f"e_d_{mid}",
            )
        e_solution = st.text_area(
            "详细解析", value=item.get("detailed_solution") or "", key=f"e_sol_{mid}", height=110, max_chars=1600
        )
        if st.form_submit_button("保存修改", width="stretch"):
            required = {
                "题目": e_question,
                "学生答案": e_student,
                "正确答案": e_correct,
                "详细解析": e_solution,
            }
            missing = [name for name, value in required.items() if not str(value or "").strip()]
            if missing:
                st.error("这些内容不能为空：" + "、".join(missing))
            elif mistake_db.update_mistake_fields(
                mid,
                {
                    "question_text": e_question,
                    "student_answer": e_student,
                    "error_reason": e_reason,
                    "correct_answer": e_correct,
                    "detailed_solution": e_solution,
                    "grade": e_grade,
                    "difficulty": e_difficulty,
                },
            ):
                # 内容变了，旧的 AI 讲解作废，避免展示与新题目不符的过期讲解。
                mistake_db.clear_mistake_ai_explanation(mid)
                refresh_data_cache()
                st.success("修改已保存，原讲解缓存已清空。")
                st.rerun()
            else:
                st.error("保存失败。")

    st.markdown("---")
    st.markdown("**删除错题**")
    confirm = st.checkbox("我确认删除这道错题", key=f"del_ok_{mid}")
    if st.button("删除", key=f"del_{mid}", width="stretch", disabled=not confirm):
        if mistake_db.delete_mistake(mid):
            mistake_recommender.delete_mistake_from_vector_store(mid)
            refresh_data_cache()
            st.success("已删除。")
            st.rerun()
        else:
            st.error("删除失败。")


def render_mistake_book_tab(mistakes: list[dict[str, Any]]) -> None:
    """错题本浏览、搜索、分页、状态更新、编辑与删除。"""
    st.markdown('<div class="section-title">错题本</div>', unsafe_allow_html=True)
    view = st.radio(
        "视图",
        ["待复习", "全部", "按知识点", "按状态", "按年级"],
        horizontal=True,
    )
    items = filtered_mistakes(view, mistakes)

    query = st.text_input("搜索题目 / 知识点 / 学生答案", key="book_search")
    items = search_mistakes(items, query)
    st.caption(f"当前视图共 {len(items)} 道")

    if not items:
        st.info("没有匹配的错题。")
        return

    col_size, col_page = st.columns([1, 2])
    with col_size:
        page_size = st.selectbox("每页", [5, 10, 20, 50], index=1, key="book_page_size")
    total_pages = max(1, (len(items) + page_size - 1) // page_size)
    with col_page:
        page = int(
            st.number_input(
                "页码", min_value=1, max_value=total_pages, value=1, step=1, key="book_page"
            )
        )
    start = (page - 1) * page_size
    page_items = items[start : start + page_size]
    st.caption(f"第 {page} / {total_pages} 页")

    for item in page_items:
        render_mistake_card(item, card_type="target")
        with st.expander(f"管理 #{item['id']}"):
            render_mistake_admin(item)


def render_learning_tab(api_ready: bool) -> None:
    """统计概览和 AI 学情报告。"""
    st.markdown('<div class="section-title">学情分析</div>', unsafe_allow_html=True)
    overview = learning_overview()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("有效错题", overview.get("total_mistakes", 0), "去重后")
    with col2:
        metric_card("掌握率", f"{overview.get('overall_mastery_rate', 0)}%", "已掌握占比")
    with col3:
        metric_card("待复习", overview.get("pending_review_count", 0), "未掌握 + 复习中")
    with col4:
        metric_card("重复记录", overview.get("duplicate_records_ignored", 0), "统计时忽略")

    st.markdown("#### 掌握状态")
    status_counts = overview.get("status_counts", {})
    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("未掌握", status_counts.get("未掌握", 0))
    sc2.metric("复习中", status_counts.get("复习中", 0))
    sc3.metric("已掌握", status_counts.get("已掌握", 0))

    left, right = st.columns([1.05, 1])
    with left:
        st.markdown("#### 薄弱知识点")
        weak_rows = []
        for item in overview.get("weakest_points", []):
            weak_rows.append(
                {
                    "知识点": item.get("knowledge_point_name"),
                    "上级": item.get("parent_name"),
                    "错题数": item.get("mistake_count"),
                    "待复习": item.get("unmastered_count"),
                    "掌握率": f"{item.get('mastery_rate', 0)}%",
                }
            )
        st.dataframe(weak_rows, hide_index=True, width="stretch")

    with right:
        st.markdown("#### 大方向")
        parent_rows = []
        for item in overview.get("by_parent_area", []):
            parent_rows.append(
                {
                    "方向": item.get("area_name"),
                    "错题数": item.get("mistake_count"),
                    "待复习": item.get("unmastered_count"),
                    "掌握率": f"{item.get('mastery_rate', 0)}%",
                }
            )
        st.dataframe(parent_rows, hide_index=True, width="stretch")

    generate_report = st.button(
        "生成 AI 学情报告",
        width="stretch",
        disabled=not api_ready,
    )
    if not api_ready:
        st.warning("未检测到 DEEPSEEK_API_KEY，暂时不能生成 AI 学情报告。")

    if generate_report:
        with st.spinner("正在生成学情报告..."):
            result = mistake_ai.generate_learning_report()
        st.session_state["learning_report"] = result

    report_result = st.session_state.get("learning_report")
    if report_result:
        st.info(report_result.get("message", ""))
        if report_result.get("report"):
            st.markdown(report_result["report"])


def render_recommendation_tab(mistakes: list[dict[str, Any]]) -> None:
    """相似题推荐。"""
    st.markdown('<div class="section-title">相似题推荐</div>', unsafe_allow_html=True)
    selected = choose_mistake(
        "选择目标错题",
        mistakes,
        key="recommend_mistake",
        default_id=st.session_state.get("last_mistake_id"),
    )
    if not selected:
        return

    render_mistake_card(selected, card_type="target")

    col_a, col_b, col_c = st.columns([1, 1, 1])
    with col_a:
        same_limit = st.slider("同知识点数量", 1, 8, 5)
    with col_b:
        cross_limit = st.slider("思路相近数量", 1, 8, 5)
    with col_c:
        ensure_synced = st.checkbox("先同步向量库", value=True)

    if st.button("生成推荐", width="stretch"):
        with st.spinner("正在检索相似题..."):
            result = mistake_recommender.recommend_similar_mistakes(
                int(selected["id"]),
                same_knowledge_limit=same_limit,
                cross_knowledge_limit=cross_limit,
                ensure_synced=ensure_synced,
            )
        st.session_state["recommendation_result"] = result

    result = st.session_state.get("recommendation_result")
    if not result:
        return

    st.success(result.get("message", "推荐完成。"))
    same_items = result.get("same_knowledge", [])
    cross_items = result.get("cross_knowledge", [])

    left, right = st.columns(2)
    with left:
        st.markdown("#### 同知识点")
        if not same_items:
            st.info("暂无同知识点推荐。")
        for item in same_items:
            render_mistake_card(item, card_type="same")

    with right:
        st.markdown("#### 思路相近")
        if not cross_items:
            st.info("暂无跨知识点推荐。")
        for item in cross_items:
            render_mistake_card(item, card_type="cross")


def render_app() -> None:
    """页面主入口。"""
    configure_page()
    bootstrap_data()

    api_ready = has_deepseek_key()
    mistakes = all_mistakes()

    render_header(api_ready, len(mistakes))
    render_sidebar(api_ready, mistakes)

    tabs = st.tabs(["录入错题", "错题讲解", "错题本", "学情分析", "相似题推荐"])
    with tabs[0]:
        render_entry_tab(api_ready)
    with tabs[1]:
        render_explanation_tab(api_ready, mistakes)
    with tabs[2]:
        render_mistake_book_tab(mistakes)
    with tabs[3]:
        render_learning_tab(api_ready)
    with tabs[4]:
        render_recommendation_tab(mistakes)


if __name__ == "__main__":
    render_app()
