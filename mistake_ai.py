"""
K12 数学错题讲解助手 —— AI 自动归类模块
======================================

这个文件负责“让 DeepSeek 判断一道题属于哪个知识点”。

为什么单独放一个文件？
  - mistake_db.py 只管数据库。
  - mistake_ai.py 只管 AI 判断和自动录入流程。
  - 这样以后做网页、命令行、拍照搜题时，都能复用这两个模块。
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import OpenAI

import mistake_db


# DeepSeek API key 仍然走系统环境变量，不写进代码。
DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-pro"


def get_deepseek_client() -> OpenAI | None:
    """
    创建 DeepSeek 客户端。

    如果没有设置环境变量，就返回 None，不让程序崩溃。
    """
    api_key = os.environ.get(DEEPSEEK_API_KEY_ENV)
    if not api_key:
        print(f"[配置错误] 找不到环境变量 {DEEPSEEK_API_KEY_ENV}")
        print("请先在 PowerShell 里设置，例如：")
        print(f"$env:{DEEPSEEK_API_KEY_ENV} = Read-Host '请输入 DeepSeek API Key'")
        return None

    return OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)


def build_knowledge_catalog_text(knowledge_points: list[dict[str, Any]]) -> str:
    """
    把数据库里的知识点清单整理成给 AI 看的文本。

    我们只给 AI 必要信息：
      - ID：程序最终要用它关联外键。
      - 名称/年级/章节：帮助判断范围。
      - 上级知识点：帮助理解层级。
      - 描述/常见易错点：帮助判断题目是否匹配。
    """
    lines = []
    for item in knowledge_points:
        parent = item.get("parent_name") or "无"
        lines.append(
            f"ID: {item['id']}\n"
            f"名称: {item['name']}\n"
            f"学科: {item['subject']}\n"
            f"年级: {item['grade']}\n"
            f"章节: {item['chapter']}\n"
            f"上级知识点: {parent}\n"
            f"描述: {item['description']}\n"
            f"常见易错点: {item['common_mistakes']}\n"
        )
    return "\n---\n".join(lines)


def extract_json_object(text: str) -> dict[str, Any] | None:
    """
    从 DeepSeek 返回文本中解析 JSON。

    虽然 prompt 要求“只返回 JSON”，但模型偶尔会包一层 ```json。
    这里做一个温和清洗，提升稳定性。
    """
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:].strip()
    if cleaned.startswith("```"):
        cleaned = cleaned[3:].strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass

    # 兜底：如果模型前后说了废话，尝试截取第一个 {...}。
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        return None

    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def normalize_classification_result(
    raw_result: dict[str, Any] | None,
    valid_ids: set[int],
) -> dict[str, Any]:
    """
    把 AI 返回结果整理成程序稳定可用的格式。

    程序最终只认两种结果：
      1. supported=True 且 knowledge_point_id 是知识点库中的真实 ID。
      2. supported=False，带 reason 说明为什么超范围。
    """
    fallback = {
        "supported": False,
        "knowledge_point_id": None,
        "knowledge_point_name": None,
        "reason": "AI 返回结果无法解析",
        "confidence": "低",
    }
    if not raw_result:
        return fallback

    supported = bool(raw_result.get("supported"))
    reason = str(raw_result.get("reason") or "").strip()
    confidence = str(raw_result.get("confidence") or "中").strip()

    if not supported:
        return {
            "supported": False,
            "knowledge_point_id": None,
            "knowledge_point_name": None,
            "reason": reason or "这道题不属于当前初中数学知识点库",
            "confidence": confidence,
        }

    try:
        knowledge_point_id = int(raw_result.get("knowledge_point_id"))
    except (TypeError, ValueError):
        return {
            **fallback,
            "reason": "AI 返回了匹配结果，但知识点ID不是有效数字",
        }

    if knowledge_point_id not in valid_ids:
        return {
            **fallback,
            "reason": f"AI 返回了不存在的知识点ID：{knowledge_point_id}",
        }

    return {
        "supported": True,
        "knowledge_point_id": knowledge_point_id,
        "knowledge_point_name": raw_result.get("knowledge_point_name"),
        "reason": reason or "匹配成功",
        "confidence": confidence,
    }


