# -*- coding: utf-8 -*-
"""Flask 主应用（浏览器本地数据版）
后端只提供：页面托管 + 无状态 AI 能力（识题解题 / 看图批改）+ 静态资源。
所有业务数据在浏览器 localStorage，后端不存储任何用户数据。
"""
import os
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory

import kg
import ocr_service
import ai_service

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = os.path.join(BASE, "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


# ---------- 页面（数据由前端从 localStorage 读取，不再查库）----------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/teacher")
def teacher():
    return redirect_page("/")

@app.route("/teacher/dashboard/<int:cid>")
def teacher_dashboard(cid):
    return render_template("dashboard.html", cid=cid)

@app.route("/teacher/review")
def teacher_review():
    return render_template("review.html")

@app.route("/teacher/create")
def teacher_create():
    return render_template("create.html")

@app.route("/student")
def student_page():
    return render_template("student.html")

@app.route("/teacher/classes")
def teacher_classes():
    return render_template("classes.html")


def redirect_page(url):
    from flask import redirect
    return redirect(url)


# ---------- 公共只读知识图谱 ----------
@app.route("/api/knowledge-points")
def api_kg():
    return jsonify(kg.load_knowledge_graph())


@app.route("/api/competencies")
def api_competencies():
    return jsonify([
        {"name": k, "description": v, "domain": kg.COMPETENCY_DOMAIN[k]}
        for k, v in kg.CORE_COMPETENCIES.items()
    ])


# ---------- 无状态 AI：老师拍照识题 + 自动解题 ----------
@app.route("/api/ai/parse-homework", methods=["POST"])
def api_ai_parse():
    if "image" not in request.files:
        return jsonify({"error": "没有图片"}), 400
    file = request.files["image"]
    img_path = ocr_service.save_upload(file)
    full_path = os.path.join(BASE, img_path)
    try:
        kps = [k["name"] for k in kg.load_knowledge_graph()]
        result = ai_service.parse_homework(full_path, kps)
        result["image_path"] = img_path
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"AI 识题失败：{str(e)}"}), 500


# ---------- 无状态 AI：学生整页作业看图批改 ----------
@app.route("/api/ai/grade-page", methods=["POST"])
def api_ai_grade_page():
    """前端传：图片 + 题目标准答案列表。后端只调 AI 看图批改并返回结果，不读写任何数据库。
    前端拿到结果后自行写入 localStorage。"""
    if "image" not in request.files:
        return jsonify({"error": "没有图片"}), 400
    file = request.files["image"]
    try:
        questions = json.loads(request.form.get("questions", "[]"))
    except Exception:
        questions = []
    if not questions:
        return jsonify({"error": "题目列表为空"}), 400

    img_path = ocr_service.save_upload(file)
    full_path = os.path.join(BASE, img_path)

    std = [
        {"no": i + 1, "answer": q.get("answer", ""), "q_type": q.get("q_type", "calc"),
         "analysis": q.get("analysis", ""), "knowledge_point": q.get("knowledge_point", "")}
        for i, q in enumerate(questions)
    ]
    try:
        grade = ai_service.grade_homework_image(
            full_path, std, [k["name"] for k in kg.load_knowledge_graph()]
        )
    except Exception as e:
        return jsonify({"error": f"AI 批改失败：{str(e)}"}), 500

    result_map = {}
    for r in grade.get("results", []):
        try:
            result_map[int(r.get("no", 0))] = r
        except Exception:
            pass

    graded = []
    for i, q in enumerate(questions, 1):
        r = result_map.get(i, {})
        graded.append({
            "no": i,
            "text": q.get("text", ""),
            "question_id": q.get("id"),
            "student_answer": r.get("student_answer", ""),
            "is_correct": bool(r.get("is_correct", False)),
            "analysis": r.get("analysis") or q.get("analysis", ""),
            "grading_mode": q.get("grading_mode", "score"),
            "full_score": q.get("score", 10),
            "knowledge_point": q.get("knowledge_point", "")
        })
    return jsonify({"message": f"已批改 {len(graded)} 道题", "graded": graded,
                    "image_path": img_path})


# ---------- 单题手动判分（无状态，返回判定结果，前端写本地）----------
@app.route("/api/ai/judge", methods=["POST"])
def api_ai_judge():
    d = request.get_json() or {}
    answer = d.get("student_answer", "")
    standard = d.get("standard_answer", "")
    q_type = d.get("q_type", "fill")
    try:
        import ocr_service as ocr
        is_correct, ratio, note = ocr.judge_answer(answer, standard, q_type, d.get("scoring_rule", ""))
        return jsonify({"is_correct": is_correct, "ratio": ratio, "note": note})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------- 上传图片静态访问 ----------
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
