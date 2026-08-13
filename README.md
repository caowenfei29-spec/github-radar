# 云电脑情报雷达全家桶 (github-radar)

> 一套跑在海外云电脑上的 7×24 自动情报采集系统:从 GitHub、HuggingFace、媒体、模型评测等多源采集第一手信息,生成中文日报/报告。
> 由最初单一的 GitHub 情报站扩展为多路雷达,所有脚本可在自有云电脑/服务器一键迁移部署。

## 架构总览

```
radar/                    # 各路采集器(核心)
├── github/               # GitHub 情报站:新星项目 + Trending 日报
├── free-software/        # 全网免费软件雷达:GitHub/HN/小众软件/异次元/ProductHunt
├── hf/                   # HuggingFace 全站快照:百万模型/数据集/Spaces 元数据 → SQLite
├── info-radar/           # 信息差补充6路:LMArena榜/YouTube字幕/AppStore美区/AI新闻/IndieHackers/HF论文
└── bench-lab/            # 模型实测实验室:新模型自动下载→10题统一跑分→实测报告
misc/                     # 零散爬虫
├── deals-crawler.py      # 低价/免费资源雷达(LowEndBox/LowEndTalk/Reddit VPS/free-for-dev)
├── site-index-crawler.py # 高价值网站大全采集(awesome 分类索引)
└── world-mirror-crawler.py # 世界镜像:多国媒体头条
deploy/                   # 云电脑部署运维
├── ensure-tunnel.sh      # cloudflared 隧道每分钟保活
├── ensure-sshd.sh        # sshd 每5分钟保活(容器重启后自动拉起)
├── recover-tunnel.sh     # 隧道挂死时一键恢复(在云平台网页终端执行)
└── crontab.txt           # 云电脑完整定时任务清单
daily/                    # 日报产出(按日期)
```

## 云电脑定时任务(crontab.txt)

| 时间 | 任务 |
|---|---|
| 每分钟 | ensure-tunnel.sh 隧道保活 |
| 每5分钟 | ensure-sshd.sh SSH保活 |
| 02:00 | bench-lab:发现新模型 → 下载 → 跑分 → 实测报告 |
| 14:30 | github-radar:GitHub 情报日报 |
| 14:45 | free-software-radar:免费软件雷达 |
| 15:10 | info-radar-extra:信息差补充6路 |

## 部署到新云电脑

```bash
# 1. 拉脚本
git clone https://github.com/caowenfei29-spec/github-radar.git ~/radars
# 2. 按各雷达 README 安装依赖(多为 Python 标准库,零依赖)
# 3. 配置 cron(见 deploy/crontab.txt)
# 4. 隧道:deploy/ensure-tunnel.sh 保活;挂死用 recover-tunnel.sh
```

## 产出物

- `daily/YYYY-MM-DD.md` — GitHub 情报日报(新星/Trending/关注词命中)
- 各雷达独立输出目录(云电脑 `~/xxx-radar/`)

## 敏感信息约定

- 凭据(token/key)一律不写入仓库:云电脑的 `gh-auth.log`、`db.sqlite` 等均被 .gitignore 排除
- 脚本仅用公开 API,无硬编码密钥
