#!/bin/bash
# 云电脑侧一键恢复:重启 cloudflared 隧道(在云平台网页终端里执行)
# 用法: bash <(curl -sL ...) 或直接复制粘贴到终端
# 效果: 重启隧道 + 输出新地址。若地址变了,回本地用 connect-cloud.sh <新地址> 更新

echo "== 杀掉旧 tunnel =="
pkill -f cloudflared 2>/dev/null
sleep 2

echo "== 确认 sshd =="
pgrep -x sshd > /dev/null || { sudo /usr/sbin/sshd 2>/dev/null || sudo service ssh start 2>/dev/null; }
ss -tln | grep ':22 ' | head -1

echo "== 重启隧道(HTTP2 协议,国内网络稳) =="
nohup ~/cloudflared tunnel --protocol http2 --url ssh://localhost:22 > ~/tunnel.log 2>&1 &
sleep 10

echo "== 新隧道地址 =="
grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' ~/tunnel.log | head -1

echo "== 顺带确认推理站 =="
curl -s -o /dev/null -w "llm-server: %{http_code}\n" http://127.0.0.1:8080/health
echo "把这行新地址发回给 Hermes(如果和之前一样就不用)"
