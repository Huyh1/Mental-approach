"""
PDF内容提取脚本 - 格物心法知识库
从所有PDF中提取文本，解析章节结构，输出为结构化JSON
"""
import os
import re
import json
from pypdf import PdfReader

PDF_DIR = "/Users/lohas/Documents/知识库/格物心法"
OUTPUT_FILE = "data/chapters.json"

def extract_pdf_text(filepath):
    """提取PDF所有文本"""
    try:
        reader = PdfReader(filepath)
        text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
        return text.strip()
    except Exception as e:
        print(f"  警告: 无法提取 {filepath}: {e}")
        return ""

def parse_title(filename):
    """从文件名解析章节信息"""
    # 去掉.pdf后缀
    name = filename.replace(".pdf", "")
    
    # 匹配章节格式: 第X章：标题
    chapter_match = re.match(r"第(\d+)章[：:](.+)$", name)
    if chapter_match:
        return {
            "type": "chapter",
            "number": int(chapter_match.group(1)),
            "title": chapter_match.group(2).strip(),
        }
    
    # 匹配阶段汇总: 第X阶：标题
    stage_match = re.match(r"第([一二三四五])阶[：:](.+)$", name)
    if stage_match:
        stage_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5}
        return {
            "type": "stage_summary",
            "stage": stage_map.get(stage_match.group(1), 0),
            "title": stage_match.group(2).strip(),
        }
    
    # 匹配序章
    if name.startswith("序章"):
        num_match = re.match(r"序章([一二]?)[：:](.+)$", name)
        if num_match:
            n = num_match.group(1) or "一"
            return {
                "type": "preface",
                "number": 1 if n == "一" else 2,
                "title": num_match.group(2).strip(),
            }
    
    # 匹配后记
    if name.startswith("后记"):
        num_match = re.match(r"后记([一二]?)[：:](.+)$", name)
        if num_match:
            n = num_match.group(1) or "一"
            return {
                "type": "postscript",
                "number": 1 if n == "一" else 2,
                "title": num_match.group(2).strip(),
            }
    
    return {"type": "unknown", "title": name}

def extract_key_concepts(text):
    """从文本中提取关键概念"""
    concepts = []
    
    # 匹配冒号后面跟关键词的行
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 匹配数字编号的概念: 1. xxx 或 1、xxx
        if re.match(r'^\d+[\.、]', line) and len(line) < 120:
            concepts.append(line)
            continue
        
        # 匹配包含"是指"、"就是"、"定义"的句子
        if any(kw in line for kw in ["是指", "的核心", "的本质", "就是"]):
            if 10 < len(line) < 200:
                concepts.append(line)
    
    return concepts[:20]  # 最多20个

def extract_summary(text, max_sentences=5):
    """生成文本摘要（提取前几段和包含关键特征的句子）"""
    paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 30]
    
    # 取开头段落作为概括
    summary_parts = []
    
    # 前几段通常是故事引入
    for p in paragraphs[:3]:
        if len(p) < 500:
            summary_parts.append(p[:200])
    
    # 找结论性段落（包含特定关键词）
    conclusion_keywords = ["所以", "因此", "总结", "归根结底", "本质上", "核心", "这就是", "换言之"]
    for p in paragraphs:
        if any(kw in p for kw in conclusion_keywords) and len(p) > 50:
            summary_parts.append(p[:300])
            if len(summary_parts) >= max_sentences:
                break
    
    return summary_parts

def determine_stage(chapter_num):
    """确定章节所属阶段"""
    if chapter_num <= 10:
        return 1
    elif chapter_num <= 20:
        return 2
    elif chapter_num <= 30:
        return 3
    elif chapter_num <= 40:
        return 4
    else:
        return 5

STAGE_NAMES = {
    1: "清扫心智，建立认知地基",
    2: "决策模型，优化人生选择",
    3: "系统思维，洞察万物之联",
    4: "博弈与概率，驾驭不确定性",
    5: "智慧圆融，活出通透人生",
}

def main():
    os.makedirs("data", exist_ok=True)
    
    files = sorted(os.listdir(PDF_DIR))
    pdf_files = [f for f in files if f.endswith('.pdf')]
    
    print(f"发现 {len(pdf_files)} 个PDF文件")
    
    chapters = []
    
    for i, filename in enumerate(pdf_files):
        filepath = os.path.join(PDF_DIR, filename)
        info = parse_title(filename)
        
        print(f"[{i+1}/{len(pdf_files)}] 处理: {info.get('title', filename[:30])}")
        
        text = extract_pdf_text(filepath)
        if not text:
            print(f"  跳过（无内容）")
            continue
        
        # 提取第一行作为可能的子标题
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        subtitle = lines[0] if lines else ""
        
        # 确定阶段
        stage = None
        stage_name = None
        if info["type"] == "chapter":
            stage = determine_stage(info["number"])
            stage_name = STAGE_NAMES.get(stage, "")
        
        # 内容分段
        paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 20]
        
        chapter_data = {
            "id": f"{info['type']}_{info.get('number', i)}",
            "type": info["type"],
            "title": info["title"],
            "number": info.get("number"),
            "stage": stage,
            "stage_name": stage_name,
            "subtile": subtitle,
            "full_text": text,
            "paragraphs": paragraphs[:50],  # 保存段落用于前端展示
            "word_count": len(text),
            "key_concepts": extract_key_concepts(text),
            "summary": extract_summary(text),
            "filename": filename,
        }
        
        chapters.append(chapter_data)
        print(f"  提取 {len(text)} 字符, {len(paragraphs)} 段落, {len(chapter_data['key_concepts'])} 关键概念")
    
    # 按类型和编号排序
    type_order = {"preface": 0, "stage_summary": 1, "chapter": 2, "postscript": 3}
    chapters.sort(key=lambda c: (type_order.get(c["type"], 9), c.get("number", 0)))
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(chapters, f, ensure_ascii=False, indent=2)
    
    print(f"\n完成! 共处理 {len(chapters)} 篇内容")
    print(f"输出: {OUTPUT_FILE}")
    
    # 统计信息
    total_words = sum(c["word_count"] for c in chapters)
    print(f"总字数: {total_words:,}")
    
    types = {}
    for c in chapters:
        t = c["type"]
        types[t] = types.get(t, 0) + 1
    for t, count in types.items():
        print(f"  {t}: {count} 篇")

if __name__ == "__main__":
    main()
