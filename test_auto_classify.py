"""
AI 自动归类测试脚本
==================

这个脚本测试第 3 步：
  1. 初中数学题：应该匹配到知识点，并正常录入错题表。
  2. 小学数学题：应该返回“超出支持范围”。
  3. 非数学题：应该返回“超出支持范围”。

注意：
  这个测试会真实调用 DeepSeek，所以运行前必须设置 DEEPSEEK_API_KEY。
"""

import os
import sys
from pprint import pprint

import mistake_ai
import mistake_db


# 避免 Windows 终端打印数学符号时报编码错误。
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def print_section(title: str):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def print_result(result: dict):
    """统一打印 AI 归类结果。"""
    pprint(result)
    if result.get("supported"):
        print(f"✅ 匹配知识点ID：{result.get('knowledge_point_id')}")
        print(f"✅ 匹配知识点名称：{result.get('knowledge_point_name')}")
    else:
        print(f"🚧 超出支持范围：{result.get('reason')}")


def main():
    if not os.environ.get(mistake_ai.DEEPSEEK_API_KEY_ENV):
        print(f"[配置错误] 请先设置环境变量 {mistake_ai.DEEPSEEK_API_KEY_ENV}")
        print("PowerShell 示例：")
        print(f"$env:{mistake_ai.DEEPSEEK_API_KEY_ENV} = Read-Host '请输入 DeepSeek API Key'")
        return

    print_section("0. 建表并预置知识点")
    mistake_db.create_tables()
    knowledge_points = mistake_db.seed_core_knowledge_points()
    print(f"知识点数量：{len(knowledge_points)}")

    print_section("1. 初中题：一元二次方程，应该匹配并录入")
    result = mistake_ai.add_mistake_with_auto_classification(
        question_text="解方程：x² - 5x + 6 = 0。",
        grade="初三",
        question_type="解答",
        difficulty="中等",
        correct_answer="x = 2 或 x = 3",
        detailed_solution="x² - 5x + 6 可以分解为 (x - 2)(x - 3)，所以 x = 2 或 x = 3。",
        student_answer="x = 1 或 x = 6",
        error_reason="因式分解时把两个因数配错了。",
    )
    pprint(result)
    if result["saved"]:
        print(f"✅ 已录入错题ID：{result['mistake_id']}")
    else:
        print("⚠️ 这道初中题没有录入，请检查 AI 判断原因。")

    print_section("2. 小学题：简单乘法应用题，应该超出支持范围")
    primary_result = mistake_ai.classify_question_knowledge_point(
        "小明买了 3 盒彩笔，每盒 12 支，一共有多少支彩笔？"
    )
    print_result(primary_result)

    print_section("3. 非数学题：语文古诗题，应该超出支持范围")
    non_math_result = mistake_ai.classify_question_knowledge_point(
        "请解释《静夜思》表达了诗人怎样的思想感情。"
    )
    print_result(non_math_result)

    print_section("4. 查看一元二次方程相关错题")
    quadratic_id = mistake_db.get_knowledge_point_id("一元二次方程的解法", "初三")
    if quadratic_id is not None:
        mistakes = mistake_db.get_mistakes_by_knowledge_point(quadratic_id)
        pprint(mistakes[:3])
    else:
        print("没有找到“一元二次方程的解法”这个知识点。")

    print_section("测试完成")
    print("请重点看：初中题是否匹配到一元二次方程，小学题/非数学题是否被判为超范围。")


if __name__ == "__main__":
    main()
