"""
测试“相似题推荐”功能
====================

测试流程：
  1. 确保有一批方程/函数方向的测试错题。
  2. 把 SQLite 错题同步到 Chroma 本地向量库。
  3. 选一道一元二次方程错题，打印两层推荐结果。
"""

from __future__ import annotations

import os
import sys

import mistake_db
import mistake_recommender
import seed_similar_mistake_samples


if hasattr(sys.stdout, "reconfigure"):
    # Windows 控制台默认可能是 GBK，遇到 x²、≤ 这类数学字符会打印失败。
    sys.stdout.reconfigure(encoding="utf-8")


def find_target_mistake() -> dict | None:
    """
    找一题适合测试的目标错题。

    优先找“x^2 - 7x + 12 = 0”这道因式分解型一元二次方程，
    因为它容易和二次函数零点、判别式、因式分解题产生跨知识点相似推荐。
    """
    mistakes = mistake_db.get_all_mistakes_with_knowledge()
    for item in mistakes:
        if "x^2 - 7x + 12" in item.get("question_text", ""):
            return item

    for item in mistakes:
        if item.get("knowledge_point_name") == "一元二次方程的解法":
            return item

    return mistakes[0] if mistakes else None


def print_recommendations(title: str, items: list[dict]) -> None:
    """把推荐结果打印成方便人工检查的格式。"""
    print(f"\n{title}")
    print("-" * 70)
    if not items:
        print("暂无推荐。")
        return

    for index, item in enumerate(items, start=1):
        distance_text = "" if item.get("distance") is None else f" | distance={item['distance']}"
        print(
            f"{index}. [{item['recommendation_type']}] "
            f"#{item['mistake_id']} {item['knowledge_point_name']}{distance_text}"
        )
        print(f"   题目：{item['question_text']}")
        print(f"   错因：{item['error_reason']}")
        print(f"   推荐理由：{item['reason']}")


def main() -> None:
    """端到端跑一遍相似题推荐。"""
    print("1. 检查并准备测试错题")
    if os.environ.get("DEEPSEEK_API_KEY"):
        seed_stats = seed_similar_mistake_samples.seed_samples()
        print(f"样例准备结果：{seed_stats}")
    else:
        print("未设置 DEEPSEEK_API_KEY，跳过自动归类录入，只使用数据库里已有错题。")

    print("\n2. 同步 SQLite 错题到 Chroma 向量库")
    sync_result = mistake_recommender.sync_mistakes_to_vector_store()
    print(sync_result)

    print("\n3. 选择目标错题")
    target = find_target_mistake()
    if not target:
        print("数据库里没有错题，无法测试推荐。")
        return

    print(f"目标错题ID：{target['id']}")
    print(f"知识点：{target['knowledge_point_name']}")
    print(f"题目：{target['question_text']}")
    print(f"错因：{target.get('error_reason')}")

    print("\n4. 生成两层推荐")
    result = mistake_recommender.recommend_similar_mistakes(
        int(target["id"]),
        same_knowledge_limit=5,
        cross_knowledge_limit=5,
        ensure_synced=False,
    )

    print_recommendations("第一层：同知识点推荐", result["same_knowledge"])
    print_recommendations("第二层：跨知识点思路相近推荐", result["cross_knowledge"])


if __name__ == "__main__":
    main()