def classify_question_knowledge_point(question_text: str) -> dict[str, Any]:
    """
    自动判断一道题最匹配哪个知识点。

    输入：
      question_text：题目文字。

    输出：
      {
        "supported": True/False,
        "knowledge_point_id": 具体ID或None,
        "knowledge_point_name": 知识点名称或None,
        "reason": 匹配原因或超范围原因,
        "confidence": 高/中/低
      }

    学段边界：
      当前知识点库只覆盖“初中数学”。
      小学题、高中题、大学题、非数学题、或库里没有覆盖的初中题，都不能硬归类。
    """
    question_text = str(question_text or "").strip()
    if not question_text:
        return {
            "supported": False,
            "knowledge_point_id": None,
            "knowledge_point_name": None,
            "reason": "题目内容为空",
            "confidence": "低",
        }

    mistake_db.create_tables()
    mistake_db.seed_core_knowledge_points()
    knowledge_points = mistake_db.list_knowledge_points()
    if not knowledge_points:
        return {
            "supported": False,
            "knowledge_point_id": None,
            "knowledge_point_name": None,
            "reason": "知识点库为空，无法归类",
            "confidence": "低",
        }

    client = get_deepseek_client()
    if client is None:
        return {
            "supported": False,
            "knowledge_point_id": None,
            "knowledge_point_name": None,
            "reason": f"缺少环境变量 {DEEPSEEK_API_KEY_ENV}，无法调用 DeepSeek 自动归类",
            "confidence": "低",
        }

    valid_ids = {int(item["id"]) for item in knowledge_points}
    catalog_text = build_knowledge_catalog_text(knowledge_points)

    system_prompt = """
你是一名严格的初中数学错题归类老师。

你的任务：
根据“题目内容”和“知识点库清单”，判断这道题最匹配哪个知识点。

非常重要的边界：
1. 当前知识点库只覆盖【初中数学】。
2. 如果题目是小学数学、高中数学、大学数学、物理/语文/英语等非数学题，必须返回超出支持范围。
3. 如果题目虽然是数学题，但知识点库里没有合适知识点，也必须返回超出支持范围。
4. 不要为了录入而硬归类；不确定时宁可返回超范围，并说明原因。
5. 如果匹配，只能返回知识点库里真实存在的 ID，不允许编造 ID。

你只能返回一个 JSON 对象，不要返回 Markdown，不要解释额外文字。

JSON 格式二选一：

匹配成功：
{
  "supported": true,
  "knowledge_point_id": 14,
  "knowledge_point_name": "一元二次方程的解法",
  "reason": "题目要求解一元二次方程，和该知识点最匹配",
  "confidence": "高"
}

超出支持范围：
{
  "supported": false,
  "knowledge_point_id": null,
  "knowledge_point_name": null,
  "reason": "这是小学数学乘法应用题，不属于当前初中数学知识点库",
  "confidence": "高"
}
""".strip()

    user_prompt = f"""
【题目内容】
{question_text}

【知识点库清单】
{catalog_text}
""".strip()

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            stream=False,
        )
        content = response.choices[0].message.content or ""
        raw_result = extract_json_object(content)
        return normalize_classification_result(raw_result, valid_ids)
    except Exception as exc:
        print(f"[AI错误] 自动归类失败：{exc}")
        return {
            "supported": False,
            "knowledge_point_id": None,
            "knowledge_point_name": None,
            "reason": "DeepSeek 调用失败，暂时无法自动归类",
            "confidence": "低",
        }


