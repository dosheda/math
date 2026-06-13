"""
K12 数学错题助手 —— 相似题推荐模块
==================================

这个文件负责两层推荐：
  1. 数据库层：同一知识点下的其他错题，直接相关。
  2. RAG 层：用 Chroma 向量检索，从其他知识点里找“解题思路相近”的错题。

注意：
  这里只使用 Chroma 本地 PersistentClient，不启动 HTTP server，不开放任何网络端口。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb
from chromadb.utils import embedding_functions

import mistake_db


# 向量库固定放在项目目录下，和 SQLite 数据库一样本地落盘。
BASE_DIR = Path(__file__).resolve().parent
CHROMA_DB_PATH = BASE_DIR / "mistake_chroma_db"
COLLECTION_NAME = "math_mistakes"

# 和古诗词项目保持一致：Chroma 内置 sentence-transformers wrapper + BGE 中文模型。
EMBEDDING_MODEL_NAME = "BAAI/bge-small-zh-v1.5"


@lru_cache(maxsize=1)
def load_embedding_function():
    """
    加载中文 embedding 函数。

    第一次运行会加载模型，之后同一个 Python 进程内会复用缓存。
    """
    print("正在加载中文 embedding 模型（BAAI/bge-small-zh-v1.5）...")
    print("（首次运行会下载或加载模型缓存，之后会更快）")
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL_NAME,
        device="cpu",
        normalize_embeddings=True,
    )


def get_chroma_collection():
    """
    打开本地 Chroma collection。

    get_or_create_collection 的好处是：
      - 第一次同步时自动建库。
      - 后续推荐时直接复用已有库。
    """
    embedding_fn = load_embedding_function()
    client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"description": "K12 数学错题相似题推荐向量库"},
    )


def build_mistake_retrieval_text(mistake: dict[str, Any]) -> str:
    """
    把一道错题整理成适合向量检索的文本。

    这里不只放题目，也放知识点、错误原因和解析。
    原因是：我们想找的是“解题思路相近”，不是只找表面文字相似。
    """
    tags = extract_reasoning_tags(mistake)
    tag_text = "，".join(tags) if tags else "无"
    return "\n".join(
        [
            f"题目：{mistake.get('question_text') or ''}",
            f"知识点：{mistake.get('knowledge_point_name') or ''}",
            f"章节：{mistake.get('knowledge_point_chapter') or ''}",
            f"解题思路标签：{tag_text}",
            f"相似能力标签：{tag_text}",
            f"学生错误答案：{mistake.get('student_answer') or ''}",
            f"错误原因：{mistake.get('error_reason') or ''}",
            f"正确答案：{mistake.get('correct_answer') or ''}",
            f"详细解析：{mistake.get('detailed_solution') or ''}",
        ]
    )


def extract_reasoning_tags(mistake: dict[str, Any]) -> list[str]:
    """
    从题目、错因、解析里提取“解题思路标签”。

    这不是知识点分类，而是为了让向量检索更懂“为什么相似”：
      比如一元二次方程的因式分解，和二次函数求 x 轴交点，
      虽然知识点不同，但都可能用到“二次式因式分解、求零点”。
    """
    text = "\n".join(
        str(mistake.get(key) or "")
        for key in [
            "question_text",
            "knowledge_point_name",
            "error_reason",
            "correct_answer",
            "detailed_solution",
        ]
    )

    tag_rules = [
        ("因式分解", ["因式分解", "分解", "(x -", "(x +"]),
        ("漏根/漏解", ["漏根", "漏掉", "只写了一个", "±"]),
        ("判别式判断根的个数", ["判别式", "Δ", "实数根", "只有一个交点", "没有交点"]),
        ("二次式求零点", ["x^2", "二次函数", "与 x 轴", "交点", "零点"]),
        ("移项变号", ["移项", "变号", "符号写错"]),
        ("去括号漏乘", ["去括号", "漏乘"]),
        ("去分母漏乘", ["去分母", "同乘", "分母"]),
        ("除以负数不等号变向", ["除以负", "乘以负", "不等号", "变向"]),
        ("函数代入求值", ["代入", "经过点", "求 k", "求 y"]),
        ("数形结合", ["图像", "象限", "开口", "对称轴", "顶点", "x 轴"]),
        ("联立方程求交点", ["联立", "交点", "两个 y 相等"]),
        ("检验与代回", ["代回", "检验", "核对"]),
    ]

    tags = []
    for tag, keywords in tag_rules:
        if any(keyword in text for keyword in keywords):
            tags.append(tag)
    return tags


def build_mistake_metadata(mistake: dict[str, Any]) -> dict[str, Any]:
    """
    给 Chroma 存 metadata。

    Chroma metadata 只能放简单类型，所以这里把 None 都转成空字符串。
    """
    return {
        "mistake_id": int(mistake["id"]),
        "knowledge_point_id": int(mistake["knowledge_point_id"]),
        "knowledge_point_name": mistake.get("knowledge_point_name") or "",
        "grade": mistake.get("grade") or "",
        "question_type": mistake.get("question_type") or "",
        "difficulty": mistake.get("difficulty") or "",
        "mastery_status": mistake.get("mastery_status") or "",
    }


def sync_mistakes_to_vector_store(reset: bool = False) -> dict[str, Any]:
    """
    把 SQLite 里的错题同步到 Chroma 向量库。

    参数：
      reset=False：默认增量 upsert，同一个 mistake_id 会覆盖更新。
      reset=True：先删除旧 collection，再重新建库。一般测试时才需要。
    """
    try:
        mistake_db.create_tables()
        mistake_db.seed_core_knowledge_points()

        embedding_fn = load_embedding_function()
        client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))

        if reset:
            try:
                client.delete_collection(COLLECTION_NAME)
                print("已删除旧的错题向量库 collection，准备重建。")
            except Exception:
                # collection 不存在时不用报错，说明本来就是第一次建。
                pass

        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
            metadata={"description": "K12 数学错题相似题推荐向量库"},
        )

        mistakes = mistake_db.get_all_mistakes_with_knowledge()
        if not mistakes:
            return {"synced_count": 0, "message": "数据库里还没有错题，未同步。"}

        ids = [f"mistake_{item['id']}" for item in mistakes]
        documents = [build_mistake_retrieval_text(item) for item in mistakes]
        metadatas = [build_mistake_metadata(item) for item in mistakes]

        # upsert 可以反复运行：已有 ID 会更新，没有的 ID 会新增。
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return {
            "synced_count": len(ids),
            "collection_count": collection.count(),
            "message": "错题已同步到本地 Chroma 向量库。",
        }
    except Exception as exc:
        print(f"[向量库错误] 同步错题到 Chroma 失败：{exc}")
        return {"synced_count": 0, "collection_count": 0, "message": "同步失败。"}


def normalize_text(value: str | None) -> str:
    """推荐去重用：把题目和错答压成稳定文本。"""
    return " ".join(str(value or "").split())


def same_mistake_key(mistake: dict[str, Any]) -> tuple[int, str, str]:
    """
    判断两道推荐题是否其实是同一道重复测试题。

    口径和学情统计保持一致：同知识点、同题目、同学生错答，认为是重复。
    """
    return (
        int(mistake.get("knowledge_point_id") or 0),
        normalize_text(mistake.get("question_text")),
        normalize_text(mistake.get("student_answer")),
    )


def summarize_recommendation(
    mistake: dict[str, Any],
    recommendation_type: str,
    reason: str,
    distance: float | None = None,
) -> dict[str, Any]:
    """
    把推荐题整理成统一返回格式。

    recommendation_type：
      - 同知识点
      - 思路相近
    """
    return {
        "mistake_id": int(mistake["id"]),
        "recommendation_type": recommendation_type,
        "reason": reason,
        "distance": distance,
        "question_text": mistake.get("question_text"),
        "student_answer": mistake.get("student_answer"),
        "error_reason": mistake.get("error_reason"),
        "correct_answer": mistake.get("correct_answer"),
        "knowledge_point_id": int(mistake["knowledge_point_id"]),
        "knowledge_point_name": mistake.get("knowledge_point_name"),
        "grade": mistake.get("grade"),
        "difficulty": mistake.get("difficulty"),
    }


def recommend_same_knowledge_mistakes(
    target: dict[str, Any],
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    第一层推荐：同一知识点下的其他错题。

    这层不需要 RAG，直接用 SQLite 查询，解释性最强。
    """
    target_id = int(target["id"])
    target_key = same_mistake_key(target)
    candidates = mistake_db.get_mistakes_by_knowledge_point(int(target["knowledge_point_id"]))

    recommendations = []
    seen_keys = {target_key}
    for candidate in candidates:
        if int(candidate["id"]) == target_id:
            continue
        candidate_key = same_mistake_key(candidate)
        if candidate_key in seen_keys:
            continue
        seen_keys.add(candidate_key)
        recommendations.append(
            summarize_recommendation(
                candidate,
                recommendation_type="同知识点",
                reason="和当前错题属于同一个知识点，适合先做直接巩固。",
            )
        )
        if len(recommendations) >= limit:
            break

    return recommendations


