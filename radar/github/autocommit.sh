#!/bin/bash
# GitHub 情报站 - 每日自动提交脚本
# 用法: ./autocommit.sh  (在 ~/github-radar 下运行)
set -e
cd ~/github-radar

REPO="github-radar"
BRANCH="main"
# GitHub 用户名 (从 git 配置读)
GH_USER=$(git config --global user.name)

# 如果仓库还没初始化, 先初始化 + 建远程
if [ ! -d .git ]; then
    echo "=== 初始化仓库 ==="
    git init -q
    git checkout -q -b $BRANCH
    # 写个 README 说明这个仓库是什么
    cat > README.md << "README_EOF"
# GitHub 情报站 (github-radar)

每天自动采集 GitHub 生态情报（新星项目 + Trending），生成中文日报。

- 数据源: GitHub API + github.com/trending
- 产出: `daily/YYYY-MM-DD.md` 中文日报
- 自动化: 云电脑定时任务自动采集 + 提交

## 日报内容
- 🔥 新星项目: 近 7 天创建的高星仓库
- 📈 Trending 今日榜单
- 🎯 关注词命中标记 (AI信息差 / 科技趋势 / 赚钱工具)
README_EOF
    git add README.md
    git commit -q -m "chore: init with README"
    git remote add origin "git@github.com:${GH_USER}/${REPO}.git"
    echo "=== 仓库已初始化 ==="
fi

# 提交今天的新日报 (如果有)
TODAY=$(date -u +%Y-%m-%d)
if [ -f "daily/${TODAY}.md" ]; then
    git add daily/
    git -c user.name="$GH_USER" -c user.email="$GH_USER@users.noreply.github.com" \
        commit -q -m "daily: ${TODAY} 情报日报" 2>&1 | head -2 || true
    echo "=== 尝试推送 ==="
    git push -q -u origin $BRANCH 2>&1 | head -3 || echo "推送失败(可能网络抖动, 下次重试)"
    echo "=== 完成: $(git log --oneline -1) ==="
else
    echo "今日日报不存在: daily/${TODAY}.md (先跑 collect.py)"
fi