def add_mistake_with_auto_classification(
    question_text: str,
    grade: str,
    question_type: str,
    difficulty: str,
    correct_answer: str,
    detailed_solution: str,
    student_answer: str,
    image_path: str | None = None,
    subject: str = "数学",
    error_reason: str | None = None,
    ai_explanation: str | None = None,
    mastery_status: str = "未掌握",
) -> dict[str, Any]:
    """
    自动归类后录入错题。

    流程：
      学生录入题目
      -> DeepSeek 自动判断知识点
      -> 如果匹配，调用 mistake_db.add_mistake 正常录入
      -> 如果超范围，返回提示，不写入错题表
    """
    classification = classify_question_knowledge_point(question_text)

    if not classification["supported"]:
        message = (
            f"暂不支持这道题：{classification['reason']}。"
            "当前仅支持初中数学。"
        )
        print(f"[超出支持范围] {message}")
        return {
            "saved": False,
            "duplicate": False,
            "mistake_id": None,
            "classification": classification,
            "message": message,
        }

    # 录入前查重：同知识点、同题目、同学生错答，视为重复录入，直接指回已有错题。
    existing = mistake_db.find_existing_mistake(
        classification["knowledge_point_id"],
        question_text,
        student_answer,
    )
    if existing is not None:
        return {
            "saved": False,
            "duplicate": True,
            "mistake_id": int(existing["id"]),
            "classification": classification,
            "message": f"这道题已存在（#{existing['id']}），未重复录入。",
        }

    mistake_id = mistake_db.add_mistake(
        question_text=question_text,
        image_path=image_path,
        subject=subject,
        grade=grade,
        question_type=question_type,
        difficulty=difficulty,
        knowledge_point_id=classification["knowledge_point_id"],
        correct_answer=correct_answer,
        detailed_solution=detailed_solution,
        student_answer=student_answer,
        error_reason=error_reason,
        ai_explanation=ai_explanation,
        mastery_status=mastery_status,
    )

    if mistake_id is None:
        return {
            "saved": False,
            "duplicate": False,
            "mistake_id": None,
            "classification": classification,
            "message": "知识点匹配成功，但错题写入数据库失败。",
        }

    # 顺带生成解题思路标签，供相似题推荐用；失败不影响录入结果。
    try:
        generate_and_cache_reasoning_tags(mistake_id)
    except Exception as exc:
        print(f"[提示] 录入成功，但生成解题思路标签失败：{exc}")

    return {
        "saved": True,
        "duplicate": False,
        "mistake_id": mistake_id,
        "classification": classification,
        "message": "错题已自动归类并录入。",
    }


