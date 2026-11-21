# -*- coding: utf-8 -*-
"""学情分析 + 变式训练引擎
1. 知识点掌握度：按学生/班级聚合 learning_records，含近期加权
2. 薄弱知识点识别：正确率 + 重复错误次数
3. 核心素养诊断：由薄弱知识点反查映射的素养，聚合为雷达图数据
4. 变式训练生成：按知识点模板参数化生成新题
5. 专题突破课程：聚类薄弱知识点，生成针对性专题
"""
import os
import json
import random
from collections import defaultdict
from datetime import datetime

from kg import get_db, load_knowledge_graph, KNOWLEDGE_GRAPH, CORE_COMPETENCIES, COMPETENCY_DOMAIN, VARIANT_TEMPLATES, GENERIC_VARIANT

BASE = os.path.dirname(os.path.abspath(__file__))


def mastery_by_student(student_id):
    """某学生各知识点掌握度"""
    conn = get_db()
    rows = conn.execute("""
        SELECT knowledge_point,
               COUNT(*) AS total,
               SUM(correct) AS correct_cnt,
               AVG(score) AS avg_score
        FROM learning_records WHERE student_id=?
        GROUP BY knowledge_point
    """, (student_id,)).fetchall()
    conn.close()
    result = {}
    for r in rows:
        total = r["total"]
        correct = r["correct_cnt"] or 0
        result[r["knowledge_point"]] = {
            "total": total,
            "correct": correct,
            "accuracy": round(correct / total, 3) if total else 0,
            "avg_score": round(r["avg_score"] or 0, 3)
        }
    return result


def mastery_by_class(class_id, top_n=None):
    """班级各知识点掌握度（所有学生聚合）"""
    conn = get_db()
    rows = conn.execute("""
        SELECT r.knowledge_point,
               COUNT(*) AS total,
               SUM(r.correct) AS correct_cnt,
               AVG(r.score) AS avg_score
        FROM learning_records r
        JOIN students s ON r.student_id=s.id
        WHERE s.class_id=?
        GROUP BY r.knowledge_point
    """, (class_id,)).fetchall()
    conn.close()
    result = []
    for r in rows:
        total = r["total"]
        correct = r["correct_cnt"] or 0
        result.append({
            "knowledge_point": r["knowledge_point"],
            "total": total,
            "correct": correct,
            "accuracy": round(correct / total, 3) if total else 0,
            "avg_score": round(r["avg_score"] or 0, 3)
        })
    result.sort(key=lambda x: x["accuracy"])
    return result[:top_n] if top_n else result


def weak_points(student_id=None, class_id=None, threshold=0.6, min_attempts=2):
    """识别薄弱知识点"""
    if student_id:
        m = mastery_by_student(student_id)
        items = [{"knowledge_point": k, **v} for k, v in m.items()]
    elif class_id:
        items = mastery_by_class(class_id)
    else:
        items = []
    weak = [x for x in items if x["accuracy"] < threshold and x["total"] >= min_attempts]
    weak.sort(key=lambda x: (x["accuracy"], -x["total"]))
    return weak


def competency_diagnosis(weak_points_list):
    """由薄弱知识点反查核心素养缺失，聚合为雷达图数据
    逻辑：某素养被越多薄弱点命中、且薄弱点正确率越低，则该素养越欠缺
    """
    kg = {k["name"]: k for k in load_knowledge_graph()}
    score = defaultdict(float)     # 欠缺分（越高越缺）
    hit_count = defaultdict(int)
    evidence = defaultdict(list)

    for wp in weak_points_list:
        kp = kg.get(wp["knowledge_point"])
        if not kp:
            continue
        severity = 1.0 - wp["accuracy"]  # 0~1
        for comp in kp["competencies"]:
            score[comp] += severity
            hit_count[comp] += 1
            evidence[comp].append({
                "point": wp["knowledge_point"],
                "accuracy": wp["accuracy"],
                "error_pattern": kp["error_pattern"]
            })

    # 归一化为 0~100 的"素养水平"（欠缺越高 -> 水平越低）
    diagnosis = []
    for comp in CORE_COMPETENCIES:
        raw = score.get(comp, 0)
        level = max(0, min(100, round(100 - raw * 25)))
        diagnosis.append({
            "competency": comp,
            "domain": COMPETENCY_DOMAIN[comp],
            "level": level,
            "hits": hit_count.get(comp, 0),
            "evidence": evidence.get(comp, []),
            "description": CORE_COMPETENCIES[comp]
        })
    diagnosis.sort(key=lambda x: x["level"])
    return diagnosis


