#!/usr/bin/env python3
"""
HuggingFace 全站雷达采集器 (hf-radar)
- 每日全量快照: 模型(~100万+) / 数据集 / Spaces 元数据
- 存 SQLite, 按日期分区, 7天形成趋势曲线
- 无 token, 遵守限速; 带重试/断点续跑
用法:
  python3 collect.py              # 采集全部三类
  python3 collect.py models       # 只采模型
  python3 collect.py datasets     # 只采数据集
  python3 collect.py spaces       # 只采 spaces
"""
import json, os, sqlite3, sys, time, urllib.request, urllib.error, datetime

BASE = "https://huggingface.co/api"
DB_PATH = os.path.expanduser("~/hf-radar/db.sqlite")
LIMIT = 1000                      # 每页条数 (API 上限)
SLEEP = 0.75                      # 无 token 限速 (~80 req/min 保险)
MAX_RETRY = 5
MAX_PAGES = int(os.environ.get("HF_RADAR_MAX_PAGES", "0"))  # 0=不限, 测试用
LOG_FILE = os.path.expanduser("~/hf-radar/collect.log")

KINDS = {
    "models":   {"table": "models",   "fields": ["id","downloads","likes","createdAt","lastModified","pipeline_tag","library_name","license","tags","author"]},
    "datasets": {"table": "datasets", "fields": ["id","downloads","likes","createdAt","lastModified","tags","author"]},
    "spaces":   {"table": "spaces",   "fields": ["id","likes","createdAt","lastModified","tags","author","runtime"]},
}

def log(msg):
    line = f"[{datetime.datetime.utcnow().isoformat()}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def get(url, timeout=30):
    """带重试和限速的 GET, 返回 (json, next_url)"""
    for attempt in range(1, MAX_RETRY + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "hf-radar/0.1"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode())
                link = r.headers.get("Link", "")
                next_url = None
                for part in link.split(","):
                    if 'rel="next"' in part:
                        next_url = part.split(";")[0].strip().strip("<>")
                return data, next_url
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = min(60, 5 * attempt)
                log(f"  429 限流, 等 {wait}s (第{attempt}次)")
                time.sleep(wait)
            elif e.code >= 500:
                wait = min(120, 10 * attempt)
                log(f"  {e.code} 服务端错误, 等 {wait}s (第{attempt}次)")
                time.sleep(wait)
            else:
                log(f"  HTTP {e.code} @ {url}, 跳过该页")
                return None, None
        except Exception as e:
            wait = min(60, 5 * attempt)
            log(f"  {type(e).__name__}: {e}, 等 {wait}s (第{attempt}次)")
            time.sleep(wait)
    log(f"  !! 重试耗尽, 放弃 {url}")
    return None, None

def ensure_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)""")
    for kind, info in KINDS.items():
        fields = ", ".join(f'"{f}" TEXT' for f in info["fields"])
        conn.execute(f"""CREATE TABLE IF NOT EXISTS {info["table"]}(
            date TEXT NOT NULL, {fields},
            PRIMARY KEY(date, id))""")
    conn.commit()

def collect(conn, kind):
    info = KINDS[kind]
    today = datetime.date.today().isoformat()
    start_url = f"{BASE}/{kind}?limit={LIMIT}"
    # 断点: 上次进度
    row = conn.execute("SELECT value FROM meta WHERE key=?", (f"checkpoint_{kind}",)).fetchone()
    url = row[0] if (row and row[0]) else start_url
    count, pages = 0, 0
    log(f"[{kind}] 开始全量采集 ({'断点续跑' if row else '从头'})")
    while url:
        data, next_url = get(url)
        if data is None:
            break
        rows = []
        for item in data:
            rec = {"date": today}
            for f in info["fields"]:
                v = item.get(f)
                if isinstance(v, (dict, list)):
                    v = json.dumps(v, ensure_ascii=False)
                rec[f] = v
            rows.append(rec)
        with conn:
            cols = ", ".join(f'"{f}"' for f in ["date"] + info["fields"])
            placeholders = ", ".join("?" for _ in ["date"] + info["fields"])
            conn.executemany(
                f'INSERT OR REPLACE INTO {info["table"]} ({cols}) VALUES ({placeholders})',
                [tuple(r[f] for f in ["date"] + info["fields"]) for r in rows])
        count += len(rows)
        pages += 1
        if MAX_PAGES and pages >= MAX_PAGES:
            log(f"  [测试] 已达 {MAX_PAGES} 页上限, 停止")
            with conn:
                conn.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (f"checkpoint_{kind}", url))
            break
        if pages % 20 == 0:
            log(f"  [{kind}] 已抓 {pages} 页 / {count} 条")
            with conn:
                conn.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (f"checkpoint_{kind}", url))
        url = next_url
        time.sleep(SLEEP)
    with conn:
        conn.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (f"checkpoint_{kind}", ""))
        conn.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (f"done_{kind}", today))
    log(f"[{kind}] 完成: {pages} 页 / {count} 条")
    return count

def main():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(KINDS.keys())
    for kind in targets:
        if kind not in KINDS:
            log(f"未知类型: {kind}")
            continue
        t0 = time.time()
        try:
            n = collect(conn, kind)
            log(f"[{kind}] 用时 {int(time.time()-t0)}s, 共 {n} 条")
        except Exception as e:
            log(f"[{kind}] 失败: {e}")
    conn.close()

if __name__ == "__main__":
    main()