def build_explanation_prompt(mistake: dict[str, Any]) -> list[dict[str, str]]:
    """
    把错题完整信息整理成 DeepSeek messages。

    这里是第 4 步的核心：
      不是让 AI 泛泛讲标准答案；
      而是明确告诉它“学生具体错在哪里”，让讲解围绕这个错误展开。
    """
    system_prompt = """
你是一位耐心、温和、很会启发学生的初中数学老师。

你要根据一道错题的信息，给学生生成“针对这次错误”的讲解。

重要要求：
1. 必须围绕学生的具体错误讲，不要只复述标准答案。
2. 先指出学生错在哪一步、为什么会错，要用上“学生的错误原因”。
3. 语气要鼓励、具体、像老师在旁边带着想，不要让学生觉得犯错丢人。
4. “一起想一想”板块要用苏格拉底式提问，引导学生自己发现正确思路，先不要直接公布最终答案。
5. “正确解法”板块再给完整步骤。
6. “举一反三”板块要结合知识点库里的常见易错点，提醒以后怎么避免。

请严格按下面四个板块输出，板块标题不要改：

【你错在哪里】
针对学生这次的具体错误，指出错在哪一步、为什么。

【一起想一想】
用 3-5 个小问题引导学生想出正确思路，语气温和。

【正确解法】
写出完整、清晰、适合中学生核对的解题步骤。

【举一反三】
结合这个知识点的常见易错点，提醒学生以后注意什么。
""".strip()

    error_reason = mistake.get("error_reason") or "学生没有填写错误原因，请你根据错误答案合理分析。"
    ai_explanation = mistake.get("ai_explanation") or "暂无缓存讲解"

    user_prompt = f"""
【题目】
{mistake.get("question_text")}

【学生的错误答案】
{mistake.get("student_answer")}

【学生的错误原因】
{error_reason}

【正确答案】
{mistake.get("correct_answer")}

【详细解析】
{mistake.get("detailed_solution")}

【所属知识点】
{mistake.get("knowledge_point_name")}

【知识点描述】
{mistake.get("knowledge_point_description")}

【知识点常见易错点】
{mistake.get("knowledge_point_common_mistakes")}

【已有AI讲解缓存】
{ai_explanation}

请生成一份新的、针对学生这次错误的讲解。
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def generate_mistake_explanation(mistake: dict[str, Any]) -> str | None:
    """
    输入一道错题完整信息，调用 DeepSeek 生成针对性讲解。

    这个函数只负责“生成文本”，不直接写数据库。
    写数据库由 generate_and_cache_mistake_explanation() 负责。
    """
    client = get_deepseek_client()
    if client is None:
        return None

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=build_explanation_prompt(mistake),
            temperature=0.3,
            stream=False,
        )
        content = response.choices[0].message.content or ""
        explanation = content.strip()
        if not explanation:
            print("[AI错误] DeepSeek 返回了空讲解。")
            return None
        return explanation
    except Exception as exc:
        print(f"[AI错误] 生成错题讲解失败：{exc}")
        return None


def generate_and_cache_mistake_explanation(
    mistake_id: int,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    给指定错题生成讲解，并缓存到 mistakes.ai_explanation。

    参数：
      mistake_id：错题ID。
      force_refresh：是否强制重新生成。

    工作流程：
      1. 从数据库查错题详情。
      2. 如果已有 ai_explanation 且不强制刷新，直接返回缓存。
      3. 调 DeepSeek 生成讲解。
      4. 写回 ai_explanation 字段。
    """
    mistake = mistake_db.get_mistake_detail(mistake_id)
    if mistake is None:
        return {
            "saved": False,
            "cached": False,
            "mistake_id": mistake_id,
            "explanation": None,
            "message": "找不到这道错题。",
        }

    cached_explanation = str(mistake.get("ai_explanation") or "").strip()
    if cached_explanation and not force_refresh:
        return {
            "saved": True,
            "cached": True,
            "mistake_id": mistake_id,
            "explanation": cached_explanation,
            "message": "已读取缓存讲解，没有重复调用 DeepSeek。",
        }

    explanation = generate_mistake_explanation(mistake)
    if explanation is None:
        return {
            "saved": False,
            "cached": False,
            "mistake_id": mistake_id,
            "explanation": None,
            "message": "AI 讲解生成失败。",
        }

    ok = mistake_db.update_mistake_ai_explanation(mistake_id, explanation)
    return {
        "saved": ok,
        "cached": False,
        "mistake_id": mistake_id,
        "explanation": explanation,
        "message": "AI 讲解已生成并写入数据库。" if ok else "AI 讲解已生成，但写入数据库失败。",
    }


