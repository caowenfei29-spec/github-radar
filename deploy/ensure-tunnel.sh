#!/bin/bash
# self-heal: sshd + cloudflared tunnel (runs every minute via cron)
pgrep -x sshd >/dev/null || (sudo mkdir -p /run/sshd && sudo /usr/sbin/sshd)
pgrep -f 'cloudflared tunnel' >/dev/null || (nohup ~/cloudflared tunnel --protocol http2 --url ssh://localhost:22 > ~/tunnel.log 2>&1 &)
