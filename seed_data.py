# -*- coding: utf-8 -*-
"""填充演示数据：2个班约80名学生 + 作业题目 + 多轮提交记录
刻意制造典型错题模式，让学情分析得出有意义结论：
- 五(1)班：三角形面积、小数乘小数薄弱 -> 推理意识/空间观念/运算能力短板
- 五(2)班：倍数与因数、用字母表示薄弱 -> 数感/符号意识/模型意识短板
"""
import os, random
from datetime import datetime, timedelta
import kg

random.seed(2024)

SURNAMES = "王李张刘陈杨黄赵周吴徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾"
GIVEN = ["伟","芳","娜","敏","静","丽","强","磊","军","洋","勇","艳","杰","娟","涛","明","超","秀英","霞","平","刚","桂英","文","辉","力","俊","峰","建华","宇","晨","浩然","子涵","雨桐","梓涵","欣怡","思远","嘉豪","一诺"]

def gen_name():
    return random.choice(SURNAMES) + random.choice(GIVEN)

def main():
    kg.init_db()
    conn = kg.get_db()
    c = conn.cursor()

    # 清空旧演示数据（保留知识图谱），并重置自增ID让班级从1开始
    for t in ["learning_records","variant_assignments","submissions","questions","assignments","students","classes","teachers"]:
        c.execute(f"DELETE FROM {t}")
        c.execute("DELETE FROM sqlite_sequence WHERE name=?", (t,))

    # 老师
    c.execute("INSERT INTO teachers (username,name) VALUES (?,?)", ("teacher1","李老师"))
    tid = c.lastrowid

    # 两个班
    c.execute("INSERT INTO classes (name,teacher_id,grade,semester) VALUES (?,?,?,?)",
              ("五年级(1)班", tid, "五年级", "上册"))
    c1 = c.lastrowid
    c.execute("INSERT INTO classes (name,teacher_id,grade,semester) VALUES (?,?,?,?)",
              ("五年级(2)班", tid, "五年级", "上册"))
    c2 = c.lastrowid

    # 学生
    students = {c1: [], c2: []}
    for cid in (c1, c2):
        for i in range(40):
            name = gen_name()
            c.execute("INSERT INTO students (name,class_id,student_no) VALUES (?,?,?)",
                      (name, cid, f"{cid}{i+1:02d}"))
            students[cid].append(c.lastrowid)
    conn.commit()

    # 作业
    def add_assignment(title, cid, desc):
        c.execute("""INSERT INTO assignments (title,class_id,teacher_id,description,created_at)
            VALUES (?,?,?,?,?)""", (title, cid, tid, desc, datetime.now().isoformat()))
        return c.lastrowid

    a1 = add_assignment("第三单元 小数乘法练习", c1, "课堂练习")
    a2 = add_assignment("第五单元 多边形面积练习", c1, "单元检测")
    a3 = add_assignment("第三单元 小数乘法练习", c2, "课堂练习")
    a4 = add_assignment("第七单元 倍数与因数练习", c2, "单元检测")

    # 题目定义：(assignment, type, text, answer, kp, score, analysis, options)
    questions_def = [
        (a1,"calc","计算：2.4 × 1.5 = ?","3.6","小数乘小数",10,"先按整数乘法算24×15=360，两个因数共2位小数，积为3.6。常见错误：小数点位置点错。"),
        (a1,"calc","计算：0.8 × 0.7 = ?","0.56","小数乘小数",10,"8×7=56，共2位小数，得0.56。"),
        (a1,"calc","计算：3.6 × 2 = ?","7.2","小数乘整数",10,"36×2=72，1位小数，得7.2。"),
        (a1,"fill","4.25保留一位小数约是（ ）","4.3","积的近似数",10,"四舍五入看第二位小数5，进一得4.3。"),
        (a2,"calc","三角形底6cm，高4cm，面积是多少平方厘米？","12","三角形的面积",10,"三角形面积=底×高÷2=6×4÷2=12。常见错误：忘记除以2。"),
        (a2,"calc","平行四边形底8cm，高5cm，面积是多少？","40","平行四边形的面积",10,"平行四边形面积=底×高=8×5=40。"),
        (a2,"calc","梯形上底3cm，下底7cm，高4cm，面积是多少？","20","梯形的面积",10,"(3+7)×4÷2=20。"),
        (a2,"choice","三角形面积公式是？","B","三角形的面积",10,"三角形面积=底×高÷2","A. 底×高\nB. 底×高÷2\nC. 底+高"),
        (a3,"calc","计算：2.4 × 1.5 = ?","3.6","小数乘小数",10,"先按整数乘法算，再确定小数点位置。"),
        (a3,"calc","计算：1.2 × 0.5 = ?","0.6","小数乘小数",10,"12×5=60，2位小数，得0.6。"),
        (a3,"fill","小数乘法中，因数共有3位小数，积就有（ ）位小数","3","小数乘小数",10,"积的小数位数等于因数小数位数之和。"),
        (a4,"fill","20的因数有（ ）个","6","倍数与因数",10,"1,2,4,5,10,20 共6个。"),
        (a4,"choice","下面哪个数是3的倍数？","C","3的倍数特征",10,"各位数字和是3的倍数。","A. 14\nB. 25\nC. 27"),
        (a4,"fill","用字母表示：a与b的和的2倍是（ ）","2(a+b)","用字母表示数量关系",10,"先求和再乘2，注意括号。"),
        (a4,"fill","1既不是（ ）也不是（ ）","质数|合数","质数与合数",10,"1只有1个因数，既非质数也非合数。"),
    ]

    qids_by_a = {}
    for qd in questions_def:
        aid, qtype, text, ans, kp, score, analysis = qd[:7]
        opts = qd[7] if len(qd) > 7 else None
        opt_json = None
        if opts:
            import json
            opt_json = json.dumps(opts.split("\n"), ensure_ascii=False)
        c.execute("""INSERT INTO questions
            (assignment_id,q_type,question_text,options,standard_answer,scoring_rule,knowledge_point,analysis,score,sort_order)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (aid, qtype, text, opt_json, ans, "结果正确得满分", kp, analysis, score, 0))
        qids_by_a.setdefault(aid, []).append(c.lastrowid)
    conn.commit()

    # 制造提交记录：按班设定各知识点的"学生掌握概率"
    # 五(1)班：三角形面积0.35、小数乘小数0.45 薄弱；平行四边形0.85好
    # 五(2)班：倍数与因数0.4、3的倍数0.4、用字母表示0.45薄弱
    prob_c1 = {"小数乘小数":0.45,"小数乘整数":0.8,"积的近似数":0.75,
               "三角形的面积":0.35,"平行四边形的面积":0.85,"梯形的面积":0.6,"三角形的面积公式":0.5}
    prob_c2 = {"小数乘小数":0.7,"倍数与因数":0.4,"3的倍数特征":0.4,
               "用字母表示数量关系":0.45,"质数与合数":0.6}

    def add_records(cid, aid, prob_map, rounds=3):
        qids = qids_by_a[aid]
        for rnd in range(rounds):
            for qid in qids:
                q = c.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
                kp = q["knowledge_point"]
                p = prob_map.get(kp, 0.7)
                for sid in students[cid]:
                    correct = random.random() < p
                    # 学生答案：正确填标准答案，错误填典型错答
                    if correct:
                        ans = q["standard_answer"]
                    else:
                        ans = wrong_answer(q["standard_answer"], kp)
                    score = q["score"] if correct else 0
                    c.execute("""INSERT INTO submissions
                        (question_id,student_id,image_path,ocr_text,student_answer,answer_source,score,is_correct,needs_review,graded_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (qid, sid, None, None, ans, "manual", score, 1 if correct else 0, 0,
                         (datetime.now()-timedelta(days=rounds-rnd)).isoformat()))
                    # learning_records
                    c.execute("""INSERT INTO learning_records (student_id,knowledge_point,correct,score,timestamp)
                        VALUES (?,?,?,?,?)""",
                        (sid, kp, 1 if correct else 0, score,
                         (datetime.now()-timedelta(days=rounds-rnd)).isoformat()))

    def wrong_answer(std, kp):
        # 典型错误答案
        err_map = {
            "3.6":"36", "0.56":"5.6", "7.2":"72", "4.3":"4.2",
            "12":"24", "40":"20", "20":"10",
        }
        if std in err_map: return err_map[std]
        if "|" in std: return "质数"
        if std in ("B","C"): return "A" if std=="B" else "B"
        if "(" in std: return "a+b2"
        return "0"

    add_records(c1, a1, prob_c1)
    add_records(c1, a2, prob_c1)
    add_records(c2, a3, prob_c2)
    add_records(c2, a4, prob_c2)

    # ===== 补充：带学生作业照片的"待复核"记录（供批改中心看图复核演示）=====
    try:
        from PIL import Image, ImageDraw, ImageFont
        demo_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
        os.makedirs(demo_dir, exist_ok=True)
        fp = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
        font = ImageFont.truetype(fp, 30) if os.path.exists(fp) else ImageFont.load_default()
        # 选择几道有代表性的题，配真实作答图
        samples = [
            ("小数乘法", "36", "48", 1),      # 故意漏小数点
            ("三角形的面积", "24", "48平方厘米", 1),  # 漏除以2
            ("3的倍数特征", "不是", "是", 1),
            ("质数与合数", "27", "质数", 1),
        ]
        made = 0
        for kp, wrong, std, cid in samples:
            qrow = c.execute("SELECT * FROM questions WHERE knowledge_point=? LIMIT 1", (kp,)).fetchone()
            if not qrow:
                continue
            sid = students[cid][made % len(students[cid])]
            stu_name = c.execute("SELECT name FROM students WHERE id=?", (sid,)).fetchone()["name"]
            fname = f"demo_hw_{made+1}.png"
            img = Image.new("RGB", (760, 300), "white")
            d = ImageDraw.Draw(img)
            d.text((30, 25), f"姓名：{stu_name}", fill="#333", font=font)
            d.text((30, 95), f"{made+1}. {qrow['question_text'][:22]}", fill="#222", font=font)
            d.text((60, 175), f"答：{wrong}", fill="#1a1a1a", font=font)
            img.save(os.path.join(demo_dir, fname))
            c.execute("""INSERT INTO submissions
                (question_id,student_id,image_path,ocr_text,student_answer,answer_source,score,is_correct,needs_review,graded_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (qrow["id"], sid, f"uploads/{fname}", f"答：{wrong}", wrong,
                 "ocr", 0, 0, 1, datetime.now().isoformat()))
            made += 1
        print(f"补充 {made} 条带作业照片的待复核记录")
    except Exception as e:
        print("生成复核演示图失败（不影响主流程）:", e)

    conn.commit()
    conn.close()

    print(f"演示数据填充完成：2个班，{len(students[c1])+len(students[c2])}名学生，{len(questions_def)}道题")
    print("五(1)班薄弱点：三角形面积、小数乘小数")
    print("五(2)班薄弱点：倍数与因数、3的倍数特征、用字母表示")

if __name__ == "__main__":
    main()
