"""
批量准备“相似题推荐”测试错题
================================

这个脚本专门做一件事：
  生成一批初中数学测试错题，并逐条走现有的 DeepSeek 自动归类流程录入数据库。

为什么不直接写 knowledge_point_id：
  因为我们要测试真实闭环：题目 -> 自动归类 -> 写入 SQLite。
  所以这里虽然样例里写了“期望知识点”，但只用于打印核对，不用于直接入库。
"""

from __future__ import annotations

import argparse
import os
from typing import Any

import mistake_ai
import mistake_db


DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"


# 这些样例故意集中在“方程与不等式”和“函数”两大方向。
# 同时穿插“移项变号、因式分解、判别式、数形结合”等共同思路，
# 方便后面测试跨知识点的语义相似推荐。
SAMPLE_MISTAKES: list[dict[str, str]] = [
    {
        "expected_knowledge_point": "一元一次方程",
        "question_text": "解方程：3(x - 2) + 4 = 2x + 9。",
        "grade": "初一",
        "question_type": "解答",
        "difficulty": "基础",
        "student_answer": "x = 7",
        "error_reason": "去括号时把 3(x - 2) 错写成 3x - 2，漏乘了括号里的 -2。",
        "correct_answer": "x = 11",
        "detailed_solution": "先去括号得 3x - 6 + 4 = 2x + 9，即 3x - 2 = 2x + 9。两边同时减去 2x，得到 x - 2 = 9，所以 x = 11。",
    },
    {
        "expected_knowledge_point": "一元一次方程",
        "question_text": "解方程：2(x + 5) - 3 = 5x + 1。",
        "grade": "初一",
        "question_type": "解答",
        "difficulty": "基础",
        "student_answer": "x = -2",
        "error_reason": "移项时把 2x - 5x 写成了 3x，符号方向弄反。",
        "correct_answer": "x = 2",
        "detailed_solution": "去括号得 2x + 10 - 3 = 5x + 1，即 2x + 7 = 5x + 1。移项得 6 = 3x，所以 x = 2。",
    },
    {
        "expected_knowledge_point": "一元一次方程",
        "question_text": "解方程：(x - 3) / 4 + 1 = x / 2。",
        "grade": "初一",
        "question_type": "解答",
        "difficulty": "中等",
        "student_answer": "x = -1",
        "error_reason": "去分母时没有把常数 1 也乘以 4。",
        "correct_answer": "x = 1",
        "detailed_solution": "两边同乘 4，得到 x - 3 + 4 = 2x，即 x + 1 = 2x，所以 x = 1。",
    },
    {
        "expected_knowledge_point": "一元一次方程",
        "question_text": "解方程：5 - 2x = 3x + 20。",
        "grade": "初一",
        "question_type": "解答",
        "difficulty": "基础",
        "student_answer": "x = 3",
        "error_reason": "把 -2x 移到右边、20 移到左边时变号混乱。",
        "correct_answer": "x = -3",
        "detailed_solution": "移项得 -2x - 3x = 20 - 5，即 -5x = 15，所以 x = -3。",
    },
    {
        "expected_knowledge_point": "一元一次方程",
        "question_text": "解方程：0.3x + 0.2 = 1.1。",
        "grade": "初一",
        "question_type": "解答",
        "difficulty": "基础",
        "student_answer": "x = 30",
        "error_reason": "小数化整时扩大倍数后忘记再除以系数。",
        "correct_answer": "x = 3",
        "detailed_solution": "先移项得 0.3x = 0.9，两边同时除以 0.3，得到 x = 3。",
    },
    {
        "expected_knowledge_point": "一元一次方程",
        "question_text": "解方程：4(x - 1) = 2(x + 3)。",
        "grade": "初一",
        "question_type": "解答",
        "difficulty": "基础",
        "student_answer": "x = 1",
        "error_reason": "去括号后把常数项 -4 和 6 移项时符号写错。",
        "correct_answer": "x = 5",
        "detailed_solution": "去括号得 4x - 4 = 2x + 6。移项得 2x = 10，所以 x = 5。",
    },
    {
        "expected_knowledge_point": "一元一次方程",
        "question_text": "解方程：7x - 2(3x - 4) = 15。",
        "grade": "初一",
        "question_type": "解答",
        "difficulty": "中等",
        "student_answer": "x = 23",
        "error_reason": "去括号时 -2 没有同时乘到 -4，负负得正处理错。",
        "correct_answer": "x = 7",
        "detailed_solution": "去括号得 7x - 6x + 8 = 15，即 x + 8 = 15，所以 x = 7。",
    },
    {
        "expected_knowledge_point": "二元一次方程组",
        "question_text": "解方程组：x + y = 7，x - y = 1。",
        "grade": "初一",
        "question_type": "解答",
        "difficulty": "基础",
        "student_answer": "x = 3，y = 4",
        "error_reason": "消元后没有代回原方程核对，把 x 和 y 的值写反。",
        "correct_answer": "x = 4，y = 3",
        "detailed_solution": "两式相加得 2x = 8，所以 x = 4。代入 x + y = 7，得到 y = 3。",
    },
    {
        "expected_knowledge_point": "二元一次方程组",
        "question_text": "解方程组：2x + 3y = 12，x - y = 1。",
        "grade": "初一",
        "question_type": "解答",
        "difficulty": "中等",
        "student_answer": "x = 2，y = 3",
        "error_reason": "代入消元后把 x = y + 1 代成了 x = y - 1。",
        "correct_answer": "x = 3，y = 2",
        "detailed_solution": "由 x - y = 1 得 x = y + 1。代入 2x + 3y = 12，得 2(y + 1) + 3y = 12，5y = 10，所以 y = 2，x = 3。",
    },
    {
        "expected_knowledge_point": "二元一次方程组",
        "question_text": "解方程组：3x + 2y = 16，x + 2y = 8。",
        "grade": "初一",
        "question_type": "解答",
        "difficulty": "基础",
        "student_answer": "x = 4，y = -2",
        "error_reason": "用加减消元求出 x 后，代回时常数移项变号错。",
        "correct_answer": "x = 4，y = 2",
        "detailed_solution": "两式相减得 2x = 8，所以 x = 4。代入 x + 2y = 8，得 4 + 2y = 8，所以 y = 2。",
    },
    {
        "expected_knowledge_point": "二元一次方程组",
        "question_text": "解方程组：x + 2y = 9，2x - y = 3。",
        "grade": "初一",
        "question_type": "解答",
        "difficulty": "中等",
        "student_answer": "x = 1，y = 4",
        "error_reason": "由 2x - y = 3 变形时，把 x 表示成 y 的式子时系数漏除。",
        "correct_answer": "x = 3，y = 3",
        "detailed_solution": "由 2x - y = 3 得 y = 2x - 3。代入 x + 2y = 9，得 x + 2(2x - 3) = 9，5x = 15，所以 x = 3，y = 3。",
    },
    {
        "expected_knowledge_point": "二元一次方程组",
        "question_text": "鸡兔同笼共 20 只，腿共 56 条，设鸡为 x 只、兔为 y 只，求鸡和兔各多少只。",
        "grade": "初一",
        "question_type": "解答",
        "difficulty": "中等",
        "student_answer": "鸡 8 只，兔 12 只",
        "error_reason": "列方程时未知量含义没坚持，最后把鸡和兔数量写反。",
        "correct_answer": "鸡 12 只，兔 8 只",
        "detailed_solution": "列方程 x + y = 20，2x + 4y = 56。由 x = 20 - y，代入得 40 - 2y + 4y = 56，2y = 16，所以 y = 8，x = 12。",
    },
    {
        "expected_knowledge_point": "一元一次不等式",
        "question_text": "解不等式：-3x + 5 > 14。",
        "grade": "初一",
        "question_type": "解答",
        "difficulty": "基础",
        "student_answer": "x > -3",
        "error_reason": "两边同时除以 -3 时忘记改变不等号方向。",
        "correct_answer": "x < -3",
        "detailed_solution": "先移项得 -3x > 9。两边同除以 -3，不等号变向，得到 x < -3。",
    },
    {
        "expected_knowledge_point": "一元一次不等式",
        "question_text": "解不等式：2(x - 1) <= 3x + 4。",
        "grade": "初一",
        "question_type": "解答",
        "difficulty": "基础",
        "student_answer": "x <= -6",
        "error_reason": "移项后得到 -x <= 6 时，除以 -1 没有改变不等号方向。",
        "correct_answer": "x >= -6",
        "detailed_solution": "去括号得 2x - 2 <= 3x + 4。移项得 -6 <= x，也就是 x >= -6。",
    },
    {
        "expected_knowledge_point": "一元一次不等式",
        "question_text": "解不等式：(x + 1) / 2 - 1 < 3。",
        "grade": "初一",
        "question_type": "解答",
        "difficulty": "中等",
        "student_answer": "x < 5",
        "error_reason": "去分母时没有把 -1 和 3 同时乘以 2。",
        "correct_answer": "x < 7",
        "detailed_solution": "两边同乘 2，得到 x + 1 - 2 < 6，即 x - 1 < 6，所以 x < 7。",
    },
    {
        "expected_knowledge_point": "一元一次不等式",
        "question_text": "解不等式：5 - 2x >= 1。",
        "grade": "初一",
        "question_type": "解答",
        "difficulty": "基础",
        "student_answer": "x >= 2",
        "error_reason": "把 -2x >= -4 两边除以 -2 时忘记变号。",
        "correct_answer": "x <= 2",
        "detailed_solution": "移项得 -2x >= -4。两边同除以 -2，不等号变向，得到 x <= 2。",
    },
    {
        "expected_knowledge_point": "一元一次不等式",
        "question_text": "解不等式：3x - 7 < 2x + 5。",
        "grade": "初一",
        "question_type": "解答",
        "difficulty": "基础",
        "student_answer": "x > -12",
        "error_reason": "移项时把 -7 移到右边、2x 移到左边后符号写乱。",
        "correct_answer": "x < 12",
        "detailed_solution": "两边同时减去 2x，得 x - 7 < 5。两边加 7，得到 x < 12。",
    },
    {
        "expected_knowledge_point": "一元一次不等式",
        "question_text": "解不等式：-x / 2 <= 3。",
        "grade": "初一",
        "question_type": "解答",
        "difficulty": "基础",
        "student_answer": "x <= -6",
        "error_reason": "两边乘以 -2 时没有改变不等号方向。",
        "correct_answer": "x >= -6",
        "detailed_solution": "两边同乘 -2，不等号变向，得到 x >= -6。",
    },
    {
        "expected_knowledge_point": "一元一次不等式",
        "question_text": "解不等式组：2x + 1 > 5，且 x - 3 <= 4。",
        "grade": "初一",
        "question_type": "解答",
        "difficulty": "中等",
        "student_answer": "x > 2 或 x <= 7",
        "error_reason": "把“且”理解成“或”，没有取两个解集的交集。",
        "correct_answer": "2 < x <= 7",
        "detailed_solution": "由 2x + 1 > 5 得 x > 2；由 x - 3 <= 4 得 x <= 7。两个条件同时满足，所以解集是 2 < x <= 7。",
    },
    {
        "expected_knowledge_point": "一元二次方程的解法",
        "question_text": "解方程：x^2 - 7x + 12 = 0。",
        "grade": "初三",
        "question_type": "解答",
        "difficulty": "基础",
        "student_answer": "x = 3",
        "error_reason": "因式分解后只写了一个根，漏掉另一个因式对应的解。",
        "correct_answer": "x = 3 或 x = 4",
        "detailed_solution": "因式分解得 (x - 3)(x - 4) = 0，所以 x - 3 = 0 或 x - 4 = 0，解得 x = 3 或 x = 4。",
    },
    {
        "expected_knowledge_point": "一元二次方程的解法",
        "question_text": "解方程：x^2 - 9 = 0。",
        "grade": "初三",
        "question_type": "解答",
        "difficulty": "基础",
        "student_answer": "x = 3",
        "error_reason": "直接开平方时漏掉负根。",
        "correct_answer": "x = 3 或 x = -3",
        "detailed_solution": "由 x^2 = 9 可得 x = ±3，所以 x = 3 或 x = -3。",
    },
    {
        "expected_knowledge_point": "一元二次方程的解法",
        "question_text": "解方程：2x^2 - 5x + 2 = 0。",
        "grade": "初三",
        "question_type": "解答",
        "difficulty": "中等",
        "student_answer": "x = 1 或 x = 2",
        "error_reason": "把 2x - 1 = 0 解成了 x = 1，系数化 1 漏除以 2。",
        "correct_answer": "x = 1/2 或 x = 2",
        "detailed_solution": "因式分解得 (2x - 1)(x - 2) = 0，所以 2x - 1 = 0 或 x - 2 = 0，解得 x = 1/2 或 x = 2。",
    },
    {
        "expected_knowledge_point": "一元二次方程的解法",
        "question_text": "解方程：x^2 + 4x + 4 = 0。",
        "grade": "初三",
        "question_type": "解答",
        "difficulty": "基础",
        "student_answer": "x = 2",
        "error_reason": "把 (x + 2)^2 = 0 的根号方向理解反，符号写错。",
        "correct_answer": "x = -2",
        "detailed_solution": "左边是完全平方，x^2 + 4x + 4 = (x + 2)^2，所以 (x + 2)^2 = 0，x = -2。",
    },
    {
        "expected_knowledge_point": "一元二次方程的解法",
        "question_text": "解方程：x^2 + 2x - 8 = 0。",
        "grade": "初三",
        "question_type": "解答",
        "difficulty": "基础",
        "student_answer": "x = 4 或 x = -2",
        "error_reason": "找两个数时只看乘积，没有同时检查和为 2。",
        "correct_answer": "x = 2 或 x = -4",
        "detailed_solution": "因式分解得 (x + 4)(x - 2) = 0，所以 x = -4 或 x = 2。",
    },
    {
        "expected_knowledge_point": "一元二次方程的解法",
        "question_text": "解方程：3x^2 - 12 = 0。",
        "grade": "初三",
        "question_type": "解答",
        "difficulty": "基础",
        "student_answer": "x = 2",
        "error_reason": "把 x^2 = 4 开方时漏掉负根。",
        "correct_answer": "x = 2 或 x = -2",
        "detailed_solution": "先化简得 3x^2 = 12，所以 x^2 = 4，开平方得 x = ±2。",
    },
    {
        "expected_knowledge_point": "一元二次方程的解法",
        "question_text": "解方程：x^2 - 2x - 3 = 0。",
        "grade": "初三",
        "question_type": "解答",
        "difficulty": "基础",
        "student_answer": "x = -3 或 x = 1",
        "error_reason": "因式分解时把 (x - 3)(x + 1) 写成了 (x + 3)(x - 1)。",
        "correct_answer": "x = 3 或 x = -1",
        "detailed_solution": "因式分解得 (x - 3)(x + 1) = 0，所以 x = 3 或 x = -1。",
    },
    {
        "expected_knowledge_point": "一元二次方程的解法",
        "question_text": "判断方程 x^2 - 6x + 10 = 0 是否有实数根。",
        "grade": "初三",
        "question_type": "解答",
        "difficulty": "中等",
        "student_answer": "有两个实数根 x = 1 和 x = 5",
        "error_reason": "没有计算判别式，直接误以为能因式分解。",
        "correct_answer": "没有实数根",
        "detailed_solution": "判别式 Δ = b^2 - 4ac = (-6)^2 - 4 × 1 × 10 = 36 - 40 = -4。因为 Δ < 0，所以方程没有实数根。",
    },
    {
        "expected_knowledge_point": "一元二次方程的解法",
        "question_text": "解方程：2x^2 + 3x - 2 = 0。",
        "grade": "初三",
        "question_type": "解答",
        "difficulty": "中等",
        "student_answer": "x = -1/2 或 x = 2",
        "error_reason": "分解后求根时把 2x - 1 = 0 和 x + 2 = 0 的符号都写反。",
        "correct_answer": "x = 1/2 或 x = -2",
        "detailed_solution": "因式分解得 (2x - 1)(x + 2) = 0，所以 x = 1/2 或 x = -2。",
    },
    {
        "expected_knowledge_point": "一元二次方程的解法",
        "question_text": "解方程：x^2 - 8x + 15 = 0。",
        "grade": "初三",
        "question_type": "解答",
        "difficulty": "基础",
        "student_answer": "x = 3",
        "error_reason": "因式分解正确但只写了一个解，漏掉 x = 5。",
        "correct_answer": "x = 3 或 x = 5",
        "detailed_solution": "因式分解得 (x - 3)(x - 5) = 0，所以 x = 3 或 x = 5。",
    },
    {
        "expected_knowledge_point": "一次函数图像与性质",
        "question_text": "一次函数 y = 2x - 3，当 x = 4 时，求 y。",
        "grade": "初二",
        "question_type": "填空",
        "difficulty": "基础",
        "student_answer": "y = 11",
        "error_reason": "代入后把 -3 看成了 +3。",
        "correct_answer": "y = 5",
        "detailed_solution": "把 x = 4 代入 y = 2x - 3，得 y = 2 × 4 - 3 = 8 - 3 = 5。",
    },
    {
        "expected_knowledge_point": "一次函数图像与性质",
        "question_text": "一次函数图像经过点 (0, 3) 和 (2, 7)，求解析式。",
        "grade": "初二",
        "question_type": "解答",
        "difficulty": "中等",
        "student_answer": "y = 3x + 2",
        "error_reason": "把截距 b 和斜率 k 混淆，直接把两个数字对调。",
        "correct_answer": "y = 2x + 3",
        "detailed_solution": "设 y = kx + b。点 (0,3) 说明 b = 3。代入 (2,7)，得 7 = 2k + 3，所以 k = 2。因此解析式是 y = 2x + 3。",
    },
    {
        "expected_knowledge_point": "一次函数图像与性质",
        "question_text": "一次函数 y = -3x + 6 与 x 轴的交点坐标是多少？",
        "grade": "初二",
        "question_type": "填空",
        "difficulty": "基础",
        "student_answer": "(-2, 0)",
        "error_reason": "令 y = 0 后移项时把 -3x = -6 写成了 -3x = 6。",
        "correct_answer": "(2, 0)",
        "detailed_solution": "与 x 轴交点满足 y = 0，所以 -3x + 6 = 0，-3x = -6，x = 2，交点为 (2,0)。",
    },
    {
        "expected_knowledge_point": "一次函数图像与性质",
        "question_text": "已知一次函数 y = kx + 1 经过点 (2, 5)，求 k。",
        "grade": "初二",
        "question_type": "填空",
        "difficulty": "基础",
        "student_answer": "k = 3",
        "error_reason": "代入点坐标后没有减去截距 1，直接用 5 ÷ 2。",
        "correct_answer": "k = 2",
        "detailed_solution": "把 (2,5) 代入 y = kx + 1，得 5 = 2k + 1，所以 2k = 4，k = 2。",
    },
    {
        "expected_knowledge_point": "一次函数图像与性质",
        "question_text": "若一次函数 y = (m - 1)x + 2 是增函数，求 m 的取值范围。",
        "grade": "初二",
        "question_type": "解答",
        "difficulty": "中等",
        "student_answer": "m < 1",
        "error_reason": "把一次函数增函数条件 k > 0 记反。",
        "correct_answer": "m > 1",
        "detailed_solution": "一次函数 y = kx + b 当 k > 0 时随 x 增大而增大。这里 k = m - 1，所以 m - 1 > 0，m > 1。",
    },
    {
        "expected_knowledge_point": "一次函数图像与性质",
        "question_text": "已知 y = -2x + 4，求 y < 0 时 x 的取值范围。",
        "grade": "初二",
        "question_type": "解答",
        "difficulty": "中等",
        "student_answer": "x < 2",
        "error_reason": "解 -2x + 4 < 0 时，除以负数忘记改变不等号方向。",
        "correct_answer": "x > 2",
        "detailed_solution": "由 -2x + 4 < 0 得 -2x < -4。两边除以 -2，不等号变向，所以 x > 2。",
    },
    {
        "expected_knowledge_point": "一次函数图像与性质",
        "question_text": "求直线 y = 3x - 6 与 y = x + 2 的交点坐标。",
        "grade": "初二",
        "question_type": "解答",
        "difficulty": "中等",
        "student_answer": "(2, 8)",
        "error_reason": "联立两个解析式后移项错误，导致 x 算错。",
        "correct_answer": "(4, 6)",
        "detailed_solution": "交点处两个 y 相等，所以 3x - 6 = x + 2，2x = 8，x = 4。代入 y = x + 2，得 y = 6，交点为 (4,6)。",
    },
    {
        "expected_knowledge_point": "反比例函数",
        "question_text": "反比例函数 y = 6 / x，当 x = 3 时，求 y。",
        "grade": "初二",
        "question_type": "填空",
        "difficulty": "基础",
        "student_answer": "y = 18",
        "error_reason": "把反比例关系 y = 6 / x 误当成正比例 y = 6x。",
        "correct_answer": "y = 2",
        "detailed_solution": "代入 x = 3，得 y = 6 / 3 = 2。",
    },
    {
        "expected_knowledge_point": "反比例函数",
        "question_text": "反比例函数 y = k / x 经过点 (2, -3)，求 k。",
        "grade": "初二",
        "question_type": "填空",
        "difficulty": "基础",
        "student_answer": "k = -1.5",
        "error_reason": "误用 k = y / x，而反比例函数中 k = xy。",
        "correct_answer": "k = -6",
        "detailed_solution": "反比例函数 y = k / x 经过 (2,-3)，所以 -3 = k / 2，k = -6。也可以直接用 k = xy = 2 × (-3) = -6。",
    },
    {
        "expected_knowledge_point": "反比例函数",
        "question_text": "反比例函数 y = -8 / x，当 y = 4 时，求 x。",
        "grade": "初二",
        "question_type": "填空",
        "difficulty": "基础",
        "student_answer": "x = 2",
        "error_reason": "移项时忽略了 k 的负号。",
        "correct_answer": "x = -2",
        "detailed_solution": "由 4 = -8 / x，得 4x = -8，所以 x = -2。",
    },
    {
        "expected_knowledge_point": "反比例函数",
        "question_text": "反比例函数 y = k / x，若 k > 0，图像位于哪几个象限？",
        "grade": "初二",
        "question_type": "填空",
        "difficulty": "基础",
        "student_answer": "第二、四象限",
        "error_reason": "把 k 的正负与象限关系记反。",
        "correct_answer": "第一、三象限",
        "detailed_solution": "反比例函数 y = k / x 中，k > 0 时 x 和 y 同号，所以图像在第一、三象限。",
    },
    {
        "expected_knowledge_point": "二次函数图像与性质",
        "question_text": "二次函数 y = x^2 - 5x + 6 与 x 轴的交点坐标是多少？",
        "grade": "初三",
        "question_type": "解答",
        "difficulty": "基础",
        "student_answer": "(-2, 0) 和 (-3, 0)",
        "error_reason": "求 y = 0 时因式分解符号写反。",
        "correct_answer": "(2, 0) 和 (3, 0)",
        "detailed_solution": "令 y = 0，得 x^2 - 5x + 6 = 0。因式分解为 (x - 2)(x - 3) = 0，所以 x = 2 或 x = 3。",
    },
    {
        "expected_knowledge_point": "二次函数图像与性质",
        "question_text": "求二次函数 y = x^2 - 4x + 4 的顶点坐标。",
        "grade": "初三",
        "question_type": "填空",
        "difficulty": "基础",
        "student_answer": "(-2, 0)",
        "error_reason": "把 y = (x - 2)^2 的平移方向理解反。",
        "correct_answer": "(2, 0)",
        "detailed_solution": "y = x^2 - 4x + 4 = (x - 2)^2，所以顶点坐标是 (2,0)。",
    },
    {
        "expected_knowledge_point": "二次函数图像与性质",
        "question_text": "二次函数 y = -x^2 + 2x + 3 的开口方向、对称轴和顶点坐标分别是什么？",
        "grade": "初三",
        "question_type": "解答",
        "difficulty": "中等",
        "student_answer": "开口向上，对称轴 x = -1，顶点 (-1, 4)",
        "error_reason": "a 的符号看反，并把对称轴公式 -b/(2a) 的负号漏掉。",
        "correct_answer": "开口向下，对称轴 x = 1，顶点 (1, 4)",
        "detailed_solution": "a = -1 < 0，所以开口向下。对称轴 x = -b/(2a) = -2/(2×-1) = 1。代入 x = 1，y = -1 + 2 + 3 = 4，所以顶点为 (1,4)。",
    },
    {
        "expected_knowledge_point": "二次函数图像与性质",
        "question_text": "判断二次函数 y = x^2 + 2x + 5 的图像是否与 x 轴有交点。",
        "grade": "初三",
        "question_type": "解答",
        "difficulty": "中等",
        "student_answer": "有两个交点",
        "error_reason": "没有用判别式，看到二次函数就默认与 x 轴相交。",
        "correct_answer": "没有交点",
        "detailed_solution": "令 y = 0，得到 x^2 + 2x + 5 = 0。判别式 Δ = 2^2 - 4×1×5 = -16 < 0，所以没有实数根，图像与 x 轴没有交点。",
    },
    {
        "expected_knowledge_point": "二次函数图像与性质",
        "question_text": "求二次函数 y = 2x^2 - 8x + 6 的最小值。",
        "grade": "初三",
        "question_type": "解答",
        "difficulty": "中等",
        "student_answer": "最小值为 6",
        "error_reason": "只看常数项，没有先求顶点。",
        "correct_answer": "最小值为 -2",
        "detailed_solution": "因为 a = 2 > 0，抛物线开口向上，有最小值。对称轴 x = -b/(2a) = 8/4 = 2。代入得 y = 2×4 - 16 + 6 = -2。",
    },
    {
        "expected_knowledge_point": "二次函数图像与性质",
        "question_text": "二次函数 y = x^2 - 6x + 8，求 y < 0 时 x 的取值范围。",
        "grade": "初三",
        "question_type": "解答",
        "difficulty": "中等",
        "student_answer": "x < 2 或 x > 4",
        "error_reason": "没有结合开口向上理解图像在 x 轴下方的区间。",
        "correct_answer": "2 < x < 4",
        "detailed_solution": "令 y = 0，得 x^2 - 6x + 8 = 0，即 (x - 2)(x - 4) = 0，所以交点为 x = 2 和 x = 4。开口向上，图像在两根之间小于 0，所以 2 < x < 4。",
    },
    {
        "expected_knowledge_point": "二次函数图像与性质",
        "question_text": "二次函数 y = (x - 1)^2 + 3 的顶点坐标和最小值分别是什么？",
        "grade": "初三",
        "question_type": "填空",
        "difficulty": "基础",
        "student_answer": "顶点 (-1, 3)，最小值 3",
        "error_reason": "把 x - 1 理解成向左平移 1 个单位。",
        "correct_answer": "顶点 (1, 3)，最小值 3",
        "detailed_solution": "顶点式 y = (x - h)^2 + k 的顶点是 (h,k)。这里 h = 1，k = 3，所以顶点是 (1,3)，最小值是 3。",
    },
    {
        "expected_knowledge_point": "二次函数图像与性质",
        "question_text": "若抛物线 y = x^2 + bx + 9 与 x 轴只有一个交点，求 b 的值。",
        "grade": "初三",
        "question_type": "解答",
        "difficulty": "提高",
        "student_answer": "b = 6",
        "error_reason": "知道要用判别式等于 0，但开平方后漏掉负值。",
        "correct_answer": "b = 6 或 b = -6",
        "detailed_solution": "与 x 轴只有一个交点，说明方程 x^2 + bx + 9 = 0 有两个相等实根，所以 Δ = b^2 - 4×1×9 = 0。得到 b^2 = 36，因此 b = ±6。",
    },
]


