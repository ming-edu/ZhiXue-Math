# -*- coding: utf-8 -*-
"""
知识图谱 + 数据层
- 教材：北师大版(2024新课标) 小学数学五年级上册
- 课标：义务教育数学课程标准(2022年版)，小学阶段11项核心素养表现
- 知识点颗粒度：按教材课时/主题拆分，每个知识点映射到 1~3 项核心素养
"""
import sqlite3
import os
import json
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "data", "learning.db")

# ============ 2022课标 小学阶段核心素养（11项表现）============
CORE_COMPETENCIES = {
    "数感": "对于数与数量、数量关系及运算结果的直观感悟",
    "量感": "对事物的可测量属性及大小关系的直观感知",
    "符号意识": "感悟符号的数学功能，用符号表达数量关系与规律",
    "运算能力": "依据法则和运算律正确进行运算，理解算理、寻求合理简洁的运算途径",
    "几何直观": "运用图表描述和分析问题，借助图形理解数量关系",
    "空间观念": "对物体形状、大小、位置关系及其变换的感知与想象",
    "推理意识": "对逻辑推理过程及其意义的初步感悟，能有条理地思考",
    "数据意识": "对数据的意义、价值及随机现象的初步感悟",
    "模型意识": "感悟数学模型刻画现实问题的作用，能用模型表达数量关系",
    "应用意识": "有意识利用数学知识解决现实问题，感悟数学的实用价值",
    "创新意识": "主动尝试从不同角度思考、发现新的解法与思路",
}

# 三大方面归类（课标"三会"）
COMPETENCY_DOMAIN = {
    "数感": "数学眼光", "量感": "数学眼光", "符号意识": "数学眼光",
    "几何直观": "数学眼光", "空间观念": "数学眼光", "创新意识": "数学眼光",
    "运算能力": "数学思维", "推理意识": "数学思维",
    "数据意识": "数学语言", "模型意识": "数学语言", "应用意识": "数学语言",
}

