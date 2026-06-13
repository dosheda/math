"""
错题本 + 深度学情分析测试脚本
============================

这个脚本测试最后一步：
  1. 确保库里有几道不同知识点的错题。
  2. 演示错题本视图：按知识点、按掌握状态、按年级、待复习。
  3. 生成统计概览：错题数、掌握状态、薄弱点、掌握率。
  4. 调 DeepSeek 生成给家长/老师看的学情报告。
"""

import os
import sys

import mistake_ai
import mistake_db


# Windows 终端可能不是 UTF-8，这里避免数学符号和中文打印出错。
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def print_section(title: str):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def mistake_exists(question_text: str, student_answer: str, knowledge_point_id: int) -> bool:
    """检查样例错题是否已存在，避免测试脚本反复插入重复数据。"""
    for item in mistake_db.get_all_mistakes_with_knowledge():
        if (
            item["question_text"] == question_text
            and item["student_answer"] == student_answer
            and int(item["knowledge_point_id"]) == int(knowledge_point_id)
        ):
            return True
    return False


def add_sample_if_missing(
    question_text: str,
    knowledge_point_name: str,
    grade: str,
    question_type: str,
    difficulty: str,
    correct_answer: str,
    detailed_solution: str,
    student_answer: str,
    error_reason: str,
    mastery_status: str,
) -> int | None:
    """
    插入一条样例错题。

    这里直接用知识点名称查 ID，不调用 AI 自动归类。
    原因：这个脚本重点测试错题本和学情分析，不想额外消耗自动归类 API 调用。
    """
    knowledge_point_id = mistake_db.get_knowledge_point_id(knowledge_point_name, grade)
    if knowledge_point_id is None:
        print(f"[跳过] 找不到知识点：{knowledge_point_name} / {grade}")
        return None

    if mistake_exists(question_text, student_answer, knowledge_point_id):
        print(f"[已存在] {knowledge_point_name}：{question_text}")
        return None

    new_id = mistake_db.add_mistake(
        question_text=question_text,
        grade=grade,
        question_type=question_type,
        difficulty=difficulty,
        knowledge_point_id=knowledge_point_id,
        correct_answer=correct_answer,
        detailed_solution=detailed_solution,
        student_answer=student_answer,
        error_reason=error_reason,
        mastery_status=mastery_status,
    )
    print(f"[新增] 错题ID {new_id}：{knowledge_point_name}")
    return new_id


def ensure_sample_mistakes():
    """确保数据库里有覆盖不同知识点、不同掌握状态的样例错题。"""
    mistake_db.create_tables()
    mistake_db.seed_core_knowledge_points()

    add_sample_if_missing(
        question_text="一次函数 y = 2x + 3，当 x = -1 时，求 y 的值。",
        knowledge_point_name="一次函数图像与性质",
        grade="初二",
        question_type="填空",
        difficulty="简单",
        correct_answer="y = 1",
        detailed_solution="把 x = -1 代入 y = 2x + 3，得到 y = 2×(-1)+3 = 1。",
        student_answer="y = 5",
        error_reason="代入负数时把 2×(-1) 算成了 +2。",
        mastery_status="未掌握",
    )
    add_sample_if_missing(
        question_text="解不等式：-2x > 6。",
        knowledge_point_name="一元一次不等式",
        grade="初一",
        question_type="解答",
        difficulty="中等",
        correct_answer="x < -3",
        detailed_solution="两边同时除以 -2，不等号方向要改变，所以 x < -3。",
        student_answer="x > -3",
        error_reason="两边除以负数时忘记改变不等号方向。",
        mastery_status="未掌握",
    )
    add_sample_if_missing(
        question_text="计算：(x² - 9) / (x - 3)，并说明 x 的取值限制。",
        knowledge_point_name="分式运算",
        grade="初二",
        question_type="解答",
        difficulty="中等",
        correct_answer="x + 3，且 x ≠ 3",
        detailed_solution="x² - 9 = (x - 3)(x + 3)，约分后得 x + 3，但原分母 x - 3 不能为 0，所以 x ≠ 3。",
        student_answer="x + 3",
        error_reason="只做了约分，忘记写分母不为 0 的限制。",
        mastery_status="复习中",
    )
    add_sample_if_missing(
        question_text="已知两边及夹角对应相等，判断两个三角形是否全等。",
        knowledge_point_name="三角形全等",
        grade="初二",
        question_type="解答",
        difficulty="简单",
        correct_answer="全等，依据 SAS。",
        detailed_solution="两边及其夹角对应相等，可以用 SAS 判定两个三角形全等。",
        student_answer="不一定全等",
        error_reason="没有区分 SAS 和 SSA，把夹角条件看漏了。",
        mastery_status="已掌握",
    )