def build_reasoning_tags_prompt(mistake: dict[str, Any]) -> list[dict[str, str]]:
    """
    构造提取“解题思路 / 能力 / 易错点”标签的 messages。

    这些标签不是知识点分类，而是描述“解题时用到的方法和容易犯的错”，
    目的是让相似题推荐能跨知识点找到思路相近的题
    （例如一元二次方程漏根 ↔ 二次函数求 x 轴交点漏解）。
    """
    system_prompt = """
你是初中数学解题分析老师。请从一道错题里提取“解题思路 / 能力 / 易错点”标签。

用途：在不同知识点之间找“解题思路相近”的题，所以标签要跨知识点通用。

要求：
1. 标签描述解题用到的方法、能力或典型错误，不要用具体知识点名称当标签。
   可参考风格：因式分解、判别式判断根、配方、移项变号、去分母、去括号漏乘、
   数形结合、分类讨论、代入求参数、联立求交点、检验代回、漏根漏解、符号错误。
2. 输出 3-6 个短词标签，中文。
3. 只返回一个 JSON 对象，不要解释、不要 Markdown：
   {"tags": ["因式分解", "漏根漏解"]}
""".strip()

    user_prompt = f"""
【题目】
{mistake.get("question_text")}

【所属知识点】
{mistake.get("knowledge_point_name")}

【学生的错误答案】
{mistake.get("student_answer")}

【学生的错误原因】
{mistake.get("error_reason") or "未填写"}

【正确答案】
{mistake.get("correct_answer")}

【详细解析】
{mistake.get("detailed_solution")}
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def generate_reasoning_tags(mistake: dict[str, Any]) -> list[str] | None:
    """调用 DeepSeek 为一道错题提取解题思路标签，返回标签列表或 None。"""
    client = get_deepseek_client()
    if client is None:
        return None

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=build_reasoning_tags_prompt(mistake),
            temperature=0,
            stream=False,
        )
        content = response.choices[0].message.content or ""
        data = extract_json_object(content)
        if not data:
            return None
        raw = data.get("tags")
        if not isinstance(raw, list):
            return None
        tags: list[str] = []
        for item in raw:
            tag = str(item).strip()
            if tag and tag not in tags:
                tags.append(tag)
            if len(tags) >= 6:
                break
        return tags or None
    except Exception as exc:
        print(f"[AI错误] 提取解题思路标签失败：{exc}")
        return None


def generate_and_cache_reasoning_tags(
    mistake_id: int,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    给指定错题生成解题思路标签，并缓存到 mistakes.reasoning_tags（JSON 字符串）。

    和讲解缓存同样的思路：已有标签且不强制刷新时直接读缓存，不重复调用 DeepSeek。
    """
    mistake = mistake_db.get_mistake_detail(mistake_id)
    if mistake is None:
        return {"saved": False, "cached": False, "tags": [], "message": "找不到这道错题。"}

    existing = str(mistake.get("reasoning_tags") or "").strip()
    if existing and not force_refresh:
        try:
            cached = json.loads(existing)
        except (json.JSONDecodeError, TypeError):
            cached = []
        return {
            "saved": True,
            "cached": True,
            "tags": cached if isinstance(cached, list) else [],
            "message": "已读取缓存标签，没有重复调用 DeepSeek。",
        }

    tags = generate_reasoning_tags(mistake)
    if not tags:
        return {"saved": False, "cached": False, "tags": [], "message": "解题思路标签生成失败。"}

    ok = mistake_db.update_mistake_reasoning_tags(
        mistake_id, json.dumps(tags, ensure_ascii=False)
    )
    return {
        "saved": ok,
        "cached": False,
        "tags": tags,
        "message": "解题思路标签已生成并写入。" if ok else "标签已生成，但写入数据库失败。",
    }


def backfill_reasoning_tags(force_refresh: bool = False) -> dict[str, Any]:
    """
    批量为缺少解题思路标签的错题生成标签。

    force_refresh=False：只处理还没有标签的题（增量，成本可控）。
    force_refresh=True：所有题重新生成（会对每道题都调用一次 DeepSeek）。
    """
    mistakes = mistake_db.get_all_mistakes_with_knowledge()
    targets = [
        m
        for m in mistakes
        if force_refresh or not str(m.get("reasoning_tags") or "").strip()
    ]

    if not targets:
        return {
            "total": len(mistakes),
            "processed": 0,
            "generated": 0,
            "failed": 0,
            "message": "所有错题都已有解题思路标签，无需生成。",
        }

    if get_deepseek_client() is None:
        return {
            "total": len(mistakes),
            "processed": 0,
            "generated": 0,
            "failed": 0,
            "message": f"缺少环境变量 {DEEPSEEK_API_KEY_ENV}，无法生成标签。",
        }

    generated = 0
    failed = 0
    for mistake in targets:
        tags = generate_reasoning_tags(mistake)
        if tags and mistake_db.update_mistake_reasoning_tags(
            int(mistake["id"]), json.dumps(tags, ensure_ascii=False)
        ):
            generated += 1
        else:
            failed += 1

    return {
        "total": len(mistakes),
        "processed": len(targets),
        "generated": generated,
        "failed": failed,
        "message": f"已为 {generated} 道错题生成解题思路标签（失败 {failed} 道）。",
    }


