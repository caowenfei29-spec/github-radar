#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
低价/免费资源雷达 — 云电脑美国IP直连采集
数据源: LowEndBox RSS / LowEndTalk Discourse / Reddit r:VPS / HN Algolia / free-for-dev / GitHub awesome列表
输出: ~/deals-radar/<日期>.md
"""
import json, re, html, datetime, os, sys
import xml.etree.ElementTree as ET
from urllib.request import Request, urlopen

OUT_DIR = os.path.expanduser("~/deals-radar")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"
TIMEOUT = 30

def get(url, timeout=TIMEOUT):
    import time as _t
    last = None
    for attempt in range(3):
        try:
            req = Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:
            last = e
            _t.sleep(3 * (attempt + 1))  # 退避: 3s, 6s
    raise last

def clean(s):
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def safe(fn):
    """包装器: 单源失败不影响整体"""
    try:
        return fn()
    except Exception as e:
        return [("⚠️ 采集失败", str(e), "")]

# ---------- 源1: LowEndBox (低价VPS促销权威站) ----------
def lowendbox():
    url = "https://lowendbox.com/feed/"
    root = ET.fromstring(get(url))
    items = []
    for it in list(root.iter())[:1]:
        pass
    # 直接找 item 元素
    for it in root.iter("item"):
        title = clean(it.findtext("title", ""))
        link = it.findtext("link", "")
        desc = clean(it.findtext("description", ""))[:200]
        items.append((title, link, desc))
        if len(items) >= 20:
            break
    return items

# ---------- 源2: LowEndTalk (论坛已被反爬封死, 降级为入口) ----------
def lowendtalk():
    return [("LowEndTalk 论坛(反爬,改人工查看)", "https://lowendtalk.com/discussions",
             "论坛API/JSON/RSS均被Cloudflare拦截, 抓不到最新帖; 想挖deal可人工刷 /discussions 页")]

# ---------- 源3: Reddit r/VPS 热帖 (RSS方式, JSON被403) ----------
def reddit_vps():
    url = "https://www.reddit.com/r/VPS/hot/.rss?limit=20"
    root = ET.fromstring(get(url))
    out = []
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for it in root.findall("a:entry", ns):
        title = clean(it.findtext("a:title", "", ns))
        link = it.findtext("a:link/@href", "", ns)
        if not link:
            for l in it.findall("a:link", ns):
                link = l.get("href", "")
        updated = it.findtext("a:updated", "", ns)[:10]
        out.append((title, link, f"更新 {updated}"))
        if len(out) >= 20:
            break
    return out

# ---------- 源4: HN 搜索 (低价VPS / 免费层 / 免费云) ----------
def hn_search(query, min_points=10):
    q = quote_hn(query)
    url = (f"https://hn.algolia.com/api/v1/search?tags=story&hitsPerPage=15&query={q}"
           f"&numericFilters=points>{min_points}")
    data = json.loads(get(url))
    out = []
    for h in data.get("hits", []):
        title = h.get("title", "")
        url2 = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
        points = h.get("points", 0)
        out.append((title, url2, f"▲{points}"))
    return out

def quote_hn(s):
    from urllib.parse import quote
    return quote(s)

# ---------- 源5: free-for-dev (开发者免费服务大全, 提取关键章节) ----------
def free_for_dev():
    url = "https://raw.githubusercontent.com/ripienaar/free-for-dev/master/README.md"
    text = get(url)
    # 只保留 云/托管/AI/域名/数据库/存储/CI-CD 相关章节（二级标题 ##，条目是 "  * [Name](url) - desc" 星号格式）
    keep = []
    sections = re.split(r"\n(?=## )", text)
    wanted = re.compile(r"(Major Cloud Providers|Cloud management|APIs, Data|Generative AI|Database|Managed Data|Email|CI and CD|DNS|Domain|CDN|Storage|Monitoring|Hosting|BaaS|Low-code|Forms)", re.I)
    for sec in sections:
        head = sec.split("\n")[0]
        if wanted.search(head) and len(sec) < 30000:
            lines = sec.split("\n")
            keep.append(head)
            for ln in lines[1:]:
                if ln.startswith("### "):
                    keep.append(f"  {ln}")
                # 星号条目: "  * [Name](url) - desc" 或 "  * [Name](url)"
                m = re.match(r"^\s*\*\s*\[([^\]]+)\]\(([^)]+)\)\s*[-–—]?\s*(.*)", ln)
                if m:
                    keep.append(f"  - {m.group(1)} | {m.group(2)} | {m.group(3)[:90]}")
            keep.append("")
    return ("free-for-dev 精选章节", "https://github.com/ripienaar/free-for-dev", "\n".join(keep[:250]))

# ---------- 源6: GitHub awesome 免费/低价 列表仓库 ----------
def github_awesome():
    url = ("https://api.github.com/search/repositories?q=free+cloud+OR+vps+OR+tier+awesome&sort=stars&order=desc&per_page=10")
    data = json.loads(get(url))
    out = []
    for it in data.get("items", []):
        name = it.get("full_name", "")
        stars = it.get("stargazers_count", 0)
        desc = it.get("description") or ""
        out.append((name, it.get("html_url", ""), f"⭐{stars} {desc[:100]}"))
    return out

# ---------- 主流程 ----------
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    today = datetime.date.today().isoformat()
    lines = [f"# 低价/免费资源雷达 {today}", "",
             f"> 数据源: LowEndBox / LowEndTalk / Reddit r:VPS / HN / free-for-dev / GitHub",
             f"> 采集时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} (云电脑美国IP直连)", ""]

    lines.append("## ① LowEndBox — 低价VPS促销 (权威站)")
    for title, link, desc in safe(lowendbox):
        lines.append(f"- **{title}**")
        lines.append(f"  {link}")
        if desc and "采集失败" not in title:
            lines.append(f"  {desc}")
    lines.append("")

    lines.append("## ② LowEndTalk — 论坛最新讨论")
    for title, link, meta in safe(lowendtalk):
        lines.append(f"- **{title}** ({meta})")
        lines.append(f"  {link}")
    lines.append("")

    lines.append("## ③ Reddit r/VPS — 月度热帖")
    for title, link, meta in safe(reddit_vps):
        lines.append(f"- **{title}** ({meta})")
        lines.append(f"  {link}")
    lines.append("")

    lines.append("## ④ Hacker News — 免费/低价讨论")
    for q in ["cheap vps", "free cloud tier", "free vps"]:
        lines.append(f"### 搜「{q}」")
        for title, link, meta in safe(lambda q=q: hn_search(q)):
            lines.append(f"- **{title}** ({meta})")
            lines.append(f"  {link}")
    lines.append("")

    lines.append("## ⑤ free-for-dev — 开发者免费服务大全（精选章节）")
    try:
        _, url, content = free_for_dev()
        lines.append(f"来源: {url}")
        lines.append(content)
    except Exception as e:
        lines.append(f"(抓取失败: {e})")
    lines.append("")

    lines.append("## ⑥ GitHub — 免费/低价资源列表仓库")
    for name, link, meta in safe(github_awesome):
        lines.append(f"- **{name}** — {meta}")
        lines.append(f"  {link}")
    lines.append("")

    report = "\n".join(lines)
    fpath = os.path.join(OUT_DIR, f"{today}.md")
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"报告已保存: {fpath}")
    print(f"总字数: {len(report)}")
    # 打印每节行数统计
    for sec in ["①", "②", "③", "④", "⑤", "⑥"]:
        m = re.search(rf"## {sec}.*?(?=\n## |\Z)", report, re.S)
        if m:
            n = len([l for l in m.group(0).split("\n") if l.startswith("- ")])
            print(f"节{sec}: {n} 条")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[执行失败] {e}")
        sys.exit(1)
