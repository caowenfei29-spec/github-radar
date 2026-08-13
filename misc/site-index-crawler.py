#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高价值网站大全采集器 v2.0 — 分类索引版
改进:
  1. awesome 解析同时试 master/main + README.md/readme.md
  2. 分类用"特异性加权": 泛词(server/cloud/api)不主导, 强信号词优先
  3. 每源限量, 避免单源(如 awesome-selfhosted 1209条)淹没索引
输出: ~/site-index/<日期>.md + raw.json
"""
import json, re, os, sys, html, datetime
from urllib.request import Request, urlopen
from urllib.parse import urlparse, unquote

OUT_DIR = os.path.expanduser("~/site-index")
os.makedirs(OUT_DIR, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"

def get(url, timeout=30):
    req = Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")

def clean(s):
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def norm_url(u):
    u = (u or "").strip()
    u = re.sub(r"^https?://", "", u, flags=re.I)
    u = re.sub(r"^www\.", "", u, flags=re.I)
    u = u.rstrip("/")
    u = u.split("#")[0].split("?")[0]
    return u.lower()

# ---------- 静态源 ----------
AWESOME_LIST = [
    ("sindresorhus/awesome",              "awesome 总集", 120),
    ("steven2358/awesome-generative-ai",  "AI 工具", 150),
    ("awesome-selfhosted/awesome-selfhosted", "自托管软件", 250),
    ("vinta/awesome-python",              "Python", 120),
    ("sindresorhus/awesome-nodejs",       "Node.js", 80),
    ("enaqx/awesome-react",               "React", 60),
    ("ripienaar/free-for-dev",            "免费开发者资源", 150),
    ("trimstray/the-book-of-secret-knowledge", "黑客知识库", 60),
    ("practical-tutorials/project-based-learning", "项目学习", 80),
    ("pluja/awesome-privacy",             "隐私工具", 100),
    ("public-apis/public-apis",           "免费API", 100),
    ("sindresorhus/awesome-electron",     "Electron", 40),
    ("ossu/computer-science",             "CS自学", 40),
    ("jyguyomarch/awesome-productivity",  "效率办公", 80),
    ("gztchan/awesome-design",            "设计创意", 60),
    ("academic/awesome-datascience",      "数据科研", 60),
    ("leereilly/games",                   "游戏娱乐", 50),
    ("wilsonfreitas/awesome-quant",       "财经商业", 60),
]

def fetch_awesome(repo, label, cap):
    items = []
    for branch in ("master", "main"):
        for fname in ("README.md", "readme.md"):
            try:
                txt = get(f"https://raw.githubusercontent.com/{repo}/{branch}/{fname}")
                if txt.strip().startswith("404"):
                    continue
                # 兼容两种格式: "- [Name](url) - desc" 和 "**[Name](url)** - desc"
                for m in re.finditer(r"-?\s*\*{0,2}\[([^\]]+)\]\(([^)]+)\)\*{0,2}\s*[-–—:]\s*([^\n]*)", txt):
                    name, link, desc = m.group(1).strip(), m.group(2).strip(), clean(m.group(3))[:160]
                    if link.startswith("#") or not link.startswith("http"):
                        continue
                    if len(name) < 2 or len(link) < 8:
                        continue
                    # free-for-dev 的目录项也是链接，跳过目录
                    if name.startswith(("⬆️", "Back to Top")):
                        continue
                    items.append({"name": name, "url": link, "desc": desc, "source": f"awesome/{label}"})
                    if len(items) >= cap:
                        return items
                if items:
                    return items
            except Exception:
                continue
    return items

# ---------- 动态源 ----------
def fetch_github_trending():
    items = []
    try:
        page = get("https://github.com/trending?since=daily")
        for b in re.findall(r'<article[^>]*class="[^"]*Box-row[^"]*"[^>]*>(.*?)</article>', page, re.S)[:30]:
            m = re.search(r'href="/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"', b)
            if not m: continue
            repo = m.group(1)
            if repo.startswith(("sponsors/", "apps/")): continue
            dm = re.search(r'<p[^>]*class="col-9[^"]*"[^>]*>(.*?)</p>', b, re.S)
            desc = clean(dm.group(1))[:150] if dm else "开源项目"
            sm = re.search(r'<a[^>]*href="[^"]*/stargazers"[^>]*>.*?([\d,]+)\s*</a>', b, re.S)
            stars = sm.group(1) if sm else ""
            items.append({"name": repo, "url": f"https://github.com/{repo}", "desc": desc,
                          "source": f"GitHub Trending{' ⭐'+stars if stars else ''}"})
    except Exception as e:
        items.append({"name": "github_trending_error", "url": "", "desc": str(e), "source": "err"})
    return items

def fetch_hn_show():
    items = []
    try:
        cutoff = datetime.datetime.now().timestamp() - 2*86400
        url = f"https://hn.algolia.com/api/v1/search_by_date?tags=show_hn&hitsPerPage=40&numericFilters=created_at_i>{int(cutoff)}"
        data = json.loads(get(url))
        for hit in data.get("hits", []):
            title = clean(hit.get("title") or "")
            if not title or len(title) < 8: continue
            items.append({"name": title[:120], "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                          "desc": clean(hit.get("story_text") or "")[:160] or "Show HN 新品",
                          "source": f"HN Show HN ({hit.get('points') or 0}pts)"})
    except Exception as e:
        items.append({"name": "hn_show_error", "url": "", "desc": str(e), "source": "err"})
    return items

def fetch_hn_top_domains():
    items = []
    try:
        cutoff = int(datetime.datetime.now().timestamp() - 3*86400)
        url = f"https://hn.algolia.com/api/v1/search?tags=story&hitsPerPage=100&numericFilters=created_at_i>{cutoff}&query="
        data = json.loads(get(url))
        dom_count, dom_title = {}, {}
        for hit in data.get("hits", []):
            u = hit.get("url") or ""
            if not u: continue
            try: dom = urlparse(u).netloc.replace("www.", "")
            except: continue
            if dom in ("news.ycombinator.com", "github.com"): continue
            dom_count[dom] = dom_count.get(dom, 0) + 1
            dom_title.setdefault(dom, clean(hit.get("title") or "")[:100])
        for dom, cnt in sorted(dom_count.items(), key=lambda x: -x[1])[:25]:
            if cnt < 2: continue
            items.append({"name": dom, "url": f"https://{dom}/", "desc": dom_title.get(dom, ""),
                          "source": f"HN 高频域名 ×{cnt}"})
    except Exception as e:
        items.append({"name": "hn_dom_error", "url": "", "desc": str(e), "source": "err"})
    return items

def fetch_hn_top_stories():
    """HN 历史高分故事 (points≥100) — 补垂直领域优质站"""
    items = []
    try:
        url = "https://hn.algolia.com/api/v1/search?tags=story&hitsPerPage=50&numericFilters=points>100"
        data = json.loads(get(url))
        for hit in data.get("hits", []):
            u = hit.get("url") or ""
            if not u or "news.ycombinator.com" in u: continue
            title = clean(hit.get("title") or "")[:110]
            pts = hit.get("points") or 0
            items.append({"name": title, "url": u, "desc": clean(hit.get("story_text") or "")[:120],
                          "source": f"HN 高分 ({pts}pts)"})
    except Exception as e:
        items.append({"name": "hn_top_error", "url": "", "desc": str(e), "source": "err"})
    return items

def fetch_producthunt():
    items = []
    seen, KNOWN_BIG = set(), {"openai","claude","cursor","figma","vercel","notion","chatgpt","google",
        "microsoft","github","apple","netflix","spotify","adobe","wordpress","dropbox","linear",
        "raycast","arc","perplexity","midjourney","canva","zoom","discord","trello","asana",
        "todoist","evernote","grammarly","shopify","stripe","youtube","instagram","tiktok","grok","sora","gemini"}
    for topic in ["artificial-intelligence", "developer-tools", "productivity", "design-tools",
                  "open-source", "finance", "news", "lifestyle", "health-fitness", "games", "video", "audio"]:
        try:
            page = get(f"https://www.producthunt.com/topics/{topic}")
            for nm, tg in re.findall(r'"name":"([^"]{3,80})","tagline":"([^"]{3,160})"', page):
                key = nm.lower()
                if key in seen or key in KNOWN_BIG: continue
                seen.add(key)
                items.append({"name": nm, "url": f"https://www.producthunt.com/search?q={unquote(nm)}",
                              "desc": tg, "source": f"Product Hunt/{topic}"})
        except Exception as e:
            items.append({"name": f"ph_{topic}_error", "url": "", "desc": str(e), "source": "err"})
    return items

def fetch_rss(url, source, n=12):
    items = []
    try:
        xml_txt = get(url)
        for e in re.findall(r"<item>(.*?)</item>", xml_txt, re.S)[:n]:
            t = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", e, re.S)
            l = re.search(r"<link>(.*?)</link>", e, re.S)
            d = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", e, re.S)
            if not t: continue
            items.append({"name": clean(t.group(1))[:100], "url": l.group(1).strip() if l else "",
                          "desc": clean(d.group(1))[:140] if d else "软件推荐", "source": source})
    except Exception as ex:
        items.append({"name": f"rss_error_{source}", "url": "", "desc": str(ex), "source": "err"})
    return items

# ---------- 分类: 来源映射优先 + 关键词兜底 ----------
# awesome 源本身按主题组织, 来源是最强信号
SOURCE_MAP = {
    "AI 工具": "🤖 AI/机器学习",
    "免费开发者资源": "🎁 免费资源",
    "Python": "💻 开发者工具/开源",
    "Node.js": "💻 开发者工具/开源",
    "React": "💻 开发者工具/开源",
    "Electron": "💻 开发者工具/开源",
    "免费API": "💻 开发者工具/开源",
    "awesome 总集": "💻 开发者工具/开源",
    "自托管软件": "🏠 自托管软件",
    "隐私工具": "🔒 安全隐私",
    "黑客知识库": "🔒 安全隐私",
    "项目学习": "📚 学习教育",
    "CS自学": "📚 学习教育",
    "效率办公": "⚡ 效率办公",
    "设计创意": "🎨 设计创意",
    "数据科研": "📊 数据科研",
    "游戏娱乐": "🎮 游戏娱乐",
    "编程学习": "📚 学习教育",
    "财经商业": "💰 财经商业",
}

# 强信号词(出现即强烈指向该类别), 泛词(只做辅助, 不单独主导)
CATEGORY_RULES = [
    ("🤖 AI/机器学习", {
        "strong": ["llm", "gpt", "chatbot", "machine learning", "deep learning", "neural", "rag",
                   "diffusion", "inference", "openai", "claude", "gemini", "copilot", "prompt",
                   "aigc", "大模型", "人工智能", "ai 绘画", "ai 写作", "语音合成", "tts", "asr",
                   "transformer", "微调", "知识库", "多模态", "embedding", "hugging face",
                   "agents", "agentic", "model", "vision model", "genai", "生成式",
                   "ai-powered", "ai based", "ai search", "ai assistant", "ai writing",
                   "ai memory", "ai content", "ai tool"],
        "weak": ["ai", "模型", "识别", "语音", "ocr"]}),
    ("💻 开发者工具/开源", {
        "strong": ["framework", "sdk", "cli", "ide", "editor", "git", "docker", "kubernetes", "k8s",
                   "compiler", "debugger", "devtool", "programming", "coding", "npm", "pypi",
                   "package manager", "vscode", "ci/cd", "api 开发", "rest api", "graphql",
                   "open source library", "library for", "development", "开发者", "编程", "开发",
                   "mcp server", "debug", "测试框架", "typescript", "javascript library",
                   "python library", "命令行工具", "terminal emulator", "linux 工具"],
        "weak": ["api", "server", "database", "sql", "库", "开源", "源码", "terminal", "shell", "linux"]}),
    ("⚡ 效率办公", {
        "strong": ["note-taking", "笔记", "todo", "待办", "task manager", "calendar", "日历",
                   "email", "邮件", "文档", "office", "办公", "效率", "workflow", "工作流",
                   "表格", "excel", "时间管理", "番茄", "思维导图", "mindmap", "kanban", "看板",
                   "知识管理", "剪贴板", "剪藏", "markdown", "网盘", "云盘", "同步", "reminder",
                   "提醒", "productivity", "项目管理", "meeting", "会议", "写作", "writing assistant"],
        "weak": ["pdf", "doc", "backup", "备份", "note"]}),
    ("📚 学习教育", {
        "strong": ["education", "学习", "教育", "course", "课程", "tutorial", "教程", "learn",
                   "computer science", "cs 自学", "自学", "university", "大学", "project-based",
                   "编程学习", "英语学习", "背单词", "读书", "阅读", "词典", "翻译"],
        "weak": ["language", "语言", "knowledge", "知识"]}),
    ("🎨 设计创意", {
        "strong": ["design", "设计", "photoshop", "图库", "图标", "icon", "logo", "字体", "font",
                   "调色", "修图", "壁纸", "3d", "建模", "渲染", "animation", "动画", "矢量",
                   "svg", "素材", "海报", "banner", "figma", "creative", "配色", "ui kit",
                   "设计工具", "图片处理", "图像"],
        "weak": ["photo", "image", "图片"]}),
    ("🎬 影音媒体", {
        "strong": ["video", "音频", "音乐", "视频", "电影", "播放器", "player", "youtube",
                   "bilibili", "spotify", "转码", "ffmpeg", "字幕", "下载器", "yt-dlp", "播客",
                   "podcast", "直播", "录音", "剪辑", "投屏", "电视", "流媒体", "streaming",
                   "media server", "音乐库", "相册", "照片管理"],
        "weak": ["audio", "music", "media", "stream", "照片", "photo"]}),
    ("📰 新闻资讯", {
        "strong": ["news", "新闻", "资讯", "magazine", "媒体", "日报", "周报", "techcrunch",
                   "the verge", "venturebeat", "indiehacker", "reddit", "hacker news", "rss 阅读",
                   "信息流", "聚合"],
        "weak": ["blog", "博客", "daily"]}),
    ("🔒 安全隐私", {
        "strong": ["security", "privacy", "vpn", "proxy", "代理", "加密", "encrypt", "password",
                   "密码", "2fa", "auth", "验证", "防火墙", "杀毒", "隐私", "匿名", "防追踪",
                   "tracker", "osint", "凭据", "密钥", "secret", "leak", "漏洞", "安全",
                   "adblock", "去广告", "dns 过滤"],
        "weak": ["firewall", "antivirus"]}),
    ("🖥️ 系统网络工具", {
        "strong": ["system", "系统", "windows", "macos", "android", "ios", "清理", "优化",
                   "驱动", "磁盘", "分区", "启动盘", "镜像", "虚拟机", "vm", "远程", "remote",
                   "文件管理", "压缩", "解压", "浏览器", "browser", "dns", "网络", "network",
                   "vps", "hosting", "cloud", "云", "自托管", "self-host", "内网穿透",
                   "linux 发行版", "desktop environment", "桌面环境", "监控", "监视"],
        "weak": ["utility", "工具", "server"]}),
    ("🎮 游戏娱乐", {
        "strong": ["game", "游戏", "steam", "模拟器", "emulator", "娱乐", "电子书", "小说",
                   "漫画", "动漫", "休闲", "epic", "gaming"],
        "weak": []}),
    ("💰 财经商业", {
        "strong": ["finance", "金融", "财经", "投资", "股票", "基金", "crypto", "比特币",
                   "blockchain", "区块链", "startup", "创业", "商业", "market", "经济",
                   "trading", "交易", "理财"],
        "weak": ["币", "链", "money", "钱"]}),
    ("📊 数据科研", {
        "strong": ["dataset", "数据集", "research", "研究", "论文", "paper", "science", "科学",
                   "statistics", "统计", "数据可视化", "data visualization", "notebook",
                   "学术", "科研", "实验", "data science", "数据科学"],
        "weak": ["data", "数据", "api"]}),
    ("🛒 生活服务", {
        "strong": ["shopping", "购物", "生活", "travel", "旅行", "地图", "weather", "天气",
                   "美食", "健康", "health", "fitness", "运动", "菜谱", "租房", "房产",
                   "招聘", "job", "找工作", "求职", "比价", "优惠"],
        "weak": ["food", "工具"]}),
]

def categorize(name, desc, source=""):
    # 1) 来源映射优先(awesome 源本身按主题组织)
    for prefix, cat in SOURCE_MAP.items():
        if f"/{prefix}" in source or source == prefix:
            return cat
    # 2) 关键词加权
    text = f"{name} {desc}".lower()
    scores = {}
    for cat, rule in CATEGORY_RULES:
        s = 0
        for w in rule["strong"]:
            if w == "ai":
                if re.search(r"(?<![a-z])ai(?![a-z])", text): s += 3
            elif w in text: s += 3
        for w in rule["weak"]:
            if w == "ai":
                if re.search(r"(?<![a-z])ai(?![a-z])", text): s += 1
            elif w in text: s += 1
        scores[cat] = s
    best = max(scores, key=scores.get)
    return best if scores[best] >= 3 else "🗂️ 其他"

# ---------- 主流程 ----------
def main():
    print("== 高价值网站采集 v2 ==", flush=True)
    all_items = []
    for repo, label, cap in AWESOME_LIST:
        items = fetch_awesome(repo, label, cap)
        print(f"  awesome/{label}: {len(items)} 条", flush=True)
        all_items += items
    all_items += fetch_github_trending(); print("  GitHub Trending: 完成", flush=True)
    all_items += fetch_hn_show();         print("  HN Show HN: 完成", flush=True)
    all_items += fetch_hn_top_domains();  print("  HN 高频域名: 完成", flush=True)
    all_items += fetch_hn_top_stories();  print("  HN 历史高分: 完成", flush=True)
    all_items += fetch_producthunt();     print("  Product Hunt: 完成", flush=True)
    all_items += fetch_rss("https://www.appinn.com/feed/", "小众软件")
    all_items += fetch_rss("https://feed.iplaysoft.com/", "异次元软件世界")
    print("  中文 RSS: 完成", flush=True)

    seen, dedup = set(), []
    for it in all_items:
        if not it.get("url") or it["name"].endswith("_error"): continue
        key = norm_url(it["url"]) or it["name"].lower()
        nk = it["name"].lower().strip()
        if key in seen or nk in seen: continue
        seen.add(key); seen.add(nk)
        dedup.append(it)
    print(f"采集 {len(all_items)} → 去重后 {len(dedup)} 条", flush=True)

    grouped = {}
    for it in dedup:
        cat = categorize(it["name"], it.get("desc", ""), it.get("source", ""))
        grouped.setdefault(cat, []).append(it)

    with open(f"{OUT_DIR}/raw.json", "w", encoding="utf-8") as f:
        json.dump(dedup, f, ensure_ascii=False, indent=1)

    date_str = datetime.date.today().isoformat()
    lines = [f"# 🌐 高价值网站大全 · 分类索引 {date_str}", "",
             f"> 数据源: GitHub awesome 精选系列 / free-for-dev / GitHub Trending / HN / Product Hunt / 小众软件 / 异次元",
             f"> 采集于云电脑(美国IP) | 共 {len(dedup)} 条 | 分类=特异性加权关键词",
             ""]
    lines.append("## 📑 目录"); lines.append("")
    for cat in grouped:
        lines.append(f"- {cat} ({len(grouped[cat])})")
    lines.append("")
    for cat, its in grouped.items():
        lines.append(f"## {cat} ({len(its)})"); lines.append("")
        for it in its:
            name = it["name"].replace("|", "\\|")[:90]
            url = it["url"]
            desc = it.get("desc", "").replace("|", "\\|")[:130]
            lines.append(f"- [{name}]({url}) — {desc}")
            lines.append(f"  - `{it['source']}`")
        lines.append("")
    report = "\n".join(lines)
    fpath = f"{OUT_DIR}/{date_str}.md"
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n✅ 索引已生成: {fpath} ({len(dedup)} 条)")
    for cat, its in sorted(grouped.items(), key=lambda x: -len(x[1])):
        print(f"  {cat}: {len(its)}")

if __name__ == "__main__":
    main()