def normalize_text(value: str) -> str:
    """把文本压成统一格式，方便判断样例题是否已经录入过。"""
    return " ".join(str(value or "").split())


def existing_question_keys() -> set[str]:
    """读取数据库里已有题目，避免重复运行脚本时反复插入同一道样例题。"""
    mistake_db.create_tables()
    mistake_db.seed_core_knowledge_points()
    return {
        normalize_text(item["question_text"])
        for item in mistake_db.get_all_mistakes_with_knowledge()
    }


def seed_samples(limit: int | None = None) -> dict[str, Any]:
    """
    批量录入样例错题。

    返回一个统计字典，方便测试脚本判断录入了多少、跳过了多少。
    """
    if not os.environ.get(DEEPSEEK_API_KEY_ENV):
        message = f"缺少环境变量 {DEEPSEEK_API_KEY_ENV}，无法走 DeepSeek 自动归类流程。"
        print(f"[配置错误] {message}")
        return {"saved": 0, "skipped": 0, "failed": len(SAMPLE_MISTAKES), "message": message}

    existing = existing_question_keys()
    samples = SAMPLE_MISTAKES[:limit] if limit else SAMPLE_MISTAKES
    stats = {"saved": 0, "skipped": 0, "failed": 0, "mismatch": 0}

    for index, sample in enumerate(samples, start=1):
        question_key = normalize_text(sample["question_text"])
        if question_key in existing:
            stats["skipped"] += 1
            print(f"[{index}/{len(samples)}] 已存在，跳过：{sample['question_text']}")
            continue

        print(f"[{index}/{len(samples)}] 自动归类并录入：{sample['question_text']}")
        result = mistake_ai.add_mistake_with_auto_classification(
            question_text=sample["question_text"],
            grade=sample["grade"],
            question_type=sample["question_type"],
            difficulty=sample["difficulty"],
            correct_answer=sample["correct_answer"],
            detailed_solution=sample["detailed_solution"],
            student_answer=sample["student_answer"],
            error_reason=sample["error_reason"],
            mastery_status=sample.get("mastery_status", "未掌握"),
        )

        if not result.get("saved"):
            stats["failed"] += 1
            print(f"  录入失败：{result.get('message')}")
            continue

        stats["saved"] += 1
        existing.add(question_key)
        actual_name = result["classification"].get("knowledge_point_name")
        expected_name = sample["expected_knowledge_point"]
        print(f"  已保存错题ID：{result['mistake_id']}，AI归类：{actual_name}")

        # 期望知识点只是给人看，不干预 AI 的判断。
        if actual_name and actual_name != expected_name:
            stats["mismatch"] += 1
            print(f"  提醒：期望知识点是“{expected_name}”，AI 实际归到“{actual_name}”。")

    print("\n批量样例录入完成：")
    print(f"- 新增：{stats['saved']} 道")
    print(f"- 跳过已存在：{stats['skipped']} 道")
    print(f"- 失败：{stats['failed']} 道")
    print(f"- 期望/实际知识点不一致：{stats['mismatch']} 道")
    return stats


def main() -> None:
    """命令行入口：默认录入全部样例，也可以用 --limit 先小批量试跑。"""
    parser = argparse.ArgumentParser(description="批量录入相似题推荐测试错题。")
    parser.add_argument("--limit", type=int, default=None, help="只录入前 N 道样例，方便小批量测试。")
    args = parser.parse_args()
    seed_samples(limit=args.limit)


if __name__ == "__main__":
    main()
