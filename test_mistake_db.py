"""
数据库链路测试脚本
================

运行这个文件会做 6 件事：
  1. 建表
  2. 预置初中数学核心知识点
  3. 录入 2 道测试错题
  4. 按知识点查询错题
  5. 按掌握状态查询错题
  6. 更新掌握状态和复习次数，再统计每个知识点的错题数

这不是正式单元测试框架，而是给 vibe coding 阶段用的“冒烟测试”：
先确认最核心的数据链路能跑通。
"""

import sys
from pprint import pprint

import mistake_db


# Windows PowerShell 有时默认用 GBK 输出，遇到 ² 这类数学字符会报错。
# 这里强制测试脚本用 UTF-8 打印，避免“数据库没问题但终端打印崩了”。
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def print_section(title: str):
    """打印分隔标题，让终端输出更容易看。"""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main():
    print_section("1. 建表")
    if not mistake_db.create_tables():
        print("建表失败，测试停止。")
        return
    print(f"建表成功，数据库位置：{mistake_db.DB_PATH}")

    print_section("2. 预置初中数学核心知识点")
    knowledge_points = mistake_db.seed_core_knowledge_points()
    print(f"当前可用知识点数量：{len(knowledge_points)}")
    for name, kp_id in list(knowledge_points.items())[:8]:
        print(f"- {kp_id}: {name}")

    print_section("3. 录入 2 道测试错题")
    linear_equation_id = mistake_db.get_knowledge_point_id("一元一次方程", "初一")
    pythagorean_id = mistake_db.get_knowledge_point_id("勾股定理", "初二")

    if linear_equation_id is None or pythagorean_id is None:
        print("找不到测试需要的知识点，测试停止。")
        return

    mistake_1_id = mistake_db.add_mistake(
        question_text="解方程：3x - 5 = 10。",
        grade="初一",
        question_type="解答",
        difficulty="简单",
        knowledge_point_id=linear_equation_id,
        correct_answer="x = 5",
        detailed_solution="3x - 5 = 10，先两边同时加 5，得到 3x = 15，再两边同时除以 3，得到 x = 5。",
        student_answer="x = 3",
        error_reason="移项后没有正确计算 10 + 5。",
        ai_explanation="可以把 -5 看成挡在 3x 前面的障碍，先用 +5 把它抵消，再除以 3。",
    )
    print(f"错题1 ID：{mistake_1_id}")

    mistake_2_id = mistake_db.add_mistake(
        question_text="直角三角形两条直角边分别为 6 和 8，求斜边长。",
        grade="初二",
        question_type="解答",
        difficulty="中等",
        knowledge_point_id=pythagorean_id,
        correct_answer="10",
        detailed_solution="根据勾股定理，斜边² = 6² + 8² = 36 + 64 = 100，所以斜边 = 10。",
        student_answer="14",
        error_reason="把两条直角边直接相加了，没有先平方再开方。",
        ai_explanation=None,
    )
    print(f"错题2 ID：{mistake_2_id}")

    print_section("4. 按知识点查询错题：一元一次方程")
    linear_mistakes = mistake_db.get_mistakes_by_knowledge_point(linear_equation_id)
    pprint(linear_mistakes)

    print_section("5. 按掌握状态查询错题：未掌握")
    not_mastered = mistake_db.get_mistakes_by_mastery_status("未掌握")
    pprint(not_mastered)

    print_section("6. 更新错题1为“复习中”，复习次数 +1")
    if mistake_1_id is not None:
        ok = mistake_db.update_mistake_mastery(
            mistake_id=mistake_1_id,
            mastery_status="复习中",
            increase_review_count=True,
        )
        print(f"更新结果：{ok}")
        reviewed = mistake_db.get_mistakes_by_mastery_status("复习中")
        pprint(reviewed)

    print_section("7. 统计每个知识点的错题数")
    counts = mistake_db.count_mistakes_by_knowledge_point()
    for item in counts[:10]:
        print(
            f"{item['knowledge_point_id']:>2} | "
            f"{item['grade']} | "
            f"{item['knowledge_point_name']} | "
            f"错题数：{item['mistake_count']}"
        )

    print_section("测试完成")
    print("如果上面能看到测试错题、掌握状态更新和错题数统计，说明数据库第一步已经跑通。")


if __name__ == "__main__":
    main()