# ============ 知识图谱：单元 -> 知识点 -> 核心素养 ============
# 结构: (单元, 知识点名称, [核心素养], 难度1-5, 知识体系领域, 典型错误模式)
KNOWLEDGE_GRAPH = [
    # 第一单元 小数的再认识和加减法
    ("第一单元 小数的再认识和加减法", "小数的意义与数位", ["数感", "符号意识"], 2, "数与代数", "混淆小数数位/计数单位"),
    ("第一单元 小数的再认识和加减法", "小数的性质与化简", ["数感", "推理意识"], 2, "数与代数", "末尾添0去0规则不清"),
    ("第一单元 小数的再认识和加减法", "小数的大小比较", ["数感", "推理意识"], 2, "数与代数", "按位数多少比较大小"),
    ("第一单元 小数的再认识和加减法", "小数加减法", ["运算能力", "数感"], 3, "数与代数", "小数点未对齐/退位减法错误"),
    ("第一单元 小数的再认识和加减法", "小数加减混合运算", ["运算能力", "推理意识"], 3, "数与代数", "运算顺序错误/简算意识弱"),
    # 第二单元 三角形的再认识
    ("第二单元 三角形的再认识", "三角形内角和", ["推理意识", "几何直观"], 3, "图形与几何", "内角和定理应用不熟"),
    ("第二单元 三角形的再认识", "三角形三边关系", ["推理意识", "空间观念"], 3, "图形与几何", "两边之和大于第三边判断错误"),
    ("第二单元 三角形的再认识", "三角形分类", ["几何直观", "推理意识"], 2, "图形与几何", "按角/按边分类混淆"),
    # 综合实践 小小设计师
    ("综合实践 小小设计师", "密铺与图形设计", ["几何直观", "空间观念", "创新意识"], 3, "综合与实践", "图形拼接想象不足"),
    # 第三单元 小数乘法
    ("第三单元 小数乘法", "小数乘整数", ["运算能力", "推理意识"], 3, "数与代数", "积的小数点位置错误"),
    ("第三单元 小数乘法", "小数乘小数", ["运算能力", "推理意识"], 4, "数与代数", "小数位数确定错误"),
    ("第三单元 小数乘法", "积的近似数", ["数感", "运算能力"], 3, "数与代数", "四舍五入位数混淆"),
    ("第三单元 小数乘法", "小数乘法简算", ["运算能力", "推理意识", "模型意识"], 4, "数与代数", "运算律迁移到小数不熟"),
    # 第四单元 用字母表示(一)
    ("第四单元 用字母表示(一)", "用字母表示数", ["符号意识", "模型意识"], 3, "数与代数", "字母含义理解不清"),
    ("第四单元 用字母表示(一)", "用字母表示数量关系", ["符号意识", "模型意识", "应用意识"], 4, "数与代数", "无法将情境抽象为式子"),
    ("第四单元 用字母表示(一)", "用字母表示规律", ["符号意识", "推理意识"], 4, "数与代数", "规律归纳能力弱"),
    ("第四单元 用字母表示(一)", "等式中的规律", ["推理意识", "符号意识"], 3, "数与代数", "等式性质理解不深"),
    # 第五单元 多边形的面积
    ("第五单元 多边形的面积", "比较图形的面积", ["几何直观", "空间观念"], 2, "图形与几何", "面积守恒观念不足"),
    ("第五单元 多边形的面积", "认识底和高", ["几何直观", "空间观念"], 2, "图形与几何", "底与高对应关系混淆"),
    ("第五单元 多边形的面积", "平行四边形的面积", ["推理意识", "模型意识", "空间观念"], 4, "图形与几何", "割补转化思想不熟/公式记混"),
    ("第五单元 多边形的面积", "三角形的面积", ["推理意识", "模型意识", "空间观念"], 4, "图形与几何", "忘除以2/底高对应错误"),
    ("第五单元 多边形的面积", "梯形的面积", ["推理意识", "模型意识"], 4, "图形与几何", "公式记忆错误"),
    ("第五单元 多边形的面积", "组合图形的面积", ["几何直观", "推理意识", "应用意识"], 5, "图形与几何", "分割/添补策略单一"),
    ("第五单元 多边形的面积", "公顷与平方千米", ["量感", "应用意识"], 3, "图形与几何", "面积单位进率混淆"),
    # 数学好玩 鸡兔同笼
    ("数学好玩 鸡兔同笼", "鸡兔同笼问题", ["推理意识", "模型意识", "创新意识"], 5, "综合与实践", "假设法/列表法策略缺失"),
    # 第六单元 图形的位置与运动(一)
    ("第六单元 图形的位置与运动(一)", "确定位置", ["空间观念", "应用意识"], 3, "图形与几何", "数对顺序颠倒"),
    ("第六单元 图形的位置与运动(一)", "平移", ["空间观念", "几何直观"], 3, "图形与几何", "平移方向/距离判断错误"),
    ("第六单元 图形的位置与运动(一)", "旋转", ["空间观念", "几何直观"], 4, "图形与几何", "旋转三要素掌握不全"),
    # 第七单元 倍数与因数
    ("第七单元 倍数与因数", "倍数与因数", ["数感", "推理意识"], 3, "数与代数", "概念依存关系不清"),
    ("第七单元 倍数与因数", "2、5的倍数特征", ["推理意识", "数感"], 2, "数与代数", "特征记忆混淆"),
    ("第七单元 倍数与因数", "3的倍数特征", ["推理意识", "数感"], 3, "数与代数", "与2、5特征混用"),
    ("第七单元 倍数与因数", "最大公因数与最小公倍数", ["运算能力", "推理意识"], 4, "数与代数", "短除法出错/概念混淆"),
    ("第七单元 倍数与因数", "质数与合数", ["数感", "推理意识"], 3, "数与代数", "1既非质数也非合数易错"),
    # 第八单元 可能性
    ("第八单元 可能性", "确定性与不确定性", ["数据意识", "推理意识"], 2, "统计与概率", "可能性语言表述不准"),
    ("第八单元 可能性", "可能性的大小", ["数据意识", "推理意识", "应用意识"], 3, "统计与概率", "数量与可能性关系判断错误"),
    # 综合实践 多少落叶能铺满
    ("综合实践 多少落叶能铺满", "估测与面积应用", ["量感", "应用意识", "创新意识"], 4, "综合与实践", "估测策略缺失"),
]

