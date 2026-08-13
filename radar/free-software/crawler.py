#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全网免费软件采集器 v2
改进:
- GitHub Trending: 解析 article 块, 带真实描述/语言/star数
- Product Hunt: 只保留真正的新品 (去重, 过滤知名老牌)
- AlternativeTo: 过滤导航链接, 只要 app 名
- HN: 清洗 HTML 实体
- 分类: 补充关键词, 输出分类统计
"""
import json, re, sys, datetime, html, os
from urllib.request import Request, urlopen
from urllib.parse import quote

OUT_DIR = "/home/box/free-software-radar"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"

def get(url, timeout=30):
    req = Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")

def clean(s):
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()

# ---------- 分类规则 ----------
CATEGORY_RULES = [
    ("AI/机器学习", ["ai", "llm", "gpt", "chatbot", "machine learning", "deep learning", "neural",
                   "agent", "rag", "diffusion", "model", "inference", "embedding", "openai", "claude",
                   "gemini", "copilot", "prompt", "aigc", "生成式", "大模型", "人工智能", "ai 绘画",
                   "ai 写作", "语音合成", "tts", "asr", "语音识别", "transformer", "微调", "fine-tun",
                   "知识库", "ocr", "vision", "多模态", "推理", "embed"]),
    ("开发者工具", ["developer", "sdk", "api", "cli", "framework", "ide", "editor", "git", "docker",
                  "kubernetes", "k8s", "database", "sql", "compiler", "debug", "test", "devtool",
                  "coding", "code", "programming", "开源", "终端", "命令行", "开发", "编程", "部署",
                  "自托管", "self-host", "ci/cd", "vscode", "插件", "库", "函数库", "npm", "pypi",
                  "mcp", "kubernetes", "operator", "roslyn", "tailscale"]),
    ("效率办公", ["productivity", "note", "笔记", "todo", "待办", "task", "calendar", "日历",
                "email", "邮件", "文档", "doc", "pdf", "office", "办公", "效率", "自动化",
                "workflow", "工作流", "表格", "excel", "word", "ppt", "时间管理", "番茄", "思维导图",
                "mindmap", "kanban", "看板", "wiki", "知识管理", "剪贴板", "clipboard", "剪藏",
                "markdown", "listary", "文件搜索", "网盘", "云盘", "备份", "同步", "reminder", "提醒"]),
    ("影音媒体", ["video", "audio", "music", "音乐", "视频", "电影", "播放器", "player",
                "youtube", "bilibili", "spotify", "转码", "ffmpeg", "字幕", "subtitle", "下载器",
                "download", "yt-dlp", "播客", "podcast", "stream", "直播", "录音", "剪辑",
                "投屏", "cast", "电视", "tv", "相册", "photo backup", "照片备份", "照片"]),
    ("安全隐私", ["security", "privacy", "vpn", "proxy", "代理", "加密", "encrypt", "password",
                "密码", "2fa", "auth", "验证", "防火墙", "firewall", "杀毒", "antivirus", "防病毒",
                "隐私", "匿名", "shadow", "防追踪", "tracker", "osint", "spiderfoot", "凭据",
                "密钥", "secret", "leak", "漏洞", "安全"]),
    ("网络通信", ["network", "浏览器", "browser", "chrome", "firefox", "http", "tcp", "dns",
                "server", "服务器", "网站", "爬虫", "crawler", "scraper", "rss", "feed", "社交",
                "social", "聊天", "chat", "通讯", "通信", "传输", "transfer", "局域网", "lan",
                "localsend", "设备", "跨设备", "vps", "hosting", "云"]),
    ("设计创意", ["design", "设计", "photo", "图片", "图像", "image", "ps", "photoshop", "图库",
                "图标", "icon", "logo", "字体", "font", "调色", "修图", "壁纸", "wallpaper", "3d",
                "建模", "渲染", "动画", "animation", "矢量", "svg", "素材", "海报", "banner",
                "figma", "素材收集", "图片管理"]),
    ("学习教育", ["education", "学习", "教育", "course", "课程", "language", "语言", "翻译", "translate",
                "词典", "dictionary", "读书", "阅读", "reading", "背单词", "记忆", "知识",
                "english", "英语", "教程", "tutorial", "course"]),
    ("系统工具", ["system", "系统", "windows", "linux", "mac", "android", "ios", "清理", "优化",
                "驱动", "driver", "备份", "backup", "磁盘", "disk", "分区", "启动盘", "u盘", "镜像",
                "虚拟机", "vm", "远程", "remote", "文件管理", "file manager", "压缩", "解压", "zip",
                "监视", "监控", "应用商店", "app store", "垃圾清理", "ccleaner", "启动项", "进程"]),
    ("游戏娱乐", ["game", "游戏", "steam", "模拟器", "emulator", "娱乐", "电子书", "小说", "漫画",
                "动漫", "休闲", "epic", "领", "ipod", "复古"]),
]

def categorize(name, desc):
    text = f"{name} {desc}".lower()
    for cat, words in CATEGORY_RULES:
        for w in words:
            wl = w.lower()
            if wl == "ai":
                # 避免 available/email/detail/tailscale 等误判: 要求前后非字母
                if re.search(r"(?<![a-z])ai(?![a-z])", text):
                    return cat
            elif wl in text:
                return cat
    return "其他"

# ---------- 源1: GitHub Trending (带描述/语言/star) ----------
def fetch_github_trending():
    items = []
    try:
        page = get("https://github.com/trending?since=daily")
        # 每个 article.Box-row 是一个仓库
        blocks = re.findall(r'<article[^>]*class="[^"]*Box-row[^"]*"[^>]*>(.*?)</article>', page, re.S)
        for b in blocks:
            m = re.search(r'href="/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"', b)
            if not m:
                continue
            repo = m.group(1)
            if repo.startswith("sponsors/") or repo.startswith("apps/"):
                continue
            dm = re.search(r'<p[^>]*class="col-9[^"]*"[^>]*>(.*?)</p>', b, re.S)
            desc = clean(dm.group(1))[:150] if dm else ""
            lm = re.search(r'itemprop="programmingLanguage">([^<]+)<', b)
            lang = lm.group(1).strip() if lm else ""
            sm = re.search(r'<a[^>]*href="[^"]*/stargazers"[^>]*>\s*<svg[^>]*>.*?</svg>\s*([\d,]+)\s*</a>', b, re.S)
            stars = sm.group(1) if sm else ""
            items.append({
                "name": repo, "source": f"GitHub Trending ({lang})" if lang else "GitHub Trending",
                "desc": desc or "开源项目", "url": f"https://github.com/{repo}",
                "stars": stars, "date": datetime.date.today().isoformat()
            })
    except Exception as e:
        items.append({"name": "github_error", "source": "GitHub Trending", "desc": str(e), "url": "", "stars": ""})
    return items

# ---------- 源2: HN Show HN ----------
def fetch_hn_show():
    items = []
    try:
        cutoff = datetime.datetime.now().timestamp() - 2*86400
        url = f"https://hn.algolia.com/api/v1/search_by_date?tags=show_hn&hitsPerPage=40&numericFilters=created_at_i>{int(cutoff)}"
        data = json.loads(get(url))
        for hit in data.get("hits", []):
            title = clean(hit.get("title") or "")
            if not title or len(title) < 8:
                continue
            txt = clean(hit.get("story_text") or "")
            items.append({
                "name": title[:120], "source": "HN Show HN",
                "desc": txt[:180] or "Show HN 新品",
                "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                "stars": str(hit.get("points") or 0) + " pts",
                "date": datetime.datetime.fromtimestamp(hit.get("created_at_i", 0)).strftime("%m-%d")
            })
    except Exception as e:
        items.append({"name": "hn_error", "source": "HN Show HN", "desc": str(e), "url": "", "stars": ""})
    return items

# ---------- 源3/4: 中文 RSS ----------
def fetch_rss(url, source, n=10):
    items = []
    try:
        xml_txt = get(url)
        entries = re.findall(r"<item>(.*?)</item>", xml_txt, re.S)
        for e in entries[:n]:
            t = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", e, re.S)
            l = re.search(r"<link>(.*?)</link>", e, re.S)
            d = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", e, re.S)
            if not t:
                continue
            items.append({
                "name": clean(t.group(1))[:100], "source": source,
                "desc": clean(d.group(1))[:140] if d else "软件推荐",
                "url": l.group(1).strip() if l else "", "stars": "", "date": ""
            })
    except Exception as ex:
        items.append({"name": f"rss_error_{source}", "source": source, "desc": str(ex), "url": "", "stars": ""})
    return items

# ---------- 源5: Product Hunt (过滤知名老牌) ----------
KNOWN_BIG = {"claude by anthropic", "openai", "cursor", "figma", "vercel", "notion", "supabase",
             "framer", "slack", "notion ai", "chatgpt", "google", "microsoft", "github", "apple",
             "netflix", "spotify", "airbnb", "uber", "meta", "adobe", "wordpress", "dropbox",
             "linear", "raycast", "arc", "perplexity", "midjourney", "canva", "zoom", "discord",
             "trello", "asana", "todoist", "evernote", "1password", "notion calendar", "duolingo",
             "grammarly", "shopify", "stripe", "figma ai", "x", "youtube", "instagram", "tiktok",
             "claude code", "chatgpt by openai", "gpt-4o", "gpt-4", "gpt-5", "gemini", "copilot",
             "claude", "framer ai agents", "grok", "sora", "gemini ai", "chatgpt plus", "midjourney ai"}

def fetch_producthunt():
    items = []
    seen = set()
    for topic in ["artificial-intelligence", "developer-tools", "productivity"]:
        try:
            page = get(f"https://www.producthunt.com/topics/{topic}")
            names = re.findall(r'"name":"([^"]{3,80})","tagline":"([^"]{3,160})"', page)
            for nm, tg in names:
                key = nm.lower()
                if key in seen or key in KNOWN_BIG:
                    continue
                seen.add(key)
                items.append({
                    "name": nm, "source": f"Product Hunt/{topic}",
                    "desc": tg, "url": f"https://www.producthunt.com/search?q={quote(nm)}",
                    "stars": "", "date": ""
                })
        except Exception as ex:
            items.append({"name": f"ph_{topic}_error", "source": "Product Hunt", "desc": str(ex), "url": "", "stars": ""})
    return items

# ---------- 源6: AlternativeTo (过滤导航) ----------
NAV_LINKS = {"login", "register", "about", "privacy", "terms", "contact", "api", "blog", "faq",
             "features", "pricing", "browse", "lists", "community", "apps", "categories", "tags",
             "donate", "team", "jobs", "press", "advertise", "new", "top", "trending", "random",
             "search", "signin", "signup", "alternatives", "like", "home", "news", "help", "status"}

def fetch_alternativeto():
    items = []
    try:
        page = get("https://alternativeto.net/")
        links = re.findall(r'href="/([a-z0-9-]{3,60})/"', page)
        seen, out = set(), []
        for l in links:
            if l in NAV_LINKS or l in seen:
                continue
            seen.add(l)
            out.append(l)
        for name in out[:10]:
            items.append({
                "name": name.replace("-", " ").title(), "source": "AlternativeTo 热门",
                "desc": "免费替代品", "url": f"https://alternativeto.net/{name}/",
                "stars": "", "date": ""
            })
    except Exception as ex:
        items.append({"name": "alternativeto_error", "source": "AlternativeTo", "desc": str(ex), "url": "", "stars": ""})
    return items

# ---------- 主流程 ----------
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("== 采集开始 v2 ==", flush=True)
    all_items = []
    all_items += fetch_github_trending();  print(f"GitHub Trending 完成 ({len(all_items)})", flush=True)
    all_items += fetch_hn_show();          print(f"HN Show HN 完成 ({len(all_items)})", flush=True)
    all_items += fetch_rss("https://www.appinn.com/feed/", "小众软件");        print(f"小众软件 完成 ({len(all_items)})", flush=True)
    all_items += fetch_rss("https://feed.iplaysoft.com/", "异次元软件世界");    print(f"异次元 完成 ({len(all_items)})", flush=True)
    all_items += fetch_producthunt();      print(f"Product Hunt 完成 ({len(all_items)})", flush=True)
    all_items += fetch_alternativeto();    print(f"AlternativeTo 完成 ({len(all_items)})", flush=True)

    grouped = {}
    for it in all_items:
        cat = categorize(it["name"], it.get("desc", ""))
        grouped.setdefault(cat, []).append(it)

    date_str = datetime.date.today().isoformat()
    lines = [f"# 全网免费软件雷达 {date_str}", "",
             f"> 数据源: GitHub Trending / HN Show HN / 小众软件 / 异次元 / Product Hunt / AlternativeTo",
             f"> 采集时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}  |  共 {len(all_items)} 条", ""]
    for cat in ["AI/机器学习", "开发者工具", "效率办公", "影音媒体", "安全隐私", "网络通信",
                "设计创意", "学习教育", "系统工具", "游戏娱乐", "其他"]:
        its = grouped.get(cat, [])
        if not its:
            continue
        lines.append(f"## {cat} ({len(its)})")
        lines.append("")
        for it in its:
            if it["name"].endswith("_error"):
                lines.append(f"- ⚠️ [{it['name']}] 采集失败: {it['desc']}")
                continue
            stars = f" ⭐{it['stars']}" if it.get("stars") else ""
            lines.append(f"- **{it['name']}**{stars} — {it['desc'][:120]}")
            if it["url"]:
                lines.append(f"  - {it['source']} | {it['url']}")
        lines.append("")
    report = "\n".join(lines)
    fpath = f"{OUT_DIR}/{date_str}.md"
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n报告已保存: {fpath}")
    print(report)

if __name__ == "__main__":
    main()
