#!/bin/bash

pkill -f "uvicorn app.main:app"
sleep 1
cd /usr/andy/marathon/server || exit 1
source .venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 > /tmp/marathon-server.log 2>&1 &
echo "服务已重启, PID: $!"
