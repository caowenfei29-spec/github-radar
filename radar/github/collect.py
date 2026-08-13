#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub 情报站采集器 v1
- 数据源1: GitHub API 最近7天创建的高星仓库 (search/repos, sort=stars)
- 数据源2: GitHub Trending 今日页面 (今日 star 增速信号)
- 无认证可跑 (API 匿名限额 60次/小时, 单次采集约 3-4 次调用)
输出: 中文 Markdown 日报, 打印到 stdout 同时存到 ~/github-radar/daily/<date>.md
"""
import json, re, subprocess, sys, datetime
from urllib.request import Request, urlopen, quote

OUT_DIR = "/home/box/github-radar/daily"
# 三组关注词: 信息差 / 科技趋势 / 赚钱工具
KEYWORD_GROUPS = {
    "信息差": ["news", "digest", "radar", "monitor", "trending", "insight", "aggregator", "rss", "tracker",
               "crawler", "scraper", "discovery", "alternative", "awesome", "list", "directory", "database",
               "dataset", "index", "search", "research"],
    "科技趋势": ["ai", "llm", "agent", "model", "deep learning", "neural", "multimodal", "robot", "automation",
               "inference", "training", "quantization", "fine-tune", "embedding", "rag", "gpu", "cuda",
               "computer vision", "nlp", "speech", "audio", "video", "3d", "simulation", "quantum"],
    "赚钱工具": ["monetize", "saas", "api", "tool", "automation", "workflow", "ecommerce", "shopify", "marketplace",
               "affiliate", "seo", "marketing", "advertis", "lead", "crm", "billing", "payment", "subscription",
               "chatbot", "trading", "crypto", "bot", "extension", "plugin", "template", "starter", "sdk",
               "mcp", "claude", "gpt", "copilot", "prompt"],
}

def match_groups(name_desc):
    """返回命中的关注组列表"""
    text = (name_desc).lower()
    hits = []
    for group, words in KEYWORD_GROUPS.items():
        if any(w in text for w in words):
            hits.append(group)
    return hits

def api(url):
    req = Request(url, headers={"User-Agent": "github-radar", "Accept": "application/vnd.github+json"})
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def fetch_trending():
    """抓 GitHub Trending 今日页, 提取仓库名; 用 API 补 star 数"""
    req = Request("https://github.com/trending?since=daily",
                  headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"})
    html = urlopen(req, timeout=45).read().decode("utf-8", "ignore")
    # 提取仓库链接 (owner/repo), 过滤非仓库 (sponsors/apps/trending 等保留段)
    SKIP = {"sponsors", "apps", "trending", "topics", "collections", "marketplace", "orgs", "settings", "features", "enterprise", "login", "signup", "pricing", "about", "customer-stories", "readme"}
    items = re.findall(r'href="/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"', html)
    repos = []
    for it in items:
        owner = it.split("/")[0]
        if owner in SKIP or it in repos:
            continue
        repos.append(it)
    result = []
    for repo in repos[:15]:
        stars = 0
        try:
            data = api(f"https://api.github.com/repos/{repo}")
            stars = data.get("stargazers_count", 0)
        except Exception:
            pass
        result.append((repo, stars))
    return result

def main():
    today = datetime.date.today().isoformat()
    lines = []
    lines.append(f"# GitHub 情报日报 {today}")
    lines.append("")
    lines.append(f"> 生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M UTC')} | 来源: GitHub API + Trending")
    lines.append("")

    # === 源1: 新星项目 (7天内创建, 按star排序) ===
    lines.append("## 🔥 新星项目 (近7天创建, 按 Star 排序)")
    lines.append("")
    since = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    try:
        q = quote(f"created:>{since}")
        data = api(f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page=15")
        if data.get("items"):
            for r in data["items"]:
                desc = (r.get("description") or "")[:120]
                lang = r.get("language") or "?"
                lines.append(f"- **[{r['full_name']}]({r['html_url']})** ⭐{r['stargazers_count']:,} 🍴{r['forks_count']:,} [{lang}]")
                if desc:
                    lines.append(f"  {desc}")
                # 关注组命中标记
                hit = match_groups(r["full_name"] + " " + desc)
                if hit:
                    lines.append(f"  🎯 关注: {', '.join(hit)}")
                lines.append("")
        else:
            lines.append("(无结果)")
    except Exception as e:
        lines.append(f"(API 新星抓取失败: {e})")
    lines.append("")

    # === 源2: Trending 今日热度 ===
    lines.append("## 📈 Trending 今日榜单 (当前 Star)")
    lines.append("")
    try:
        trending = fetch_trending()
        for repo, ts in trending[:15]:
            hit = match_groups(repo)
            tag = f" 🎯 {', '.join(hit)}" if hit else ""
            lines.append(f"- **{repo}** ⭐{ts:,}{tag}")
    except Exception as e:
        lines.append(f"(Trending 抓取失败: {e})")
    lines.append("")

    # === 汇总: 值得关注 ===
    lines.append("## 🎯 一句话总结")
    lines.append("")
    lines.append("(分析引擎待接入 — v2 将用 LLM 自动生成解读)")
    lines.append("")

    report = "\n".join(lines)
    import os
    os.makedirs(OUT_DIR, exist_ok=True)
    path = f"{OUT_DIR}/{today}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)

if __name__ == "__main__":
    main()