def gen_variant(knowledge_point, student_id=None):
    """为指定知识点生成一个变式题（参数化生成）"""
    tpl = VARIANT_TEMPLATES.get(knowledge_point, GENERIC_VARIANT)
    templates = tpl["templates"]
    chosen = random.choice(templates)
    context = ""

    has_num = any(f"{{{x}}}" in chosen for x in "abcnmk")
    if has_num:
        # 数值型题目
        if knowledge_point in ("小数加减法",):
            a = round(random.uniform(1.1, 9.9), 1)
            b = round(random.uniform(1.1, 9.9), 1)
            if "-" in chosen and b > a:
                a, b = b, a
            answer = round(a + b, 1) if "+" in chosen else round(a - b, 1)
            chosen = chosen.format(a=a, b=b)
        elif knowledge_point in ("小数乘小数", "小数乘整数", "小数乘法简算"):
            a = round(random.uniform(1.2, 9.9), 1)
            b = round(random.uniform(1.2, 5.9), 1) if "小数乘小数" in knowledge_point else random.randint(2, 9)
            answer = round(a * b, 2)
            chosen = chosen.format(a=a, b=b)
        elif "三角形的面积" in knowledge_point:
            a = random.randint(4, 15); b = random.randint(3, 12)
            answer = a * b / 2
            chosen = chosen.format(a=a, b=b)
        elif "平行四边形的面积" in knowledge_point:
            a = random.randint(4, 15); b = random.randint(3, 12)
            answer = a * b
            chosen = chosen.format(a=a, b=b)
        elif "梯形" in knowledge_point:
            a = random.randint(3, 9); b = random.randint(10, 18); c = random.randint(3, 10)
            answer = (a + b) * c / 2
            chosen = chosen.format(a=a, b=b, c=c)
        elif "3的倍数" in knowledge_point:
            n = random.randint(100, 999)
            answer = "是" if n % 3 == 0 else "不是"
            chosen = chosen.format(n=n)
        elif "倍数与因数" in knowledge_point:
            n = random.randint(12, 36)
            answer = "1、它本身" if "倍数" in chosen else "、".join(
                str(i) for i in range(1, n+1) if n % i == 0)
            chosen = chosen.format(n=n)
        elif "用字母表示" in knowledge_point:
            n = random.randint(3, 12)
            answer = f"a+{n}" if "多" in chosen else f"{n}b"
            chosen = chosen.format(n=n)
        elif "质数" in knowledge_point or "合数" in knowledge_point:
            # 保证至少含一个质数，答案不为空
            n = random.choice([7, 11, 13, 17, 19])          # 质数
            m = random.choice([21, 25, 27, 33, 15, 18])     # 合数
            k = random.choice([4, 6, 8, 12, 20])            # 合数
            nums = [n, m, k]
            primes = [x for x in nums if all(x % d != 0 for d in range(2, int(x**0.5)+1))]
            answer = "、".join(str(x) for x in primes)
            if "{n}" in chosen and "{m}" not in chosen:     # 单个数判断题
                target = n if random.random() < 0.5 else m
                is_p = all(target % d != 0 for d in range(2, int(target**0.5)+1))
                answer = "质数" if is_p else "合数"
                chosen = chosen.format(n=target)
            else:
                chosen = chosen.format(n=n, m=m, k=k)
        elif "积的近似数" in knowledge_point:
            a = round(random.uniform(1.2, 9.9), 2); b = round(random.uniform(1.1, 5.9), 2)
            answer = round(a*b, 1)
            chosen = chosen.format(a=a, b=b)
        else:
            a = round(random.uniform(1, 10), 1); b = round(random.uniform(1, 10), 1)
            answer = round(a + b, 2)
            chosen = chosen.format(a=a, b=b)
    else:
        answer = "（开放题，老师复核）"
        chosen = chosen.format(kp=knowledge_point, context=context)

    return {
        "knowledge_point": knowledge_point,
        "question_text": chosen,
        "answer": str(answer),
        "analysis": tpl["analysis"],
        "created_at": datetime.now().isoformat()
    }


