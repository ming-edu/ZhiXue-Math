# -*- coding: utf-8 -*-
"""把演示数据和知识图谱导出为静态 JSON，供浏览器首次访问注入 localStorage。"""
import os, json, kg

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")


def export_demo_data():
    conn = kg.get_db()
    tables = ["teachers", "classes", "students", "assignments", "questions",
              "submissions", "learning_records", "variant_assignments"]
    data = {}
    for t in tables:
        rows = conn.execute(f"SELECT * FROM {t}").fetchall()
        data[t] = [dict(r) for r in rows]
    conn.close()
    # 给 classes 补 8 位班级号字段（演示数据也带上）
    import random, string
    for c in data["classes"]:
        if not c.get("class_code"):
            c["class_code"] = "".join(random.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8))
    p = os.path.join(STATIC, "demo_data.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"导出演示数据: {p}")
    for t in tables:
        print(f"  {t}: {len(data[t])} 条")


def export_kg():
    kg_data = {
        "knowledge_points": [
            {"unit": u, "name": n, "competencies": c, "difficulty": d, "domain": dom, "error_pattern": ep}
            for (u, n, c, d, dom, ep) in kg.KNOWLEDGE_GRAPH
        ],
        "core_competencies": kg.CORE_COMPETENCIES,
        "competency_domain": kg.COMPETENCY_DOMAIN,
        "variant_templates": kg.VARIANT_TEMPLATES,
        "generic_variant": kg.GENERIC_VARIANT,
    }
    p = os.path.join(STATIC, "kg.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(kg_data, f, ensure_ascii=False)
    print(f"导出知识图谱: {p} ({len(kg_data['knowledge_points'])} 个知识点)")


if __name__ == "__main__":
    export_demo_data()
    export_kg()
