"""
AI 错题讲解测试脚本
==================

这个脚本测试第 4 步：
  1. 找到之前录入的一元二次方程错题。
  2. 调 DeepSeek 生成针对学生具体错误的讲解。
  3. 把讲解写回 mistakes.ai_explanation 字段。
  4. 打印讲解，人工检查它有没有针对“因式分解配错”来讲。
"""

import os
import sys

import mistake_ai
import mistake_db


# 避免 Windows 终端打印 x² 这类字符时报编码错误。
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def print_section(title: str):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def find_or_create_quadratic_mistake() -> int | None:
    """
    找到那道测试用的一元二次方程错题。

    如果当前数据库里没有，就直接补录一条。
    这里不再调用自动归类，避免测试讲解时额外多调用一次 DeepSeek。
    """
    mistake_db.create_tables()
    mistake_db.seed_core_knowledge_points()

    quadratic_id = mistake_db.get_knowledge_point_id("一元二次方程的解法", "初三")
    if quadratic_id is None:
        print("找不到“一元二次方程的解法”知识点。")
        return None

    mistakes = mistake_db.get_mistakes_by_knowledge_point(quadratic_id)
    for item in mistakes:
        if "x² - 5x + 6" in item["question_text"] and "x = 1" in item["student_answer"]:
            return int(item["id"])

    return mistake_db.add_mistake(
        question_text="解方程：x² - 5x + 6 = 0。",
        grade="初三",
        question_type="解答",
        difficulty="中等",
        knowledge_point_id=quadratic_id,
        correct_answer="x = 2 或 x = 3",
        detailed_solution="x² - 5x + 6 可以分解为 (x - 2)(x - 3)，所以 x = 2 或 x = 3。",
        student_answer="x = 1 或 x = 6",
        error_reason="因式分解时把两个因数配错了。",
    )


def main():
    if not os.environ.get(mistake_ai.DEEPSEEK_API_KEY_ENV):
        print(f"[配置错误] 请先设置环境变量 {mistake_ai.DEEPSEEK_API_KEY_ENV}")
        print("PowerShell 示例：")
        print(f"$env:{mistake_ai.DEEPSEEK_API_KEY_ENV} = Read-Host '请输入 DeepSeek API Key'")
        return

    print_section("1. 找到测试错题")
    mistake_id = find_or_create_quadratic_mistake()
    if mistake_id is None:
        print("没有可用错题，测试停止。")
        return
    print(f"测试错题ID：{mistake_id}")

    mistake = mistake_db.get_mistake_detail(mistake_id)
    print(f"题目：{mistake['question_text']}")
    print(f"学生错误答案：{mistake['student_answer']}")
    print(f"学生错误原因：{mistake['error_reason']}")
    print(f"知识点：{mistake['knowledge_point_name']}")

    print_section("2. 生成并缓存 AI 讲解")
    result = mistake_ai.generate_and_cache_mistake_explanation(
        mistake_id=mistake_id,
        force_refresh=True,
    )
    print(result["message"])

    if not result["saved"] or not result["explanation"]:
        print("讲解生成失败，测试停止。")
        return

    print_section("3. 打印 AI 讲解")
    print(result["explanation"])

    print_section("4. 检查是否写回数据库")
    updated = mistake_db.get_mistake_detail(mistake_id)
    saved_text = (updated.get("ai_explanation") or "").strip()
    print(f"数据库中的 ai_explanation 字符数：{len(saved_text)}")
    print("是否提到“因式分解”：", "因式分解" in saved_text)
    print("是否提到“配错”：", "配错" in saved_text or "配对" in saved_text)

    print_section("测试完成")
    print("请人工看上面的讲解：重点检查它有没有针对“因式分解配错”这个具体错误来讲。")


if __name__ == "__main__":
    main()