def recommend_cross_knowledge_mistakes(
    target: dict[str, Any],
    limit: int = 5,
    search_k: int = 80,
) -> list[dict[str, Any]]:
    """
    第二层推荐：跨知识点找“思路相近”的错题。

    Chroma 会根据“题目 + 知识点 + 错因 + 解析”的语义相似度找候选，
    这里再过滤掉同一知识点，只保留跨知识点结果。
    """
    try:
        collection = get_chroma_collection()
        query_text = build_mistake_retrieval_text(target)
        # 先多取一些候选，再过滤“同知识点”和“重复知识点”。
        # 如果只取很少，过滤后可能不够返回数量。
        collection_count = collection.count()
        if collection_count == 0:
            return []
        actual_search_k = min(max(search_k, limit * 10), collection_count)
        result = collection.query(
            query_texts=[query_text],
            n_results=actual_search_k,
            include=["documents", "metadatas", "distances"],
        )

        ids = result.get("ids", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        target_id = int(target["id"])
        target_kp_id = int(target["knowledge_point_id"])

        recommendations = []
        seen_ids = {target_id}
        seen_kp_ids = {target_kp_id}
        for item_id, metadata, distance in zip(ids, metadatas, distances):
            if not metadata:
                continue
            mistake_id = int(metadata.get("mistake_id") or str(item_id).replace("mistake_", ""))
            kp_id = int(metadata.get("knowledge_point_id") or 0)
            if mistake_id in seen_ids or kp_id in seen_kp_ids:
                continue

            detail = mistake_db.get_mistake_detail(mistake_id)
            if not detail:
                continue

            seen_ids.add(mistake_id)
            seen_kp_ids.add(kp_id)
            recommendations.append(
                summarize_recommendation(
                    detail,
                    recommendation_type="思路相近",
                    reason="向量检索认为它和当前错题的解题思路或易错点相近，但知识点不同。",
                    distance=round(float(distance), 4) if distance is not None else None,
                )
            )
            if len(recommendations) >= limit:
                break

        return recommendations
    except Exception as exc:
        print(f"[向量库错误] 跨知识点相似题检索失败：{exc}")
        return []


def recommend_similar_mistakes(
    mistake_id: int,
    same_knowledge_limit: int = 5,
    cross_knowledge_limit: int = 5,
    ensure_synced: bool = True,
) -> dict[str, Any]:
    """
    给定一道错题 ID，返回两层相似题推荐。

    返回结构：
      {
        "target": 当前错题摘要,
        "same_knowledge": 同知识点推荐,
        "cross_knowledge": 思路相近推荐,
        "recommendations": 合并列表
      }
    """
    target = mistake_db.get_mistake_detail(mistake_id)
    if not target:
        return {
            "target": None,
            "same_knowledge": [],
            "cross_knowledge": [],
            "recommendations": [],
            "message": f"没有找到错题ID：{mistake_id}",
        }

    if ensure_synced:
        sync_mistakes_to_vector_store()

    same_knowledge = recommend_same_knowledge_mistakes(
        target,
        limit=same_knowledge_limit,
    )
    cross_knowledge = recommend_cross_knowledge_mistakes(
        target,
        limit=cross_knowledge_limit,
        search_k=max(80, cross_knowledge_limit * 12),
    )

    # 合并时再按 ID 去重，避免同一道题通过不同入口重复出现。
    combined = []
    seen_ids = {int(target["id"])}
    for item in same_knowledge + cross_knowledge:
        if item["mistake_id"] in seen_ids:
            continue
        seen_ids.add(item["mistake_id"])
        combined.append(item)

    return {
        "target": summarize_recommendation(
            target,
            recommendation_type="当前错题",
            reason="用户指定的错题。",
        ),
        "same_knowledge": same_knowledge,
        "cross_knowledge": cross_knowledge,
        "recommendations": combined,
        "message": "相似题推荐已生成。",
    }
