#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
discover.py — 从 HuggingFace 发现"值得实测"的新模型
输出候选清单到 candidates.json,并挑选当日重点模型写入 candidate.txt
零依赖(标准库 urllib)。每天 cron 调用一次。

策略(贴近用户需求:强 + 能赚钱):
1. 最近7天创建/修改的模型,筛选:
   - 仓库名含 GGUF 或 语言模型特征(7B/8B/14B/32B/70B、llama、qwen、deepseek、mistral、gemma、glm、phi、yi、minicpm 等)
   - 排除已有实测报告(读 reports/ 目录)
   - 排除 embed/whisper/stable-diffusion 等非LLM
2. 按下载量排序,取前5写入 candidates.json
3. 用关键词权重打分(中文/推理/代码强的厂商加分),最高分写入 candidate.txt
"""
import json, os, re, time, urllib.request

HF_API = "https://huggingface.co/api/models"
LLM_PAT = re.compile(r"(gguf|llama|qwen|deepseek|mistral|gemma|glm|phi|yi-|minicpm|granite|olmo|falcon|gpt-oss|dbrx|command-r|internlm|baichuan|aquila|wizardlm|zephyr|tulu)", re.I)
SKIP_PAT = re.compile(r"(embed|whisper|stt|tts|stable-diffusion|sdxl|flux|musicgen|image|video|audio|clip|vit|bge-|e5-|minilm|speech|vits|wav2vec|hubert|asr)", re.I)
GOOD_PAT = re.compile(r"(qwen|deepseek|glm|minicpm|internlm|gpt-oss|mistral|gemma|phi)", re.I)

def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)

def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "bench-lab/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def done_reports():
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
    if not os.path.isdir(d):
        return set()
    return {f.lower() for f in os.listdir(d)}

def score(name, likes, downloads):
    s = 0
    if re.search(r"(instruct|chat)", name, re.I): s += 2
    if re.search(r"(14b|32b|70b|72b)", name, re.I): s += 2
    if re.search(r"(8b|7b)", name, re.I): s += 1
    if GOOD_PAT.search(name): s += 3
    if likes > 50: s += 2
    elif likes > 10: s += 1
    if downloads > 50000: s += 2
    elif downloads > 5000: s += 1
    return s

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    done = done_reports()
    seen = set()
    cands = []
    # 最近30天修改的模型,翻3页
    for page in range(3):
        url = f"{HF_API}?sort=lastModified&direction=-1&limit=100&full=false&config=false&skip={page*100}"
        try:
            items = get(url)
        except Exception as e:
            log(f"拉取失败: {e}")
            break
        if not items:
            break
        for it in items:
            rid = it.get("id", "")
            name = rid.split("/")[-1]
            if not LLM_PAT.search(name) or SKIP_PAT.search(name):
                continue
            if rid.lower() in seen or rid.lower() in done:
                continue
            # 只留 GGUF 或纯权重仓库(纯权重也值得试,默认挑 Q4 量化方案由 run_bench 处理下载)
            if not re.search(r"gguf", name, re.I):
                continue  # 只盯 GGUF,能直接跑
            seen.add(rid.lower())
            cands.append({"id": rid, "name": name,
                          "likes": it.get("likes", 0),
                          "downloads": it.get("downloads", 0),
                          "lastModified": it.get("lastModified", "")[:10]})
    # 打分排序
    for c in cands:
        c["score"] = score(c["name"], c["likes"], c["downloads"])
    cands.sort(key=lambda x: -x["score"])
    top = cands[:8]
    with open(os.path.join(here, "candidates.json"), "w", encoding="utf-8") as f:
        json.dump(top, f, ensure_ascii=False, indent=2)
    log(f"候选 {len(top)} 个 → candidates.json")
    if top:
        best = top[0]
        with open(os.path.join(here, "candidate.txt"), "w") as f:
            f.write(best["id"])
        log(f"今日重点: {best['id']} (score={best['score']})")
    else:
        log("今日无新候选")

if __name__ == "__main__":
    main()