# 变式题模板库：知识点 -> (题干模板, 答案生成函数描述, 解析要点)
# 用参数化生成，保证变式训练可批量产出
VARIANT_TEMPLATES = {
    "小数加减法": {
        "templates": ["计算：{a} + {b} = ?", "计算：{a} - {b} = ?", "脱式计算：{a} + {b} - {c} = ?"],
        "gen": "两位小数加减，注意小数点对齐与退位",
        "analysis": "先把小数点对齐（相同数位对齐），再按整数加减法计算，最后在得数里对齐横线上的小数点。",
    },
    "小数乘小数": {
        "templates": ["计算：{a} × {b} = ?", "计算：{a} × {b} = ?（保留两位小数）"],
        "gen": "一位或两位小数相乘",
        "analysis": "先按整数乘法算出积，再看两个因数中一共有几位小数，就从积的右边起数出几位点上小数点。",
    },
    "三角形的面积": {
        "templates": ["一个三角形，底为{a}cm，高为{b}cm，它的面积是多少平方厘米？"],
        "gen": "给定底和高求面积",
        "analysis": "三角形面积 = 底 × 高 ÷ 2。切勿忘记除以2。",
    },
    "平行四边形的面积": {
        "templates": ["一个平行四边形，底为{a}cm，高为{b}cm，面积是多少平方厘米？"],
        "gen": "给定底和高求面积",
        "analysis": "平行四边形面积 = 底 × 高。通过割补可转化为长方形理解。",
    },
    "梯形的面积": {
        "templates": ["一个梯形上底{a}cm，下底{b}cm，高{c}cm，求面积。"],
        "gen": "给定上底下底高求面积",
        "analysis": "梯形面积 = (上底+下底) × 高 ÷ 2。两个完全一样的梯形可拼成平行四边形。",
    },
    "3的倍数特征": {
        "templates": ["数 {n} 是3的倍数吗？请说明理由。"],
        "gen": "判断多位数是否为3的倍数",
        "analysis": "一个数各位上的数字之和是3的倍数，这个数就是3的倍数。",
    },
    "倍数与因数": {
        "templates": ["写出 {n} 的所有因数。", "{n} 的倍数中，最小的是多少？"],
        "gen": "找因数/倍数",
        "analysis": "找一个数的因数要成对找；一个数的最小倍数是它本身，没有最大倍数。",
    },
    "用字母表示数量关系": {
        "templates": ["小明有 a 本书，小华比小明多 {n} 本，小华有（ ）本书。（用含字母的式子表示）", "每支笔 b 元，买 {n} 支需要（ ）元。"],
        "gen": "用含字母的式子表示数量关系",
        "analysis": "用字母表示数时，数字与字母相乘省略乘号，数字写在字母前面；注意数量关系的先后顺序。",
    },
    "质数与合数": {
        "templates": ["下面各数中，哪些是质数：{n}、{m}、{k}？", "{n} 是质数还是合数？"],
        "gen": "判断质数合数",
        "analysis": "只有1和它本身两个因数的数是质数；有两个以上因数的数是合数。1既不是质数也不是合数。",
    },
    "积的近似数": {
        "templates": ["计算 {a} × {b}，结果保留一位小数。"],
        "gen": "小数乘法后取近似数",
        "analysis": "先算出准确积，再按四舍五入要求保留相应小数位数。",
    },
    "小数乘整数": {
        "templates": ["计算：{a} × {b} = ?"],
        "gen": "小数乘整数",
        "analysis": "按整数乘法算，因数中有几位小数，积就有几位小数。",
    },
}

