# GitHub 情报站 (github-radar)

每天自动采集 GitHub 生态情报（新星项目 + Trending），生成中文日报。

- 数据源: GitHub API + github.com/trending
- 产出: `daily/YYYY-MM-DD.md` 中文日报
- 自动化: 云电脑定时任务自动采集 + 提交

## 日报内容
- 🔥 新星项目: 近 7 天创建的高星仓库
- 📈 Trending 今日榜单
- 🎯 关注词命中标记 (AI信息差 / 科技趋势 / 赚钱工具)
