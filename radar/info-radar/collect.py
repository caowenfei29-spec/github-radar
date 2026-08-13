#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 云电脑信息差雷达·新增6路 v1.0
# 每日采集: ①LMArena模型榜 ②YouTube AI频道字幕 ③App Store美国区榜
#           ④AI新闻(TechCrunch/VentureBeat/The Verge) ⑤IndieHackers ⑥HF每日论文
# 输出: daily/YYYY-MM-DD.md + snapshots/*.json(增量对比用)
# 用法: python3 collect.py              # 全量采集(不含字幕)
#       python3 collect.py --subs <url> # 按需下载某视频英文字幕(YouTube限流时换隧道重试)
import json, re, html, os, sys, time, subprocess, urllib.request
from datetime import datetime, timezone

BASE = os.path.expanduser("~/info-radar-extra")
DAILY = os.path.join(BASE, "daily")
SNAP = os.path.join(BASE, "snapshots")
SUBS_DIR = os.path.join(BASE, "subtitles")
for d in (DAILY, SNAP, SUBS_DIR):
    os.makedirs(d, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
YDAY = (datetime.now(timezone.utc) - __import__("datetime").timedelta(days=1)).strftime("%Y-%m-%d")
NO_SUBS = "--subs" not in sys.argv

def fetch(url, timeout=25, retries=2):
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            time.sleep(2 * (i + 1))
    raise last

def clean(s):
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def load_snap(name):
    p = os.path.join(SNAP, name)
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None

def save_snap(name, data):
    with open(os.path.join(SNAP, name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

def extract_rss(xml):
    """兼容 RSS <item> 与 Atom <entry>"""
    items = []
    for block in re.findall(r"<(?:item|entry)>.*?</(?:item|entry)>", xml, re.S):
        t = re.search(r"<(?:title|media:title)[^>]*>(.*?)</(?:title|media:title)>", block, re.S)
        l = re.search(r"<link[^>]*href=\"([^\"]+)\"|<link>([^<]+)</link>", block)
        d = re.search(r"<pubDate>([^<]+)</pubDate>|<published>([^<]+)</published>|<updated>([^<]+)</updated>", block)
        de = re.search(r"<description[^>]*>(.*?)</description>|<content[^>]*>(.*?)</content>", block, re.S)
        items.append({
            "title": clean(t.group(1)) if t else "",
            "link": (l.group(1) or l.group(2)) if l else "",
            "date": (d.group(1) or d.group(2) or d.group(3) or "") if d else "",
            "desc": clean(de.group(1) or de.group(2))[:300] if de else "",
        })
    return [x for x in items if x["title"]]

# ============ ① LMArena 模型榜 ============
def lmarena():
    try:
        page = fetch("https://lmarena.ai/leaderboard", timeout=30)
        models = []
        for m in re.findall(r'title="([^"]+)"\s*>\1<', page):
            if "(" in m and m not in models:
                models.append(m)
        prev = load_snap("lmarena.json")
        save_snap("lmarena.json", {"date": TODAY, "models": models})
        out = [f"### ① LMArena 模型榜（Top {min(30, len(models))} 名序，共 {len(models)} 个条目）"]
        for i, m in enumerate(models[:30], 1):
            out.append(f"{i}. {m}")
        if prev and prev.get("models"):
            old = set(prev["models"]); new = set(models)
            added = [m for m in models if m not in old][:10]
            gone = [m for m in prev["models"] if m not in new][:10]
            if added: out.append(f"\n**🆕 新进榜**: {', '.join(added)}")
            if gone: out.append(f"\n**📉 跌出榜**: {', '.join(gone)}")
        return "\n".join(out)
    except Exception as e:
        return f"### ① LMArena 模型榜\n⚠️ 抓取失败: {e}"

# ============ ② YouTube AI 频道 ============
YT_CHANNELS = [
    ("Fireship", "UCsBjURrPoezykLs9EqgamOA"),
    ("Andrej Karpathy", "UCXUPKJO5MZQN11PqgIvyuvQ"),
    ("Two Minute Papers", "UCbfYPyITQ-7l4upoX8nvctg"),
    ("Yannic Kilcher", "UCZHmQk67mSJgfCCTn7xBfew"),
    ("AI Explained", "UCNJ1Ymd5yFuUPtn21xtRbbw"),
    ("Matthew Berman", "UCawZsQWqfGSbCI5yjkdVkTA"),
    ("Lex Fridman", "UCSHZKyawb77ixDdsGog4iWA"),
    ("Wes Roth", "UCqcbQf6yw5KzRoDDcZ_wBSw"),
]

def youtube():
    out = ["### ② YouTube AI 频道新视频（今日，含字幕）"]
    vids = []
    for name, cid in YT_CHANNELS:
        try:
            xml = fetch(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}", timeout=20)
            for it in extract_rss(xml):
                if TODAY in it["date"] or it["date"].startswith(TODAY):
                    vid = re.search(r"v=([\w-]{6,})", it["link"])
                    vids.append({"chan": name, "title": it["title"], "link": it["link"],
                                 "id": vid.group(1) if vid else "", "desc": it["desc"]})
        except Exception as e:
            out.append(f"- ⚠️ {name} 抓取失败: {e}")
        time.sleep(1)
    if not vids:
        out.append("- 今日暂无新视频")
    else:
        for v in vids:
            out.append(f"- [{v['chan']}] {v['title']}\n  {v['link']}")
        out.append(f"\n（共 {len(vids)} 条；字幕按需下载: python3 collect.py --subs <视频URL>）")
    return "\n".join(out)

# ============ ③ App Store 美国区榜 ============
APPSTORE_FEEDS = [
    ("美国区免费总榜", "https://itunes.apple.com/us/rss/topfreeapplications/limit=200/json"),
    ("美国区效率类免费榜", "https://itunes.apple.com/us/rss/topfreeapplications/limit=100/genre=6006/json"),
    ("美国区效率类付费榜", "https://itunes.apple.com/us/rss/toppaidapplications/limit=100/genre=6006/json"),
]

def appstore():
    cur = {}
    out = ["### ③ App Store 美国区榜单（新上榜 = 今日有昨日无）"]
    for label, url in APPSTORE_FEEDS:
        try:
            data = json.loads(fetch(url))
            entries = data.get("feed", {}).get("entry", [])
            for e in entries:
                name = e.get("im:name", {}).get("label", "")
                appid = e.get("id", {}).get("attributes", {}).get("im:id", "")
                if name:
                    cur[name] = {"id": appid, "rank": entries.index(e) + 1, "list": label}
            out.append(f"- {label}: {len(entries)} 个应用")
        except Exception as e:
            out.append(f"- ⚠️ {label} 抓取失败: {e}")
        time.sleep(1)
    prev = load_snap("appstore.json")
    save_snap("appstore.json", {"date": TODAY, "apps": cur})
    if prev and prev.get("apps"):
        old = set(prev["apps"].keys())
        added = [n for n in cur if n not in old][:20]
        if added:
            out.append("\n**🆕 新上榜应用**:")
            for n in added:
                out.append(f"- {n}（{cur[n]['list']} 第{cur[n]['rank']}名）")
    return "\n".join(out)

# ============ ④ AI 新闻三源 ============
NEWS_FEEDS = [
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/", ""),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/", ""),
    ("The Verge", "https://www.theverge.com/rss/index.xml",
     r"ai|llm|gpt|claude|gemini|agent|model|robot|chip|startup|funding|acqui|openai|anthropic|google|meta|microsoft|nvidia"),
]

def ai_news():
    out = ["### ④ AI 融资/产品新闻（TechCrunch / VentureBeat / The Verge）"]
    seen = set()
    count = 0
    for label, url, kw in NEWS_FEEDS:
        try:
            xml = fetch(url)
            for it in extract_rss(xml):
                if kw and not re.search(kw, it["title"], re.I):
                    continue
                if it["title"] in seen:
                    continue
                seen.add(it["title"])
                count += 1
                out.append(f"- [{label}] {it['title']}\n  {it['link']}")
        except Exception as e:
            out.append(f"- ⚠️ {label} 抓取失败: {e}")
        time.sleep(1)
    if count == 0:
        out.append("- 今日暂无")
    out.append(f"\n（共 {count} 条，来源去重）")
    return "\n".join(out)

# ============ ⑤ IndieHackers ============
def indie():
    out = ["### ⑤ IndieHackers 独立开发者动态（新帖）"]
    try:
        page = fetch("https://www.indiehackers.com/", timeout=25)
        pairs = re.findall(r'<a[^>]+href="(/post/[^"]+)"[^>]*>(.*?)</a>', page, re.S)
        posts, titles = [], []
        for slug, body in pairs:
            t = clean(body)
            if slug not in posts and len(t) > 5:
                posts.append(slug)
                titles.append(t[:80])
        prev = load_snap("ih_seen.json") or []
        new = [s for s in posts if s not in prev]
        save_snap("ih_seen.json", list(dict.fromkeys(prev + posts))[-300:])
        if not new:
            out.append("- 无新帖")
        else:
            for s in new[:15]:
                i = posts.index(s)
                t = titles[i] if i < len(titles) else s.split("/")[-1].replace("-", " ")[:60]
                out.append(f"- {t}\n  https://www.indiehackers.com{s}")
    except Exception as e:
        out.append(f"- ⚠️ 抓取失败: {e}")
    return "\n".join(out)

# ============ ⑥ HF 每日论文 ============
PAPER_KW = re.compile(
    r"agent|rag|reasoning|multimodal|small model|edge|on-device|efficient|fine-tun|world model|"
    r"evaluation|benchmark|video|code|mcp|tool use|reinforcement|quantiz|inference|long context|"
    r"vision|speech|voice|robotics", re.I)

def papers():
    out = ["### ⑥ HF 每日论文（arXiv 前沿精选，🎯=命中关注词）"]
    try:
        data = json.loads(fetch("https://huggingface.co/api/daily_papers", timeout=30))
        rows = []
        for item in data:
            p = item.get("paper", {})
            title = p.get("title", "")
            pid = p.get("id", "")
            url = p.get("url", "") or f"https://arxiv.org/abs/{pid}"
            abstract = p.get("abstract", "") or ""
            hit = "🎯" if PAPER_KW.search(title + " " + abstract[:200]) else "  "
            rows.append({"hit": hit, "title": title, "url": url, "id": pid})
        save_snap("papers.json", {"date": TODAY, "papers": rows})
        if not rows:
            out.append("- 今日暂无")
        else:
            n_hit = sum(1 for r in rows if r["hit"] == "🎯")
            out.append(f"（今日 {len(rows)} 篇，其中 {n_hit} 篇命中关注词）")
            for r in rows[:25]:
                out.append(f"{r['hit']} {r['title']}\n  {r['url']}")
    except Exception as e:
        out.append(f"- ⚠️ 抓取失败: {e}")
    return "\n".join(out)

# ============ 主流程 ============
def download_subs(url):
    dl_dir = os.path.join(SUBS_DIR, TODAY)
    os.makedirs(dl_dir, exist_ok=True)
    r = subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--skip-download", "--write-auto-subs",
         "--sub-langs", "en", "--sub-format", "vtt", "--no-warnings",
         "-o", os.path.join(dl_dir, "%(id)s"), url],
        timeout=90, capture_output=True)
    if r.returncode == 0:
        vtts = [f for f in os.listdir(dl_dir) if f.endswith(".en.vtt")]
        if vtts:
            print(f"✅ 字幕已下载: {os.path.join(dl_dir, vtts[0])}")
            return
    print(f"⚠️ 字幕下载失败(可能被限流): {r.stderr.decode()[-200:]}")

def main():
    if "--subs" in sys.argv:
        url = sys.argv[sys.argv.index("--subs") + 1] if len(sys.argv) > sys.argv.index("--subs") + 1 else ""
        if url:
            download_subs(url)
        else:
            print("用法: python3 collect.py --subs <视频URL>")
        return
    print(f"[{TODAY}] 开始采集 6 路雷达...", flush=True)
    parts = [
        f"# 云电脑信息差雷达·新增6路 {TODAY}\n",
        lmarena(), "\n",
        youtube(), "\n",
        appstore(), "\n",
        ai_news(), "\n",
        indie(), "\n",
        papers(), "\n",
        f"\n---\n采集时间(UTC): {datetime.now(timezone.utc).strftime('%H:%M')} · 云电脑出口: 美国",
    ]
    report = "\n".join(parts)
    path = os.path.join(DAILY, TODAY + ".md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"✅ 完成 → {path}（{len(report)} 字符）")

if __name__ == "__main__":
    main()