# 通用兜底模板
GENERIC_VARIANT = {
    "templates": ["请解决与「{kp}」相关的问题：{context}"],
    "analysis": "回顾该知识点的核心概念与解题步骤，注意常见错误。",
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS teachers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        teacher_id INTEGER NOT NULL,
        grade TEXT DEFAULT '五年级',
        semester TEXT DEFAULT '上册',
        FOREIGN KEY (teacher_id) REFERENCES teachers(id)
    );
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        class_id INTEGER NOT NULL,
        student_no TEXT,
        FOREIGN KEY (class_id) REFERENCES classes(id)
    );
    CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        class_id INTEGER NOT NULL,
        teacher_id INTEGER NOT NULL,
        description TEXT,
        created_at TEXT,
        FOREIGN KEY (class_id) REFERENCES classes(id),
        FOREIGN KEY (teacher_id) REFERENCES teachers(id)
    );
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_id INTEGER NOT NULL,
        q_type TEXT NOT NULL,          -- choice / fill / calc
        question_text TEXT NOT NULL,
        options TEXT,                  -- JSON array for choice
        standard_answer TEXT NOT NULL,
        scoring_rule TEXT,             -- teacher-defined scoring note
        knowledge_point TEXT NOT NULL,
        analysis TEXT,                 -- 错题解析
        score REAL DEFAULT 10,
        sort_order INTEGER DEFAULT 0,
        grading_mode TEXT DEFAULT 'score',  -- score=赋分制 / passfail=只判对错
        source TEXT DEFAULT 'manual',       -- manual=手录 / ai=拍照识题
        FOREIGN KEY (assignment_id) REFERENCES assignments(id)
    );
    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        image_path TEXT,
        ocr_text TEXT,
        student_answer TEXT,
        answer_source TEXT DEFAULT 'manual',  -- ocr / manual / teacher_review
        score REAL DEFAULT 0,
        is_correct INTEGER DEFAULT 0,
        needs_review INTEGER DEFAULT 0,
        graded_at TEXT,
        FOREIGN KEY (question_id) REFERENCES questions(id),
        FOREIGN KEY (student_id) REFERENCES students(id)
    );
    CREATE TABLE IF NOT EXISTS learning_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        knowledge_point TEXT NOT NULL,
        correct INTEGER NOT NULL,
        score REAL,
        timestamp TEXT,
        FOREIGN KEY (student_id) REFERENCES students(id)
    );
    CREATE TABLE IF NOT EXISTS variant_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        knowledge_point TEXT NOT NULL,
        question_text TEXT NOT NULL,
        answer TEXT NOT NULL,
        analysis TEXT,
        is_done INTEGER DEFAULT 0,
        is_correct INTEGER,
        created_at TEXT,
        FOREIGN KEY (student_id) REFERENCES students(id)
    );
    CREATE TABLE IF NOT EXISTS knowledge_points (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        unit TEXT NOT NULL,
        name TEXT UNIQUE NOT NULL,
        competencies TEXT NOT NULL,   -- JSON array
        difficulty INTEGER,
        domain TEXT,
        error_pattern TEXT
    );
    """)
    # ---- 轻量迁移：为旧库补新增字段 ----
    for col, ddl in [("grading_mode", "TEXT DEFAULT 'score'"), ("source", "TEXT DEFAULT 'manual'")]:
        try:
            c.execute(f"ALTER TABLE questions ADD COLUMN {col} {ddl}")
        except sqlite3.OperationalError:
            pass  # 字段已存在
    conn.commit()
    # 写入知识图谱
    c.execute("SELECT COUNT(*) FROM knowledge_points")
    if c.fetchone()[0] == 0:
        for unit, name, comps, diff, domain, err in KNOWLEDGE_GRAPH:
            c.execute("""INSERT INTO knowledge_points
                (unit,name,competencies,difficulty,domain,error_pattern)
                VALUES (?,?,?,?,?,?)""",
                (unit, name, json.dumps(comps, ensure_ascii=False), diff, domain, err))
    conn.commit()
    conn.close()


def load_knowledge_graph():
    """返回结构化知识图谱 dict"""
    conn = get_db()
    rows = conn.execute("SELECT * FROM knowledge_points ORDER BY id").fetchall()
    conn.close()
    kg = []
    for r in rows:
        kg.append({
            "id": r["id"], "unit": r["unit"], "name": r["name"],
            "competencies": json.loads(r["competencies"]),
            "difficulty": r["difficulty"], "domain": r["domain"],
            "error_pattern": r["error_pattern"]
        })
    return kg


if __name__ == "__main__":
    init_db()
    kg = load_knowledge_graph()
    print(f"知识图谱已初始化：{len(kg)} 个知识点")
    units = set(x["unit"] for x in kg)
    print(f"覆盖 {len(units)} 个单元/板块：")
    for u in units:
        print("  -", u)
