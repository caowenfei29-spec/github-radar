#!/bin/bash
if ! pgrep -x sshd > /dev/null; then sudo /usr/sbin/sshd 2>/dev/null || service ssh start 2>/dev/null; fi
