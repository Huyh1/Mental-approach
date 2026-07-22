# 格物心法 · 知识库

基于《格物心法》系列书籍构建的在线知识库网站，收录 **50 个心智模型**，支持全文检索、智能分析、关键信息提取与在线阅读。

## 内容概览

| 类型 | 数量 | 说明 |
|------|------|------|
| 章节 | 50 篇 | 50 个心智模型（约 50 万字） |
| 序章 | 2 篇 | 认知囚笼 / 格物之眼 |
| 后记 | 2 篇 | 开始格物 / 最伟大的作品 |

### 五阶修炼体系

```
第一阶  清扫心智，建立认知地基  →  第 1-10 章
第二阶  决策模型，优化人生选择  →  第 11-20 章
第三阶  系统思维，洞察万物之联  →  第 21-30 章
第四阶  博弈与概率，驾驭不确定性 → 第 31-40 章
第五阶  智慧圆融，活出通透人生  →  第 41-50 章
```

## 功能特性

- **全文搜索** — 中文分词 + N-gram 索引，支持关键词检索与片段高亮
- **在线阅读** — 逐段落展示，按五阶体系浏览
- **智能分析** — 词频统计、关键词提取、核心段落摘要
- **一句话总结** — 自动识别章节核心观点
- **关键概念** — 每章提炼要点列表
- **响应式布局** — 适配桌面与移动端

## 项目结构

```
mental-approach/
├── extract_pdfs.py          # PDF 提取脚本（数据预处理）
├── server.py                # FastAPI 后端服务
├── data/
│   └── chapters.json        # 提取后的结构化数据
├── static/
│   ├── index.html           # 前端 SPA（内嵌 CSS/JS）
│   ├── favicon.ico          # 浏览器页签图标
│   ├── favicon-16x16.png
│   └── favicon-32x32.png
└── README.md
```

## 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 后端 | Python 3.9+ / FastAPI / uvicorn | RESTful API |
| 前端 | Vanilla HTML/CSS/JS | 零依赖 SPA |
| PDF 解析 | pypdf | 文本提取 |
| 搜索 | 自建倒排索引 + N-gram 分词 | 轻量中文全文检索 |

## 快速开始

### 环境要求

- Python 3.9+
- 已安装 `pypdf`、`fastapi`、`uvicorn`

### 安装依赖

```bash
pip install pypdf fastapi uvicorn
```

### 数据提取（首次部署必须执行）

将 PDF 源文件放在指定目录后运行提取脚本，生成 `data/chapters.json`：

```bash
# 1. 修改 extract_pdfs.py 中的 PDF_DIR 为实际路径
#    PDF_DIR = "/path/to/格物心法"

# 2. 运行提取
python extract_pdfs.py
```

提取完成将输出类似信息：

```
发现 59 个PDF文件
[59/59] 处理: 博弈与概率，驾驭不确定性 (31-40)
完成! 共处理 59 篇内容
总字数: 501,774
  preface: 2 篇
  stage_summary: 5 篇
  chapter: 50 篇
  postscript: 2 篇
```

### 启动服务

```bash
# 开发模式
python server.py

# 或指定 host/port
uvicorn server:app --host 0.0.0.0 --port 8765
```

访问 **http://localhost:8765**

## API 接口

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/overview` | GET | 知识库总览（五阶统计） |
| `/api/stats` | GET | 全局统计数据 |
| `/api/chapters` | GET | 章节列表（支持按阶段/类型筛选） |
| `/api/chapters/{id}` | GET | 章节详情（完整内容） |
| `/api/search?q=关键词` | GET | 全文搜索（返回评分 + 片段） |
| `/api/analyze/{id}` | GET | 章节智能分析（词频/摘要/总结） |

## 部署

### 本地 / 内网部署

```bash
# 后台运行
nohup python server.py > server.log 2>&1 &

# 或使用 screen / tmux
screen -S mental
python server.py
# Ctrl+A D 分离
```

### 生产环境建议

1. **使用 systemd 管理进程**（Linux）

```ini
# /etc/systemd/system/mental-approach.service
[Unit]
Description=格物心法知识库
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/mental-approach
ExecStart=/usr/bin/python3 server.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable mental-approach
sudo systemctl start mental-approach
```

2. **使用 Nginx 反向代理**

```nginx
server {
    listen 80;
    server_name mental.your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

3. **Docker 部署**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python extract_pdfs.py
EXPOSE 8765
CMD ["python", "server.py"]
```

```bash
docker build -t mental-approach .
docker run -d -p 8765:8765 mental-approach
```

## 注意事项

1. **PDF 路径** — `extract_pdfs.py` 中的 `PDF_DIR` 为硬编码路径，部署前需修改为实际 PDF 目录
2. **数据文件** — `data/chapters.json` 是核心数据文件，部署时必须存在；若缺失会导致所有接口无法工作
3. **阶段总览 PDF** — 五阶封面为纯封面页（无实质文本），提取后内容极少，这是正常现象
4. **搜索索引** — 索引在服务启动时全量构建于内存中，约 50 万字内容，内存占用约 50-80 MB
5. **中文分词** — 当前使用 N-gram（2-4 字）分词方案，对于纯中文场景效果良好，不支持拼音搜索
6. **并发** — FastAPI 默认单进程，可通过 `uvicorn --workers N` 开启多 worker（注意索引会在每个 worker 中独立构建）
7. **端口** — 默认 8765，可在 `server.py` 底部修改
8. **Python 版本** — 建议 3.9+，使用 `asynccontextmanager` 需要 3.7+
