# -*- coding: utf-8 -*-
"""OCR识别 + 规则判分服务
- 拍照/上传 -> 图片预处理 -> pytesseract(chi_sim+eng) 识别 -> 文本清洗
- 按老师设置的题型与标准答案做规则判分
- 分数计算、等价答案匹配、错题判定
"""
import os
import re
import json
import uuid
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import pytesseract

BASE = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE, "uploads")


def preprocess_image(image_path):
    """图片预处理，提升OCR识别率"""
    img = Image.open(image_path)
    # 放大
    scale = 2
    img = img.resize((img.width * scale, img.height * scale), Image.LANCZOS)
    # 灰度
    img = ImageOps.grayscale(img)
    # 增强对比度
    img = ImageEnhance.Contrast(img).enhance(1.8)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    # 二值化
    img = img.point(lambda p: p > 165 and 255)
    return img


def ocr_image(image_path):
    """识别图片中的文字，返回清洗后的文本"""
    img = preprocess_image(image_path)
    cfg = "--oem 3 --psm 6"
    text = pytesseract.image_to_string(img, lang="chi_sim+eng", config=cfg)
    return clean_ocr_text(text)


def clean_ocr_text(text):
    """清洗OCR结果：去噪、规范化数字与符号"""
    lines = []
    for line in text.splitlines():
        s = line.strip()
        s = re.sub(r"[ \t]+", " ", s)
        if len(s) >= 1 and re.search(r"[\w\u4e00-\u9fff\d=+\-×÷/.]", s):
            lines.append(s)
    return "\n".join(lines)


def extract_answer(ocr_text, q_type):
    """从OCR文本中提取学生答案"""
    text = ocr_text.strip()
    # 优先提取 "答：xxx" / "答案：xxx" / "= xxx"
    m = re.search(r"(?:答案|答)[:：]\s*(.+)", text)
    if m:
        return m.group(1).strip()
    # 取最后一行非空
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if lines:
        last = lines[-1]
        # 形如 "1.2 + 3.4 = 4.6"
        eq = re.search(r"=\s*([^\s]+)\s*$", last)
        if eq:
            return eq.group(1).strip()
        return last
    return text


def normalize_number(s):
    """数值规范化，用于等价判断"""
    s = str(s).strip().replace(" ", "").replace("，", ",")
    s = s.replace("。", ".").replace("．", ".")
    s = s.replace("×", "*").replace("÷", "/").replace("－", "-").replace("—", "-")
    # 去掉单位
    s = re.sub(r"(平方厘米|平方米|cm²?|cm2|平方|厘米|米|千克|克|元|个|只)$", "", s)
    try:
        val = float(s)
        return round(val, 6)
    except (ValueError, TypeError):
        return s


def judge_answer(student_answer, standard_answer, q_type, scoring_rule=""):
    """规则判分：返回 (是否正确, 得分, 判定说明)"""
    std = str(standard_answer).strip()
    stu = str(student_answer).strip()

    if q_type == "choice":
        # 选择题：提取字母
        sm = re.search(r"[A-Da-d]", std.upper())
        tm = re.search(r"[A-Da-d]", stu.upper())
        ok = bool(sm and tm and sm.group().upper() == tm.group().upper())
        return ok, 1.0 if ok else 0.0, "选项匹配" if ok else f"标准={std} 学生={stu}"

    if q_type in ("fill", "calc"):
        # 允许标准答案中用 | 分隔多个等价答案
        accepted = [a.strip() for a in std.split("|")]
        for a in accepted:
            na, ns = normalize_number(a), normalize_number(stu)
            if na == ns:
                return True, 1.0, "答案匹配"
            # 分数形式 3/4 与 0.75
            if isinstance(na, float) and isinstance(ns, float) and abs(na - ns) < 1e-6:
                return True, 1.0, "数值等价"
            if str(na) == str(ns):
                return True, 1.0, "文本匹配"
        return False, 0.0, f"标准={std} 学生={stu}"

    # 主观题默认需要老师复核
    return False, 0.0, "主观题需老师复核"


def save_upload(file_storage):
    """保存上传文件，返回相对路径"""
    ext = os.path.splitext(file_storage.filename)[1].lower() or ".jpg"
    fname = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, fname)
    file_storage.save(path)
    return f"uploads/{fname}"


def process_submission(image_path, question):
    """端到端处理一次提交：OCR -> 提取答案 -> 判分"""
    try:
        ocr_text = ocr_image(image_path)
    except Exception as e:
        ocr_text = f"[OCR失败: {e}]"
    stu_answer = extract_answer(ocr_text, question["q_type"])
    ok, ratio, note = judge_answer(
        stu_answer, question["standard_answer"],
        question["q_type"], question.get("scoring_rule", "")
    )
    return {
        "ocr_text": ocr_text,
        "student_answer": stu_answer,
        "is_correct": ok,
        "score_ratio": ratio,
        "judge_note": note,
        "needs_review": question["q_type"] == "solution" or "[OCR失败" in ocr_text
    }


if __name__ == "__main__":
    # 自测：生成一张测试图片
    from PIL import ImageDraw, ImageFont
    img = Image.new("RGB", (600, 200), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 40), "Answer: 4.6", fill="black")
    d.text((20, 90), "3.4 + 1.2 = 4.6", fill="black")
    p = os.path.join(UPLOAD_DIR, "test.png")
    img.save(p)
    print("OCR结果:", repr(ocr_image(p)))
    print("判分:", judge_answer("4.6", "4.6", "fill"))
