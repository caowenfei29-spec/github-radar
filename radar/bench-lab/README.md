# 云电脑实测实验室(bench-lab)

> 7天试用机验证过的方案,可迁移到自有云电脑/服务器。
> 目标机器:8核 / 16G内存 / 纯CPU(有GPU更快)。
> 配套:cloud-pc-ssh-tunnel 技能(隧道连接)、recover-tunnel.sh(隧道恢复)。

## 这是什么

每天自动从 HuggingFace 发现新模型 → 下载 → 统一基准跑分 → 生成实测报告。
别人只知道"模型发布了",你拿到的是"它实际好不好用"的第一手数据。
(推理站方案已弃用,不再常驻加载模型。)

## 部署(新机器 5 分钟)

```bash
mkdir -p ~/bench-lab
# 上传 run_bench.py / discover.py / bench_prompts.json 到 ~/bench-lab/
# 依赖: python3(标准库即可)、tmux、curl、aria2c(大模型下载加速,可选)
```

## 手动跑一次

```bash
cd ~/bench-lab
# 测本地文件
python3 run_bench.py ~/模型.gguf
# 或从 HF 仓库自动下载再测
python3 run_bench.py "Qwen/Qwen3-14B-GGUF:Qwen3-14B-Q4_K_M.gguf"
# 报告 → ~/bench-lab/reports/bench_日期_模型名.md
```

## 每日自动(已在云电脑 cron)

```bash
# 02:00 发现新模型 → 评测 → 报告(取回看 ~/bench-lab/reports/ 最新文件)
0 2 * * * cd ~/bench-lab && python3 discover.py >> bench.log 2>&1 && python3 run_bench.py "$(cat candidate.txt)" >> bench.log 2>&1
```

## 报告内容

10 道题:数学×2(自动判分)、代码、中文知识×2、逻辑推理、JSON 指令遵循、中文写作、安全红线、工具调用。
每题记录耗时/生成token数,报告含生成速度(tok/s)、自动判分、逐题问答、人工复核区。

## 已知坑

| 坑 | 解法 |
|---|---|
| Qwen3 默认思考模式吞 token,回答为空 | llama-server 加 `--reasoning off` |
| 8核CPU跑 14B Q4 ≈ 4-5 tok/s | 评测 10 题约 10-20 分钟,凌晨跑不影响 |
| 下载慢(单线程 1MB/s) | aria2c -x16 + HF CDN 直链,可到 100MB/s+ |
| 模型加载期间 CPU 满载,SSH/隧道易断 | 用 tmux 后台跑长任务,ssh 只发短命令取结果 |
| 容器重启丢 crontab | 重启后重跑部署命令;cron 用 `bash xxx.sh` 防权限丢失 |
| 云电脑侧 cloudflared 隧道会挂 | ensure-tunnel.sh 每分钟保活;recover-tunnel.sh 手动恢复 |
| pkill 模式匹配到 ssh 会话自身 | 用 `[l]lama-server` 括号技巧,或精确进程名 |
