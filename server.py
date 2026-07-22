"""
格物心法 - 知识库后端API服务
功能：全文检索、内容浏览、关键信息提取、分析总结

运行模式：
  开发模式（自服务静态文件）: python server.py
  生产模式（仅 API，配合 Nginx）: python server.py --production
"""
import json
import re
import os
import sys
from collections import Counter
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

# 命令行参数
PRODUCTION = "--production" in sys.argv or os.environ.get("PRODUCTION", "").lower() in ("1", "true", "yes")
API_HOST = os.environ.get("API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("API_PORT", "8765"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not chapters_data:
        load_data()
    yield

app = FastAPI(title="格物心法 知识库", version="1.1", lifespan=lifespan)

# 加载数据
DATA_FILE = "data/chapters.json"
chapters_data = []

def load_data():
    global chapters_data
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            chapters_data = json.load(f)
        print(f"已加载 {len(chapters_data)} 篇内容")
    else:
        print("警告: 数据文件未找到，请先运行 extract_pdfs.py")

load_data()

# 构建分词索引
def tokenize(text):
    """简单中文分词 + 英文分词"""
    # 提取中文词组（2-4字）和英文单词
    tokens = []
    # 英文单词
    eng_words = re.findall(r'[a-zA-Z]+', text)
    tokens.extend([w.lower() for w in eng_words if len(w) > 2])
    # 中文n-gram (2-4字)
    chinese = re.sub(r'[^\u4e00-\u9fff]', '', text)
    for n in [2, 3, 4]:
        for i in range(len(chinese) - n + 1):
            tokens.append(chinese[i:i+n])
    return tokens

# 构建搜索索引
def build_search_index():
    """为所有章节构建搜索索引"""
    index = {}
    for chapter in chapters_data:
        if chapter.get("type") != "chapter":
            continue
        text = chapter.get("full_text", "")
        tokens = tokenize(text)
        for token in set(tokens):
            if token not in index:
                index[token] = []
            index[token].append(chapter["id"])
    return index

search_index = build_search_index()

# ===== API 端点 =====

@app.get("/api/health")
def health():
    return {"status": "ok", "chapters": len(chapters_data)}

@app.get("/api/chapters")
def get_chapters(
    stage: Optional[int] = Query(None, description="按阶段筛选 1-5"),
    type_filter: Optional[str] = Query(None, alias="type", description="按类型筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    """获取章节列表"""
    results = chapters_data.copy()
    
    if stage is not None:
        results = [c for c in results if c.get("stage") == stage]
    
    if type_filter:
        results = [c for c in results if c.get("type") == type_filter]
    
    total = len(results)
    start = (page - 1) * page_size
    end = start + page_size
    
    # 返回简洁列表
    items = []
    for c in results[start:end]:
        items.append({
            "id": c["id"],
            "type": c["type"],
            "title": c["title"],
            "number": c.get("number"),
            "stage": c.get("stage"),
            "stage_name": c.get("stage_name"),
            "word_count": c.get("word_count", 0),
            "key_concepts_count": len(c.get("key_concepts", [])),
        })
    
    return {"total": total, "page": page, "page_size": page_size, "items": items}

@app.get("/api/chapters/{chapter_id}")
def get_chapter_detail(chapter_id: str):
    """获取章节详情"""
    for c in chapters_data:
        if c["id"] == chapter_id:
            return {
                "id": c["id"],
                "type": c["type"],
                "title": c["title"],
                "number": c.get("number"),
                "stage": c.get("stage"),
                "stage_name": c.get("stage_name"),
                "full_text": c.get("full_text", ""),
                "paragraphs": c.get("paragraphs", []),
                "word_count": c.get("word_count", 0),
                "key_concepts": c.get("key_concepts", []),
                "summary": c.get("summary", []),
            }
    return {"error": "未找到"}

@app.get("/api/search")
def search(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    """全文搜索"""
    if not q.strip():
        return {"total": 0, "query": q, "items": []}
    
    query_tokens = tokenize(q)
    if not query_tokens:
        return {"total": 0, "query": q, "items": []}
    
    # 评分：每个章节的匹配分数
    scores = {}
    for token in query_tokens:
        matched_chapters = search_index.get(token, [])
        for cid in matched_chapters:
            scores[cid] = scores.get(cid, 0) + 1
    
    # 额外：全文模糊匹配
    for chapter in chapters_data:
        if chapter.get("type") != "chapter":
            continue
        text = chapter.get("full_text", "")
        title = chapter.get("title", "")
        cid = chapter["id"]
        
        # 标题匹配加分
        if q in title:
            scores[cid] = scores.get(cid, 0) + 10
        
        # 内容精确匹配加分
        count = text.count(q)
        if count > 0:
            scores[cid] = scores.get(cid, 0) + min(count, 20)
    
    # 排序
    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    
    total = len(sorted_ids)
    start = (page - 1) * page_size
    end = start + page_size
    
    items = []
    for cid in sorted_ids[start:end]:
        for c in chapters_data:
            if c["id"] == cid:
                text = c.get("full_text", "")
                # 提取匹配片段
                snippets = []
                idx = text.find(q)
                if idx >= 0:
                    for i in range(min(3, text.count(q))):
                        start_pos = max(0, idx - 50)
                        end_pos = min(len(text), idx + len(q) + 80)
                        snippet = ("..." if start_pos > 0 else "") + text[start_pos:end_pos] + ("..." if end_pos < len(text) else "")
                        snippet = snippet.replace('\n', ' ')
                        if snippet not in snippets:
                            snippets.append(snippet)
                        idx = text.find(q, idx + 1)
                        if idx < 0:
                            break
                
                items.append({
                    "id": c["id"],
                    "type": c["type"],
                    "title": c["title"],
                    "number": c.get("number"),
                    "stage": c.get("stage"),
                    "stage_name": c.get("stage_name"),
                    "score": scores[cid],
                    "snippets": snippets[:3],
                })
                break
    
    return {"total": total, "query": q, "page": page, "items": items}

@app.get("/api/analyze/{chapter_id}")
def analyze_chapter(chapter_id: str):
    """分析章节：提取关键信息、做总结"""
    chapter = None
    for c in chapters_data:
        if c["id"] == chapter_id:
            chapter = c
            break
    
    if not chapter:
        return {"error": "未找到"}
    
    text = chapter.get("full_text", "")
    paragraphs = chapter.get("paragraphs", [])
    
    # 1. 词频分析 - 提取高频关键词
    all_words = []
    for p in paragraphs:
        # 提取中文词
        words = re.findall(r'[\u4e00-\u9fff]{2,4}', p)
        all_words.extend(words)
    
    word_freq = Counter(all_words)
    # 过滤常见停用词
    stopwords = {'一个', '我们', '他们', '这个', '那个', '什么', '自己', '就是', '不是', '可以',
                 '因为', '但是', '所以', '如果', '已经', '没有', '还是', '只是', '一种', '这种',
                 '那种', '这些', '那些', '它们', '所有', '时候', '知道', '觉得', '问题', '事情',
                 '可能', '需要', '应该', '能够', '进行', '通过', '对于', '关于', '以及', '并且',
                 '或者', '然而', '因此', '而且', '不过', '虽然', '但是', '这样', '那样', '怎么',
                 '如何', '为什么', '怎么办', '开始', '然后', '最后', '第一', '第二', '第三',
                 '很多', '非常', '比较', '更加', '越来越'}
    
    keywords = [(w, c) for w, c in word_freq.most_common(50) if w not in stopwords]
    
    # 2. 生成综合摘要
    # 选择信息量最大的段落
    para_scores = []
    for i, p in enumerate(paragraphs):
        # 评分：长度适中 + 包含关键词 + 包含总结性词汇
        score = 0
        if 30 < len(p) < 500:
            score += 1
        # 包含关键信号词
        signal_words = ['所以', '因此', '核心', '本质', '关键', '总结', '这就是', '换言之',
                        '意味着', '归根结底', '最重要', '记住', '简而言之']
        for sw in signal_words:
            if sw in p:
                score += 2
        
        para_scores.append((i, score, p))
    
    # 取最高分的5段作为摘要
    para_scores.sort(key=lambda x: x[1], reverse=True)
    top_paragraphs = para_scores[:8]
    top_paragraphs.sort(key=lambda x: x[0])  # 恢复原始顺序
    
    summary = [p for _, _, p in top_paragraphs]
    
    # 3. 一句话总结
    one_liner = ""
    for p in paragraphs:
        if len(p) > 20 and len(p) < 150:
            if any(kw in p for kw in ['核心', '本质', '归根结底', '这就是', '简而言之']):
                one_liner = p
                break
    if not one_liner and keywords:
        top_kw = [w for w, _ in keywords[:5]]
        one_liner = f"本章核心概念：{'、'.join(top_kw)}"
    
    return {
        "id": chapter["id"],
        "title": chapter["title"],
        "keywords": keywords[:20],
        "summary": summary[:5],
        "one_liner": one_liner,
        "word_count": len(text),
        "paragraph_count": len(paragraphs),
    }

@app.get("/api/overview")
def get_overview():
    """获取知识库总览"""
    stages = {}
    chapters_by_stage = {}
    
    for c in chapters_data:
        if c.get("type") == "chapter":
            stage = c.get("stage", 0)
            stage_name = c.get("stage_name", "")
            
            if stage not in chapters_by_stage:
                chapters_by_stage[stage] = {
                    "stage": stage,
                    "name": stage_name,
                    "chapters": [],
                    "total_concepts": 0,
                    "total_words": 0,
                }
            
            chapters_by_stage[stage]["chapters"].append({
                "id": c["id"],
                "number": c.get("number"),
                "title": c["title"],
                "word_count": c.get("word_count", 0),
            })
            chapters_by_stage[stage]["total_concepts"] += len(c.get("key_concepts", []))
            chapters_by_stage[stage]["total_words"] += c.get("word_count", 0)
    
    # 排序
    sorted_stages = [chapters_by_stage[s] for s in sorted(chapters_by_stage.keys())]
    
    prefaces = [{
        "id": c["id"],
        "title": c["title"],
        "number": c.get("number"),
    } for c in chapters_data if c.get("type") == "preface"]
    
    postscripts = [{
        "id": c["id"],
        "title": c["title"],
        "number": c.get("number"),
    } for c in chapters_data if c.get("type") == "postscript"]
    
    total_words = sum(c.get("word_count", 0) for c in chapters_data)
    
    return {
        "total_chapters": sum(1 for c in chapters_data if c.get("type") == "chapter"),
        "total_words": total_words,
        "stages": sorted_stages,
        "prefaces": prefaces,
        "postscripts": postscripts,
    }

@app.get("/api/stats")
def get_stats():
    """统计数据"""
    total_words = sum(c.get("word_count", 0) for c in chapters_data)
    
    # 按类型统计
    type_counts = Counter(c.get("type") for c in chapters_data)
    
    all_keywords = []
    for c in chapters_data:
        if c.get("type") == "chapter":
            all_keywords.extend(c.get("key_concepts", []))
    
    return {
        "total_files": len(chapters_data),
        "total_words": total_words,
        "total_key_concepts": len(all_keywords),
        "by_type": dict(type_counts),
    }

# 静态文件服务（仅开发模式）
if not PRODUCTION:
    app.mount("/static", StaticFiles(directory="static"), name="static")

    @app.get("/")
    def serve_frontend():
        return FileResponse("static/index.html")

if __name__ == "__main__":
    mode = "生产模式 (仅 API)" if PRODUCTION else "开发模式 (含静态文件)"
    print(f"启动 格物心法 知识库服务 [{mode}]")
    print(f"监听: {API_HOST}:{API_PORT}")
    uvicorn.run(app, host=API_HOST, port=API_PORT)