def print_mistake_brief(items: list[dict], limit: int = 5):
    """用简短格式打印错题列表，避免终端输出太长。"""
    for item in items[:limit]:
        print(
            f"#{item['id']} | {item['grade']} | {item['mastery_status']} | "
            f"{item['knowledge_point_name']} | {item['question_text']}"
        )
    if len(items) > limit:
        print(f"... 还有 {len(items) - limit} 条")


def main():
    print_section("1. 准备样例错题")
    ensure_sample_mistakes()

    print_section("2. 错题本视图：按知识点查（一元二次方程）")
    quadratic_id = mistake_db.get_knowledge_point_id("一元二次方程的解法", "初三")
    if quadratic_id:
        print_mistake_brief(mistake_db.get_mistakes_by_knowledge_point(quadratic_id))

    print_section("3. 错题本视图：按掌握状态查（未掌握）")
    print_mistake_brief(mistake_db.get_mistakes_by_mastery_status("未掌握"))

    print_section("4. 错题本视图：按年级查（初二）")
    print_mistake_brief(mistake_db.get_mistakes_by_grade("初二"))

    print_section("5. 错题本视图：待复习（未掌握 + 复习中）")
    pending = mistake_db.get_pending_review_mistakes()
    print(f"待复习错题数：{len(pending)}")
    print_mistake_brief(pending, limit=8)

    print_section("6. 统计概览")
    overview = mistake_db.build_learning_overview(deduplicate=True)
    print(f"数据库原始记录数：{overview['total_records']}")
    print(f"去重后错题数：{overview['total_mistakes']}")
    print(f"忽略重复记录数：{overview['duplicate_records_ignored']}")
    print(f"掌握状态分布：{overview['status_counts']}")
    print(f"整体掌握率：{overview['overall_mastery_rate']}%")
    print(f"待复习错题数：{overview['pending_review_count']}")

    print("\n薄弱知识点 Top：")
    for item in overview["weakest_points"]:
        print(
            f"- {item['knowledge_point_name']}（上级：{item['parent_name']}）"
            f" 错题{item['mistake_count']}道，待复习{item['unmastered_count']}道，"
            f"掌握率{item['mastery_rate']}%"
        )

    print("\n大方向聚合：")
    for item in overview["by_parent_area"]:
        print(
            f"- {item['area_name']}：错题{item['mistake_count']}道，"
            f"待复习{item['unmastered_count']}道，掌握率{item['mastery_rate']}%"
        )

    print_section("7. AI 学情报告")
    if not os.environ.get(mistake_ai.DEEPSEEK_API_KEY_ENV):
        print(f"未设置 {mistake_ai.DEEPSEEK_API_KEY_ENV}，跳过 AI 报告。")
        print("PowerShell 示例：")
        print(f"$env:{mistake_ai.DEEPSEEK_API_KEY_ENV} = Read-Host '请输入 DeepSeek API Key'")
        return

    report_result = mistake_ai.generate_learning_report(min_mistakes=3)
    print(report_result["message"])
    print()
    print(report_result["report"])


if __name__ == "__main__":
    main()
