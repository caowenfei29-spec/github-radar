#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型实测实验室 run_bench.py
对任意 GGUF 模型跑统一基准,输出 markdown 实测报告。
零依赖(仅标准库 urllib),可迁移到任何 Linux 云主机。

用法:
  python3 run_bench.py <模型标识>
    模型标识 = HF仓库:文件名  或  本地gguf路径
    例: python3 run_bench.py "Qwen/Qwen3-14B-GGUF:Qwen3-14B-Q4_K_M.gguf"
        python3 run_bench.py ~/Qwen3-14B-Q4_K_M.gguf
可选环境变量:
  BENCH_PORT   服务端口(默认 8099,避免与主推理站 8080 冲突)
  BENCH_MODEL_CTX 上下文长度(默认 8192)
"""
import json, os, re, subprocess, sys, time, urllib.request, urllib.parse

HOME = os.path.expanduser("~")
LLAMA_DIR = os.environ.get("LLAMA_DIR", os.path.join(HOME, "llama"))
SERVER_BIN = os.path.join(LLAMA_DIR, "llama-server")
PORT = int(os.environ.get("BENCH_PORT", "8099"))
CTX = int(os.environ.get("BENCH_MODEL_CTX", "8192"))
API = f"http://127.0.0.1:{PORT}/v1/chat/completions"
HERE = os.path.dirname(os.path.abspath(__file__))
PROMPTS = os.path.join(HERE, "bench_prompts.json")
OUT_DIR = os.path.join(HERE, "reports")

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def http_json(url, data=None, timeout=600):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def resolve_model(spec):
    """返回 (本地gguf路径, 显示名)。支持 HF仓库:文件名 或 本地路径。"""
    if os.path.exists(spec):
        return os.path.abspath(spec), os.path.basename(spec)
    if ":" in spec:
        repo, fname = spec.split(":", 1)
        local = os.path.join(HOME, "bench-models", fname)
        if not os.path.exists(local):
            os.makedirs(os.path.dirname(local), exist_ok=True)
            url = f"https://huggingface.co/{repo}/resolve/main/{fname}"
            log(f"下载模型: {url}")
            urllib.request.urlretrieve(url, local)
            log(f"下载完成: {os.path.getsize(local)/1e9:.2f} GB")
        return local, fname
    raise SystemExit(f"无法解析模型标识: {spec}")

def wait_server(pid, timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pid and pid.poll() is not None:
            raise SystemExit(f"llama-server 退出, rc={pid.returncode}")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=3) as r:
                if r.status == 200:
                    log("服务就绪")
                    return
        except Exception:
            time.sleep(2)
    raise SystemExit("服务启动超时")

def ask(model_path, messages, max_tokens=800, temperature=0.3):
    payload = {"model": "local", "messages": messages, "max_tokens": max_tokens,
               "temperature": temperature, "stream": False}
    t0 = time.time()
    resp = http_json(API, payload)
    elapsed = time.time() - t0
    usage = resp.get("usage", {})
    content = resp["choices"][0]["message"]["content"]
    return content, elapsed, usage

def check_answer(text, check):
    """按 check 规则验证。支持: {"contains": "答案"} 关键词包含 / {"not_contains": "x"}"""
    t = text.lower()
    if "contains" in check:
        return check["contains"].lower() in t
    if "not_contains" in check:
        return check["not_contains"].lower() not in t
    return None

def main():
    if len(sys.argv) < 2:
        raise SystemExit("用法: python3 run_bench.py <模型标识>")
    spec = sys.argv[1]
    model_path, display = resolve_model(spec)
    with open(PROMPTS, encoding="utf-8") as f:
        suite = json.load(f)

    # 起服务
    log(f"启动 llama-server: {display} (ctx={CTX}, port={PORT})")
    srv_log = open(os.path.join(HERE, "server_bench.log"), "a")
    proc = subprocess.Popen([SERVER_BIN, "-m", model_path, "--port", str(PORT),
                             "-c", str(CTX), "--n-gpu-layers", "0",
                             "--jinja", "--log-disable"],
                            stdout=srv_log, stderr=subprocess.STDOUT)
    try:
        wait_server(proc)
        # 热身
        ask(model_path, [{"role": "user", "content": "hi"}], max_tokens=8)
        log("热身完成,开始评测")

        results = []
        total_tokens = 0
        total_sec = 0.0
        for item in suite:
            q = item["question"]
            log(f"评测: {item['id']}")
            try:
                content, elapsed, usage = ask(model_path, [{"role": "user", "content": q}],
                                              max_tokens=item.get("max_tokens", 600))
                ntok = usage.get("completion_tokens", 0)
                total_tokens += ntok
                total_sec += elapsed
                ok = check_answer(content, item.get("check", {}))
                results.append({"item": item, "answer": content, "elapsed": elapsed,
                                "tokens": ntok, "ok": ok})
                log(f"  {item['id']}: {ntok} tok / {elapsed:.1f}s / check={'PASS' if ok else ('MISS' if ok is False else 'n/a')}")
            except Exception as e:
                log(f"  {item['id']} 失败: {e}")
                results.append({"item": item, "answer": f"[评测失败] {e}", "elapsed": 0,
                                "tokens": 0, "ok": False})

        # 报告
        os.makedirs(OUT_DIR, exist_ok=True)
        date = time.strftime("%Y%m%d")
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", display)[:60]
        report = os.path.join(OUT_DIR, f"bench_{date}_{safe}.md")
        speed = total_tokens / total_sec if total_sec > 0 else 0
        passed = sum(1 for r in results if r["ok"])
        checked = sum(1 for r in results if r["ok"] is not None)
        with open(report, "w", encoding="utf-8") as f:
            f.write(f"# 模型实测报告: {display}\n\n")
            f.write(f"- 日期: {time.strftime('%Y-%m-%d %H:%M')}\n")
            f.write(f"- 环境: {os.uname().nodename} / {os.cpu_count()} 核 / {round(os.sysconf('SC_PHYS_PAGES')*os.sysconf('SC_PAGE_SIZE')/1e9)}G 内存\n")
            f.write(f"- 量化: {os.path.basename(model_path)}\n")
            f.write(f"- 生成速度: **{speed:.1f} tok/s**(共 {total_tokens} tok / {total_sec:.0f}s)\n")
            f.write(f"- 自动检查: {passed}/{checked} 通过\n\n")
            f.write("## 逐题结果\n\n")
            for r in results:
                it = r["item"]
                mark = {True: "✅", False: "❌", None: "⬜"}[r["ok"]]
                f.write(f"### {mark} {it['id']} — {it.get('category','')}\n\n")
                f.write(f"**题目**: {it['question']}\n\n")
                if it.get("ref"):
                    f.write(f"**参考答案**: {it['ref']}\n\n")
                f.write(f"**模型回答**({r['tokens']} tok / {r['elapsed']:.1f}s):\n\n{r['answer']}\n\n---\n\n")
            f.write("## 结论(人工复核后填)\n\n- 亮点:\n- 短板:\n- 适配场景建议:\n")
        log(f"报告已生成: {report}")
        print(report)
    finally:
        proc.terminate()
        try: proc.wait(timeout=10)
        except Exception: proc.kill()

if __name__ == "__main__":
    main()
