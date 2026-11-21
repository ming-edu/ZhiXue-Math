# -*- coding: utf-8 -*-
"""AI 视觉服务：接入硅基流动多模态模型，实现「拍照识题 → 自动解题 → 自动批改」。

设计要点：
- Key 只存后端配置文件，绝不返回前端。
- 所有返回强制结构化 JSON，并做清洗容错（模型偶有 markdown 包裹/多余文字）。
- 自动解题结果一律标记 needs_review，需老师核对后才计入学情，避免 AI 错题误导学生。
"""
import os
import re
import json
import base64
import requests

BASE = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(BASE, "ai_config.json")

with open(CFG_PATH, encoding="utf-8") as f:
    CFG = json.load(f)

API_KEY = CFG["api_key"]
BASE_URL = CFG["base_url"].rstrip("/")
MODEL = CFG["model"]


def _img_to_data_url(path):
    """本地图片 -> data URL（模型可直接读）"""
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(ext, "jpeg")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/{mime};base64,{b64}"


def _call_vlm(messages, max_tokens=1500, timeout=120):
    """调用视觉语言模型，返回文本"""
    resp = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"model": MODEL, "messages": messages, "max_tokens": max_tokens, "temperature": 0.2},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _parse_json(text):
    """从模型输出里稳健提取 JSON"""
    text = text.strip()
    # 去掉 ```json ... ``` 包裹
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    # 截取第一个 { 到最后一个 }
    s, e = text.find("{"), text.rfind("}")
    if s >= 0 and e > s:
        text = text[s:e + 1]
    return json.loads(text)


def parse_homework(image_path, knowledge_points=None):
    """识题 + 自动解题。

    返回: {"count": n, "questions":[{"no","text","answer","analysis","q_type","knowledge_point"}]}
    """
    kp_hint = ""
    if knowledge_points:
        kp_hint = "\n可选知识点（从中选最匹配的一个，没有就填“其他”）：" + "、".join(knowledge_points)

    prompt = f"""你是一位小学五年级数学老师。下面是一张作业题照片。请完成：
1. 数出一共有几道题；
2. 逐题抄录题目原文（保留数字与单位，选择题请列出选项）；
3. 独立解出每题的正确答案；
4. 用一句话写出每题的解题思路（给老师核对用）；
5. 判断每题题型：choice(选择题)/fill(填空题)/calc(计算或解答题)；
6. 为每题匹配一个知识点。{kp_hint}

严格只返回如下 JSON，不要任何解释文字：
{{"count": 题数, "questions": [{{"no": 1, "text": "题目原文", "answer": "正确答案", "analysis": "解题思路", "q_type": "calc", "knowledge_point": "知识点名"}}]}}"""

    messages = [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": _img_to_data_url(image_path)}},
        {"type": "text", "text": prompt},
    ]}]
    result = _parse_json(_call_vlm(messages))
    qs = result.get("questions", [])
    # 兜底清洗：确保字段齐全
    cleaned = []
    for i, q in enumerate(qs, 1):
        cleaned.append({
            "no": q.get("no", i),
            "text": str(q.get("text", "")).strip(),
            "answer": str(q.get("answer", "")).strip(),
            "analysis": str(q.get("analysis", "")).strip(),
            "q_type": q.get("q_type") if q.get("q_type") in ("choice", "fill", "calc") else "calc",
            "knowledge_point": str(q.get("knowledge_point", "其他")).strip(),
        })
    return {"count": len(cleaned), "questions": cleaned}


def grade_homework_image(image_path, standard_answers, knowledge_points=None):
    """直接看学生作业照片逐题批改（不走本地OCR，准确率高）。

    standard_answers: [{"no","answer","q_type","analysis","knowledge_point"}]
    返回: {"results":[{"no","student_answer","is_correct","analysis","knowledge_point"}]}
    """
    std = json.dumps(standard_answers, ensure_ascii=False)
    kp_hint = ""
    if knowledge_points:
        kp_hint = "\n可选知识点（每题选最匹配的一个）：" + "、".join(knowledge_points)
    prompt = f"""你是一位辛苦批改作业的小学五年级数学老师。下面是一位学生写好的作业照片。

standard answers（标准答案）：
{std}

请仔细看照片，找到每一题学生手写的答案，逐题与标准答案比对判断是否做对。
要求：
- 数值答案允许等价写法（0.5=1/2、48平方厘米=48cm²）；
- 看不清或没写的题，is_correct=false，student_answer 填“未作答”；
- 每题匹配一个知识点。{kp_hint}
严格只返回 JSON，不要任何解释：
{{"results":[{{"no":1,"student_answer":"学生手写的答案","is_correct":true,"analysis":"简短点评","knowledge_point":"知识点名"}}]}}"""
    messages = [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": _img_to_data_url(image_path)}},
        {"type": "text", "text": prompt},
    ]}]
    result = _parse_json(_call_vlm(messages))
    return {"results": result.get("results", [])}


def grade_answers(standard_answers, ocr_lines, knowledge_points=None):
    """对学生整页作答 OCR 文本，逐题与标准答案比对判分（走纯文本模型，更快更省）。

    standard_answers: [{"no","answer","q_type","analysis","knowledge_point"}]
    ocr_lines: 学生作业 OCR 出来的整段文本
    返回: {"results":[{"no","student_answer","is_correct","score_ratio"}]}
    """
    kp_hint = ""
    if knowledge_points:
        kp_hint = "\n可选知识点（每题选最匹配的一个）：" + "、".join(knowledge_points)

    std = json.dumps(standard_answers, ensure_ascii=False)
    prompt = f"""你是小学五年级数学老师，请批改学生作业。

标准答案与题目：
{std}

学生作答原文（OCR识别，可能有错别字或符号误差，请合理容错）：
\"\"\"{ocr_lines}\"\"\"

请逐题判断学生对错，并把每题匹配一个知识点。{kp_hint}
注意：数值答案允许等价写法（如 0.5 = 1/2）；解答题看最终结果是否正确即可。
严格只返回 JSON：
{{"results":[{{"no":1,"student_answer":"学生写的答案","is_correct":true,"analysis":"简短点评","knowledge_point":"知识点名"}}]}}"""

    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    result = _parse_json(_call_vlm(messages))
    return {"results": result.get("results", [])}


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(json.dumps(parse_homework(sys.argv[1]), ensure_ascii=False, indent=2))