def generate_variant_set(student_id=None, class_id=None, n=5):
    """针对薄弱知识点批量生成变式训练"""
    weak = weak_points(student_id=student_id, class_id=class_id)
    if not weak:
        return []
    exercises = []
    for i in range(n):
        wp = weak[i % len(weak)]
        ex = gen_variant(wp["knowledge_point"], student_id)
        ex["source_weakness"] = wp["knowledge_point"]
        ex["source_accuracy"] = wp["accuracy"]
        exercises.append(ex)
    # 持久化
    if student_id:
        conn = get_db()
        for ex in exercises:
            conn.execute("""INSERT INTO variant_assignments
                (student_id,knowledge_point,question_text,answer,analysis,created_at)
                VALUES (?,?,?,?,?,?)""",
                (student_id, ex["knowledge_point"], ex["question_text"],
                 ex["answer"], ex["analysis"], ex["created_at"]))
        conn.commit()
        conn.close()
    return exercises


def topic_recommendations(class_id=None, student_id=None):
    """专题突破课程推荐：按知识体系领域聚合薄弱点"""
    weak = weak_points(student_id=student_id, class_id=class_id)
    if not weak:
        return []
    kg = {k["name"]: k for k in load_knowledge_graph()}
    domain_groups = defaultdict(list)
    for wp in weak:
        kp = kg.get(wp["knowledge_point"])
        if kp:
            domain_groups[kp["domain"]].append(wp)

    topics = []
    for domain, points in domain_groups.items():
        points.sort(key=lambda x: x["accuracy"])
        avg_acc = round(sum(p["accuracy"] for p in points) / len(points), 3)
        topics.append({
            "domain": domain,
            "weak_count": len(points),
            "avg_accuracy": avg_acc,
            "points": [p["knowledge_point"] for p in points],
            "competencies": sorted(set(
                c for p in points for c in kg.get(p["knowledge_point"], {}).get("competencies", [])
            )),
            "title": f"{domain}专题突破",
            "suggestion": build_suggestion(domain, [p["knowledge_point"] for p in points])
        })
    topics.sort(key=lambda x: x["avg_accuracy"])
    return topics


def build_suggestion(domain, points):
    suggestions = {
        "数与代数": "建议安排「算理理解 + 运算技能」双线训练：先通过实例讲清算理，再设计分层计算练习，重点纠正小数点位置和运算顺序类错误。",
        "图形与几何": "建议安排「操作感知 + 转化思想」专题：借助剪纸、割补、拼摆等活动建立空间表象，强化底与高的对应关系和公式推导过程。",
        "统计与概率": "建议安排「数据感悟 + 随机现象体验」活动：通过摸球、掷骰等实验建立可能性大小与数量的关系，用真实数据支撑判断。",
        "综合与实践": "建议安排「问题解决策略」专题：训练列表、假设、画图等策略的灵活选择，鼓励一题多解，发展模型意识与创新意识。",
    }
    base = suggestions.get(domain, "针对薄弱知识点设计分层练习与变式训练。")
    return base + f" 本专题聚焦：{'、'.join(points[:5])}。"


def class_overview(class_id):
    """班级整体学情概览"""
    conn = get_db()
    students = conn.execute("SELECT id,name FROM students WHERE class_id=?", (class_id,)).fetchall()
    total = len(students)
    if total == 0:
        conn.close()
        return {"student_count": 0}
    # 班级整体正确率
    r = conn.execute("""SELECT AVG(r.correct) as acc, COUNT(*) as cnt
        FROM learning_records r JOIN students s ON r.student_id=s.id
        WHERE s.class_id=?""", (class_id,)).fetchone()
    avg_acc = round((r["acc"] or 0), 3)
    total_records = r["cnt"]
    # 学生排行榜（按掌握度）
    ranking = []
    for s in students:
        m = mastery_by_student(s["id"])
        if m:
            acc = round(sum(x["correct"] for x in m.values()) / sum(x["total"] for x in m.values()), 3)
            ranking.append({"id": s["id"], "name": s["name"], "accuracy": acc,
                            "point_count": len(m)})
    ranking.sort(key=lambda x: -x["accuracy"])
    conn.close()
    return {
        "student_count": total,
        "avg_accuracy": avg_acc,
        "total_records": total_records,
        "ranking": ranking,
        "weak_points": mastery_by_class(class_id, top_n=5)
    }


if __name__ == "__main__":
    print("素养诊断示例:")
    d = competency_diagnosis([{
        "knowledge_point": "三角形的面积", "accuracy": 0.3, "total": 5
    }, {
        "knowledge_point": "小数乘小数", "accuracy": 0.4, "total": 6
    }])
    for x in d[:6]:
        print(f"  {x['competency']}: {x['level']} (命中{x['hits']}次)")