def build_learning_report_data(overview: dict[str, Any]) -> dict[str, Any]:
    """
    把完整统计概览压缩成适合发给 DeepSeek 的数据。

    注意：
      这里不发送每道题的完整题目内容，只发送统计结果和知识点层级摘要。
      这样更省 token，也更适合后面真实学生数据的隐私边界。
    """
    weak_points = []
    for item in overview.get("weakest_points", []):
        weak_points.append({
            "knowledge_point_id": item["knowledge_point_id"],
            "knowledge_point_name": item["knowledge_point_name"],
            "parent_name": item["parent_name"],
            "grade": item["grade"],
            "chapter": item["chapter"],
            "mistake_count": item["mistake_count"],
            "unmastered_count": item["unmastered_count"],
            "status_counts": item["status_counts"],
            "mastery_rate": item["mastery_rate"],
            "common_mistakes": item["common_mistakes"],
        })

    parent_areas = []
    for item in overview.get("by_parent_area", [])[:8]:
        parent_areas.append({
            "area_name": item["area_name"],
            "mistake_count": item["mistake_count"],
            "unmastered_count": item["unmastered_count"],
            "mastery_rate": item["mastery_rate"],
            "knowledge_points": item["knowledge_points"],
        })

    return {
        "统计口径": (
            "只统计数据库里真实录入的错题；每道错题算一次；"
            "同题同错答同知识点的重复测试记录默认只保留最新一条。"
        ),
        "总记录数": overview["total_records"],
        "去重后错题数": overview["total_mistakes"],
        "忽略的重复记录数": overview["duplicate_records_ignored"],
        "掌握状态分布": overview["status_counts"],
        "整体掌握率": overview["overall_mastery_rate"],
        "待复习错题数": overview["pending_review_count"],
        "薄弱知识点": weak_points,
        "按上级知识点聚合": parent_areas,
    }


def generate_learning_report(min_mistakes: int = 3) -> dict[str, Any]:
    """
    生成深度学情报告。

    流程：
      1. 先用本地 SQLite 统计错题概览。
      2. 如果错题太少，诚实提示数据不足，不调用 DeepSeek。
      3. 如果数据足够，把统计摘要发给 DeepSeek 生成报告。
    """
    overview = mistake_db.build_learning_overview(deduplicate=True)
    total_mistakes = overview.get("total_mistakes", 0)

    if total_mistakes < min_mistakes:
        report = (
            "## 学情报告暂不生成\n\n"
            f"当前去重后只有 {total_mistakes} 道错题，数据量还比较少。\n\n"
            "为了避免过度解读，建议至少录入 3 道以上、覆盖不同知识点的错题后，"
            "再生成更可靠的学情报告。"
        )
        return {
            "generated": False,
            "overview": overview,
            "report": report,
            "message": "错题数量不足，未调用 DeepSeek。",
        }

    client = get_deepseek_client()
    if client is None:
        return {
            "generated": False,
            "overview": overview,
            "report": None,
            "message": f"缺少环境变量 {DEEPSEEK_API_KEY_ENV}，无法生成 AI 学情报告。",
        }

    report_data = build_learning_report_data(overview)

    system_prompt = """
你是一位懂初中数学教学和错题分析的学习顾问。

请根据错题统计数据，生成一份给家长/老师看的学情报告。

要求：
1. 先说明统计口径，特别是“每道错题算一次”和“重复测试记录已去重”。
2. 报告必须包括：
   - 孩子整体情况概览：共录入多少错题、去重后多少道、掌握率、待复习数量。
   - 薄弱知识点分析：哪些知识点反复出错。
   - 层级分析：结合 parent_name 或上级知识点，指出哪个大方向偏弱，例如“代数中的方程部分较薄弱”。
   - 针对性建议：每个薄弱知识点建议怎么复习。
   - 鼓励性的结语。
3. 语气专业、温和、务实，不要制造焦虑。
4. 不要编造数据库里没有的错题或知识点。
5. 用 Markdown 输出，标题清晰，适合直接展示给家长/老师。
""".strip()

    user_prompt = (
        "下面是本地 SQLite 统计出的错题学情数据，请生成报告：\n\n"
        f"{json.dumps(report_data, ensure_ascii=False, indent=2)}"
    )

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            stream=False,
        )
        report = (response.choices[0].message.content or "").strip()
        if not report:
            return {
                "generated": False,
                "overview": overview,
                "report": None,
                "message": "DeepSeek 返回了空报告。",
            }
        return {
            "generated": True,
            "overview": overview,
            "report": report,
            "message": "AI 学情报告已生成。",
        }
    except Exception as exc:
        print(f"[AI错误] 生成学情报告失败：{exc}")
        return {
            "generated": False,
            "overview": overview,
            "report": None,
            "message": "DeepSeek 调用失败，暂时无法生成学情报告。",
        }
