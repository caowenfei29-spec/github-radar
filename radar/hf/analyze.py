#!/usr/bin/env python3
"""
hf-radar 趋势分析: 对比每日快照, 输出情报报告
- 总量 / 新增 / 下载增速TOP / likes增速TOP / 最新模型
- 输出 markdown 报告 + 精简情报CSV(取回本地用)
用法: python3 analyze.py [date]
"""
import csv, datetime, os, sqlite3, sys

DB = os.path.expanduser("~/hf-radar/db.sqlite")
OUT = os.path.expanduser("~/hf-radar")

def q(conn, sql, args=()):
    return conn.execute(sql, args).fetchall()

def top_gainers(conn, table, date, prev_date, metric, n=25):
    """对比两天, 算增量 TOP n (metric 字段: downloads / likes)"""
    rows = q(conn, f"""
        SELECT a.id, a.{metric} AS cur, b.{metric} AS prev,
               CAST(a.{metric} AS INT) - CAST(b.{metric} AS INT) AS gain
        FROM {table} a JOIN {table} b ON a.id = b.id
        WHERE a.date=? AND b.date=?
        ORDER BY gain DESC LIMIT ?""", (date, prev_date, n))
    return rows

def newest(conn, table, date, n=15):
    return q(conn, f"""
        SELECT id, createdAt, CAST(downloads AS INT) FROM {table}
        WHERE date=? AND createdAt != '' ORDER BY createdAt DESC LIMIT ?""", (date, n))

def main():
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().isoformat()
    conn = sqlite3.connect(DB)
    days = [r[0] for r in q(conn, "SELECT DISTINCT date FROM models ORDER BY date DESC")]
    prev = days[1] if len(days) > 1 else None
    lines = [f"# HF 全站雷达日报 {date}", ""]
    if prev:
        lines.append(f"> 对比基准: {prev}")
    lines.append("")

    for t in ["models", "datasets", "spaces"]:
        n = q(conn, f"SELECT COUNT(*) FROM {t} WHERE date=?", (date,))[0][0]
        lines.append(f"## {t}: {n:,} 条")
        if prev:
            only_new = q(conn, f"""
                SELECT COUNT(*) FROM {t} a WHERE a.date=? AND NOT EXISTS
                (SELECT 1 FROM {t} b WHERE b.date=? AND b.id=a.id)""", (date, prev))[0][0]
            lines.append(f"- 相比 {prev} 新增: **{only_new:,}**")
        lines.append("")

    # 模型情报
    if prev:
        lines.append("## 🚀 下载增速 TOP 20 (24h)")
        for rid, cur, pv, gain in top_gainers(conn, "models", date, prev, "downloads"):
            lines.append(f"- {rid}: +{gain:,} (累计 {cur:,})")
        lines.append("")
        lines.append("## ❤️ Likes 增速 TOP 15 (24h)")
        for rid, cur, pv, gain in top_gainers(conn, "models", date, prev, "likes", 15):
            lines.append(f"- {rid}: +{gain} (累计 {cur})")
        lines.append("")

    lines.append("## 🆕 新发布模型 TOP 15")
    for rid, ctime, dl in newest(conn, "models", date):
        lines.append(f"- {rid} ({ctime}) 下载 {dl:,}")
    lines.append("")

    report = "\n".join(lines)
    rp = os.path.join(OUT, f"report_{date}.md")
    with open(rp, "w") as f:
        f.write(report)

    # 精简情报 CSV (取回用): 下载增速榜+新模型
    if prev:
        with open(os.path.join(OUT, f"gainers_{date}.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["rank", "model_id", "downloads_gain_24h", "downloads_total", "likes_total"])
            for i, (rid, cur, pv, gain) in enumerate(top_gainers(conn, "models", date, prev, "downloads", 200), 1):
                likes = q(conn, "SELECT likes FROM models WHERE id=? AND date=?", (rid, date))
                w.writerow([i, rid, gain, cur, likes[0][0] if likes else ""])
    print(report)

if __name__ == "__main__":
    main()
